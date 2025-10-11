import logging, math, time
from typing import List, Dict

from ib_insync import ScannerSubscription
from indicators import ema, true_atr
from contracts import build_and_qualify
from state_bus import STATE

logger = logging.getLogger(__name__)

class MarketScanner:
    def __init__(self, ib, md_bus, publish_cb=None, interval_sec=60, top_n=15, k_atr=1.5):
        self.ib = ib
        self.md = md_bus
        self.publish = publish_cb or (lambda rows: None)
        self.interval = interval_sec
        self.top_n = top_n
        self._last_scan = 0
        self.k_atr = k_atr
        self._alert_id = 100000  # ensure distinct from PositionMonitor

    def _alert(self, symbol, direction, label):
        self._alert_id += 1
        alerts = STATE.get().get("alerts", [])
        alerts.append({"id": self._alert_id, "text": f"{symbol} {direction} ({label})", "kind": "up" if direction=='UP' else "down"})
        STATE.update(alerts=alerts)

    def _scan_once(self) -> List[Dict]:
        cands = []

        def process_scan(instr, loc, code, label):
            try:
                sub = ScannerSubscription(instrument=instr, locationCode=loc, scanCode=code)
                rows = self.ib.reqScannerData(sub)
                for r in rows:
                    sym = getattr(r.contractDetails.contract, "symbol", None)
                    if not sym:
                        continue
                    qc = build_and_qualify(self.ib, sym)
                    if not qc:
                        continue
                    key = sym.upper()
                    if key not in self.md._subs:
                        try:
                            self.md.subscribe_with_contract(key, qc)
                        except Exception:
                            continue
                    closes = self.md.get_series(key, 200)
                    highs, lows, bar_closes = self.md.get_bar_series(key, 60)
                    if len(closes) < 50 or len(bar_closes) < 15:
                        continue
                    last = closes[-1]
                    f = ema(closes, 8)
                    s = ema(closes, 21)
                    atr = true_atr(highs, lows, bar_closes, 14)
                    if any(map(lambda x: x!=x, [f, s, atr])):
                        continue
                    signal = None
                    score = None
                    if last > s + self.k_atr*atr and f > s:
                        signal = "UP"
                        score = (last - s)/max(atr,1e-6)
                    elif last < s - self.k_atr*atr and f < s:
                        signal = "DOWN"
                        score = (s - last)/max(atr,1e-6)
                    if signal:
                        cands.append({"symbol": key, "label": label, "signal": signal, "score": float(score), "last": last, "atr": atr})
                        self._alert(key, signal, label)
            except Exception:
                logger.exception(f"Scanner failed: {label}")

        process_scan("STK", "STK.US.MAJOR", "TOP_PERC_GAIN", "STK_GAIN")
        process_scan("STK", "STK.US.MAJOR", "TOP_PERC_LOSE", "STK_LOSE")
        process_scan("FUT", "FUT.US", "HOT_BY_VOLUME", "FUT_VOL")

        cands.sort(key=lambda x: x["score"], reverse=True)
        return cands[: self.top_n]

    def tick(self):
        now = time.time()
        if now - self._last_scan < self.interval:
            return
        self._last_scan = now
        rows = self._scan_once()
        try:
            self.publish(rows)
        except Exception:
            logger.exception("MarketScanner publish failed")
