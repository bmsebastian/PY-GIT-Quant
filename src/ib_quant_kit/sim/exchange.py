
from dataclasses import dataclass
@dataclass
class SimQuote:
    bid: float
    ask: float
def fill_limit(side: str, qty: float, limit: float, q: SimQuote):
    if side.upper()=="BUY" and limit >= q.ask: return qty, q.ask
    if side.upper()=="SELL" and limit <= q.bid: return qty, q.bid
    return 0.0, 0.0
