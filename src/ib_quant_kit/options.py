
from dataclasses import dataclass
from typing import List, Optional
@dataclass
class OptionQuote:
    symbol: str; expiry: str; right: str; strike: float; bid: float; ask: float; delta: float; tte_days: int
    volume: int = 0; open_interest: int = 0; exchange: str = "SMART"; currency: str = "USD"; trading_class: Optional[str] = None; multiplier: str = "100"
def _spread_bps(bid: float, ask: float) -> float:
    mid = (bid + ask)/2 if (bid and ask) else max(bid, ask, 0.0)
    if mid <= 0: return 1e9
    return ((ask - bid) / mid) * 1e4
def select_options_by_delta(chain: List[OptionQuote], target_right: str,
                            delta_min: float = 0.25, delta_max: float = 0.35,
                            max_spread_bps: int = 80, max_tte_days: int = 10, min_oi: int = 0) -> List[OptionQuote]:
    right = target_right.upper(); out = []
    for q in chain:
        if q.right.upper() != right: continue
        if q.tte_days > max_tte_days: continue
        d = abs(q.delta)
        if not (delta_min <= d <= delta_max): continue
        if q.open_interest < min_oi: continue
        if _spread_bps(q.bid, q.ask) > max_spread_bps: continue
        out.append(q)
    out.sort(key=lambda x: (_spread_bps(x.bid, x.ask), -x.open_interest))
    return out[:6]
