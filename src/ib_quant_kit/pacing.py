
import time
from threading import Lock
class Pacer:
    def __init__(self, rate_per_sec: float, burst: int):
        self.rate, self.burst = rate_per_sec, burst
        self._tokens, self._last, self._lock = burst, time.monotonic(), Lock()
    def _refill(self):
        now = time.monotonic(); elapsed = now - self._last; self._last = now
        self._tokens = min(self.burst, self._tokens + int(elapsed * self.rate))
    def wait(self):
        with self._lock:
            self._refill()
            if self._tokens == 0: time.sleep(0.1); self._refill()
            if self._tokens > 0: self._tokens -= 1; return True
            time.sleep(0.05); return self.wait()
hist_pacer = Pacer(rate_per_sec=4, burst=8)
mkt_pacer  = Pacer(rate_per_sec=10, burst=20)
