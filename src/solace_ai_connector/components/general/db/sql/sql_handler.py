"""SQL Database Handler for SQL agent components."""

import logging
from typing import List, Dict, Any, Optional, Union
import importlib

from .mysql_database_handler import MySQLDatabase
from .postgres_database_handler import PostgreSQLDatabase

log = logging.getLogger(__name__)

class DatabaseFactory:
    """Factory class to create database instances."""

    DATABASE_PROVIDERS = {
        "mysql": MySQLDatabase,
        "postgres": PostgreSQLDatabase,
    }

    @staticmethod
    def get_database(
        db_type: str,
        host: str,
        port: Optional[int],
        user: str,
        password: str,
        database: str,
        **kwargs,
    ) -> Union[MySQLDatabase, PostgreSQLDatabase]:
        """
        Get a database connection instance.

        Args:
            db_type: Type of database ('mysql' or 'postgres').
            host: Database host.
            port: Database port.
            user: Database user.
            password: Database password.
            database: Database name.
            **kwargs: Additional arguments for the database connector.

        Returns:
            A database handler instance.

        Raises:
            ValueError: If the database type is unsupported.
        """
        db_type = db_type.lower()
        if db_type not in DatabaseFactory.DATABASE_PROVIDERS:
            raise ValueError("Unsupported database type: %s" % db_type)

        provider_class = DatabaseFactory.DATABASE_PROVIDERS[db_type]
        if port is not None:
            return provider_class(
                host=host,
                port=port, # Pass port directly
                user=user,
                password=password,
                database=database,
                **kwargs,
            )
        else:
             return provider_class(
                host=host, # Port might be embedded here or handler uses default
                user=user,
                password=password,
                database=database,
                **kwargs,
            )


class SQLHandler:
    """Handler for SQL database operations."""

    def __init__(
        self,
        db_type: str,
        host: str,
        port: Optional[int],
        user: str,
        password: str,
        database: str,
        **kwargs,
    ):
        """
        Initialize the SQL handler.

        Args:
            db_type: Type of database ('mysql' or 'postgres').
            host: Database host.
            port: Database port.
            user: Database user.
            password: Database password.
            database: Database name.
            **kwargs: Additional arguments for the database connector.
        """
        self.db_type = db_type.lower()
        log.info(
            "Initializing SQLHandler for %s at %s:%s/%s",
            self.db_type,
            host,
            port or 'default',
            database
        )
        self.db_client = DatabaseFactory.get_database(
            db_type=self.db_type,
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            **kwargs,
        )
        self.connect() # Ensure connection is attempted on init

    def connect(self):
        """Ensure the database connection is active."""
        try:
            if hasattr(self.db_client, 'connect') and callable(getattr(self.db_client, 'connect')):
                if getattr(self.db_client, 'connection', None) is None or \
                   (hasattr(getattr(self.db_client, 'connection', None), 'closed') and getattr(self.db_client.connection, 'closed', False)):
                    log.debug("Attempting to connect to %s database.", self.db_type)
                    self.db_client.connect()
                    log.info("Successfully connected/reconnected to %s database.", self.db_type)
            else: # If no explicit connect, try getting a cursor to test
                with self.db_client.cursor() as cursor: # cursor variable is not used here
                    log.debug("Connection to %s database confirmed via cursor.", self.db_type)
        except Exception:
            log.exception("Error connecting to %s database", self.db_type)
            raise ValueError("Failed to connect to %s database." % (self.db_type)) from None

    def close(self):
        """Close the database connection."""
        if self.db_client and hasattr(self.db_client, "close"):
            try:
                self.db_client.close()
                log.info("Successfully closed %s database connection.", self.db_type)
            except Exception:
                log.exception(
                    "Error closing %s database connection", self.db_type
                )

    def execute_query(
        self, query: str, params: Optional[Union[tuple, Dict]] = None, fetch_results: bool = True
    ) -> Union[List[Dict[str, Any]], int]:
        """
        Execute a SQL query.

        Args:
            query: The SQL query to execute.
            params: Parameters to bind to the query (tuple for %s, dict for named).
            fetch_results: Whether to fetch and return results.

        Returns:
            List of dictionaries if fetch_results is True, otherwise row count for DML.

        Raises:
            ValueError: If query execution fails.
        """
        log.debug("Executing query on %s: %s with params: %s", self.db_type, query, params)
        try:
            # PostgreSQLDatabase has its own execute method that returns a cursor
            if self.db_type == "postgres" and hasattr(self.db_client, 'execute'):
                cursor = self.db_client.execute(query, params)
            else: # For MySQL or other generic path
                # Ensure connection before getting cursor
                if getattr(self.db_client, 'connection', None) is None or \
                    (self.db_type == "mysql" and isinstance(getattr(self.db_client, 'connection', None), importlib.import_module('mysql.connector').connection.MySQLConnection) and not self.db_client.connection.is_connected()) or \
                    (self.db_type == "postgres" and getattr(self.db_client.connection, 'closed', True)):
                    self.connect()

                # MySQL uses dictionary=True for dict results, psycopg2 uses RealDictCursor
                cursor_kwargs = {}
                if self.db_type == "mysql":
                    cursor_kwargs['dictionary'] = True

                actual_cursor = self.db_client.cursor(**cursor_kwargs)
                actual_cursor.execute(query, params)
                cursor = actual_cursor


            if fetch_results:
                if hasattr(cursor, "fetchall") and callable(getattr(cursor, "fetchall")):
                    columns = [desc[0] for desc in cursor.description]
                    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                    log.debug("Query fetched %d rows.", len(results))
                    return results
                else:
                    log.warning("Cursor does not support fetchall, cannot return results as list of dicts.")
                    return [] # Or raise error
            else:
                rowcount = cursor.rowcount
                if self.db_type == "mysql" and self.db_client.connection.autocommit is False:
                     self.db_client.connection.commit()
                elif self.db_type == "postgres" and self.db_client.connection.autocommit is False:
                     self.db_client.connection.commit()

                log.debug("Query executed, row count: %s.", rowcount) # rowcount can be -1
                return rowcount

        except Exception as e:
            log.exception("Error executing query on %s", self.db_type)
            # Attempt to rollback if autocommit is false and an error occurs
            if self.db_type == "mysql" and hasattr(self.db_client, 'connection') and self.db_client.connection and self.db_client.connection.autocommit is False:
                self.db_client.connection.rollback()
            elif self.db_type == "postgres" and hasattr(self.db_client, 'connection') and self.db_client.connection and self.db_client.connection.autocommit is False:
                 self.db_client.connection.rollback()
            raise ValueError("Failed to execute query on %s: %s" % (self.db_type, e)) from e
        finally:
            if 'actual_cursor' in locals() and actual_cursor: # Check if actual_cursor was defined
                if hasattr(actual_cursor, 'closed') and not actual_cursor.closed:
                    actual_cursor.close()
                elif not hasattr(actual_cursor, 'closed'): # For cursors without a 'closed' attribute
                    actual_cursor.close()


    def insert_data(
        self,
        table_name: str,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
        on_duplicate_update_columns: Optional[List[str]] = None,
    ) -> int:
        """
        Insert data into a table.

        Args:
            table_name: Name of the table.
            data: A dictionary for a single row or a list of dictionaries for multiple rows.
            on_duplicate_update_columns: List of column names to update on duplicate key.

        Returns:
            Number of affected rows.

        Raises:
            ValueError: If data is not in the expected format or insertion fails.
        """
        if not isinstance(data, (dict, list)):
            raise ValueError("Data must be a dictionary or a list of dictionaries.")
        if isinstance(data, dict):
            data_list = [data]
        else:
            data_list = data

        if not data_list:
            return 0

        first_row = data_list[0]
        columns = list(first_row.keys())
        placeholders = ", ".join(["%s"] * len(columns))
        column_names = ", ".join([f"`{col}`" if self.db_type == "mysql" else f'"{col}"' for col in columns]) # Quote column names

        base_query = f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})"

        if on_duplicate_update_columns:
            if self.db_type == "mysql":
                update_clause = ", ".join([f"`{col}`=VALUES(`{col}`)" for col in on_duplicate_update_columns])
                query = f"{base_query} ON DUPLICATE KEY UPDATE {update_clause}"
            elif self.db_type == "postgres":
                update_clause = ", ".join([f'"{col}"=EXCLUDED."{col}"' for col in on_duplicate_update_columns])
                log.warning("PostgreSQL ON CONFLICT DO UPDATE is simplified and assumes conflict on primary key(s). "
                            "For complex cases, provide conflict_target_columns.")
                query = f"{base_query} ON CONFLICT DO UPDATE SET {update_clause}"
            else:
                raise ValueError(
                    f"ON DUPLICATE UPDATE not implemented for db_type: {self.db_type}"
                )
        else:
            query = base_query

        total_affected_rows = 0
        
        # Ensure connection
        if getattr(self.db_client, 'connection', None) is None or \
            (self.db_type == "mysql" and isinstance(getattr(self.db_client, 'connection', None), importlib.import_module('mysql.connector').connection.MySQLConnection) and not self.db_client.connection.is_connected()) or \
            (self.db_type == "postgres" and getattr(self.db_client.connection, 'closed', True)):
            self.connect()

        cursor_kwargs = {}
        if self.db_type == "mysql":
            cursor_kwargs['prepared'] = True # Use prepared statements for MySQL inserts if possible
        
        actual_cursor = None
        try:
            actual_cursor = self.db_client.cursor(**cursor_kwargs)
            if len(data_list) > 1 and hasattr(actual_cursor, 'executemany') and callable(getattr(actual_cursor, 'executemany')):
                values_to_insert = [tuple(row[col] for col in columns) for row in data_list]
                actual_cursor.executemany(query, values_to_insert)
                total_affected_rows = actual_cursor.rowcount
            else: # Fallback to one by one if executemany is not available or for single insert
                for row_data in data_list:
                    values = tuple(row_data[col] for col in columns)
                    actual_cursor.execute(query, values)
                    total_affected_rows += actual_cursor.rowcount
            
            # Commit if autocommit is off
            if self.db_type == "mysql" and self.db_client.connection.autocommit is False:
                self.db_client.connection.commit()
            elif self.db_type == "postgres" and self.db_client.connection.autocommit is False:
                self.db_client.connection.commit()

            log.debug(
                "Successfully inserted/updated data into %s. Affected rows: %s",
                table_name,
                total_affected_rows
            )
            return total_affected_rows
        except Exception as e:
            log.exception("Error inserting data into %s for %s", table_name, self.db_type)
            if self.db_type == "mysql" and hasattr(self.db_client, 'connection') and self.db_client.connection and self.db_client.connection.autocommit is False:
                self.db_client.connection.rollback()
            elif self.db_type == "postgres" and hasattr(self.db_client, 'connection') and self.db_client.connection and self.db_client.connection.autocommit is False:
                 self.db_client.connection.rollback()
            raise ValueError("Failed to insert data into %s: %s" % (table_name, e)) from e
        finally:
            if actual_cursor: # Check if actual_cursor was defined
                if hasattr(actual_cursor, 'closed') and not actual_cursor.closed:
                    actual_cursor.close()
                elif not hasattr(actual_cursor, 'closed'): # For cursors without a 'closed' attribute
                    actual_cursor.close()
