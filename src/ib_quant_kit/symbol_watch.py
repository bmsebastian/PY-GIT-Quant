import time
from dataclasses import dataclass

@dataclass
class Freshness:
    last_tick_ts: float = 0.0
    last_news_ts: float = 0.0

class SymbolWatch:
    """
    Per-symbol staleness guard for ticks and news.
    """
    def __init__(self, max_tick_age_s=5, max_news_age_s=3600):
        self.max_tick_age = max_tick_age_s
        self.max_news_age = max_news_age_s
        self._m = {}

    def update_tick(self, symbol):
        self._m.setdefault(symbol, Freshness()).last_tick_ts = time.time()

    def update_news(self, symbol, ts_epoch):
        self._m.setdefault(symbol, Freshness()).last_news_ts = ts_epoch

    def is_fresh(self, symbol):
        f = self._m.get(symbol)
        if not f: return False
        now = time.time()
        return (now - f.last_tick_ts) <= self.max_tick_age and (now - f.last_news_ts) <= self.max_news_age
