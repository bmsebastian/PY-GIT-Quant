
from ib_quant_kit.risk.limits import allowed_notional, DEFAULT_LIMITS
def test_allowed_notional_caps():
    assert allowed_notional(50000, "RTH", DEFAULT_LIMITS)
    assert not allowed_notional(200000, "RTH", DEFAULT_LIMITS)
