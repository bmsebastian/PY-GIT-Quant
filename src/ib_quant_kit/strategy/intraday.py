
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple
import pandas as pd

@dataclass
class Bar:
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float

def bars_to_df(bars: List[dict]) -> pd.DataFrame:
    # Convert list-of-dicts bars to a sorted DataFrame
    if not bars:
        return pd.DataFrame(columns=["time","open","high","low","close","volume"])
    df = pd.DataFrame(bars).copy()
    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time")
    return df

def opening_range_breakout(df: pd.DataFrame, minutes: int = 5, buffer_bps: int = 5) -> Tuple[str, float]:
    # Return ('BUY'/'SELL'/'FLAT', trigger_price)
    if df.empty or len(df) < minutes + 1:
        return "FLAT", 0.0
    or_df = df.iloc[:minutes]
    high = or_df["high"].max()
    low = or_df["low"].min()
    last = df.iloc[-1]["close"]
    up_trigger = high * (1 + buffer_bps/1e4)
    dn_trigger = low * (1 - buffer_bps/1e4)
    if last > up_trigger:
        return "BUY", up_trigger
    if last < dn_trigger:
        return "SELL", dn_trigger
    return "FLAT", 0.0

def vwap_reversion(df: pd.DataFrame, lookback: int = 30, z_entry: float = 1.0) -> Tuple[str, float]:
    # Buy if price < VWAP by z_entry std; sell if > VWAP by z_entry std
    if df.empty:
        return "FLAT", 0.0
    lb = df.tail(lookback)
    if lb.empty:
        return "FLAT", 0.0
    tp = (lb["high"] + lb["low"] + lb["close"]) / 3.0
    vwap = (tp * lb["volume"]).sum() / max(1.0, lb["volume"].sum())
    last = lb.iloc[-1]["close"]
    spread = float(lb["close"].std(ddof=1) or 0.01)
    z = (last - vwap) / spread
    if z <= -z_entry:
        return "BUY", last
    if z >= z_entry:
        return "SELL", last
    return "FLAT", 0.0
