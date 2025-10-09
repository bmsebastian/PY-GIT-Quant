from dataclasses import dataclass
from typing import List, Tuple, Optional

@dataclass
class OptionSpec:
    underlying: str
    expiry: str      # 'YYYYMMDD'
    right: str       # 'C' or 'P'
    strike: float

@dataclass
class GreekQuote:
    spec: OptionSpec
    delta: float
    mark: float

class OptionsFactory:
    """
    Builds qualified IB option contracts filtered by delta window and expiry regime.
    Expects ib_client to expose:
      - get_expiries(mode, today_yyyymmdd) -> List[str]
      - secdef_opt_params(underlying) -> chain metadata
      - closest_strikes(underlying, expiry) -> List[float]
      - qualify_option(OptionSpec) -> IB Contract
      - greeks_snapshot(contracts) -> List[GreekQuote]
    """
    def __init__(self, ib_client):
        self.ib = ib_client

    def expiry_regime(self, mode: str, today_yyyymmdd: str) -> List[str]:
        return self.ib.get_expiries(mode, today_yyyymmdd)

    def generate_grid(self, underlying: str, expiries: List[str]) -> List[OptionSpec]:
        _ = self.ib.secdef_opt_params(underlying)  # ensure metadata cached
        grid: List[OptionSpec] = []
        for e in expiries:
            strikes = self.ib.closest_strikes(underlying, e)  # atm ring
            for r in ('C','P'):
                for k in strikes:
                    grid.append(OptionSpec(underlying, e, r, k))
        return grid

    def qualify_contracts(self, specs: List[OptionSpec]):
        return [self.ib.qualify_option(s) for s in specs]

    def request_greeks(self, qualified_contracts) -> List[GreekQuote]:
        return self.ib.greeks_snapshot(qualified_contracts)

    def by_delta(self, quotes: List[GreekQuote], lo=0.30, hi=0.45, calls_only=False, puts_only=False):
        out = []
        for q in quotes:
            if calls_only and q.spec.right != 'C': continue
            if puts_only and q.spec.right != 'P': continue
            d = abs(q.delta)
            if lo <= d <= hi:
                out.append(q)
        return out

    def build(self, underlying: str, regime='WEEKLY', delta_window=(0.30,0.45), side=None, today=None):
        expiries = self.expiry_regime(regime, today)
        grid = self.generate_grid(underlying, expiries)
        qualified = self.qualify_contracts(grid)
        quotes = self.request_greeks(qualified)
        lo, hi = delta_window
        calls_only = side == 'C'
        puts_only = side == 'P'
        return self.by_delta(quotes, lo, hi, calls_only, puts_only)
