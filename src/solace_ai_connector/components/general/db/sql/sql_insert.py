"""Component for inserting data into a SQL database."""

import logging
from typing import List, Dict, Any, Union, Optional
import copy

from .sql_base import SQLBaseComponent, info as base_info

log = logging.getLogger(__name__)

# Component-specific information
info = copy.deepcopy(base_info)
info["class_name"] = "SQLInsertComponent"
info["description"] = "Inserts data into a SQL database table."

info["config_parameters"].append(
    {
        "name": "default_on_duplicate_update_columns",
        "required": False,
        "description": "Optional. Default list of column names to update if a duplicate key conflict occurs. Used if not provided in the input message.",
        "type": "array",
        "items": {"type": "string"},
        "default": []
    }
)

info["input_schema"] = {
    "type": "object",
    "properties": {
        "table_name": {
            "type": "string",
            "description": "The name of the table to insert data into.",
        },
        "data": {
            "type": ["object", "array"],
            "description": "The data to insert. A single dictionary for one row, or a list of dictionaries for multiple rows. Keys should match column names.",
            "items": {"type": "object"} # For array type
        },
        "on_duplicate_update_columns": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional. List of column names to update if a duplicate key conflict occurs (e.g., for INSERT ... ON DUPLICATE KEY UPDATE or ON CONFLICT ... DO UPDATE).",
            "default": []
        },
    },
    "required": ["table_name", "data"],
}
info["output_schema"] = {
    "type": "object",
    "properties": {
        "affected_rows": {
            "type": "integer",
            "description": "The number of rows affected by the insert operation."
        },
        "table_name": {
            "type": "string",
            "description": "The table into which data was inserted."
        }
    }
}


class SQLInsertComponent(SQLBaseComponent):
    """Component for inserting data into a SQL database table."""

    def __init__(self, **kwargs):
        """Initialize the SQLInsertComponent."""
        super().__init__(module_info=info, **kwargs)

    def invoke(self, message, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inserts data into the specified SQL table.

        Args:
            message: The input message (unused in this component).
            data: A dictionary containing:
                - table_name (str): The name of the table.
                - data (Union[Dict[str, Any], List[Dict[str, Any]]]): Data to insert.
                - on_duplicate_update_columns (Optional[List[str]]): Columns to update on conflict.

        Returns:
            A dictionary containing the number of affected rows and the table name.

        Raises:
            ValueError: If required parameters are missing or data is malformed, or if an SQL error occurs.
        """
        table_name: Optional[str] = data.get("table_name")
        data_to_insert: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = data.get("data")
        
        # Get on_duplicate_update_columns from input data, or fallback to config
        on_duplicate_update_columns: Optional[List[str]] = data.get(
            "on_duplicate_update_columns",
            self.get_config("default_on_duplicate_update_columns", [])
        )

        if not table_name:
            raise ValueError("'table_name' is a required input parameter.")
        if data_to_insert is None: # Can be empty list/dict, but not None
            raise ValueError("'data' is a required input parameter.")
        
        if not isinstance(data_to_insert, (dict, list)):
            raise ValueError("'data' must be a dictionary (for a single row) or a list of dictionaries (for multiple rows).")
        
        if isinstance(data_to_insert, list) and data_to_insert:
            if not all(isinstance(item, dict) for item in data_to_insert):
                raise ValueError("If 'data' is a list, all its elements must be dictionaries.")
        elif isinstance(data_to_insert, list) and not data_to_insert:
            log.info("No data provided to insert into table '%s'. Returning 0 affected rows.", table_name)
            return {"affected_rows": 0, "table_name": table_name}
        elif isinstance(data_to_insert, dict) and not data_to_insert:
             log.info("Empty data dictionary provided to insert into table '%s'. Returning 0 affected rows.", table_name)
             return {"affected_rows": 0, "table_name": table_name}

        log.info(
            "Attempting to insert data into table '%s' in %s database.",
            table_name,
            self.db_handler.db_type
        )

        try:
            affected_rows = self.db_handler.insert_data(
                table_name=table_name,
                data=data_to_insert,
                on_duplicate_update_columns=on_duplicate_update_columns,
            )
            log.info(
                "Successfully inserted/updated data into '%s'. Affected rows: %d",
                table_name,
                affected_rows
            )
            return {"affected_rows": affected_rows, "table_name": table_name}
        except ValueError:
            log.exception("ValueError during insert operation for table '%s'", table_name)
            # Re-raise the ValueError to be caught by the component runner or flow controller
            raise
        except Exception as e:
            log.exception("Unexpected error during insert operation for table '%s'", table_name)
            # Wrap unexpected errors in a ValueError or a more specific component error
            raise ValueError("An unexpected error occurred while inserting data into '%s': %s" % (table_name, e)) from e
