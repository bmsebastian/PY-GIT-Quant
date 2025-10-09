# ib_quant_kit/options/greeks.py
"""Helpers for option greek calculations or normalization.
Currently a thin wrapper as IB supplies greeks via tickOptionComputation."""
from dataclasses import dataclass
from typing import Optional

@dataclass
class Greeks:
    delta: Optional[float] = None
    gamma: Optional[float] = None
    vega: Optional[float] = None
    theta: Optional[float] = None
    implied_vol: Optional[float] = None