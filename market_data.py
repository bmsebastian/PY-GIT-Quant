import logging, random, time
from typing import Dict
from collections import deque

logger = logging.getLogger(__name__)

class MarketDataBus:
    def __init__(self, ib, window: int = 600):
        self.ib = ib
        self.tickers: Dict[str, Dict] = {}
        self.history: Dict[str, deque] = {}
        self.window = window
        self._use_live = getattr(self.ib, "isConnected", lambda: False)()
        self._subs = {}  # sym -> (contract, ticker)

    def subscribe_with_contract(self, symbol: str, contract):
        symbol = symbol.strip().upper()
        self.tickers.setdefault(symbol, {"last": None, "ts": None})
        self.history.setdefault(symbol, deque(maxlen=self.window))
        if getattr(self.ib, "isConnected", lambda: False)():
            try:
                t = self.ib.reqMktData(contract, "", False, False)
                self._subs[symbol] = (contract, t)
                self._use_live = True
                logger.info(f"Subscribed LIVE {symbol}")
            except Exception:
                logger.exception(f"Live subscribe failed for {symbol}; falling back to SIM")
        else:
            logger.info(f"Subscribed (SIM) {symbol}")

    def subscribe(self, symbol: str):
        self.subscribe_with_contract(symbol, None)

    def _sim_tick(self, symbol: str):
        rec = self.tickers[symbol]
        base = rec["last"] or 100.0 + random.uniform(-1,1)
        newp = round(base + random.uniform(-0.25, 0.25), 2)
        ts = time.time()
        self.tickers[symbol] = {"last": newp, "ts": ts}
        self.history[symbol].append(newp)
        return newp, ts

    def _live_tick(self, symbol: str):
        _, t = self._subs.get(symbol, (None, None))
        if not t:
            return self._sim_tick(symbol)
        px = t.last or t.close or t.marketPrice() or t.midpoint()
        if px is None:
            ts = time.time()
            last = self.tickers[symbol].get("last")
            self.tickers[symbol] = {"last": last, "ts": ts}
            return last, ts
        px = float(px)
        ts = time.time()
        self.tickers[symbol] = {"last": px, "ts": ts}
        self.history[symbol].append(px)
        return px, ts

    def get_last(self, symbol: str):
        if self._use_live:
            return self._live_tick(symbol)
        return self._sim_tick(symbol)

    def get_series(self, symbol: str, n: int):
        if not self._use_live:
            for _ in range(max(0, n - len(self.history[symbol]))):
                self._sim_tick(symbol)
        return list(self.history[symbol])[-n:]
