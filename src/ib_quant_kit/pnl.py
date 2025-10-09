# src/ib_quant_kit/pnl.py - Complete implementation

from typing import Dict
from dataclasses import dataclass
from threading import Lock

@dataclass
class PnLRec:
    symbol: str
    qty: float = 0.0
    avg_cost: float = 0.0
    realized: float = 0.0
    unrealized: float = 0.0
    mark_price: float = 0.0
    total_commission: float = 0.0

class PnLBook:
    def __init__(self):
        self._by_symbol: Dict[str, PnLRec] = {}
        self._lock = Lock()

    def on_ib_position(self, symbol: str, qty: float, avg_cost: float):
        """Called when IBKR sends position update"""
        with self._lock:
            rec = self._by_symbol.get(symbol)
            if rec is None:
                self._by_symbol[symbol] = PnLRec(
                    symbol=symbol,
                    qty=qty,
                    avg_cost=avg_cost,
                    mark_price=avg_cost
                )
            else:
                rec.qty = qty
                rec.avg_cost = avg_cost

    def mark_price(self, symbol: str, price: float):
        """Update market price for unrealized PnL"""
        with self._lock:
            rec = self._by_symbol.get(symbol)
            if rec:
                rec.mark_price = price
                rec.unrealized = rec.qty * (price - rec.avg_cost)

    def on_fill(self, symbol: str, side: str, qty: float, price: float, commission: float = 0.0):
        """Update PnL on fill"""
        with self._lock:
            rec = self._by_symbol.get(symbol)
            if rec is None:
                rec = PnLRec(symbol=symbol, qty=0.0, avg_cost=0.0)
                self._by_symbol[symbol] = rec

            signed_qty = qty if side.upper() in ("BUY", "BOT") else -qty
            old_qty = rec.qty
            new_qty = old_qty + signed_qty

            # Track commission
            rec.total_commission += abs(commission)

            # Calculate realized PnL on closing trades
            if old_qty * signed_qty < 0:  # Opposite direction = closing
                close_qty = min(abs(signed_qty), abs(old_qty))
                realized_per_share = (price - rec.avg_cost) * (-1 if old_qty > 0 else 1)
                rec.realized += close_qty * realized_per_share - commission

            # Update position
            if new_qty == 0:
                rec.qty = 0.0
                rec.avg_cost = 0.0
                rec.unrealized = 0.0
            elif old_qty * signed_qty > 0:  # Same direction = adding
                total_cost = (abs(old_qty) * rec.avg_cost) + (abs(signed_qty) * price)
                rec.avg_cost = total_cost / abs(new_qty)
                rec.qty = new_qty
            else:  # Reversing
                rec.qty = new_qty
                rec.avg_cost = price

            # Update unrealized
            rec.unrealized = rec.qty * (rec.mark_price - rec.avg_cost)

    def snapshot(self) -> Dict:
        """Get current PnL snapshot"""
        with self._lock:
            total_realized = sum(r.realized for r in self._by_symbol.values())
            total_unrealized = sum(r.unrealized for r in self._by_symbol.values())
            total_commission = sum(r.total_commission for r in self._by_symbol.values())
            
            return {
                "realized": round(total_realized, 2),
                "unrealized": round(total_unrealized, 2),
                "net": round(total_realized + total_unrealized, 2),
                "commission": round(total_commission, 2),
                "by_symbol": {
                    sym: {
                        "qty": r.qty,
                        "avg_cost": round(r.avg_cost, 2),
                        "mark": round(r.mark_price, 2),
                        "realized": round(r.realized, 2),
                        "unrealized": round(r.unrealized, 2)
                    }
                    for sym, r in self._by_symbol.items()
                }
            }

pnl = PnLBook()
