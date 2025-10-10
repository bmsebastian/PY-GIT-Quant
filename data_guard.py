import time

class StalenessGuard:
    def __init__(self, max_age_sec: int):
        self.max_age = max_age_sec
        self.last_ts = {}

    def on_tick(self, sym: str, ts: float):
        self.last_ts[sym] = ts

    def is_fresh(self, sym: str) -> bool:
        ts = self.last_ts.get(sym, 0)
        return (time.time() - ts) <= self.max_age
