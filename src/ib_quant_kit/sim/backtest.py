
from .exchange import SimQuote, fill_limit
def run_backtest_once(side: str, qty: float, limit: float, bid: float, ask: float):
    q = SimQuote(bid=bid, ask=ask)
    return fill_limit(side, qty, limit, q)
