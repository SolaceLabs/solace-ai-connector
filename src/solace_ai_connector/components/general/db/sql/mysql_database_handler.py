"""Manage a MySQL database connection."""

import mysql.connector

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
        if self.connection is None:
            self.connect()
        try:
            return self.connection.cursor(**kwargs)
        except mysql.connector.errors.OperationalError:
            self.connect()
            return self.connection.cursor(**kwargs)

    def connect(self):
        self.connection = mysql.connector.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            raise_on_warnings=False,
            connection_timeout=60,
            autocommit=True,
        )
        return self.connection

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None

