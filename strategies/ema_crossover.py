import logging
import math
import time
from typing import List

from config import QUOTE_STALE_SEC
from data_guard import StalenessGuard

logger = logging.getLogger(__name__)

def ema(values: List[float], period: int) -> float:
    if not values or len(values) < period:
        return math.nan
    k = 2 / (period + 1)
    e = values[0]
    for v in values[1:]:
        e = v * k + e * (1 - k)
    return e

class EMACrossover:
    """
    Simple EMA cross with:
      - warmup bars before first evaluation
      - min evaluation interval (prevents rapid-fire on boot)
      - staleness guard
      - optional live order placement (kept in DRY by default)
    """
    def __init__(self, md_bus, order_tracker, fast=8, slow=21, dry_run=True):
        self.md = md_bus
        self.order_tracker = order_tracker
        self.fast = fast
        self.slow = slow
        self.dry_run = dry_run

        self.guard = StalenessGuard(QUOTE_STALE_SEC)
        self.positions = {}  # sym -> qty (stub logic)

        self._last_bar_ts = 0
        self.min_bar_sec = 2                    # evaluate at most every 2s
        self.warmup = max(self.slow * 3, 60)    # need at least this many samples

    def on_bar(self):
        now = time.time()
        if now - self._last_bar_ts < self.min_bar_sec:
            return
        self._last_bar_ts = now

        # Evaluate all subscribed symbols
        for sym in list(self.md.tickers.keys()):
            price, ts = self.md.get_last(sym)
            self.guard.on_tick(sym, ts)
            if not self.guard.is_fresh(sym):
                logger.debug(f"Skip {sym}: stale")
                continue

            series = self.md.get_series(sym, self.warmup)
            if len(series) < self.warmup:
                # wait for warmup bars
                continue

            f = ema(series, self.fast)
            s = ema(series, self.slow)
            if math.isnan(f) or math.isnan(s):
                continue

            held = self.positions.get(sym, 0)

            # Basic cross logic
            if f > s and held <= 0:
                self._enter_long(sym, qty=1, price=price)
                self.positions[sym] = 1
            elif f < s and held > 0:
                self._exit_long(sym, qty=1, price=price)
                self.positions[sym] = 0

    # --- Order helpers ---

    def _place_mkt(self, sym: str, qty: int, action: str):
        """
        Live order helper (remains DRY unless DRY_RUN=0).
        Uses ib_insync if available and md_bus has a real IB connection.
        """
        if self.dry_run:
            logger.info(f"[DRY] {action} {qty} {sym}")
            return

        ib = getattr(self.md, "ib", None)
        if ib is None:
            logger.error("No IB handle available for live order placement")
            return

        try:
            from ib_insync import Stock, MarketOrder
        except Exception:
            logger.error("ib_insync not available; cannot place live orders")
            return

        try:
            c = Stock(sym, exchange="SMART", currency="USD")
            qc = ib.qualifyContracts(c)
            c = qc[0] if qc else c
            o = MarketOrder(action, qty)
            trade = ib.placeOrder(c, o)
            order_id = getattr(getattr(trade, "order", None), "orderId", "N/A")
            logger.info(f"Placed {action} {qty} {sym} orderId={order_id}")
        except Exception:
            logger.exception(f"Order failure {action} {sym}")

    def _enter_long(self, sym, qty, price):
        self._place_mkt(sym, qty, "BUY")

    def _exit_long(self, sym, qty, price):
        self._place_mkt(sym, qty, "SELL")
