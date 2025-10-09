
from dataclasses import dataclass
@dataclass
class L1:
    bid: float
    ask: float
    bid_size: float = 1000
    ask_size: float = 1000

def simulate_limit(side: str, qty: float, limit: float, book: L1, seconds: float = 1.0):
    # Simple partial fill model:
    # - If price crosses the spread -> full fill at contra
    # - Else, partial fill proportional to seconds and queue size
    if side.upper() == "BUY":
        if limit >= book.ask:
            return qty, book.ask
        # partial
        fill = min(qty, (seconds * (book.ask_size / 60.0)) * 0.1)
        return fill, limit
    else:
        if limit <= book.bid:
            return qty, book.bid
        fill = min(qty, (seconds * (book.bid_size / 60.0)) * 0.1)
        return fill, limit
