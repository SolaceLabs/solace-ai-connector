import threading
import time
import heapq
from ..common.event import Event, EventType


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
        self.thread = threading.Thread(target=self.run)
        self.thread.start()

    def add_timer(self, delay_ms, component, timer_id, interval_ms=None, payload=None):
        with self.lock:
            expiration = time.time() + (delay_ms / 1000.0)
            timer = Timer(expiration, interval_ms, component, timer_id, payload)
            heapq.heappush(self.timers, timer)

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

            time.sleep(0.01)  # Sleep briefly to avoid busy-waiting

    def stop(self):
        self.thread.join()
