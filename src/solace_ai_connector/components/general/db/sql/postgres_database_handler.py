"""Manage a PostgreSQL database connection."""

import psycopg2
import psycopg2.extras
from time import sleep
from solace_ai_connector.common.log import log


class PostgreSQLDatabase:
    def __init__(self, host: str, user: str, password: str, database: str, port: int = 5432):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.port = port
        self.connection = None

        if ":" in self.host:
            self.host, self.port = self.host.split(":")

    def cursor(self, **kwargs):
        if self.connection is None or self.connection.closed:
            self.connect()
        try:
            return self.connection.cursor(**kwargs)
        except Exception:  # pylint: disable=broad-except
            self.connect()
            return self.connection.cursor(**kwargs)

    def connect(self, auto_commit=True):
        self.connection = psycopg2.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            connect_timeout=10,
        )
        self.connection.autocommit = auto_commit

    def close(self):
        if self.connection is None:
            return
        self.connection.close()
        self.connection = None

    def execute(self, query, params=None):
        sanity = 3
        while True:
            try:
                cursor = self.cursor()
                cursor.execute(query, params)
                break
            except Exception as e:
                log.error("Database error.", trace=e)
                sanity -= 1
                if sanity == 0:
                    raise e
                sleep(1)

        return cursor

def get_db_for_action(action_obj, sql_params=None):
    if sql_params:
        sql_host = sql_params.get("sql_host")
        sql_user = sql_params.get("sql_user")
        sql_password = sql_params.get("sql_password")
        sql_database = sql_params.get("sql_database")
    else:
        sql_host = action_obj.get_config("sql_host")
        sql_user = action_obj.get_config("sql_user")
        sql_password = action_obj.get_config("sql_password")
        sql_database = action_obj.get_config("sql_database")
    sql_db = None

    if sql_host and sql_user and sql_password and sql_database:
        sql_db = PostgreSQLDatabase(
            host=sql_host,
            user=sql_user,
            password=sql_password,
            database=sql_database,
        )

    if sql_db is None:
        raise ValueError(
            f"SQL database expected but not configured on {action_obj.__class__.__name__}"
        )

    return sql_db