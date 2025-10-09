# scanner.py — simple momentum/breakout scanner
import time, logging
from threading import Thread
from typing import List
from config import SCAN_UNIVERSE, SCAN_BAR_SIZE, SCAN_LOOKBACK_DUR, SMA_SHORT, SMA_LONG, BREAKOUT_WINDOW
log = logging.getLogger("scanner")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
def sma(vals: List[float], n: int) -> float:
    if len(vals) < n: return float('nan')
    return sum(vals[-n:]) / n
class TrendScanner(Thread):
    def __init__(self, ib, trade_manager):
        super().__init__(daemon=True)
        self.ib = ib; self.tm = trade_manager; self.running = True
    def run(self):
        while self.running:
            opps = []
            for sym in SCAN_UNIVERSE:
                if sym in self.tm.non_tradable: 
                    continue
                if not self.ib.is_tradable(sym):
                    self.tm.non_tradable.add(sym)
                    continue
                bars = self.ib.fetch_bars(sym, SCAN_LOOKBACK_DUR, SCAN_BAR_SIZE)
                closes = [b[4] for b in bars if isinstance(b[4], (int, float))]
                if len(closes) < max(SMA_LONG, BREAKOUT_WINDOW) + 1: 
                    continue
                last = closes[-1]
                s = sma(closes, SMA_SHORT)
                l = sma(closes, SMA_LONG)
                sigs = []
                if s and l and s > l: sigs.append("SMA_X")
                hh = max(closes[-BREAKOUT_WINDOW:]); ll = min(closes[-BREAKOUT_WINDOW:])
                if last >= hh: sigs.append("BRK_H")
                if last <= ll: sigs.append("BRK_L")
                if sigs:
                    opps.append({"symbol": sym, "signal": "+".join(sigs), "last": float(last),
                                 "sma_s": float(s), "sma_l": float(l), "note": ""})
                time.sleep(0.10)
            self.tm.opportunities = opps
            time.sleep(30)
