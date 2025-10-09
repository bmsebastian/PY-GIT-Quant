
import pandas as pd
from .intraday import opening_range_breakout, vwap_reversion

def momentum(df: pd.DataFrame, fast: int = 5, slow: int = 20):
    if df.empty or len(df) < slow + 1: return "FLAT", 0.0
    ma_f = df["close"].rolling(fast).mean().iloc[-1]
    ma_s = df["close"].rolling(slow).mean().iloc[-1]
    last = df["close"].iloc[-1]
    if ma_f > ma_s: return "BUY", last
    if ma_f < ma_s: return "SELL", last
    return "FLAT", 0.0

def mean_reversion_z(df: pd.DataFrame, lookback: int = 30, z_entry: float = 1.0):
    if df.empty or len(df) < lookback + 1: return "FLAT", 0.0
    lb = df.tail(lookback)
    mu = lb["close"].mean(); sd = lb["close"].std(ddof=1) or 0.01
    last = lb["close"].iloc[-1]
    z = (last - mu) / sd
    if z <= -z_entry: return "BUY", last
    if z >= z_entry: return "SELL", last
    return "FLAT", 0.0

def run_pipeline(df: pd.DataFrame, pipeline: list[dict]):
    # pipeline: [{name: ORBO|VWAP_R|MOMO|MR_Z, params:{...}}, ...]
    for step in pipeline:
        name = step.get("name")
        params = step.get("params", {})
        if name == "ORBO":
            sig = opening_range_breakout(df, **params)
        elif name == "VWAP_R":
            sig = vwap_reversion(df, **params)
        elif name == "MOMO":
            sig = momentum(df, **params)
        elif name == "MR_Z":
            sig = mean_reversion_z(df, **params)
        else:
            continue
        if sig[0] != "FLAT":
            return sig
    return ("FLAT", 0.0)
