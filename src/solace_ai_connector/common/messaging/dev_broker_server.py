"""TCP server that exposes DevBroker functionality over the network.

This server allows remote processes (e.g., Docker containers) to connect to
a DevBroker instance running on the host machine.
"""

import asyncio
import json
import logging
import queue
import threading
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .dev_broker_protocol import (
    CMD_ACK,
    CMD_CONNECT,
    CMD_DISCONNECT,
    CMD_PUBLISH,
    CMD_RECEIVE,
    CMD_SUBSCRIBE,
    CMD_UNSUBSCRIBE,
    ERR_INTERNAL_ERROR,
    ERR_INVALID_COMMAND,
    ERR_NOT_CONNECTED,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_TIMEOUT,
    subscription_to_regex,
    topic_matches,
)

log = logging.getLogger(__name__)


@dataclass
class ClientSession:
    """State for a connected network client."""

    client_id: str
    queue_name: str
    message_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    subscriptions: Set[str] = field(default_factory=set)  # regex patterns
    writer: Optional[asyncio.StreamWriter] = None


class DevBrokerServer:
    """
    TCP server that exposes message broker functionality over the network.

    This server manages its own subscriptions and queues for network clients,
    and can optionally integrate with a local DevBroker instance to share
    messages between local and network clients.

    Usage:
        server = DevBrokerServer(host="0.0.0.0", port=55555)
        await server.start()
        # ... server runs ...
        await server.stop()

    Or with context manager:
        async with DevBrokerServer(port=55555) as server:
            # server is running
            pass
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 55555,
        local_broker=None,
    ):
        """
        Initialize the server.

        Args:
            host: Host to bind to.  Defaults to ``0.0.0.0`` (all interfaces)
                  so that Docker containers on the host network can reach the
                  broker.  For local-only use, pass ``127.0.0.1`` instead.
                  **Note:** binding to ``0.0.0.0`` exposes the broker to all
                  network interfaces with no authentication — only use this in
                  trusted development environments.
            port: Port to listen on (0 for auto-assign)
            local_broker: Optional DevBroker instance to integrate with
        """
        self._host = host
        self._port = port
        self._local_broker = local_broker
        self._server: Optional[asyncio.Server] = None
        self._clients: Dict[str, ClientSession] = {}
        self._subscriptions: Dict[str, List[str]] = {}  # pattern -> [client_ids]
        self._lock = asyncio.Lock()
        self._running = False
        self._actual_port: Optional[int] = None

        # Network routing is now handled via flow_kv_store callback
        # (set in DevBroker._maybe_start_network_server) so ALL DevBroker
        # instances forward to network clients, not just the one that
        # created the server.

    async def _route_message_to_network(
        self, topic: str, payload: Any, user_properties: Dict = None
    ):
        """Route a message to matching network clients."""
        # Ensure payload is JSON-serializable (BrokerOutput may encode to bytes)
        if isinstance(payload, (bytes, bytearray)):
            try:
                payload = json.loads(payload)
            except (json.JSONDecodeError, UnicodeDecodeError):
                payload = payload.decode("utf-8", errors="replace")

        async with self._lock:
            for pattern, client_ids in self._subscriptions.items():
                if topic_matches(pattern, topic):
                    for client_id in client_ids:
                        if client_id in self._clients:
                            session = self._clients[client_id]
                            message = {
                                "message_id": str(uuid.uuid4()),
                                "topic": topic,
                                "payload": payload,
                                "user_properties": user_properties or {},
                            }
                            await session.message_queue.put(deepcopy(message))

    @property
    def port(self) -> int:
        """Return the actual port the server is listening on."""
        return self._actual_port or self._port

    @property
    def is_running(self) -> bool:
        """Return whether the server is currently running."""
        return self._running

    async def start(self) -> int:
        """
        Start the TCP server.

        Returns:
            The actual port the server is listening on.
        """
        if self._running:
            log.warning("DevBrokerServer: Already running")
            return self._actual_port

        self._loop = asyncio.get_event_loop()
        self._server = await asyncio.start_server(
            self._handle_client, self._host, self._port,
            reuse_address=True,
        )

        # Get the actual port (useful when port=0 for auto-assign)
        addr = self._server.sockets[0].getsockname()
        self._actual_port = addr[1]
        self._running = True

        log.info(f"DevBrokerServer: Listening on {self._host}:{self._actual_port}")
        return self._actual_port

    async def stop(self):
        """Stop the server and disconnect all clients."""
        if not self._running:
            return

        self._running = False

        # Close all client connections
        async with self._lock:
            for client_id, session in list(self._clients.items()):
                if session.writer:
                    try:
                        session.writer.close()
                        await session.writer.wait_closed()
                    except Exception:
                        pass
            self._clients.clear()
            self._subscriptions.clear()

        # Stop the server
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        log.info("DevBrokerServer: Stopped")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """Handle a new client connection."""
        addr = writer.get_extra_info("peername")
        log.info(f"DevBrokerServer: New connection from {addr}")

        # Increase readline limit to support large payloads (default is 64KB)
        reader._limit = 10 * 1024 * 1024  # 10MB limit

        session: Optional[ClientSession] = None

        try:
            while self._running:
                try:
                    line = await asyncio.wait_for(reader.readline(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                if not line:
                    break  # Connection closed

                try:
                    cmd = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError as e:
                    await self._send_response(
                        writer,
                        {"status": STATUS_ERROR, "error_code": ERR_INVALID_COMMAND, "error_message": str(e)},
                    )
                    continue

                cmd_type = cmd.get("cmd")

                # Handle CONNECT
                if cmd_type == CMD_CONNECT:
                    session = await self._handle_connect(cmd, writer)
                    if session:
                        await self._send_response(
                            writer, {"status": STATUS_OK, "client_id": session.client_id}
                        )
                    else:
                        await self._send_response(
                            writer,
                            {"status": STATUS_ERROR, "error_code": ERR_INTERNAL_ERROR, "error_message": "Connect failed"},
                        )
                    continue

                # All other commands require connection
                if not session:
                    await self._send_response(
                        writer,
                        {"status": STATUS_ERROR, "error_code": ERR_NOT_CONNECTED, "error_message": "Not connected"},
                    )
                    continue

                # Handle other commands
                if cmd_type == CMD_SUBSCRIBE:
                    response = await self._handle_subscribe(session, cmd)
                elif cmd_type == CMD_UNSUBSCRIBE:
                    response = await self._handle_unsubscribe(session, cmd)
                elif cmd_type == CMD_PUBLISH:
                    response = await self._handle_publish(session, cmd)
                elif cmd_type == CMD_RECEIVE:
                    response = await self._handle_receive(session, cmd)
                elif cmd_type == CMD_ACK:
                    response = {"status": STATUS_OK}  # No-op for now
                elif cmd_type == CMD_DISCONNECT:
                    await self._send_response(writer, {"status": STATUS_OK})
                    break
                else:
                    response = {
                        "status": STATUS_ERROR,
                        "error_code": ERR_INVALID_COMMAND,
                        "error_message": f"Unknown command: {cmd_type}",
                    }

                await self._send_response(writer, response)

        except Exception as e:
            log.error(f"DevBrokerServer: Client error: {e}")
        finally:
            # Clean up client
            if session:
                await self._disconnect_client(session.client_id)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            log.info(f"DevBrokerServer: Client {addr} disconnected")

    async def _handle_connect(
        self, cmd: Dict, writer: asyncio.StreamWriter
    ) -> Optional[ClientSession]:
        """Handle CONNECT command."""
        client_id = cmd.get("client_id", str(uuid.uuid4()))
        queue_name = cmd.get("queue_name", f"queue-{client_id}")
        subscriptions = cmd.get("subscriptions", [])

        async with self._lock:
            # Create client session
            session = ClientSession(
                client_id=client_id,
                queue_name=queue_name,
                writer=writer,
            )
            self._clients[client_id] = session

            # Process initial subscriptions
            for topic_pattern in subscriptions:
                regex = subscription_to_regex(topic_pattern)
                session.subscriptions.add(regex)
                if regex not in self._subscriptions:
                    self._subscriptions[regex] = []
                if client_id not in self._subscriptions[regex]:
                    self._subscriptions[regex].append(client_id)

        log.info(
            f"DevBrokerServer: Client {client_id} connected with {len(subscriptions)} subscriptions"
        )
        return session

    async def _disconnect_client(self, client_id: str):
        """Remove a client and its subscriptions."""
        async with self._lock:
            if client_id not in self._clients:
                return

            session = self._clients[client_id]

            # Remove from subscriptions
            for pattern in session.subscriptions:
                if pattern in self._subscriptions:
                    if client_id in self._subscriptions[pattern]:
                        self._subscriptions[pattern].remove(client_id)
                    if not self._subscriptions[pattern]:
                        del self._subscriptions[pattern]

            del self._clients[client_id]

    async def _handle_subscribe(
        self, session: ClientSession, cmd: Dict
    ) -> Dict[str, Any]:
        """Handle SUBSCRIBE command."""
        topic_pattern = cmd.get("topic_pattern", "")
        if not topic_pattern:
            return {
                "status": STATUS_ERROR,
                "error_code": ERR_INVALID_COMMAND,
                "error_message": "Missing topic_pattern",
            }

        regex = subscription_to_regex(topic_pattern)

        async with self._lock:
            session.subscriptions.add(regex)
            if regex not in self._subscriptions:
                self._subscriptions[regex] = []
            if session.client_id not in self._subscriptions[regex]:
                self._subscriptions[regex].append(session.client_id)

        log.debug(f"DevBrokerServer: {session.client_id} subscribed to {topic_pattern}")
        return {"status": STATUS_OK}

    async def _handle_unsubscribe(
        self, session: ClientSession, cmd: Dict
    ) -> Dict[str, Any]:
        """Handle UNSUBSCRIBE command."""
        topic_pattern = cmd.get("topic_pattern", "")
        if not topic_pattern:
            return {
                "status": STATUS_ERROR,
                "error_code": ERR_INVALID_COMMAND,
                "error_message": "Missing topic_pattern",
            }

        regex = subscription_to_regex(topic_pattern)

        async with self._lock:
            session.subscriptions.discard(regex)
            if regex in self._subscriptions:
                if session.client_id in self._subscriptions[regex]:
                    self._subscriptions[regex].remove(session.client_id)
                if not self._subscriptions[regex]:
                    del self._subscriptions[regex]

        log.debug(f"DevBrokerServer: {session.client_id} unsubscribed from {topic_pattern}")
        return {"status": STATUS_OK}

    async def _handle_publish(
        self, session: ClientSession, cmd: Dict
    ) -> Dict[str, Any]:
        """Handle PUBLISH command."""
        topic = cmd.get("topic", "")
        payload = cmd.get("payload")
        user_properties = cmd.get("user_properties", {})

        if not topic:
            return {
                "status": STATUS_ERROR,
                "error_code": ERR_INVALID_COMMAND,
                "error_message": "Missing topic",
            }

        message_id = str(uuid.uuid4())

        # Route to matching network clients
        async with self._lock:
            for pattern, client_ids in self._subscriptions.items():
                if topic_matches(pattern, topic):
                    for client_id in client_ids:
                        if client_id in self._clients and client_id != session.client_id:
                            target = self._clients[client_id]
                            message = {
                                "message_id": message_id,
                                "topic": topic,
                                "payload": payload,
                                "user_properties": user_properties,
                            }
                            await target.message_queue.put(deepcopy(message))

        # Also route to local broker if available.
        # Pass _from_network flag so send_message() skips network forwarding
        # (we already routed to network clients above).
        if self._local_broker and self._local_broker.connected:
            try:
                self._local_broker.send_message(
                    topic, payload, user_properties,
                    user_context={"_from_network": True},
                )
            except Exception as e:
                log.warning(f"DevBrokerServer: Failed to route to local broker: {e}")

        log.debug(f"DevBrokerServer: Published to {topic}")
        return {"status": STATUS_OK, "message_id": message_id}

    async def _handle_receive(
        self, session: ClientSession, cmd: Dict
    ) -> Dict[str, Any]:
        """Handle RECEIVE command."""
        timeout_ms = cmd.get("timeout_ms", 5000)
        timeout_sec = timeout_ms / 1000

        try:
            message = await asyncio.wait_for(
                session.message_queue.get(), timeout=timeout_sec
            )
            return {"status": STATUS_OK, "message": message}
        except asyncio.TimeoutError:
            return {"status": STATUS_TIMEOUT}

    async def _send_response(
        self, writer: asyncio.StreamWriter, response: Dict[str, Any]
    ):
        """Send a JSON response to the client."""
        data = (json.dumps(response, default=str) + "\n").encode("utf-8")
        writer.write(data)
        await writer.drain()

def start_server_in_thread(
    host: str = "0.0.0.0", port: int = 55555, local_broker=None
) -> "DevBrokerServer":
    """
    Start a DevBrokerServer in a background thread.

    This is useful when you want to run the server alongside other code
    that isn't async.

    Returns:
        The server instance (call server.stop() to shut down)
    """
    server = DevBrokerServer(host=host, port=port, local_broker=local_broker)
    startup_error = [None]  # Use list to allow mutation from inner function
    ready_event = threading.Event()

    def run_server():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            server._loop = loop
            loop.run_until_complete(server.start())
            ready_event.set()
            loop.run_forever()
        except Exception as e:
            startup_error[0] = e
            ready_event.set()  # Unblock the waiting thread
            log.error("DevBrokerServer: Failed to start: %s", e)

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    ready_event.wait(timeout=5)

    if startup_error[0] is not None:
        raise RuntimeError(
            f"DevBrokerServer failed to start on port {port}: {startup_error[0]}"
        ) from startup_error[0]

    if not server.is_running:
        raise RuntimeError(
            f"DevBrokerServer failed to start on port {port} within 5 seconds"
        )

    return server
