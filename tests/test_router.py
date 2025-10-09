
from datetime import datetime
from ib_quant_kit.events.router import resolve_instrument_for_event
def test_router_returns_contract():
    c = resolve_instrument_for_event("SPY", datetime(2025,1,1,15,0,0))
    assert c.symbol in {"SPY","ES","NQ"}
