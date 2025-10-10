import logging, random, time
from typing import Dict, List
from collections import deque

from ib_client import Stock

logger = logging.getLogger(__name__)

class MarketDataBus:
    def __init__(self, ib):
        self.ib = ib
        self.tickers: Dict[str, Dict] = {}
        self.history: Dict[str, deque] = {}
        self.window = 60  # store last 60 ticks for simplicity

    def subscribe(self, symbol: str):
        # If ib_insync available and connected, request live data.
        # Otherwise generate synthetic ticks so system can run.
        self.tickers.setdefault(symbol, {"last": None, "ts": None})
        self.history[symbol] = deque(maxlen=self.window)
        logger.info(f"Subscribed (logical) {symbol}")

    def tick(self, symbol: str):
        # In absence of real ticks, simulate a gentle random walk
        rec = self.tickers[symbol]
        base = rec["last"] or 100.0 + random.uniform(-1,1)
        newp = round(base + random.uniform(-0.2, 0.2), 2)
        ts = time.time()
        self.tickers[symbol] = {"last": newp, "ts": ts}
        self.history[symbol].append(newp)
        return newp, ts

    def get_last(self, symbol: str):
        # Try real ticker if available later; for now return simulated
        if symbol not in self.tickers:
            raise KeyError(symbol)
        p, ts = self.tick(symbol)
        return p, ts

    def get_series(self, symbol: str, n: int):
        # Return last n prices (simulate by ticking up to n)
        for _ in range(max(0, n - len(self.history[symbol]))):
            self.tick(symbol)
        return list(self.history[symbol])[-n:]
