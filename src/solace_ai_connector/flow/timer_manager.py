import threading
import time
import heapq
from ..common.event import Event, EventType
from ..common.log import log


class Timer:

    def __init__(self, expiration, interval, component, timer_id, payload=None):
        self.expiration = expiration
        self.interval = interval
        self.component = component
        self.timer_id = timer_id
        self.payload = payload

    def __lt__(self, other):
        return self.expiration < other.expiration


class TimerManager:

    def __init__(self, stop_signal):
        self.timers = []
        self.lock = threading.Lock()
        self.stop_signal = stop_signal
        self.event = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def add_timer(self, delay_ms, component, timer_id, interval_ms=None, payload=None):
        with self.lock:
            expiration = time.time() + (delay_ms / 1000.0)
            timer = Timer(expiration, interval_ms, component, timer_id, payload)
            heapq.heappush(self.timers, timer)
            self.event.set()

    def cancel_timer(self, component, timer_id):
        with self.lock:
            self.timers = [
                t
                for t in self.timers
                if not (t.component == component and t.timer_id == timer_id)
            ]
            heapq.heapify(self.timers)

    def run(self):
        while not self.stop_signal.is_set():
            with self.lock:
                if not self.timers:
                    next_expiration = None
                else:
                    next_expiration = self.timers[0].expiration

            if next_expiration is None:
                self.event.wait()
            else:
                wait_time = max(0, next_expiration - time.time())
                self.event.wait(timeout=wait_time)

            self.event.clear()

            with self.lock:
                now = time.time()
                while self.timers and self.timers[0].expiration <= now:
                    timer = heapq.heappop(self.timers)
                    event = Event(
                        EventType.TIMER,
                        {"timer_id": timer.timer_id, "payload": timer.payload},
                    )
                    timer.component.enqueue(event)
                    if timer.interval is not None:
                        timer.expiration += timer.interval / 1000.0
                        heapq.heappush(self.timers, timer)

    def stop(self):
        # Signal the thread to stop
        log.debug("Stopping timer manager")
        self.stop_signal.set()
        self.event.set()  # Wake up the timer thread
        self.thread.join()
        log.debug("Timer manager stopped")

    def cleanup(self):
        """Clean up resources used by the TimerManager"""
        log.debug("Cleaning up TimerManager")
        with self.lock:
            self.timers.clear()
