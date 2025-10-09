from dataclasses import dataclass
from threading import Lock
from typing import Dict, Optional

@dataclass
class PositionRecord:
    symbol: str
    qty: float = 0.0
    avg_price: float = 0.0

class Positions:
    def __init__(self):
        self._by_symbol: Dict[str, PositionRecord] = {}
        self._lock = Lock()

    def snapshot(self) -> Dict[str, PositionRecord]:
        with self._lock:
            return {k: PositionRecord(v.symbol, v.qty, v.avg_price) for k, v in self._by_symbol.items()}

    def get(self, symbol: str) -> Optional[PositionRecord]:
        with self._lock:
            return self._by_symbol.get(symbol)

    def update_from_ib(self, account: str, contract, position: float, avg_cost: float):
        symbol = getattr(contract, "symbol", None) or getattr(contract, "localSymbol", "UNKNOWN")
        with self._lock:
            rec = self._by_symbol.get(symbol)
            if rec is None:
                self._by_symbol[symbol] = PositionRecord(symbol=symbol, qty=float(position), avg_price=float(avg_cost))
            else:
                rec.qty = float(position)
                rec.avg_price = float(avg_cost)

    def update_from_fill(self, symbol: str, side: str, qty: float, price: float):
        signed = qty if side.upper().startswith(("BOT", "BUY")) else -qty
        with self._lock:
            rec = self._by_symbol.get(symbol)
            if rec is None or abs(rec.qty) < 1e-9:
                self._by_symbol[symbol] = PositionRecord(symbol=symbol, qty=signed, avg_price=price)
                return
            new_qty = rec.qty + signed
            if rec.qty * signed > 0 and abs(new_qty) > 0:
                rec.avg_price = (rec.avg_price * abs(rec.qty) + price * abs(signed)) / abs(new_qty)
            if rec.qty * signed < 0 and abs(new_qty) > 0 and (abs(signed) > abs(rec.qty)):
                rec.avg_price = price
            rec.qty = new_qty

positions = Positions()
