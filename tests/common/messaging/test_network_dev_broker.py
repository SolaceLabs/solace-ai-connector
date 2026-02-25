"""Tests for the network dev broker: protocol, server, and client."""

import asyncio
import json
import sys
import socket
import threading
import time

import pytest

sys.path.append("src")

from solace_ai_connector.common.messaging.dev_broker_protocol import (
    CMD_CONNECT,
    CMD_DISCONNECT,
    CMD_PUBLISH,
    CMD_RECEIVE,
    CMD_SUBSCRIBE,
    CMD_UNSUBSCRIBE,
    CMD_ACK,
    STATUS_OK,
    STATUS_ERROR,
    STATUS_TIMEOUT,
    ERR_NOT_CONNECTED,
    ERR_INVALID_COMMAND,
    ConnectCommand,
    SubscribeCommand,
    UnsubscribeCommand,
    PublishCommand,
    ReceiveCommand,
    AckCommand,
    DisconnectCommand,
    Response,
    BrokerMessage,
    encode_command,
    encode_response,
    decode_command,
    decode_response,
)
from solace_ai_connector.common.messaging.dev_broker_server import (
    DevBrokerServer,
    ClientSession,
    start_server_in_thread,
)
from solace_ai_connector.common.messaging.network_dev_broker import (
    NetworkDevBroker,
    NetworkConnectionStatus,
)


# ── Protocol Tests ──────────────────────────────────────────────────────


class TestProtocolDataclasses:
    """Tests for the protocol dataclass definitions."""

    def test_connect_command_defaults(self):
        cmd = ConnectCommand()
        assert cmd.cmd == CMD_CONNECT
        assert cmd.client_id == ""
        assert cmd.queue_name == ""
        assert cmd.subscriptions == []

    def test_connect_command_with_values(self):
        cmd = ConnectCommand(client_id="c1", queue_name="q1", subscriptions=["t/>"])
        assert cmd.client_id == "c1"
        assert cmd.queue_name == "q1"
        assert cmd.subscriptions == ["t/>"]

    def test_subscribe_command(self):
        cmd = SubscribeCommand(topic_pattern="test/*")
        assert cmd.cmd == CMD_SUBSCRIBE
        assert cmd.topic_pattern == "test/*"

    def test_unsubscribe_command(self):
        cmd = UnsubscribeCommand(topic_pattern="test/*")
        assert cmd.cmd == CMD_UNSUBSCRIBE
        assert cmd.topic_pattern == "test/*"

    def test_publish_command(self):
        cmd = PublishCommand(topic="a/b", payload={"key": "val"}, user_properties={"p": "1"})
        assert cmd.cmd == CMD_PUBLISH
        assert cmd.topic == "a/b"
        assert cmd.payload == {"key": "val"}
        assert cmd.user_properties == {"p": "1"}

    def test_receive_command_default_timeout(self):
        cmd = ReceiveCommand()
        assert cmd.cmd == CMD_RECEIVE
        assert cmd.timeout_ms == 5000

    def test_ack_command(self):
        cmd = AckCommand(message_id="msg-1")
        assert cmd.cmd == CMD_ACK
        assert cmd.message_id == "msg-1"

    def test_disconnect_command(self):
        cmd = DisconnectCommand()
        assert cmd.cmd == CMD_DISCONNECT


class TestResponse:
    """Tests for the Response dataclass."""

    def test_ok_response(self):
        r = Response.ok(client_id="c1")
        assert r.status == STATUS_OK
        assert r.client_id == "c1"
        assert r.error_code is None

    def test_error_response(self):
        r = Response.error("SOME_CODE", "something went wrong")
        assert r.status == STATUS_ERROR
        assert r.error_code == "SOME_CODE"
        assert r.error_message == "something went wrong"

    def test_timeout_response(self):
        r = Response.timeout()
        assert r.status == STATUS_TIMEOUT


class TestBrokerMessage:
    """Tests for BrokerMessage serialization."""

    def test_to_dict(self):
        msg = BrokerMessage(message_id="m1", topic="t/1", payload="hello", user_properties={"k": "v"})
        d = msg.to_dict()
        assert d == {
            "message_id": "m1",
            "topic": "t/1",
            "payload": "hello",
            "user_properties": {"k": "v"},
        }

    def test_from_dict(self):
        data = {"message_id": "m2", "topic": "t/2", "payload": 42, "user_properties": {}}
        msg = BrokerMessage.from_dict(data)
        assert msg.message_id == "m2"
        assert msg.topic == "t/2"
        assert msg.payload == 42

    def test_from_dict_missing_fields(self):
        msg = BrokerMessage.from_dict({})
        assert msg.topic == ""
        assert msg.payload is None
        assert msg.user_properties == {}

    def test_auto_generated_message_id(self):
        msg = BrokerMessage()
        assert msg.message_id  # non-empty UUID


class TestProtocolEncodeDecode:
    """Tests for encode/decode helpers."""

    def test_encode_decode_command(self):
        cmd = ConnectCommand(client_id="c1", queue_name="q1", subscriptions=["a/b"])
        encoded = encode_command(cmd)
        assert encoded.endswith(b"\n")
        decoded = decode_command(encoded)
        assert decoded["cmd"] == CMD_CONNECT
        assert decoded["client_id"] == "c1"

    def test_encode_decode_response(self):
        resp = Response.ok(client_id="c1")
        encoded = encode_response(resp)
        assert encoded.endswith(b"\n")
        decoded = decode_response(encoded)
        assert decoded.status == STATUS_OK
        assert decoded.client_id == "c1"
        # None fields should be filtered out
        assert b"error_code" not in encoded

    def test_decode_response_missing_fields(self):
        raw = b'{"status": "OK"}\n'
        resp = decode_response(raw)
        assert resp.status == STATUS_OK
        assert resp.error_code is None
        assert resp.message is None


# ── Server Tests ────────────────────────────────────────────────────────


class TestDevBrokerServerTopicMatching:
    """Tests for the server's static helpers."""

    def test_topic_matches_exact(self):
        regex = DevBrokerServer._subscription_to_regex("test/topic")
        assert DevBrokerServer._topic_matches(regex, "test/topic")
        assert not DevBrokerServer._topic_matches(regex, "test/other")

    def test_topic_matches_single_wildcard(self):
        regex = DevBrokerServer._subscription_to_regex("test/*")
        assert DevBrokerServer._topic_matches(regex, "test/foo")
        assert not DevBrokerServer._topic_matches(regex, "test/foo/bar")

    def test_topic_matches_multi_wildcard(self):
        regex = DevBrokerServer._subscription_to_regex("test/>")
        assert DevBrokerServer._topic_matches(regex, "test/foo")
        assert DevBrokerServer._topic_matches(regex, "test/foo/bar/baz")

    def test_subscription_to_regex(self):
        assert DevBrokerServer._subscription_to_regex("a/b") == "a/b"
        assert DevBrokerServer._subscription_to_regex("a/*") == "a/[^/]+"
        assert DevBrokerServer._subscription_to_regex("a/>") == "a/.*"


class TestDevBrokerServerLifecycle:
    """Tests for server start/stop."""

    @pytest.fixture
    def event_loop(self):
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()

    def test_start_stop(self, event_loop):
        server = DevBrokerServer(host="127.0.0.1", port=0)

        async def run():
            port = await server.start()
            assert port > 0
            assert server.is_running
            await server.stop()
            assert not server.is_running

        event_loop.run_until_complete(run())

    def test_context_manager(self, event_loop):
        async def run():
            async with DevBrokerServer(host="127.0.0.1", port=0) as server:
                assert server.is_running
                assert server.port > 0
            assert not server.is_running

        event_loop.run_until_complete(run())

    def test_double_start(self, event_loop):
        server = DevBrokerServer(host="127.0.0.1", port=0)

        async def run():
            port1 = await server.start()
            port2 = await server.start()  # should be no-op
            assert port1 == port2
            await server.stop()

        event_loop.run_until_complete(run())


class TestDevBrokerServerProtocol:
    """Tests for the server protocol handling via raw TCP."""

    @pytest.fixture
    def server_and_port(self):
        """Start a server in a background thread and yield the port."""
        server = start_server_in_thread(host="127.0.0.1", port=0)
        yield server, server.port
        # Stop the server
        if server._loop and server._loop.is_running():
            asyncio.run_coroutine_threadsafe(server.stop(), server._loop).result(timeout=5)

    def _connect_raw(self, port):
        """Create a raw TCP connection and return (socket, file)."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect(("127.0.0.1", port))
        return sock, sock.makefile("rb")

    def _send_recv(self, sock, sock_file, cmd_dict):
        """Send a JSON command and receive the JSON response."""
        data = (json.dumps(cmd_dict) + "\n").encode("utf-8")
        sock.sendall(data)
        line = sock_file.readline()
        return json.loads(line.decode("utf-8"))

    def test_connect_command(self, server_and_port):
        server, port = server_and_port
        sock, sf = self._connect_raw(port)
        try:
            resp = self._send_recv(sock, sf, {
                "cmd": CMD_CONNECT,
                "client_id": "test-client",
                "queue_name": "q1",
                "subscriptions": ["test/>"],
            })
            assert resp["status"] == STATUS_OK
            assert resp["client_id"] == "test-client"
        finally:
            sock.close()

    def test_command_before_connect_returns_error(self, server_and_port):
        server, port = server_and_port
        sock, sf = self._connect_raw(port)
        try:
            resp = self._send_recv(sock, sf, {"cmd": CMD_SUBSCRIBE, "topic_pattern": "a/b"})
            assert resp["status"] == STATUS_ERROR
            assert resp["error_code"] == ERR_NOT_CONNECTED
        finally:
            sock.close()

    def test_unknown_command(self, server_and_port):
        server, port = server_and_port
        sock, sf = self._connect_raw(port)
        try:
            # Connect first
            self._send_recv(sock, sf, {"cmd": CMD_CONNECT, "client_id": "c1"})
            # Send unknown command
            resp = self._send_recv(sock, sf, {"cmd": "FOOBAR"})
            assert resp["status"] == STATUS_ERROR
            assert resp["error_code"] == ERR_INVALID_COMMAND
        finally:
            sock.close()

    def test_invalid_json(self, server_and_port):
        server, port = server_and_port
        sock, sf = self._connect_raw(port)
        try:
            sock.sendall(b"not json\n")
            line = sf.readline()
            resp = json.loads(line.decode("utf-8"))
            assert resp["status"] == STATUS_ERROR
            assert resp["error_code"] == ERR_INVALID_COMMAND
        finally:
            sock.close()

    def test_subscribe_unsubscribe(self, server_and_port):
        server, port = server_and_port
        sock, sf = self._connect_raw(port)
        try:
            self._send_recv(sock, sf, {"cmd": CMD_CONNECT, "client_id": "c1"})

            resp = self._send_recv(sock, sf, {"cmd": CMD_SUBSCRIBE, "topic_pattern": "a/b"})
            assert resp["status"] == STATUS_OK

            resp = self._send_recv(sock, sf, {"cmd": CMD_UNSUBSCRIBE, "topic_pattern": "a/b"})
            assert resp["status"] == STATUS_OK
        finally:
            sock.close()

    def test_subscribe_missing_pattern(self, server_and_port):
        server, port = server_and_port
        sock, sf = self._connect_raw(port)
        try:
            self._send_recv(sock, sf, {"cmd": CMD_CONNECT, "client_id": "c1"})
            resp = self._send_recv(sock, sf, {"cmd": CMD_SUBSCRIBE, "topic_pattern": ""})
            assert resp["status"] == STATUS_ERROR
        finally:
            sock.close()

    def test_publish_missing_topic(self, server_and_port):
        server, port = server_and_port
        sock, sf = self._connect_raw(port)
        try:
            self._send_recv(sock, sf, {"cmd": CMD_CONNECT, "client_id": "c1"})
            resp = self._send_recv(sock, sf, {"cmd": CMD_PUBLISH, "topic": "", "payload": "x"})
            assert resp["status"] == STATUS_ERROR
        finally:
            sock.close()

    def test_receive_timeout(self, server_and_port):
        server, port = server_and_port
        sock, sf = self._connect_raw(port)
        try:
            self._send_recv(sock, sf, {"cmd": CMD_CONNECT, "client_id": "c1", "subscriptions": ["a/>"]})
            sock.settimeout(10)
            resp = self._send_recv(sock, sf, {"cmd": CMD_RECEIVE, "timeout_ms": 200})
            assert resp["status"] == STATUS_TIMEOUT
        finally:
            sock.close()

    def test_publish_and_receive_between_clients(self, server_and_port):
        """Two clients: one subscribes and receives, the other publishes."""
        server, port = server_and_port

        # Client 1: subscriber
        sock1, sf1 = self._connect_raw(port)
        self._send_recv(sock1, sf1, {
            "cmd": CMD_CONNECT,
            "client_id": "subscriber",
            "subscriptions": ["test/>"],
        })

        # Client 2: publisher
        sock2, sf2 = self._connect_raw(port)
        self._send_recv(sock2, sf2, {"cmd": CMD_CONNECT, "client_id": "publisher"})

        try:
            # Publish
            resp = self._send_recv(sock2, sf2, {
                "cmd": CMD_PUBLISH,
                "topic": "test/hello",
                "payload": {"msg": "world"},
                "user_properties": {"key": "val"},
            })
            assert resp["status"] == STATUS_OK

            # Receive on subscriber
            sock1.settimeout(10)
            resp = self._send_recv(sock1, sf1, {"cmd": CMD_RECEIVE, "timeout_ms": 3000})
            assert resp["status"] == STATUS_OK
            assert resp["message"]["topic"] == "test/hello"
            assert resp["message"]["payload"] == {"msg": "world"}
            assert resp["message"]["user_properties"] == {"key": "val"}
        finally:
            sock1.close()
            sock2.close()

    def test_disconnect_command(self, server_and_port):
        server, port = server_and_port
        sock, sf = self._connect_raw(port)
        try:
            self._send_recv(sock, sf, {"cmd": CMD_CONNECT, "client_id": "c1"})
            resp = self._send_recv(sock, sf, {"cmd": CMD_DISCONNECT})
            assert resp["status"] == STATUS_OK
        finally:
            sock.close()

    def test_ack_command(self, server_and_port):
        server, port = server_and_port
        sock, sf = self._connect_raw(port)
        try:
            self._send_recv(sock, sf, {"cmd": CMD_CONNECT, "client_id": "c1"})
            resp = self._send_recv(sock, sf, {"cmd": CMD_ACK, "message_id": "m1"})
            assert resp["status"] == STATUS_OK
        finally:
            sock.close()

    def test_publisher_does_not_receive_own_message(self, server_and_port):
        """A client that publishes should not receive its own message."""
        server, port = server_and_port
        sock, sf = self._connect_raw(port)
        try:
            self._send_recv(sock, sf, {
                "cmd": CMD_CONNECT,
                "client_id": "self-pub",
                "subscriptions": ["test/>"],
            })
            # Publish to a topic we're subscribed to
            self._send_recv(sock, sf, {
                "cmd": CMD_PUBLISH,
                "topic": "test/echo",
                "payload": "hi",
            })
            # Should timeout since there's nothing in queue
            sock.settimeout(10)
            resp = self._send_recv(sock, sf, {"cmd": CMD_RECEIVE, "timeout_ms": 300})
            assert resp["status"] == STATUS_TIMEOUT
        finally:
            sock.close()

    def test_wildcard_subscription_routing(self, server_and_port):
        """Single-level wildcard should only match one level."""
        server, port = server_and_port

        sock1, sf1 = self._connect_raw(port)
        self._send_recv(sock1, sf1, {
            "cmd": CMD_CONNECT,
            "client_id": "sub-wc",
            "subscriptions": ["level1/*/level3"],
        })

        sock2, sf2 = self._connect_raw(port)
        self._send_recv(sock2, sf2, {"cmd": CMD_CONNECT, "client_id": "pub-wc"})

        try:
            # Should match
            self._send_recv(sock2, sf2, {
                "cmd": CMD_PUBLISH,
                "topic": "level1/anything/level3",
                "payload": "match",
            })

            sock1.settimeout(10)
            resp = self._send_recv(sock1, sf1, {"cmd": CMD_RECEIVE, "timeout_ms": 2000})
            assert resp["status"] == STATUS_OK
            assert resp["message"]["payload"] == "match"

            # Should NOT match (two levels in wildcard position)
            self._send_recv(sock2, sf2, {
                "cmd": CMD_PUBLISH,
                "topic": "level1/a/b/level3",
                "payload": "nomatch",
            })

            resp = self._send_recv(sock1, sf1, {"cmd": CMD_RECEIVE, "timeout_ms": 300})
            assert resp["status"] == STATUS_TIMEOUT
        finally:
            sock1.close()
            sock2.close()


# ── NetworkDevBroker Client Tests ───────────────────────────────────────


class TestNetworkDevBroker:
    """Tests for the NetworkDevBroker client against a real server."""

    @pytest.fixture
    def server(self):
        """Start a server in a background thread."""
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

    def test_connect_disconnect(self, server):
        client = self._make_client(server)
        client.connect()
        assert client.get_connection_status() == NetworkConnectionStatus.CONNECTED
        client.disconnect()
        assert client.get_connection_status() == NetworkConnectionStatus.DISCONNECTED

    def test_connect_already_connected(self, server):
        client = self._make_client(server)
        client.connect()
        # Should not raise
        client.connect()
        client.disconnect()

    def test_send_and_receive(self, server):
        """One client publishes, another receives."""
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

    def test_receive_timeout(self, server):
        client = self._make_client(server)
        client.connect()
        try:
            msg = client.receive_message(200, "test-queue")
            assert msg is None
        finally:
            client.disconnect()

    def test_subscribe_after_connect(self, server):
        """Dynamic subscription after initial connect."""
        receiver = self._make_client(server, client_name="dyn-recv", subscriptions=[])
        sender = self._make_client(server, client_name="dyn-send", subscriptions=[])
        receiver.connect()
        sender.connect()

        try:
            # Subscribe dynamically
            result = receiver.add_topic_to_queue("dynamic/>", "test-queue")
            assert result is True

            sender.send_message("dynamic/topic", "hello")

            msg = receiver.receive_message(3000, "test-queue")
            assert msg is not None
            assert msg["topic"] == "dynamic/topic"
            assert msg["payload"] == "hello"
        finally:
            sender.disconnect()
            receiver.disconnect()

    def test_unsubscribe(self, server):
        receiver = self._make_client(server, client_name="unsub-recv")
        sender = self._make_client(server, client_name="unsub-send", subscriptions=[])
        receiver.connect()
        sender.connect()

        try:
            # Unsubscribe from the initial subscription
            result = receiver.remove_topic_from_queue("test/>", "test-queue")
            assert result is True

            sender.send_message("test/foo", "bar")

            msg = receiver.receive_message(300, "test-queue")
            assert msg is None  # should not receive after unsubscribe
        finally:
            sender.disconnect()
            receiver.disconnect()

    def test_ack_nack_no_error(self, server):
        """ack/nack should not raise."""
        client = self._make_client(server)
        client.connect()
        try:
            client.ack_message(None)
            from solace_ai_connector.common import Message_NACK_Outcome
            client.nack_message(None, Message_NACK_Outcome.FAILED)
        finally:
            client.disconnect()

    def test_send_bytes_payload(self, server):
        """Bytes payload should be decoded for JSON transport."""
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

    def test_send_message_with_callback(self, server):
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

    def test_connect_failure_with_retries(self):
        """Client should raise after exhausting retries to an unreachable server."""
        client = NetworkDevBroker({
            "dev_broker_host": "127.0.0.1",
            "dev_broker_port": 1,  # unlikely to be open
            "connect_retries": 2,
            "connect_retry_delay_ms": 100,
        })
        with pytest.raises((ConnectionRefusedError, OSError)):
            client.connect()

    def test_send_when_not_connected_raises(self):
        client = NetworkDevBroker({
            "dev_broker_host": "127.0.0.1",
            "dev_broker_port": 1,
            "connect_retries": 1,
            "connect_retry_delay_ms": 100,
        })
        with pytest.raises(RuntimeError, match="Not connected"):
            client.send_message("test/topic", "payload")

    def test_receive_when_not_connected(self):
        client = NetworkDevBroker({
            "dev_broker_host": "127.0.0.1",
            "dev_broker_port": 1,
            "connect_retries": 1,
            "connect_retry_delay_ms": 100,
        })
        msg = client.receive_message(100, "q")
        assert msg is None

    def test_add_topic_subscription(self, server):
        client = self._make_client(server, client_name="add-topic-sub")
        client.connect()
        try:
            result = client.add_topic_subscription("new/topic/>")
            assert result is True
        finally:
            client.disconnect()

    def test_remove_topic_subscription(self, server):
        client = self._make_client(server, client_name="rm-topic-sub")
        client.connect()
        try:
            client.add_topic_subscription("new/topic/>")
            result = client.remove_topic_subscription("new/topic/>")
            assert result is True
        finally:
            client.disconnect()

    def test_dynamic_subscriptions_tracked(self, server):
        """Dynamic subscriptions should be tracked in _dynamic_subscriptions."""
        client = self._make_client(server, client_name="track-subs")
        client.connect()
        try:
            client.add_topic_to_queue("tracked/topic", "test-queue")
            assert "tracked/topic" in client._dynamic_subscriptions

            client.remove_topic_from_queue("tracked/topic", "test-queue")
            assert "tracked/topic" not in client._dynamic_subscriptions
        finally:
            client.disconnect()


# ── start_server_in_thread Tests ────────────────────────────────────────


class TestStartServerInThread:

    def test_start_and_connect(self):
        server = start_server_in_thread(host="127.0.0.1", port=0)
        assert server.is_running
        assert server.port > 0

        # Verify we can actually TCP connect
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        try:
            sock.connect(("127.0.0.1", server.port))
        finally:
            sock.close()
            asyncio.run_coroutine_threadsafe(server.stop(), server._loop).result(timeout=5)
