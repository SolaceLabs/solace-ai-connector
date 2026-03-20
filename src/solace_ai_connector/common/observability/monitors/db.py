"""Monitor for database operations."""

from .base import Monitor, MonitorInstance


class DBMonitor(Monitor):
    """
    Monitor for database operation duration.

    Maps to: db.duration histogram
    Labels: db.collection.name, db.operation.name, error.type
    """

    monitor_type = "db.duration"

    @staticmethod
    def parse_error(exc: Exception) -> str:
        """
        Navigate to root cause for DB errors.

        Walks exception chain to find root cause, then categorizes.
        """
        # Walk exception chain to root cause
        root = exc
        while root.__cause__ is not None:
            root = root.__cause__

        # Categorize based on root cause message
        root_str = str(root).lower()
        if 'timeout' in root_str:
            return "db_timeout"
        if 'connection' in root_str:
            return "db_connection_error"
        if 'deadlock' in root_str:
            return "db_deadlock"
        if 'constraint' in root_str:
            return "db_constraint_violation"

        return root.__class__.__name__

    @classmethod
    def query(cls, collection: str):
        """Create monitor instance for query operation."""
        return MonitorInstance(
            monitor_type=cls.monitor_type,
            labels={
                "db.collection.name": collection,
                "db.operation.name": "query"
            },
            error_parser=cls.parse_error
        )

    @classmethod
    def insert(cls, collection: str):
        """Create monitor instance for insert operation."""
        return MonitorInstance(
            monitor_type=cls.monitor_type,
            labels={
                "db.collection.name": collection,
                "db.operation.name": "insert"
            },
            error_parser=cls.parse_error
        )

    @classmethod
    def update(cls, collection: str):
        """Create monitor instance for update operation."""
        return MonitorInstance(
            monitor_type=cls.monitor_type,
            labels={
                "db.collection.name": collection,
                "db.operation.name": "update"
            },
            error_parser=cls.parse_error
        )

    @classmethod
    def delete(cls, collection: str):
        """Create monitor instance for delete operation."""
        return MonitorInstance(
            monitor_type=cls.monitor_type,
            labels={
                "db.collection.name": collection,
                "db.operation.name": "delete"
            },
            error_parser=cls.parse_error
        )