import logging, math, time
from indicators import ema, true_atr
from state_bus import STATE

logger = logging.getLogger(__name__)

class PositionMonitor:
    def __init__(self, ib, md_bus, publish_cb=None, fast=8, slow=21):
        self.ib = ib
        self.md = md_bus
        self.fast = fast
        self.slow = slow
        self.publish = publish_cb or (lambda rows: None)
        self.symbols = []
        self.started = False
        self.k_atr = 1.5
        self._last_signal = {}  # symbol -> last signal
        self._alert_id = 0

    def start(self):
        self.symbols = list(self.md._subs.keys())
        self.started = True
        logger.info(f"PositionMonitor tracking {len(self.symbols)} symbols: {self.symbols}")

    def _alert(self, symbol, direction):
        self._alert_id += 1
        alerts = STATE.get().get("alerts", [])
        alerts.append({"id": self._alert_id, "text": f"{symbol} {direction}", "kind": "up" if "UP" in direction else "down"})
        STATE.update(alerts=alerts)

    def tick(self):
        if not self.started:
            return
        rows = []
        for sym in self.symbols:
            closes = self.md.get_series(sym, max(self.slow*3, 120))
            highs, lows, bar_closes = self.md.get_bar_series(sym, 60)
            last = closes[-1] if closes else None
            f = ema(closes, self.fast)
            s = ema(closes, self.slow)
            atr = true_atr(highs, lows, bar_closes, 14)
            series = closes[-60:]
            signal = "HOLD"
            if all(x==x for x in [f, s, atr]) and last is not None:
                if last > s + self.k_atr*atr and f > s:
                    signal = "BREAKOUT_UP"
                elif last < s - self.k_atr*atr and f < s:
                    signal = "BREAKOUT_DOWN"
            # alert on transition to breakout
            prev = self._last_signal.get(sym)
            if signal in ("BREAKOUT_UP","BREAKOUT_DOWN") and prev != signal:
                self._alert(sym, signal)
            self._last_signal[sym] = signal
            rows.append({"symbol": sym, "last": last, "ema_fast": f, "ema_slow": s, "atr": atr, "signal": signal, "series": series})
        try:
            self.publish(rows)
        except Exception:
            logger.exception("PositionMonitor publish failed")
