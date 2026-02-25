"""Tests for the network dev broker: server and client end-to-end behavior.

These tests verify the actual behavior of the network dev broker system
by running a real TCP server and connecting real clients to it.
"""

import asyncio
import json
import sys
import socket

import pytest

sys.path.append("src")

from solace_ai_connector.common.messaging.dev_broker_protocol import (
    CMD_CONNECT,
    CMD_PUBLISH,
    CMD_RECEIVE,
    CMD_SUBSCRIBE,
    STATUS_OK,
    STATUS_ERROR,
    STATUS_TIMEOUT,
    ERR_NOT_CONNECTED,
    ERR_INVALID_COMMAND,
)
from solace_ai_connector.common.messaging.dev_broker_server import (
    start_server_in_thread,
    DevBrokerServer,
)
from solace_ai_connector.common.messaging.network_dev_broker import (
    NetworkDevBroker,
    NetworkConnectionStatus,
)
from solace_ai_connector.common.messaging.dev_broker_protocol import (
    subscription_to_regex,
    topic_matches,
)


# ── Server Protocol Error Handling ──────────────────────────────────────
# These test error paths that the high-level client can't trigger.


class TestServerProtocolErrors:
    """Verify the server rejects malformed or out-of-order protocol messages."""

    @pytest.fixture
    def server_and_port(self):
        server = start_server_in_thread(host="127.0.0.1", port=0)
        yield server, server.port
        if server._loop and server._loop.is_running():
            asyncio.run_coroutine_threadsafe(server.stop(), server._loop).result(timeout=5)

    def _connect_raw(self, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect(("127.0.0.1", port))
        return sock, sock.makefile("rb")

    def _send_recv(self, sock, sock_file, cmd_dict):
        data = (json.dumps(cmd_dict) + "\n").encode("utf-8")
        sock.sendall(data)
        line = sock_file.readline()
        return json.loads(line.decode("utf-8"))

    def test_command_before_connect_rejected(self, server_and_port):
        """Server should reject any command sent before CONNECT."""
        _, port = server_and_port
        sock, sf = self._connect_raw(port)
        try:
            resp = self._send_recv(sock, sf, {"cmd": CMD_SUBSCRIBE, "topic_pattern": "a/b"})
            assert resp["status"] == STATUS_ERROR
            assert resp["error_code"] == ERR_NOT_CONNECTED
        finally:
            sock.close()

    def test_invalid_json_rejected(self, server_and_port):
        """Server should return an error for non-JSON input without crashing."""
        _, port = server_and_port
        sock, sf = self._connect_raw(port)
        try:
            sock.sendall(b"not json at all\n")
            line = sf.readline()
            resp = json.loads(line.decode("utf-8"))
            assert resp["status"] == STATUS_ERROR
            assert resp["error_code"] == ERR_INVALID_COMMAND
        finally:
            sock.close()

    def test_unknown_command_rejected(self, server_and_port):
        """Server should return an error for unrecognized command types."""
        _, port = server_and_port
        sock, sf = self._connect_raw(port)
        try:
            self._send_recv(sock, sf, {"cmd": CMD_CONNECT, "client_id": "c1"})
            resp = self._send_recv(sock, sf, {"cmd": "FOOBAR"})
            assert resp["status"] == STATUS_ERROR
            assert resp["error_code"] == ERR_INVALID_COMMAND
        finally:
            sock.close()

    def test_publish_without_topic_rejected(self, server_and_port):
        """Server should reject publish commands with empty topic."""
        _, port = server_and_port
        sock, sf = self._connect_raw(port)
        try:
            self._send_recv(sock, sf, {"cmd": CMD_CONNECT, "client_id": "c1"})
            resp = self._send_recv(sock, sf, {"cmd": CMD_PUBLISH, "topic": "", "payload": "x"})
            assert resp["status"] == STATUS_ERROR
        finally:
            sock.close()

    def test_publisher_does_not_receive_own_message(self, server_and_port):
        """A client subscribed to a topic should NOT get its own published messages."""
        _, port = server_and_port
        sock, sf = self._connect_raw(port)
        try:
            self._send_recv(sock, sf, {
                "cmd": CMD_CONNECT,
                "client_id": "self-pub",
                "subscriptions": ["test/>"],
            })
            self._send_recv(sock, sf, {
                "cmd": CMD_PUBLISH,
                "topic": "test/echo",
                "payload": "hi",
            })
            sock.settimeout(10)
            resp = self._send_recv(sock, sf, {"cmd": CMD_RECEIVE, "timeout_ms": 300})
            assert resp["status"] == STATUS_TIMEOUT
        finally:
            sock.close()


# ── Client Behavioral Tests ─────────────────────────────────────────────
# All tests use the NetworkDevBroker client against a real server,
# testing the system end-to-end through the Messaging interface.


class TestNetworkDevBrokerEndToEnd:
    """End-to-end behavioral tests for NetworkDevBroker client + server."""

    @pytest.fixture
    def server(self):
        srv = start_server_in_thread(host="127.0.0.1", port=0)
        yield srv
        if srv._loop and srv._loop.is_running():
            asyncio.run_coroutine_threadsafe(srv.stop(), srv._loop).result(timeout=5)

    def _make_client(self, server, **extra_props):
        props = {
            "dev_broker_host": "127.0.0.1",
            "dev_broker_port": server.port,
            "queue_name": "test-queue",
            "subscriptions": [{"topic": "test/>"}],
            "connect_retries": 3,
            "connect_retry_delay_ms": 200,
        }
        props.update(extra_props)
        return NetworkDevBroker(props)

    def test_publish_and_receive_message(self, server):
        """Core behavior: a sender publishes a message and a subscriber receives it
        with correct topic, payload, and user properties."""
        receiver = self._make_client(server, client_name="receiver")
        sender = self._make_client(server, client_name="sender", subscriptions=[])
        receiver.connect()
        sender.connect()

        try:
            sender.send_message("test/hello", {"data": 42}, {"prop": "val"})

            msg = receiver.receive_message(3000, "test-queue")
            assert msg is not None
            assert msg["topic"] == "test/hello"
            assert msg["payload"] == {"data": 42}
            assert msg["user_properties"] == {"prop": "val"}
        finally:
            sender.disconnect()
            receiver.disconnect()

    def test_receive_returns_none_on_timeout(self, server):
        """Receive should return None when no messages arrive within the timeout."""
        client = self._make_client(server)
        client.connect()
        try:
            assert client.receive_message(200, "test-queue") is None
        finally:
            client.disconnect()

    def test_dynamic_subscribe_enables_delivery(self, server):
        """A client that subscribes after connecting should receive matching messages."""
        receiver = self._make_client(server, client_name="dyn-recv", subscriptions=[])
        sender = self._make_client(server, client_name="dyn-send", subscriptions=[])
        receiver.connect()
        sender.connect()

        try:
            receiver.add_topic_to_queue("dynamic/>", "test-queue")
            sender.send_message("dynamic/topic", "hello")

            msg = receiver.receive_message(3000, "test-queue")
            assert msg is not None
            assert msg["topic"] == "dynamic/topic"
            assert msg["payload"] == "hello"
        finally:
            sender.disconnect()
            receiver.disconnect()

    def test_unsubscribe_stops_delivery(self, server):
        """After unsubscribing, a client should no longer receive messages on that topic."""
        receiver = self._make_client(server, client_name="unsub-recv")
        sender = self._make_client(server, client_name="unsub-send", subscriptions=[])
        receiver.connect()
        sender.connect()

        try:
            receiver.remove_topic_from_queue("test/>", "test-queue")
            sender.send_message("test/foo", "bar")

            assert receiver.receive_message(300, "test-queue") is None
        finally:
            sender.disconnect()
            receiver.disconnect()

    def test_wildcard_routing_single_level(self, server):
        """Single-level wildcard (*) should match exactly one topic level."""
        receiver = self._make_client(
            server, client_name="wc-recv",
            subscriptions=[{"topic": "level1/*/level3"}],
        )
        sender = self._make_client(server, client_name="wc-send", subscriptions=[])
        receiver.connect()
        sender.connect()

        try:
            # Should match: one level between level1 and level3
            sender.send_message("level1/anything/level3", "match")
            msg = receiver.receive_message(3000, "test-queue")
            assert msg is not None
            assert msg["payload"] == "match"

            # Should NOT match: two levels in wildcard position
            sender.send_message("level1/a/b/level3", "nomatch")
            assert receiver.receive_message(300, "test-queue") is None
        finally:
            sender.disconnect()
            receiver.disconnect()

    def test_bytes_payload_decoded_for_transport(self, server):
        """Bytes payload (as produced by BrokerOutput) should be decoded to
        JSON-serializable form for network transport."""
        receiver = self._make_client(server, client_name="bytes-recv")
        sender = self._make_client(server, client_name="bytes-send", subscriptions=[])
        receiver.connect()
        sender.connect()

        try:
            payload = json.dumps({"key": "value"}).encode("utf-8")
            sender.send_message("test/bytes", payload)

            msg = receiver.receive_message(3000, "test-queue")
            assert msg is not None
            assert msg["payload"] == {"key": "value"}
        finally:
            sender.disconnect()
            receiver.disconnect()

    def test_send_message_invokes_callback(self, server):
        """The user_context callback should be invoked after a successful publish."""
        client = self._make_client(server, client_name="cb-client", subscriptions=[])
        client.connect()

        try:
            called = {}

            def callback(ctx):
                called["done"] = True

            client.send_message("test/cb", "data", user_context={"callback": callback})
            assert called.get("done") is True
        finally:
            client.disconnect()

    def test_connect_failure_exhausts_retries(self):
        """Client should raise after exhausting connect retries to an unreachable server."""
        client = NetworkDevBroker({
            "dev_broker_host": "127.0.0.1",
            "dev_broker_port": 1,
            "connect_retries": 2,
            "connect_retry_delay_ms": 100,
        })
        with pytest.raises((ConnectionRefusedError, OSError)):
            client.connect()

    def test_send_when_disconnected_raises(self):
        """Sending on a client that was never connected should raise after reconnect fails."""
        client = NetworkDevBroker({
            "dev_broker_host": "127.0.0.1",
            "dev_broker_port": 1,
            "connect_retries": 1,
            "connect_retry_delay_ms": 100,
        })
        with pytest.raises(RuntimeError, match="Not connected"):
            client.send_message("test/topic", "payload")

    def test_receive_when_disconnected_returns_none(self):
        """Receiving on a disconnected client should return None (not raise)."""
        client = NetworkDevBroker({
            "dev_broker_host": "127.0.0.1",
            "dev_broker_port": 1,
            "connect_retries": 1,
            "connect_retry_delay_ms": 100,
        })
        assert client.receive_message(100, "q") is None

    def test_multiple_subscribers_all_receive(self, server):
        """When two clients subscribe to the same topic, both should receive the message."""
        recv1 = self._make_client(server, client_name="multi-recv1")
        recv2 = self._make_client(server, client_name="multi-recv2")
        sender = self._make_client(server, client_name="multi-send", subscriptions=[])
        recv1.connect()
        recv2.connect()
        sender.connect()

        try:
            sender.send_message("test/multi", {"fan": "out"})

            msg1 = recv1.receive_message(3000, "test-queue")
            msg2 = recv2.receive_message(3000, "test-queue")
            assert msg1 is not None
            assert msg2 is not None
            assert msg1["payload"] == {"fan": "out"}
            assert msg2["payload"] == {"fan": "out"}
        finally:
            sender.disconnect()
            recv1.disconnect()
            recv2.disconnect()

    def test_disconnect_and_reconnect_preserves_subscriptions(self, server):
        """After reconnecting, dynamically-added subscriptions should be
        re-established and the client should receive messages again."""
        receiver = self._make_client(server, client_name="reconn-recv", subscriptions=[])
        sender = self._make_client(server, client_name="reconn-send", subscriptions=[])
        receiver.connect()
        sender.connect()

        try:
            # Add a dynamic subscription and verify it works
            receiver.add_topic_to_queue("reconn/>", "test-queue")
            sender.send_message("reconn/before", "one")
            msg = receiver.receive_message(3000, "test-queue")
            assert msg is not None
            assert msg["payload"] == "one"

            # Simulate disconnect + reconnect
            receiver.disconnect()
            receiver._shutdown.clear()  # Reset so we can reconnect
            receiver._connected = False
            receiver.connect()

            # The dynamic subscription should have been re-established
            sender.send_message("reconn/after", "two")
            msg = receiver.receive_message(3000, "test-queue")
            assert msg is not None
            assert msg["payload"] == "two"
        finally:
            sender.disconnect()
            receiver.disconnect()

    def test_shutdown_interrupts_connect_retry(self):
        """Calling disconnect (setting the shutdown event) should interrupt
        the connect retry loop instead of waiting for all retries."""
        import time as _time

        client = NetworkDevBroker({
            "dev_broker_host": "127.0.0.1",
            "dev_broker_port": 1,
            "connect_retries": 0,  # retry forever
            "connect_retry_delay_ms": 5000,
        })

        import threading as _threading
        errors = []

        def try_connect():
            try:
                client.connect()
            except ConnectionError:
                errors.append("interrupted")

        t = _threading.Thread(target=try_connect)
        t.start()
        _time.sleep(0.5)  # Let the first attempt fail and start sleeping
        client._shutdown.set()  # Signal shutdown
        t.join(timeout=3)
        assert not t.is_alive(), "Connect retry loop was not interrupted by shutdown"
        assert len(errors) == 1


# ── Topic Matching / Regex Escaping ────────────────────────────────────


class TestTopicMatching:
    """Verify that topic subscription patterns handle metacharacters correctly."""

    def test_literal_dot_does_not_match_any_char(self):
        """A dot in a topic segment should match only a literal dot,
        not act as a regex wildcard."""
        regex = subscription_to_regex("sensor.1/temperature")
        assert topic_matches(regex, "sensor.1/temperature") is True
        assert topic_matches(regex, "sensorX1/temperature") is False

    def test_literal_plus_in_topic(self):
        """A plus sign in a topic segment should be treated as literal."""
        regex = subscription_to_regex("a+b/c")
        assert topic_matches(regex, "a+b/c") is True
        assert topic_matches(regex, "ab/c") is False

    def test_multi_level_wildcard_at_end(self):
        """The > wildcard should match one or more trailing levels."""
        regex = subscription_to_regex("a/b/>")
        assert topic_matches(regex, "a/b/c") is True
        assert topic_matches(regex, "a/b/c/d/e") is True
        assert topic_matches(regex, "a/b") is False
