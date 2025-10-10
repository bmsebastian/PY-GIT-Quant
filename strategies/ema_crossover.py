import logging
from typing import List
import math

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
    def __init__(self, md_bus, order_tracker, fast=8, slow=21, dry_run=True):
        self.md = md_bus
        self.order_tracker = order_tracker
        self.fast = fast
        self.slow = slow
        self.dry_run = dry_run
        self.guard = StalenessGuard(QUOTE_STALE_SEC)
        self.positions = {}  # sym -> qty (stub logic)

    def on_bar(self):
        # Evaluate all subscribed symbols known to MarketDataBus
        for sym in list(self.md.tickers.keys()):
            price, ts = self.md.get_last(sym)
            self.guard.on_tick(sym, ts)
            if not self.guard.is_fresh(sym):
                logger.debug(f"Skip {sym}: stale")
                continue

            series = self.md.get_series(sym, max(self.slow*3, 30))
            f = ema(series, self.fast)
            s = ema(series, self.slow)
            if math.isnan(f) or math.isnan(s):
                continue

            held = self.positions.get(sym, 0)

            if f > s and held <= 0:
                self._enter_long(sym, qty=1, price=price)
                self.positions[sym] = 1
            elif f < s and held > 0:
                self._exit_long(sym, qty=1, price=price)
                self.positions[sym] = 0

    def _enter_long(self, sym, qty, price):
        if self.dry_run:
            logger.info(f"[DRY] BUY {qty} {sym} @ ~{price}")
            return
        # place order via IB here when wiring real flow
        logger.info(f"BUY {qty} {sym} @ ~{price} (live)")

    def _exit_long(self, sym, qty, price):
        if self.dry_run:
            logger.info(f"[DRY] SELL {qty} {sym} @ ~{price}")
            return
        logger.info(f"SELL {qty} {sym} @ ~{price} (live)")
