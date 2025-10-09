from src.ib_quant_kit.risk.limits import RiskState, RiskLimits
from src.ib_quant_kit.positions import positions

def test_allowed_order_uses_live_positions():
    positions._by_symbol.clear()
    positions.update_from_fill("SPY", "BUY", 2, 500.0)
    rs = RiskState(RiskLimits(per_symbol_notional_cap=10_000.0, max_position_per_symbol=5))
    assert rs.allowed_order("SPY", "BUY", 500.0, 3) is True
    assert rs.allowed_order("SPY", "BUY", 500.0, 1) is False
