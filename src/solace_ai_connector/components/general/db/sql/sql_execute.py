"""Component for executing arbitrary SQL queries."""

import logging
from typing import List, Dict, Any, Union, Optional
import copy
import json

from .sql_base import SQLBaseComponent, info as base_info
log = logging.getLogger(__name__)

# Component-specific information
info = copy.deepcopy(base_info)
info["class_name"] = "SQLExecuteComponent"
info["description"] = "Executes an arbitrary SQL query against the database."
info["input_schema"] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "The SQL query to execute.",
        },
        "params": {
            "type": ["object", "array"],
            "description": "Optional. Parameters to bind to the query. Use a list/tuple for positional placeholders (e.g., %s) or a dictionary for named placeholders (e.g., %(name)s), if supported by the DB driver.",
        },
        "fetch_results": {
            "type": "boolean",
            "description": "Optional. Whether to fetch and return results (e.g., for SELECT queries). If False, might return row count for DML operations.",
            "default": True,
        },
    },
    "required": ["query"],
}
info["output_schema"] = {
    "type": "object",
    "properties": {
        "results": {
            "type": ["array", "integer"], # Array of objects for SELECT, integer for DML row count
            "description": "Query results. For SELECT, typically a list of dictionaries. For DML (if fetch_results=false), typically the number of affected rows.",
            "items": {"type": "object"}
        },
        "query": {
            "type": "string",
            "description": "The executed query."
        }
    }
}


class SQLExecuteComponent(SQLBaseComponent):
    """Component for executing arbitrary SQL queries."""

    def __init__(self, **kwargs):
        """Initialize the SQLExecuteComponent."""
        super().__init__(module_info=info, **kwargs)

    def invoke(self, message, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the given SQL query.

        Args:
            message: The input message (unused in this component).
            data: A dictionary containing:
                - query (str): The SQL query to execute.
                - params (Optional[Union[List, Dict]]): Parameters for the query.
                - fetch_results (Optional[bool]): Whether to fetch results.

        Returns:
            A dictionary containing the query results or affected row count, and the original query.

        Raises:
            ValueError: If 'query' parameter is missing or an SQL error occurs.
        """
        query_str: Optional[str] = data.get("query")
        query_params: Optional[Union[List, Dict, tuple]] = data.get("params")
        fetch_results: bool = data.get("fetch_results", True)

        if not query_str:
            raise ValueError("'query' is a required input parameter.")

        # Ensure params are tuple if list for some drivers (e.g. psycopg2)
        if isinstance(query_params, list):
            query_params = tuple(query_params)
        
        log.info(
            "Attempting to execute query on %s database: %s",
            self.db_handler.db_type,
            query_str
        )
        if query_params:
            log.debug("Query parameters: %s", query_params)

        try:
            results = self.db_handler.execute_query(
                query=query_str, params=query_params, fetch_results=fetch_results
            )
            
            log.info(
                "Successfully executed query. Fetch results: %s. Result type: %s",
                fetch_results,
                type(results)
            )
            # To convert things like datetime to string for JSON serialization and back to dict
            return {"results": json.loads(json.dumps(results, default=str)), "query": query_str}
        except ValueError:
            log.exception("ValueError during query execution")
            raise
        except Exception as e:
            log.exception("Unexpected error during query execution")
            raise ValueError("An unexpected error occurred while executing query: %s" % e) from e