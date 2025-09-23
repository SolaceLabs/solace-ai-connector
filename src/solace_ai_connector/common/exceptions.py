"""Custom exceptions for the Solace AI Connector."""


class SessionLimitExceededError(Exception):
    """Raised when the maximum number of request/reply sessions is reached."""

    pass


class SessionClosedError(Exception):
    """Raised when an operation is attempted on a closed or expired session."""

    pass


class SessionNotFoundError(ValueError):
    """Raised when a specified session_id does not exist."""

    pass
