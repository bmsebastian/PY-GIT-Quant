# src/ib_quant_kit/risk/helpers.py
# Module-level helper functions for risk checks

from typing import Tuple
from datetime import datetime
from .limits import RiskState, RiskLimits

# Default limits instance
DEFAULT_LIMITS = RiskLimits()

def allowed_order(
    symbol: str,
    session: str,
    notional: float,
    portfolio_gross: float,
    state: RiskState,
    limits: RiskLimits,
    now: datetime
) -> Tuple[bool, str]:
    """
    Check if order is allowed based on risk limits.
    
    Returns:
        (allowed: bool, reason: str)
    """
    # Check session caps
    session_cap = limits.session_caps.get(session, 100_000.0)
    if portfolio_gross + notional > session_cap:
        return False, f"session_cap_{session}"
    
    # Check per-symbol notional
    if notional > limits.per_symbol_notional_cap:
        return False, "per_symbol_notional_cap"
    
    # Check daily order count
    count = state.order_count.get(symbol, 0)
    if count >= limits.max_orders_per_day_per_symbol:
        return False, "max_orders_per_day"
    
    return True, "ok"


def allowed_notional(notional: float, session: str, limits: RiskLimits) -> bool:
    """Check if notional is within session caps"""
    session_cap = limits.session_caps.get(session, 100_000.0)
    return notional <= session_cap
