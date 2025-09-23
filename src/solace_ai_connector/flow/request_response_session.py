"""
Request/Response Session class for the Solace AI Connector.
This class wraps a RequestResponseFlowController with session-specific state.
"""

import time
import threading
import uuid
from typing import Dict, Any, Generator, Tuple

from ..common.session_config import SessionConfig
from .request_response_flow_controller import RequestResponseFlowController
from ..common.exceptions import SessionClosedError
from ..common.message import Message


class RequestResponseSession:
    """
    Wraps a RequestResponseFlowController with session-specific configuration,
    managing its lifecycle and state.
    """

    def __init__(self, session_id: str, config: SessionConfig, connector: Any):
        """
        Initializes the RequestResponseSession.

        Args:
            session_id: The unique identifier for this session.
            config: The SessionConfig object with all session parameters.
            connector: A reference to the main SolaceAiConnector instance.
        """
        self.session_id = session_id
        self.config = config
        self.created_at = time.time()
        self.last_used_at = time.time()
        self.active_requests = set()
        self._lock = threading.RLock()
        self._is_shutdown = threading.Event()

        # Create the underlying RequestResponseFlowController for this session
        self.controller = RequestResponseFlowController(
            config=config.to_controller_config(), connector=connector
        )

    def do_request_response(
        self,
        message: Message,
        stream: bool = False,
        streaming_complete_expression: str = None,
        wait_for_response: bool = True,
    ) -> Generator[Tuple[Message, bool], None, None]:
        """
        Executes a request/response operation using this session's controller.

        Args:
            message: The request message to send.
            stream: Whether the response is expected to be streaming.
            streaming_complete_expression: Expression to detect the end of a stream.
            wait_for_response: If False, sends the request and returns immediately.

        Yields:
            A tuple containing the response Message and a boolean indicating if it's the last message.

        Raises:
            SessionClosedError: If the session has been closed.
            TimeoutError: If the request times out.
        """
        if self._is_shutdown.is_set():
            raise SessionClosedError(f"Session {self.session_id} has been closed.")

        self.update_last_used()
        request_id = str(uuid.uuid4())

        with self._lock:
            self.active_requests.add(request_id)

        try:
            yield from self.controller.do_broker_request_response(
                message, stream, streaming_complete_expression, wait_for_response
            )
        finally:
            with self._lock:
                self.active_requests.remove(request_id)

    def get_status(self) -> Dict[str, Any]:
        """
        Returns a dictionary with detailed status information for this session.

        Returns:
            A dictionary containing session status.
        """
        with self._lock:
            active_request_count = len(self.active_requests)

        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
            "active_request_count": active_request_count,
        }

    def cleanup(self) -> None:
        """
        Cleans up all resources used by the session, including the underlying
        flow controller and its broker connection.
        """
        if self._is_shutdown.is_set():
            return

        self._is_shutdown.set()
        if hasattr(self.controller, "cleanup"):
            self.controller.cleanup()
        elif self.controller and self.controller.flow:
            # Fallback if cleanup() is not yet on the controller.
            # The controller's internal flow cleanup will handle resources.
            self.controller.flow.cleanup()

    def update_last_used(self) -> None:
        """Updates the last used timestamp for the session."""
        self.last_used_at = time.time()
