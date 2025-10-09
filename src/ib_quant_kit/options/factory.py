# ib_quant_kit/options/factory.py
"""Utilities to build IB Option Contracts filtered by target delta and expiry buckets.

Usage:
    from ib_quant_kit.options.factory import pick_contracts_by_delta
    contracts = pick_contracts_by_delta(underlying='SPY', exchange='SMART',
                                        currency='USD', target_delta=-0.30, tol=0.05,
                                        expiry_bucket='0DTE', max_per_side=3)
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from ibapi.contract import Contract

# Expiry bucket helper
def _bucket_to_window(bucket: str) -> Tuple[int, int]:
    bucket = (bucket or '').upper()
    if bucket == '0DTE':
        return (0, 0)
    if bucket == 'WEEKLY':
        return (1, 9)  # 1-9 days out
    if bucket == 'MONTHLY':
        return (10, 45)
    # default any
    return (0, 365)

@dataclass
class OptionSpec:
    symbol: str
    right: str  # 'C' or 'P'
    expiry: str # 'YYYYMMDD'
    strike: float
    exchange: str = 'SMART'
    currency: str = 'USD'
    multiplier: str = '100'

def make_option_contract(spec: OptionSpec) -> Contract:
    c = Contract()
    c.symbol = spec.symbol
    c.secType = 'OPT'
    c.exchange = spec.exchange
    c.currency = spec.currency
    c.lastTradeDateOrContractMonth = spec.expiry
    c.right = spec.right
    c.strike = float(spec.strike)
    c.multiplier = spec.multiplier
    return c

def pick_contracts_by_delta(available_chain: List[Tuple[str, float, float]],
                            # list of (expiry 'YYYYMMDD', strike, model_delta)
                            target_delta: float,
                            tol: float = 0.05,
                            expiry_bucket: str = 'WEEKLY',
                            calls_and_puts: bool = True,
                            max_per_side: int = 3,
                            symbol: str = 'SPY',
                            exchange: str = 'SMART',
                            currency: str = 'USD') -> List[Contract]:
    """Select contracts whose abs(delta) is within target±tol and expiry within bucket window.

    available_chain: produced by your data collection layer using tickOptionComputation or secDefOptParams.
    target_delta: e.g., -0.30 for ~30-delta puts, +0.30 for calls
    calls_and_puts: if True, return both sides matching |delta|; else preserve sign direction of target
    """
    d0, d1 = _bucket_to_window(expiry_bucket)
    today = datetime.utcnow().date()
    out: List[Contract] = []

    def in_bucket(yyyymmdd: str) -> bool:
        try:
            d = datetime.strptime(yyyymmdd, '%Y%m%d').date()
        except ValueError:
            return False
        days = (d - today).days
        return d0 <= days <= d1

    # Split by right using delta sign convention
    calls, puts = [], []
    for exp, strike, delta in available_chain:
        if not in_bucket(exp):
            continue
        if delta is None:
            continue
        if abs(abs(delta) - abs(target_delta)) <= tol:
            if delta >= 0:
                calls.append((exp, strike, delta))
            else:
                puts.append((exp, strike, delta))

    calls = sorted(calls, key=lambda x: abs(abs(x[2]) - abs(target_delta)))[:max_per_side]
    puts = sorted(puts, key=lambda x: abs(abs(x[2]) - abs(target_delta)))[:max_per_side]

    if calls_and_puts:
        sides = [('C', calls), ('P', puts)]
    else:
        sides = [('C', calls)] if target_delta >= 0 else [('P', puts)]

    for right, rows in sides:
        for exp, strike, delta in rows:
            out.append(make_option_contract(OptionSpec(symbol=symbol, right=right, expiry=exp,
                                                       strike=strike, exchange=exchange, currency=currency)))
    return out