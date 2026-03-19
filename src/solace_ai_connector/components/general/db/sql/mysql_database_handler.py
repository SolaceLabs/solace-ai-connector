"""Manage a MySQL database connection."""

import pymysql
import pymysql.cursors

class MySQLDatabase:
    def __init__(self, host: str, user: str, password: str, database: str, port: int = 3306):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.connection = None

        if ":" in self.host:
            self.host, self.port = self.host.split(":")

    def cursor(self, **kwargs):
        if self.connection is None or not self.connection.open:
            self.connect()
        try:
            return self.connection.cursor(**kwargs)
        except (pymysql.OperationalError, pymysql.InterfaceError):
            self.connect()
            return self.connection.cursor(**kwargs)

    def connect(self):
        self.connection = pymysql.connect(
            host=self.host,
            port=int(self.port),
            user=self.user,
            password=self.password,
            database=self.database,
            connect_timeout=60,
            autocommit=True,
        )
        return self.connection

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None

