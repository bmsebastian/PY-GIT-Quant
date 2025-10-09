
from __future__ import annotations
from datetime import datetime
from typing import List
from ibapi.contract import Contract
from .ib_client import IBClient
from .contract_cache import contract_cache
from .options import OptionQuote

def _parse_expiry_days(expiry: str) -> int:
    y = int(expiry[:4]); m = int(expiry[4:6]); d = int(expiry[6:8] if len(expiry) >= 8 else 1)
    from datetime import datetime as dt
    tgt = dt(y, m, d)
    return max(0, (tgt - dt.utcnow()).days)

def _atm_strikes(strikes, und_price, width=5):
    if not strikes: return []
    arr = sorted(strikes, key=lambda x: abs(x - und_price))
    return sorted(arr[:max(3, min(width, len(arr)))])

def build_option_quotes_snapshot(
    ib: IBClient, underlying_symbol: str, right: str, exchange: str = "SMART", currency: str = "USD",
    max_tte_days: int = 14, max_candidates: int = 12, wait_seconds: float = 3.0
) -> List[OptionQuote]:
    # 1) qualify underlying stock
    u = Contract(); u.symbol = underlying_symbol; u.secType = "STK"; u.exchange = exchange; u.currency = currency
    uq = ib.qualify(u)
    # 2) secdef params
    reqId = contract_cache.next_req_id()
    ib.reqSecDefOptParams(reqId, underlying_symbol, "", "STK", uq.conId)
    import time
    t0 = time.time()
    while reqId not in ib._secdef_done and (time.time() - t0) < wait_seconds:
        time.sleep(0.05)
    info = ib._secdef.get(reqId, {})
    expirations = sorted(list(info.get("expirations", [])))
    strikes = sorted(list(info.get("strikes", [])))
    trading_class = next(iter(info.get("tradingClass", [])), None)
    if not expirations or not strikes:
        return []
    expiries = [e for e in expirations if _parse_expiry_days(e) <= max_tte_days] or [expirations[0]]
    expiry = sorted(expiries, key=lambda e: _parse_expiry_days(e))[0]
    # 3) underlying midpoint via stock NBBO
    und_req = ib.subscribe_stock_nbbo(uq)
    time.sleep(0.25)
    b = ib._bid.get(und_req); a = ib._ask.get(und_req)
    und_mid = (b+a)/2 if b and a else 0.0
    if und_mid <= 0: und_mid = strikes[len(strikes)//2]
    picks = _atm_strikes(strikes, und_mid, width=max_candidates)
    # 4) subscribe greeks for chosen strikes
    req_ids, out = [], []
    for k in picks:
        c = Contract(); c.symbol=underlying_symbol; c.secType="OPT"; c.exchange=exchange; c.currency=currency
        c.lastTradeDateOrContractMonth = expiry; c.strike = float(k); c.right = right.upper(); 
        if trading_class: c.tradingClass = trading_class
        cq = ib.qualify(c); rid = ib.subscribe_option_greeks(cq); req_ids.append(rid)
    t0 = time.time()
    while (time.time() - t0) < wait_seconds:
        if all(r in ib._delta and r in ib._bid and r in ib._ask for r in req_ids): break
        time.sleep(0.05)
    for rid in req_ids:
        bid = float(ib._bid.get(rid, 0.0)); ask = float(ib._ask.get(rid, 0.0)); delta = float(ib._delta.get(rid, 0.0))
        out.append(OptionQuote(symbol=underlying_symbol, expiry=expiry, right=right.upper(), strike=float(ib._req_contracts[rid].strike),
                               bid=bid, ask=ask, delta=delta, tte_days=_parse_expiry_days(expiry), trading_class=trading_class, exchange=exchange, currency=currency))
    return out
