
from dataclasses import dataclass
from typing import Optional
from datetime import date
import os, yaml
from ibapi.contract import Contract
from .futures import choose_front_month, CODE_TO_MONTH
from .config import settings

@dataclass(frozen=True)
class CMESpec:
    symbol: str; exchange: str; currency: str; secType: str = "FUT"; trading_class: Optional[str] = None; multiplier: Optional[str] = None
CME = {
    "ES": CMESpec("ES", "CME", "USD", trading_class="ES", multiplier="50"),
    "NQ": CMESpec("NQ", "CME", "USD", trading_class="NQ", multiplier="20"),
    "RTY": CMESpec("RTY", "CME", "USD", trading_class="RTY", multiplier="50"),
    "CL": CMESpec("CL", "NYMEX", "USD", trading_class="CL", multiplier="1000"),
    "GC": CMESpec("GC", "COMEX", "USD", trading_class="GC", multiplier="100"),
}
def _load_roll_day_default(root: str) -> int:
    path = settings.roll_cal_file or os.path.join(os.path.dirname(__file__), "data", "roll_calendar.yaml")
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f: cfg = yaml.safe_load(f) or {}
        return int(cfg.get(root, {}).get("roll_day", 18))
    except Exception:
        return 18
def _yyyymm(y: int, code: str) -> str:
    m = CODE_TO_MONTH[code]; return f"{y}{m:02d}"
def build_cme_future_quarterly(root: str, on_date: date) -> Contract:
    spec = CME[root]
    y, code = choose_front_month(on_date, roll_pre_days=7)
    c = Contract(); c.symbol = spec.symbol; c.secType = spec.secType; c.exchange = spec.exchange; c.currency = spec.currency
    c.lastTradeDateOrContractMonth = _yyyymm(y, code)
    if spec.trading_class: c.tradingClass = spec.trading_class
    if spec.multiplier: c.multiplier = spec.multiplier
    return c
def _month_after(y: int, m: int):
    return (y + (1 if m==12 else 0), 1 if m==12 else m+1)
def build_monthly_future_CL_GC(root: str, on_date: date, roll_day: Optional[int] = None) -> Contract:
    assert root in ("CL","GC")
    roll_day = roll_day or _load_roll_day_default(root)
    spec = CME[root]
    y, m = on_date.year, on_date.month
    if on_date.day >= roll_day: y, m = _month_after(y, m)
    c = Contract(); c.symbol = spec.symbol; c.secType = spec.secType; c.exchange = spec.exchange; c.currency = spec.currency
    c.lastTradeDateOrContractMonth = f"{y}{m:02d}"
    if spec.trading_class: c.tradingClass = spec.trading_class
    if spec.multiplier: c.multiplier = spec.multiplier
    return c
