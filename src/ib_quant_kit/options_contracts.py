
from ibapi.contract import Contract
from .options import OptionQuote
def _norm_expiry(expiry: str) -> str:
    if len(expiry) in (6,8): return expiry
    e = ''.join(ch for ch in expiry if ch.isdigit())
    if len(e) in (6,8): return e
    raise ValueError(f"Unrecognized expiry format: {expiry}")
def make_option_contract(q: OptionQuote) -> Contract:
    c = Contract()
    c.symbol = q.symbol; c.secType = "OPT"; c.currency = q.currency; c.exchange = q.exchange
    c.lastTradeDateOrContractMonth = _norm_expiry(q.expiry); c.strike = float(q.strike); c.right = q.right.upper()
    if q.trading_class: c.tradingClass = q.trading_class
    c.multiplier = q.multiplier
    return c
