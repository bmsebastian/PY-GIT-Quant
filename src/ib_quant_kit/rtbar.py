
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List
from datetime import datetime

@dataclass
class RTBar:
    start_sec: int
    open: float
    high: float
    low: float
    close: float
    volume: float

class RTBarManager:
    def __init__(self):
        self.bars: Dict[int, List[RTBar]] = {}
        self.current: Dict[int, RTBar] = {}

    def on_trade(self, reqId: int, price: float, size: float, ts_ms: int):
        sec = ts_ms // 1000
        cur = self.current.get(reqId)
        if cur is None or cur.start_sec != sec:
            # flush previous
            if cur is not None:
                self._append(reqId, cur)
            cur = RTBar(sec, price, price, price, price, size)
            self.current[reqId] = cur
        else:
            cur.close = price
            cur.high = max(cur.high, price)
            cur.low = min(cur.low, price)
            cur.volume += size

    def _append(self, reqId: int, bar: RTBar):
        arr = self.bars.setdefault(reqId, [])
        arr.append(bar)
        # keep ~120 seconds worth (2 minutes) of 1s bars; aggregation to 1m happens on read

    def get_bars_1min(self, reqId: int, now_ms: int, lookback_min: int = 30) -> List[dict]:
        # Aggregate 1s RT bars to 1m OHLCV
        arr = list(self.bars.get(reqId, []))
        cur = self.current.get(reqId)
        if cur: arr.append(cur)
        if not arr: return []
        # group by minute
        out = {}
        for b in arr:
            minute_key = b.start_sec // 60
            d = out.get(minute_key)
            if d is None:
                out[minute_key] = dict(time=minute_key*60, open=b.open, high=b.high, low=b.low, close=b.close, volume=b.volume)
            else:
                d["close"] = b.close
                d["high"] = max(d["high"], b.high)
                d["low"] = min(d["low"], b.low)
                d["volume"] += b.volume
        # sort and clip
        rows = [out[k] for k in sorted(out.keys())][-lookback_min:]
        # convert time to iso
        for r in rows:
            r["time"] = datetime.utcfromtimestamp(r["time"]).isoformat()
        return rows

rtbars = RTBarManager()
