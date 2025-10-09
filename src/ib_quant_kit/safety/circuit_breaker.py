# src/ib_quant_kit/safety/circuit_breaker.py
from dataclasses import dataclass
from threading import Lock
from time import time
from typing import Optional

@dataclass
class CircuitConfig:
    max_orders_per_minute: int = 60
    max_rejections_per_hour: int = 20
    manual_kill: bool = False

class CircuitBreaker:
    def __init__(self, cfg: CircuitConfig = CircuitConfig()):
        self.cfg = cfg
        self._lock = Lock()
        self._order_timestamps = []
        self._rejections = []
        self._manual_kill = cfg.manual_kill

    def record_order(self):
        with self._lock:
            now = time()
            self._order_timestamps.append(now)
            self._order_timestamps = [t for t in self._order_timestamps if now - t < 60]

    def record_rejection(self):
        with self._lock:
            now = time()
            self._rejections.append(now)
            self._rejections = [t for t in self._rejections if now - t < 3600]

    def kill(self, on: bool = True):
        with self._lock:
            self._manual_kill = on

    def check(self) -> bool:
        """Return True to block trading"""
        with self._lock:
            if self._manual_kill:
                return True
            if len(self._order_timestamps) > self.cfg.max_orders_per_minute:
                return True
            if len(self._rejections) > self.cfg.max_rejections_per_hour:
                return True
            return False

breaker = CircuitBreaker()
