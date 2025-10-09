
from datetime import datetime
from ..session import resolve_session
from ..cme_map import build_cme_future_quarterly, build_monthly_future_CL_GC
from ibapi.contract import Contract

def resolve_instrument_for_event(symbol: str, now: datetime) -> Contract:
    """RTH -> equity; otherwise -> futures proxy (ES for SPY/QQQ, etc.).
       Simple mapping; extend as needed.
    """
    session = resolve_session(now)
    if session == "RTH":
        c = Contract(); c.symbol, c.secType, c.exchange, c.currency = symbol, "STK", "SMART", "USD"
        return c
    # Overnight proxies: simple examples
    if symbol in ("SPY","QQQ"):
        return build_cme_future_quarterly("ES" if symbol=="SPY" else "NQ", now.date())
    if symbol in ("GLD",):  # Gold ETF -> GC
        return build_monthly_future_CL_GC("GC", now.date())
    # default to stock even overnight
    c = Contract(); c.symbol, c.secType, c.exchange, c.currency = symbol, "STK", "SMART", "USD"
    return c
