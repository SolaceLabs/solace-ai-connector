"""Tests for TimerManager, including the deadlock fix for enqueue-under-lock."""

import queue
import threading
import time

from solace_ai_connector.flow.timer_manager import TimerManager
from solace_ai_connector.common.event import EventType


def _stop_timer_manager(tm):
    tm.stop_signal.set()
    tm.event.set()
    tm.thread.join(timeout=2)
    assert not tm.thread.is_alive()


class FakeComponent:
    """A minimal stand-in for a SAC component with an input queue."""

    def __init__(self, maxsize=5):
        self.input_queue = queue.Queue(maxsize=maxsize)
        self.stop_signal = threading.Event()

    def enqueue(self, event):
        while not self.stop_signal.is_set():
            try:
                self.input_queue.put(event, timeout=1)
                return
            except queue.Full:
                pass


class TestTimerManagerBasics:

    def test_single_timer_fires(self):
        stop = threading.Event()
        tm = TimerManager(stop)
        comp = FakeComponent(maxsize=10)

        try:
            tm.add_timer(50, comp, "t1")
            time.sleep(0.2)
            assert not comp.input_queue.empty()
            event = comp.input_queue.get_nowait()
            assert event.event_type == EventType.TIMER
            assert event.data["timer_id"] == "t1"
        finally:
            _stop_timer_manager(tm)

    def test_recurring_timer_fires_multiple_times(self):
        stop = threading.Event()
        tm = TimerManager(stop)
        comp = FakeComponent(maxsize=50)

        try:
            tm.add_timer(50, comp, "recurring", interval_ms=100)
            time.sleep(0.6)
            assert comp.input_queue.qsize() >= 4
        finally:
            _stop_timer_manager(tm)

    def test_cancel_timer_prevents_firing(self):
        stop = threading.Event()
        tm = TimerManager(stop)
        comp = FakeComponent(maxsize=10)

        try:
            tm.add_timer(200, comp, "cancel_me")
            tm.cancel_timer(comp, "cancel_me")
            time.sleep(0.4)
            assert comp.input_queue.empty()
        finally:
            _stop_timer_manager(tm)

    def test_timer_payload_delivered(self):
        stop = threading.Event()
        tm = TimerManager(stop)
        comp = FakeComponent(maxsize=10)

        try:
            tm.add_timer(50, comp, "with_payload", payload={"key": "value"})
            time.sleep(0.2)
            event = comp.input_queue.get_nowait()
            assert event.data["payload"] == {"key": "value"}
        finally:
            _stop_timer_manager(tm)


class TestTimerManagerDeadlockFix:
    """Verify that a full component queue does not block add_timer or starve other timers.

    The original bug: TimerManager.run() called component.enqueue() while
    holding self.lock.  When the component queue was full (because component
    threads had not started yet), enqueue() blocked indefinitely.  Any
    subsequent add_timer() call also tried to acquire self.lock, causing a
    deadlock.  Additionally, the blocked run() thread prevented timer events
    from being delivered to any other component (starvation).
    """

    def test_add_timer_does_not_deadlock_when_queue_full(self):
        """Reproduce the exact deadlock scenario from production.

        1. Create a component with a small queue (depth 2).
        2. Register a fast-firing recurring timer to fill that queue.
        3. Wait for the queue to fill (nobody is draining it).
        4. From another thread, call add_timer() — this must not hang.
        """
        stop = threading.Event()
        tm = TimerManager(stop)
        comp_a = FakeComponent(maxsize=2)
        comp_b = FakeComponent(maxsize=10)

        try:
            tm.add_timer(50, comp_a, "fast", interval_ms=50)

            time.sleep(0.3)
            assert comp_a.input_queue.full()

            # Release pressure from blocked dispatch threads before the
            # add_timer() call so GIL contention does not mask a real deadlock.
            comp_a.stop_signal.set()

            add_completed = threading.Event()

            def attempt_add():
                tm.add_timer(5000, comp_b, "second_timer")
                add_completed.set()

            t = threading.Thread(target=attempt_add, daemon=True)
            t.start()
            t.join(timeout=3)

            assert add_completed.is_set(), (
                "add_timer() deadlocked — the lock is held by the run() "
                "thread while it blocks on a full enqueue()"
            )
        finally:
            _stop_timer_manager(tm)

    def test_multiple_components_with_mixed_queue_states(self):
        """One component's full queue must not prevent timers for others.

        With the original bug, add_timer() itself would deadlock here because
        run() held self.lock while blocked inside enqueue().  The add_timer()
        call is therefore made from a worker thread so the test fails with a
        clear assertion rather than hanging indefinitely.
        """
        stop = threading.Event()
        tm = TimerManager(stop)
        blocked_comp = FakeComponent(maxsize=1)
        healthy_comp = FakeComponent(maxsize=50)

        try:
            tm.add_timer(50, blocked_comp, "blocker", interval_ms=50)
            time.sleep(0.3)
            assert blocked_comp.input_queue.full()

            # Release pressure from blocked dispatch threads before the
            # add_timer() call so GIL contention does not mask a real deadlock.
            blocked_comp.stop_signal.set()

            add_completed = threading.Event()

            def add_healthy():
                tm.add_timer(50, healthy_comp, "healthy")
                add_completed.set()

            t = threading.Thread(target=add_healthy, daemon=True)
            t.start()
            t.join(timeout=3)

            assert add_completed.is_set(), (
                "add_timer() deadlocked — run() is holding the lock while "
                "blocked on a full component queue"
            )

            time.sleep(0.3)

            assert not healthy_comp.input_queue.empty(), (
                "Healthy component should receive its timer event even when "
                "another component's queue is full"
            )
        finally:
            _stop_timer_manager(tm)

    def test_slow_enqueue_does_not_starve_other_timers(self):
        """A slow enqueue on one component must not prevent timers for another.

        This simulates the production scenario where broker connections are
        slow and component.run() has not started, so input queues fill up.
        Other components' timers must still be serviceable.

        With the original bug, add_timer() itself would deadlock here, so the
        call is made from a worker thread to produce a clean test failure.
        """
        stop = threading.Event()
        tm = TimerManager(stop)

        slow_comp = FakeComponent(maxsize=1)
        fast_comp = FakeComponent(maxsize=50)

        try:
            tm.add_timer(50, slow_comp, "slow", interval_ms=50)
            time.sleep(0.3)
            assert slow_comp.input_queue.full()

            # Release pressure from blocked dispatch threads before the
            # add_timer() call so GIL contention does not mask a real deadlock.
            slow_comp.stop_signal.set()

            add_completed = threading.Event()

            def add_fast():
                tm.add_timer(50, fast_comp, "fast")
                add_completed.set()

            t = threading.Thread(target=add_fast, daemon=True)
            t.start()
            t.join(timeout=3)

            assert add_completed.is_set(), (
                "add_timer() deadlocked — run() is holding the lock while "
                "blocked on a full component queue"
            )

            time.sleep(0.2)

            assert not fast_comp.input_queue.empty()
            event = fast_comp.input_queue.get_nowait()
            assert event.data["timer_id"] == "fast"
        finally:
            _stop_timer_manager(tm)
