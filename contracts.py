# contracts.py
import re
import logging
from typing import Optional
logger = logging.getLogger(__name__)

# Futures root → exchange map (expand as needed)
FUTURES_MAP = {
    "ES": ("CME",  "E-mini S&P 500"),
    "NQ": ("CME",  "E-mini NASDAQ-100"),
    "RTY":("CME",  "E-mini Russell 2000"),
    "YM": ("CBOT", "E-mini Dow"),
    "CL": ("NYMEX","Crude Oil"),
    "GC": ("COMEX","Gold"),
}

def looks_nontradable_symbol(sym: str) -> bool:
    s = sym.upper()
    # Common non-tradable/equity-like junk we should skip from auto-subscription
    if ".CVR" in s or ".OLD" in s or ".RIGHT" in s or ".WT" in s:
        return True
    # Anything with a dot is often an OTC local symbol variant we can’t SMART-qualify
    if "." in s:
        return True
    return False

def is_futures_root(sym: str) -> bool:
    return sym.upper() in FUTURES_MAP

def qualify_stock(ib, symbol: str):
    from ib_insync import Stock
    c = Stock(symbol, exchange="SMART", currency="USD")
    q = ib.qualifyContracts(c)
    return q[0] if q else None

def qualify_nearest_future(ib, root: str):
    """
    Pick the nearest active future for a root like CL, NQ, ES.
    """
    from ib_insync import Future, util
    exch, _desc = FUTURES_MAP[root.upper()]
    cd_list = ib.reqContractDetails(Future(symbol=root.upper(), exchange=exch))
    if not cd_list:
        return None
    # Choose the soonest non-expired monthly/weekly
    cd_list.sort(key=lambda cd: cd.contract.lastTradeDateOrContractMonth or "9999")
    return cd_list[0].contract

def build_and_qualify(ib, sym: str):
    """
    Returns a qualified Contract or None if not tradable.
    """
    if looks_nontradable_symbol(sym):
        logger.info(f"Skip {sym}: looks non-tradable (CVR/OLD/OTC variant)")
        return None

    # Futures roots
    if is_futures_root(sym):
        try:
            c = qualify_nearest_future(ib, sym)
            if c:
                logger.info(f"Qualified FUT {sym} -> {c.localSymbol} @ {c.exchange}")
            return c
        except Exception:
            logger.exception(f"Futures qualify failed for {sym}")
            return None

    # Default: equity
    try:
        c = qualify_stock(ib, sym)
        if c:
            # Exclude OTC/PINK by default
            ex = (getattr(c, "primaryExchange", "") or "").upper()
            if ex in {"PINK", "OTC", "OTCBB"}:
                logger.info(f"Skip {sym}: primaryExchange={ex}")
                return None
            return c
    except Exception:
        logger.exception(f"Stock qualify failed for {sym}")
    return None
