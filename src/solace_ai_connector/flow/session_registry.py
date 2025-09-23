"""Thread-safe registry for managing request/response sessions."""

import threading
from typing import Dict, List, TYPE_CHECKING

from ..common.exceptions import SessionNotFoundError

if TYPE_CHECKING:
    from .request_response_session import RequestResponseSession


class SessionRegistry:
    """
    Thread-safe registry for tracking active request/response sessions.
    """

    def __init__(self):
        """Initializes the SessionRegistry."""
        self._sessions: Dict[str, "RequestResponseSession"] = {}
        self._lock = threading.RLock()
        self._session_counter = 0

    def generate_session_id(self) -> str:
        """
        Generates a unique, thread-safe session ID.

        Returns:
            A unique session ID string.
        """
        with self._lock:
            self._session_counter += 1
            return f"session_{self._session_counter}"

    def register_session(self, session: "RequestResponseSession") -> None:
        """
        Adds a session to the registry.

        Args:
            session: The RequestResponseSession instance to register.
        """
        with self._lock:
            if session.session_id in self._sessions:
                raise ValueError(f"Session ID {session.session_id} already exists.")
            self._sessions[session.session_id] = session

    def unregister_session(self, session_id: str) -> "RequestResponseSession":
        """
        Removes and returns a session from the registry.

        Args:
            session_id: The ID of the session to unregister.

        Returns:
            The removed RequestResponseSession instance, or None if not found.
        """
        with self._lock:
            return self._sessions.pop(session_id, None)

    def get_session(self, session_id: str) -> "RequestResponseSession":
        """
        Retrieves a session by its ID.

        Args:
            session_id: The ID of the session to retrieve.

        Returns:
            The RequestResponseSession instance.

        Raises:
            SessionNotFoundError: If the session ID is not found.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                raise SessionNotFoundError(f"Session with ID '{session_id}' not found.")
            return session

    def list_sessions(self) -> List["RequestResponseSession"]:
        """
        Returns a list of all active session objects.

        Returns:
            A list of RequestResponseSession instances.
        """
        with self._lock:
            return list(self._sessions.values())

    def clear(self) -> List["RequestResponseSession"]:
        """
        Removes all sessions from the registry and returns them.
        Used for graceful shutdown.

        Returns:
            A list of all RequestResponseSession instances that were removed.
        """
        with self._lock:
            all_sessions = list(self._sessions.values())
            self._sessions.clear()
            return all_sessions
