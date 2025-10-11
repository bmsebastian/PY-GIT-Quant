# market_data.py — v14 (IB-only, with ensure_ib_connected helper)
import logging, time
from typing import Dict, Tuple, Optional
from collections import deque
from state_bus import STATE

logger = logging.getLogger(__name__)

FALLBACK_AFTER_S = 20
HIST_REFETCH_COOLDOWN_S = 300
HIST_DURATION = "1 D"
HIST_BAR = "5 mins"

def ensure_ib_connected(ib):
    """Ensure IB instance is connected before any requests."""
    if ib is None:
        raise RuntimeError("IB instance is None")
    if not getattr(ib, "isConnected", lambda: False)():
        try:
            ib.connect('127.0.0.1', 7497, clientId=1)
            logger.info("Reconnected to IBKR on 127.0.0.1:7497 clientId=1")
        except Exception as e:
            raise RuntimeError(f"Unable to connect to IBKR: {e}")
    else:
        logger.info("IBKR connection verified.")

class MarketDataBus:
    def __init__(self, ib, window: int = 600):
        ensure_ib_connected(ib)
        self.ib = ib
        self.tickers: Dict[str, Dict] = {}
        self.history: Dict[str, deque] = {}
        self.window = int(window)
        self._subs: Dict[str, Tuple] = {}
        self._last_hist_fetch: Dict[str, float] = {}
        try:
            self.ib.reqMarketDataType(1)
        except Exception as e:
            logger.warning(f"reqMarketDataType(1) failed: {e}")

    def _record_tick(self, symbol: str, px: float, ts: float):
        self.tickers[symbol] = {"last": px, "ts": ts}
        self.history[symbol].append(px)
        STATE.mark_tick(symbol, px)

    def _now(self) -> float:
        return time.time()

    def subscribe(self, symbol: str, contract):
        if not symbol or contract is None:
            raise ValueError("subscribe() requires symbol and a valid IB Contract")
        ensure_ib_connected(self.ib)
        symbol = symbol.strip().upper()
        self.tickers.setdefault(symbol, {"last": None, "ts": None})
        self.history.setdefault(symbol, deque(maxlen=self.window))
        try:
            t = self.ib.reqMktData(contract, "", False, False)
            self._subs[symbol] = (contract, t)
            STATE.symbols_subscribed.add(symbol)
            logger.info(f"Subscribed LIVE {symbol}")
        except Exception as e:
            logger.exception(f"Live subscribe failed for {symbol}: {e}")
            raise

    def _live_tick(self, symbol: str) -> Tuple[Optional[float], float]:
        contract, ticker = self._subs.get(symbol, (None, None))
        if not ticker:
            raise RuntimeError(f"{symbol} not subscribed")
        px = ticker.last or ticker.close or ticker.marketPrice() or ticker.midpoint()
        ts = self._now()
        if px is None:
            last = self.tickers[symbol].get("last")
            self.tickers[symbol] = {"last": last, "ts": ts}
            return last, ts
        px = float(px)
        self._record_tick(symbol, px, ts)
        return px, ts

    def _historical_fallback(self, symbol: str):
        last_hist_ts = self._last_hist_fetch.get(symbol)
        now = self._now()
        if last_hist_ts and (now - last_hist_ts) < HIST_REFETCH_COOLDOWN_S:
            return
        contract, _ = self._subs.get(symbol, (None, None))
        if not contract:
            return
        try:
            self._last_hist_fetch[symbol] = now
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime="",
                durationStr=HIST_DURATION,
                barSizeSetting=HIST_BAR,
                whatToShow="TRADES",
                useRTH=0,
                formatDate=1,
                keepUpToDate=False,
                chartOptions=[],
            )
            if bars and len(bars) > 0:
                last_bar = bars[-1]
                px = float(last_bar.close)
                ts = self._now()
                self._record_tick(symbol, px, ts)
                logger.info(f"Historical fallback for {symbol}: {px}")
        except Exception as e:
            logger.warning(f"Fallback fetch failed for {symbol}: {e}")

    def get_last(self, symbol: str) -> Tuple[Optional[float], float]:
        px, ts = self._live_tick(symbol)
        last_ts = self.tickers.get(symbol, {}).get("ts")
        if (px is None) or (last_ts and (self._now() - last_ts) >= FALLBACK_AFTER_S):
            self._historical_fallback(symbol)
            px = self.tickers.get(symbol, {}).get("last")
            ts = self.tickers.get(symbol, {}).get("ts") or ts
        return px, ts

    def get_series(self, symbol: str, n: int):
        return list(self.history.get(symbol, []))[-n:]

    def snapshot(self) -> Dict:
        now = self._now()
        out = {}
        for sym, rec in self.tickers.items():
            ts = rec.get("ts")
            out[sym] = {"last": rec.get("last"), "age_s": (int(now - ts) if ts else None)}
        return out
