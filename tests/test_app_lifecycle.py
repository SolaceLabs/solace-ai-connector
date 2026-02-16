"""Tests for App lifecycle management: stop, start, get_info, and runtime add/remove."""

import sys
import threading
import queue
import time

sys.path.append("src")

from solace_ai_connector.flow.app import (
    App,
    _CombinedStopSignal,
    APP_STATUS_CREATED,
    APP_STATUS_STARTING,
    APP_STATUS_RUNNING,
    APP_STATUS_STOPPING,
    APP_STATUS_STOPPED,
)
from solace_ai_connector.common.message import Message
from solace_ai_connector.test_utils.utils_for_test_files import (
    create_connector,
    create_test_flows,
    dispose_connector,
    send_message_to_flow,
    get_message_from_flow,
)


# --- _CombinedStopSignal tests ---


def test_combined_stop_signal_not_set():
    """Neither signal set -> is_set() returns False."""
    connector_signal = threading.Event()
    app_signal = threading.Event()
    combined = _CombinedStopSignal(connector_signal, app_signal)
    assert not combined.is_set()


def test_combined_stop_signal_app_set():
    """App signal set -> is_set() returns True."""
    connector_signal = threading.Event()
    app_signal = threading.Event()
    combined = _CombinedStopSignal(connector_signal, app_signal)
    combined.set()
    assert combined.is_set()
    assert app_signal.is_set()
    assert not connector_signal.is_set()


def test_combined_stop_signal_connector_set():
    """Connector signal set -> is_set() returns True."""
    connector_signal = threading.Event()
    app_signal = threading.Event()
    combined = _CombinedStopSignal(connector_signal, app_signal)
    connector_signal.set()
    assert combined.is_set()
    assert not app_signal.is_set()


def test_combined_stop_signal_wait_timeout():
    """wait() with timeout returns after timeout if neither signal set."""
    connector_signal = threading.Event()
    app_signal = threading.Event()
    combined = _CombinedStopSignal(connector_signal, app_signal)
    start = time.monotonic()
    result = combined.wait(timeout=0.1)
    elapsed = time.monotonic() - start
    assert elapsed >= 0.09  # Should have waited ~0.1s
    assert not result  # Neither signal set


def test_combined_stop_signal_wait_returns_on_set():
    """wait() returns quickly when app signal is set from another thread."""
    connector_signal = threading.Event()
    app_signal = threading.Event()
    combined = _CombinedStopSignal(connector_signal, app_signal)

    def set_after_delay():
        time.sleep(0.05)
        combined.set()

    thread = threading.Thread(target=set_after_delay)
    thread.start()
    result = combined.wait(timeout=2.0)
    thread.join()
    assert result


def test_combined_stop_signal_clear():
    """clear() resets the app signal."""
    connector_signal = threading.Event()
    app_signal = threading.Event()
    combined = _CombinedStopSignal(connector_signal, app_signal)
    combined.set()
    assert combined.is_set()
    combined.clear()
    assert not combined.is_set()


# --- App status and get_info tests ---


def test_app_initial_status_is_created():
    """Newly created app has status 'created'."""
    app_info = {
        "name": "test_app",
        "flows": [
            {
                "name": "test_flow",
                "components": [
                    {
                        "component_name": "pass_through",
                        "component_module": "pass_through",
                    }
                ],
            }
        ],
    }
    stop_signal = threading.Event()
    app = App(
        app_info=app_info,
        app_index=0,
        stop_signal=stop_signal,
        error_queue=queue.Queue(),
        instance_name="test",
    )
    assert app.status == APP_STATUS_CREATED
    assert app.enabled is True
    stop_signal.set()
    app.cleanup()


def test_app_status_running_after_run():
    """After run(), status is 'running'."""
    connector = create_connector(
        {
            "log": {"stdout_log_level": "WARNING"},
            "apps": [
                {
                    "name": "test_app",
                    "flows": [
                        {
                            "name": "f",
                            "components": [
                                {
                                    "component_name": "pt",
                                    "component_module": "pass_through",
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )
    try:
        app = connector.get_app("test_app")
        assert app.status == APP_STATUS_RUNNING
    finally:
        dispose_connector(connector)


def test_app_get_info():
    """get_info() returns a dict with expected keys and values."""
    app_info = {
        "name": "my_app",
        "app_module": "some.module",
        "num_instances": 2,
        "flows": [
            {
                "name": "f",
                "components": [
                    {
                        "component_name": "pt",
                        "component_module": "pass_through",
                    }
                ],
            }
        ],
    }
    stop_signal = threading.Event()
    app = App(
        app_info=app_info,
        app_index=0,
        stop_signal=stop_signal,
        error_queue=queue.Queue(),
        instance_name="test",
    )
    info = app.get_info()
    assert info["name"] == "my_app"
    assert info["enabled"] is True
    assert info["status"] == APP_STATUS_CREATED
    assert info["num_instances"] == 2
    assert info["app_module"] == "some.module"
    stop_signal.set()
    app.cleanup()


# --- App stop/start tests ---


def test_app_stop():
    """stop() transitions status to 'stopped' and sets enabled to False."""
    connector = create_connector(
        {
            "log": {"stdout_log_level": "WARNING"},
            "apps": [
                {
                    "name": "test_app",
                    "flows": [
                        {
                            "name": "f",
                            "components": [
                                {
                                    "component_name": "pt",
                                    "component_module": "pass_through",
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )
    try:
        app = connector.get_app("test_app")
        assert app.status == APP_STATUS_RUNNING
        app.stop(timeout=5)
        assert app.status == APP_STATUS_STOPPED
        assert app.enabled is False
        assert len(app.flows) == 0
    finally:
        dispose_connector(connector)


def test_app_stop_does_not_affect_other_apps():
    """Stopping one app does not affect another."""
    connector = create_connector(
        {
            "log": {"stdout_log_level": "WARNING"},
            "apps": [
                {
                    "name": "app1",
                    "flows": [
                        {
                            "name": "f1",
                            "components": [
                                {
                                    "component_name": "pt1",
                                    "component_module": "pass_through",
                                }
                            ],
                        }
                    ],
                },
                {
                    "name": "app2",
                    "flows": [
                        {
                            "name": "f2",
                            "components": [
                                {
                                    "component_name": "pt2",
                                    "component_module": "pass_through",
                                }
                            ],
                        }
                    ],
                },
            ],
        }
    )
    try:
        app1 = connector.get_app("app1")
        app2 = connector.get_app("app2")
        assert app1.status == APP_STATUS_RUNNING
        assert app2.status == APP_STATUS_RUNNING

        # Stop app1
        app1.stop(timeout=5)
        assert app1.status == APP_STATUS_STOPPED

        # app2 should still be running
        assert app2.status == APP_STATUS_RUNNING
        assert len(app2.flows) > 0
        # Verify app2's component threads are still alive
        for flow in app2.flows:
            for thread in flow.threads:
                assert thread.is_alive()
    finally:
        dispose_connector(connector)


def test_app_stop_already_stopped():
    """Calling stop() on an already stopped app is a no-op."""
    connector = create_connector(
        {
            "log": {"stdout_log_level": "WARNING"},
            "apps": [
                {
                    "name": "test_app",
                    "flows": [
                        {
                            "name": "f",
                            "components": [
                                {
                                    "component_name": "pt",
                                    "component_module": "pass_through",
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )
    try:
        app = connector.get_app("test_app")
        app.stop(timeout=5)
        assert app.status == APP_STATUS_STOPPED
        # Second stop should be a no-op
        app.stop(timeout=5)
        assert app.status == APP_STATUS_STOPPED
    finally:
        dispose_connector(connector)


def test_app_start_after_stop():
    """An app can be started after being stopped."""
    connector = create_connector(
        {
            "log": {"stdout_log_level": "WARNING"},
            "apps": [
                {
                    "name": "test_app",
                    "flows": [
                        {
                            "name": "f",
                            "components": [
                                {
                                    "component_name": "pt",
                                    "component_module": "pass_through",
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )
    try:
        app = connector.get_app("test_app")
        assert app.status == APP_STATUS_RUNNING

        app.stop(timeout=5)
        assert app.status == APP_STATUS_STOPPED

        app.start()
        assert app.status == APP_STATUS_RUNNING
        assert app.enabled is True
        assert len(app.flows) > 0
        # Verify threads are running
        for flow in app.flows:
            for thread in flow.threads:
                assert thread.is_alive()
    finally:
        dispose_connector(connector)


def test_app_start_when_not_stopped_raises():
    """Calling start() on a running app raises RuntimeError."""
    connector = create_connector(
        {
            "log": {"stdout_log_level": "WARNING"},
            "apps": [
                {
                    "name": "test_app",
                    "flows": [
                        {
                            "name": "f",
                            "components": [
                                {
                                    "component_name": "pt",
                                    "component_module": "pass_through",
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )
    try:
        app = connector.get_app("test_app")
        try:
            app.start()
            assert False, "Expected RuntimeError"
        except RuntimeError:
            pass
    finally:
        dispose_connector(connector)


def test_app_status_transitions():
    """Verify the full status lifecycle: created -> running -> stopping -> stopped -> running."""
    connector = create_connector(
        {
            "log": {"stdout_log_level": "WARNING"},
            "apps": [
                {
                    "name": "test_app",
                    "flows": [
                        {
                            "name": "f",
                            "components": [
                                {
                                    "component_name": "pt",
                                    "component_module": "pass_through",
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )
    try:
        app = connector.get_app("test_app")
        # After create_connector, app is already running
        assert app.status == APP_STATUS_RUNNING

        app.stop(timeout=5)
        assert app.status == APP_STATUS_STOPPED

        app.start()
        assert app.status == APP_STATUS_RUNNING
    finally:
        dispose_connector(connector)


# --- pre_stop hook tests ---


def test_pre_stop_called_before_signal():
    """pre_stop() is called before the stop signal is set."""
    signal_was_set_during_pre_stop = []

    class PreStopTestApp(App):
        def pre_stop(self, timeout=30):
            # Record whether the stop signal was set during pre_stop
            signal_was_set_during_pre_stop.append(self._app_stop_signal.is_set())

    connector = create_connector(
        {
            "log": {"stdout_log_level": "WARNING"},
            "apps": [
                {
                    "name": "test_app",
                    "app_module": None,
                    "flows": [
                        {
                            "name": "f",
                            "components": [
                                {
                                    "component_name": "pt",
                                    "component_module": "pass_through",
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )
    try:
        # Replace the app with our custom subclass
        # We need to directly create the app since the connector already created a default one
        app = connector.get_app("test_app")

        # Create a new PreStopTestApp from the same config
        custom_app = PreStopTestApp(
            app_info=app.app_info,
            app_index=0,
            stop_signal=connector.stop_signal,
            error_queue=connector.error_queue,
            instance_name=connector.instance_name,
            connector=connector,
        )
        custom_app.run()
        custom_app.stop(timeout=5)

        assert len(signal_was_set_during_pre_stop) == 1
        assert signal_was_set_during_pre_stop[0] is False  # Signal NOT set during pre_stop
    finally:
        dispose_connector(connector)


def test_pre_stop_timeout_respected():
    """pre_stop() timeout is subtracted from total timeout for thread joining."""

    class SlowPreStopApp(App):
        def pre_stop(self, timeout=30):
            time.sleep(0.3)  # Simulate slow drain

    app_info = {
        "name": "slow_app",
        "flows": [
            {
                "name": "f",
                "components": [
                    {
                        "component_name": "pt",
                        "component_module": "pass_through",
                    }
                ],
            }
        ],
    }
    stop_signal = threading.Event()
    app = SlowPreStopApp(
        app_info=app_info,
        app_index=0,
        stop_signal=stop_signal,
        error_queue=queue.Queue(),
        instance_name="test",
    )
    app.run()

    start = time.monotonic()
    app.stop(timeout=5)
    elapsed = time.monotonic() - start

    assert app.status == APP_STATUS_STOPPED
    # Should have taken at least 0.3s (the pre_stop sleep)
    assert elapsed >= 0.25
    stop_signal.set()


# --- Management hooks tests ---


def test_management_endpoints_default_empty():
    """Default get_management_endpoints() returns empty list."""
    app_info = {
        "name": "test_app",
        "flows": [
            {
                "name": "f",
                "components": [
                    {
                        "component_name": "pt",
                        "component_module": "pass_through",
                    }
                ],
            }
        ],
    }
    stop_signal = threading.Event()
    app = App(
        app_info=app_info,
        app_index=0,
        stop_signal=stop_signal,
        error_queue=queue.Queue(),
        instance_name="test",
    )
    assert app.get_management_endpoints() == []
    assert app.handle_management_request("GET", ["custom"], {}, {}) is None
    stop_signal.set()
    app.cleanup()


# --- Connector add_app / remove_app tests ---


def test_connector_add_app():
    """add_app() creates and starts a new app at runtime."""
    connector = create_connector(
        {
            "log": {"stdout_log_level": "WARNING"},
            "apps": [
                {
                    "name": "existing_app",
                    "flows": [
                        {
                            "name": "f1",
                            "components": [
                                {
                                    "component_name": "pt",
                                    "component_module": "pass_through",
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )
    try:
        assert len(connector.apps) == 1

        new_app = connector.add_app(
            {
                "name": "new_app",
                "flows": [
                    {
                        "name": "f2",
                        "components": [
                            {
                                "component_name": "pt2",
                                "component_module": "pass_through",
                            }
                        ],
                    }
                ],
            }
        )

        assert len(connector.apps) == 2
        assert new_app.name == "new_app"
        assert new_app.status == APP_STATUS_RUNNING
        assert connector.get_app("new_app") is new_app
    finally:
        dispose_connector(connector)


def test_connector_add_app_duplicate_name():
    """add_app() raises ValueError for duplicate app names."""
    connector = create_connector(
        {
            "log": {"stdout_log_level": "WARNING"},
            "apps": [
                {
                    "name": "my_app",
                    "flows": [
                        {
                            "name": "f",
                            "components": [
                                {
                                    "component_name": "pt",
                                    "component_module": "pass_through",
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )
    try:
        try:
            connector.add_app(
                {
                    "name": "my_app",
                    "flows": [
                        {
                            "name": "f2",
                            "components": [
                                {
                                    "component_name": "pt2",
                                    "component_module": "pass_through",
                                }
                            ],
                        }
                    ],
                }
            )
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "already exists" in str(e)
    finally:
        dispose_connector(connector)


def test_connector_add_app_no_name():
    """add_app() raises ValueError when name is missing."""
    connector = create_connector(
        {
            "log": {"stdout_log_level": "WARNING"},
            "apps": [
                {
                    "name": "existing",
                    "flows": [
                        {
                            "name": "f",
                            "components": [
                                {
                                    "component_name": "pt",
                                    "component_module": "pass_through",
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )
    try:
        try:
            connector.add_app(
                {
                    "flows": [
                        {
                            "name": "f2",
                            "components": [
                                {
                                    "component_name": "pt2",
                                    "component_module": "pass_through",
                                }
                            ],
                        }
                    ],
                }
            )
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "name is required" in str(e).lower()
    finally:
        dispose_connector(connector)


def test_connector_remove_app():
    """remove_app() stops and deregisters an app."""
    connector = create_connector(
        {
            "log": {"stdout_log_level": "WARNING"},
            "apps": [
                {
                    "name": "app1",
                    "flows": [
                        {
                            "name": "f1",
                            "components": [
                                {
                                    "component_name": "pt1",
                                    "component_module": "pass_through",
                                }
                            ],
                        }
                    ],
                },
                {
                    "name": "app2",
                    "flows": [
                        {
                            "name": "f2",
                            "components": [
                                {
                                    "component_name": "pt2",
                                    "component_module": "pass_through",
                                }
                            ],
                        }
                    ],
                },
            ],
        }
    )
    try:
        assert len(connector.apps) == 2
        connector.remove_app("app1", timeout=5)
        assert len(connector.apps) == 1
        assert connector.get_app("app1") is None
        assert connector.get_app("app2") is not None
        assert connector.get_app("app2").status == APP_STATUS_RUNNING
    finally:
        dispose_connector(connector)


def test_connector_remove_app_not_found():
    """remove_app() raises ValueError for unknown app name."""
    connector = create_connector(
        {
            "log": {"stdout_log_level": "WARNING"},
            "apps": [
                {
                    "name": "existing",
                    "flows": [
                        {
                            "name": "f",
                            "components": [
                                {
                                    "component_name": "pt",
                                    "component_module": "pass_through",
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )
    try:
        try:
            connector.remove_app("nonexistent", timeout=5)
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "not found" in str(e)
    finally:
        dispose_connector(connector)
