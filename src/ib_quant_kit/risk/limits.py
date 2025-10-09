from dataclasses import dataclass, field
from typing import Dict, Optional

@dataclass
class RiskLimits:
    session_caps: Dict[str, float] = field(default_factory=lambda: {"RTH": 100_000.0})
    per_symbol_notional_cap: float = 50_000.0
    max_position_per_symbol: int = 5
    max_orders_per_day_per_symbol: int = 50

class RiskState:
    def __init__(self, limits: Optional[RiskLimits] = None):
        self.limits = limits or RiskLimits()
        self.order_count: Dict[str, int] = {}

    def allowed_notional(self, symbol: str, price: float) -> float:
        return max(0.0, self.limits.per_symbol_notional_cap)

    def allowed_order(self, symbol: str, side: str, price: float, qty: float) -> bool:
        from ..positions import positions
        rec = positions.get(symbol)
        live_qty = rec.qty if rec else 0.0
        signed = qty if side.upper().startswith(("BUY", "BOT")) else -qty
        projected = live_qty + signed
        if abs(projected) > self.limits.max_position_per_symbol:
            return False
        notional = abs(price * projected)
        if notional > self.allowed_notional(symbol, price):
            return False
        used = self.order_count.get(symbol, 0)
        if used + 1 > self.limits.max_orders_per_day_per_symbol:
            return False
        self.order_count[symbol] = used + 1
        return True

    def reset_daily_counters(self):
        self.order_count.clear()
