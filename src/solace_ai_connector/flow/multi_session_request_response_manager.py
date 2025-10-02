"""
Manages multiple independent request/response sessions for a component.
"""

import logging
import threading
import weakref
from typing import Dict, Any, List, Optional

from ..common.exceptions import SessionLimitExceededError
from ..common.session_config import SessionConfig
from .session_registry import SessionRegistry
from .request_response_session import RequestResponseSession

log = logging.getLogger(__name__)

class MultiSessionRequestResponseManager:
    """
    Manages multiple independent request/response sessions for a component.
    """

    def __init__(
        self,
        component: Any,
        default_session_config: Optional[SessionConfig] = None,
        max_sessions: int = 50,
    ):
        """
        Initializes the MultiSessionRequestResponseManager.

        Args:
            component: A weak reference to the parent component.
            default_session_config: The default session configuration.
            max_sessions: The maximum number of concurrent sessions allowed.
        """
        self.component_ref = weakref.ref(component)
        self.session_registry = SessionRegistry()
        self.default_session_config = default_session_config
        self.max_sessions = max_sessions
        self._lock = threading.RLock()
        self._shutdown_event = threading.Event()

    def create_session(
        self, session_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Creates a new request/response session, applies configuration to the default
        settings, registers it, and returns its unique ID.

        Args:
            session_config: A dictionary of configuration values for the session.

        Returns:
            The unique session ID of the newly created session.

        Raises:
            SessionLimitExceededError: If the maximum number of sessions is reached.
            RuntimeError: If the parent component reference is lost.
        """
        with self._lock:
            if len(self.session_registry.list_sessions()) >= self.max_sessions:
                raise SessionLimitExceededError(
                    "Cannot create new session. Maximum session limit of "
                    f"{self.max_sessions} reached."
                )

            session_config = session_config or {}

            # If no default config, the session_config must contain a complete broker_config.
            if not self.default_session_config:
                if "broker_config" not in session_config or not isinstance(
                    session_config.get("broker_config"), dict
                ):
                    raise ValueError(
                        "session_config must contain a 'broker_config' dictionary "
                        "when no default broker config is defined for the component."
                    )

            try:
                final_config = SessionConfig.from_dict(
                    session_config, self.default_session_config
                )
            except (ValueError, TypeError) as e:
                # Catch potential validation errors from SessionConfig and add context.
                raise ValueError(
                    f"Invalid session configuration. The combination of defaults and overrides is incomplete or invalid: {e}"
                ) from e

            component = self.component_ref()
            if not component:
                raise RuntimeError(
                    "Component reference is lost. Cannot create session."
                )

            session_id = self.session_registry.generate_session_id()
            session = RequestResponseSession(
                session_id=session_id,
                config=final_config,
                connector=component.connector,
            )
            self.session_registry.register_session(session)
            log.info(f"Created request/response session: {session_id}")
            return session_id

    def destroy_session(self, session_id: str) -> bool:
        """
        Destroys a session and cleans up its associated resources.

        Args:
            session_id: The ID of the session to destroy.

        Returns:
            True if the session was found and destroyed, False otherwise.
        """
        session = self.session_registry.unregister_session(session_id)
        if session:
            log.info(f"Destroying request/response session: {session_id}")
            session.cleanup()
            return True
        log.warning(f"Attempted to destroy non-existent session: {session_id}")
        return False

    def get_session(self, session_id: str) -> "RequestResponseSession":
        """
        Retrieves an active session by its ID.

        Args:
            session_id: The ID of the session to retrieve.

        Returns:
            The RequestResponseSession instance.
        """
        return self.session_registry.get_session(session_id)

    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        Returns a list of dictionaries containing detailed status for each
        active session.

        Returns:
            A list of session status dictionaries.
        """
        sessions = self.session_registry.list_sessions()
        return [session.get_status() for session in sessions]

    def shutdown(self):
        """
        Gracefully stops the cleanup thread and destroys all active sessions.
        """
        log.info("Shutting down MultiSessionRequestResponseManager.")
        self._shutdown_event.set()

        all_sessions = self.session_registry.clear()
        for session in all_sessions:
            log.info(f"Shutting down session during manager shutdown: {session.session_id}")
            session.cleanup()
        log.info("MultiSessionRequestResponseManager shut down complete.")
