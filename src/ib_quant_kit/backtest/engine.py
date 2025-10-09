from dataclasses import dataclass
from typing import List, Dict, Callable, Optional
import csv
from pathlib import Path

@dataclass
class Bar:
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float

@dataclass
class Trade:
    ts: int
    symbol: str
    side: str
    qty: int
    price: float

@dataclass
class Result:
    trades: List[Trade]
    pnl: float
    max_drawdown: float

def load_csv_bars(path: str) -> List[Bar]:
    bars = []
    with open(path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        # expect columns: ts,open,high,low,close,volume
        for row in r:
            bars.append(Bar(
                ts=int(row["ts"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("volume", 0.0)),
            ))
    bars.sort(key=lambda b: b.ts)
    return bars

class SimpleBroker:
    def __init__(self, commission_per_share: float = 0.005):
        self.position = 0
        self.cash = 0.0
        self.entry_price = 0.0
        self.commission = commission_per_share
        self.equity_curve = []

    def _fill(self, side: str, qty: int, price: float):
        fee = qty * self.commission
        if side == "BUY":
            prev_pos = self.position
            self.position += qty
            if prev_pos <= 0 and self.position > 0:
                self.entry_price = price
            self.cash -= qty * price + fee
        else:
            prev_pos = self.position
            self.position -= qty
            self.cash += qty * price - fee
            if prev_pos >= 0 and self.position < 0:
                self.entry_price = price

    def mark(self, price: float):
        # unrealized PnL based on long/short sign
        unreal = self.position * (price - self.entry_price)
        self.equity_curve.append(self.cash + unreal)

    def trade(self, side: str, qty: int, price: float):
        self._fill(side, qty, price)

def run_backtest(symbol: str, bars: List[Bar], strategy_fn: Callable, lot: int = 1) -> Result:
    broker = SimpleBroker()
    trades: List[Trade] = []
    state: Dict = {}

    for b in bars:
        signal = strategy_fn(state, b)  # returns 'BUY', 'SELL', or None
        if signal in ("BUY", "SELL"):
            broker.trade(signal, lot, b.close)
            trades.append(Trade(b.ts, symbol, signal, lot, b.close))
        broker.mark(b.close)

    pnl = broker.equity_curve[-1] if broker.equity_curve else 0.0
    peak, mdd = float("-inf"), 0.0
    for eq in broker.equity_curve:
        if eq > peak:
            peak = eq
        drawdown = (peak - eq)
        if drawdown > mdd:
            mdd = drawdown
    return Result(trades=trades, pnl=pnl, max_drawdown=mdd)
