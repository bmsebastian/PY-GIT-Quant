# state_bus.py
from threading import RLock
from time import time

class _StateBus:
    def __init__(self):
        self._lock = RLock()
        self._state = {"heartbeat_ts": 0}

    def update(self, **kwargs):
        with self._lock:
            self._state.update(kwargs)
            self._state["heartbeat_ts"] = time()

    def get(self):
        with self._lock:
            return dict(self._state)

STATE = _StateBus()
