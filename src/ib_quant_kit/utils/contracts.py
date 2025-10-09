# Minimal contract qualifier placeholder.
# In your live system, replace with proper IB API qualification.
from dataclasses import dataclass

@dataclass
class Contract:
    symbol: str
    secType: str = "STK"
    currency: str = "USD"
    exchange: str = "SMART"

def qualify_contract(ib, symbol: str):
    # Stub for now; integrate with real ibapi EClient/EWrapper if present.
    return Contract(symbol=symbol)
