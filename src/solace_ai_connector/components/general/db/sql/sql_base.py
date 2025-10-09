"""Base component for SQL database operations."""
import logging
from ....component_base import ComponentBase
from .sql_handler import SQLHandler

log = logging.getLogger(__name__)

# Base information for SQL components
# Derived components will copy and update this.
info = {
    "class_name": "SQLBaseComponent",
    "description": "Base component for SQL database operations.",
    "category": "database",
    "status": "preview", # Or "stable" once well-tested
    "config_parameters": [
        {
            "name": "database_type",
            "required": True,
            "description": "Type of SQL database. Supported: 'postgres', 'mysql'.",
            "type": "string",
            "default": "postgres",
            "enum": ["postgres", "mysql"],
        },
        {
            "name": "sql_host",
            "required": True,
            "description": "SQL database host.",
            "type": "string",
        },
        {
            "name": "sql_port",
            "required": True,
            "description": "SQL database port.",
            "type": "integer",
        },
        {
            "name": "sql_user",
            "required": True,
            "description": "SQL database user.",
            "type": "string",
        },
        {
            "name": "sql_password",
            "required": True,
            "description": "SQL database password.",
            "type": "string",
            "sensitive": True,
        },
        {
            "name": "sql_database",
            "required": True,
            "description": "SQL database name.",
            "type": "string",
        },
    ],
    "input_schema": {
        "type": "object",
        "properties": {}, # To be defined by derived classes
    },
    "output_schema": {
        "type": "object", # Or other types, to be defined by derived classes
    },
}


class SQLBaseComponent(ComponentBase):
    """Base class for SQL database components."""

    def __init__(self, module_info: dict, **kwargs):
        """
        Initialize the SQLBaseComponent.

        Args:
            module_info: Component's specific information dictionary.
            **kwargs: Additional keyword arguments.

        Raises:
            ValueError: If required database configuration is missing or invalid.
        """
        super().__init__(module_info, **kwargs)
        self.db_handler: SQLHandler = None

        try:
            db_type = self.get_config("database_type", "postgres")
            host = self.get_config("sql_host")
            port = self.get_config("sql_port")
            user = self.get_config("sql_user")
            password = self.get_config("sql_password")
            database_name = self.get_config("sql_database")

            if not all([host, port, user, password, database_name]):
                missing_configs = [
                    name for name, val in [
                        ("sql_host", host), ("sql_port", port), ("sql_user", user),
                        ("sql_password", password), ("sql_database", database_name)
                    ] if not val
                ]
                raise ValueError(
                    "Missing required SQL configuration parameters: %s" % ", ".join(missing_configs)
                )
            
            # Ensure port is an integer
            try:
                port = int(port)
            except ValueError:
                raise ValueError("sql_port must be an integer, got: %s" % port)


            self.db_handler = SQLHandler(
                db_type=db_type,
                host=host,
                port=port,
                user=user,
                password=password,
                database=database_name,
            )
            log.info("%s initialized with %s handler.", self.__class__.__name__, db_type)

        except ValueError:
            log.exception("Configuration error in %s", self.__class__.__name__)
            raise
        except Exception as e:
            log.exception(
                "Error initializing SQLHandler in %s", self.__class__.__name__
            )
            # Wrap in ValueError or a custom component error
            raise ValueError("Failed to initialize SQL database handler: %s" % e) from e

    def invoke(self, message, data: dict):
        """
        Process an incoming message.
        This method should be overridden by derived classes.
        """
        raise NotImplementedError(
            "%s must implement the 'invoke' method." % self.__class__.__name__
        )

    def cleanup(self):
        """
        Clean up resources, such as closing database connections.
        """
        if self.db_handler:
            log.debug("Cleaning up %s, closing DB handler.", self.__class__.__name__)
            self.db_handler.close()
        super().cleanup()
