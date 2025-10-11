
# state_bus.py — v14 singleton state
from dataclasses import dataclass, asdict, field
from time import time
from typing import Dict, Set, Optional, Any

@dataclass
class Heartbeat:
    seq: int = 0
    ts: float = 0.0
    uptime_s: int = 0
    last_tick_age_s: Optional[int] = None
    last_pos_sync_age_s: Optional[int] = None
    subs: int = 0
    ib_connected: bool = False
    live_mode: bool = False
    dry_run: bool = True
    loop_lag_ms: Optional[int] = None
    symbols: int = 0

class StateBus:
    def __init__(self):
        self.started_at: float = time()
        self.last_tick_at: Optional[float] = None
        self.last_pos_sync_at: Optional[float] = None
        self.symbols_subscribed: Set[str] = set()
        self.ib_connected: bool = False
        self.live_mode: bool = False
        self.dry_run: bool = True
        self.loop_lag_ms: Optional[int] = None
        self.pnl_today: float = 0.0
        self.open_orders: int = 0
        self.prices: Dict[str, float] = {}
        self.ema8: Dict[str, float] = {}
        self.ema21: Dict[str, float] = {}
        self.positions_rows: list[dict] = []
        self.breakouts: list[dict] = []
        self.alerts: list[dict] = []
        self.heartbeat: Heartbeat = Heartbeat()

    # --- mutation helpers ---
    def mark_tick(self, symbol: str, price: float):
        self.prices[symbol] = float(price)
        self.last_tick_at = time()

    def mark_pos_sync(self):
        self.last_pos_sync_at = time()

    def update(self, **kwargs):
        # Basic shallow update for known fields so callers can pass flexible maps
        for k, v in kwargs.items():
            if k == "subs_symbols" and isinstance(v, set):
                self.symbols_subscribed = set(v)
            elif hasattr(self, k):
                setattr(self, k, v)

    def update_heartbeat(self, **kwargs):
        # Build a new heartbeat struct from kwargs
        hb = Heartbeat(
            seq=int(kwargs.get("seq", self.heartbeat.seq)),
            ts=kwargs.get("ts", time()),
            uptime_s=int(kwargs.get("uptime_s", 0)),
            last_tick_age_s=kwargs.get("last_tick_age_s"),
            last_pos_sync_age_s=kwargs.get("last_pos_sync_age_s"),
            subs=int(kwargs.get("subs", len(self.symbols_subscribed))),
            ib_connected=bool(kwargs.get("ib_connected", self.ib_connected)),
            live_mode=bool(kwargs.get("live_mode", self.live_mode)),
            dry_run=bool(kwargs.get("dry_run", self.dry_run)),
            loop_lag_ms=kwargs.get("loop_lag_ms"),
            symbols=int(kwargs.get("prices", len(self.prices))),
        )
        self.heartbeat = hb

    # --- views ---
    def snapshot(self) -> Dict[str, Any]:
        return {
            "env": "prod" if self.live_mode else "dev",
            "dry_run": self.dry_run,
            "ib_connected": self.ib_connected,
            "subs": len(self.symbols_subscribed),
            "live_mode": self.live_mode,
            "pnl_day": self.pnl_today,
            "open_orders": self.open_orders,
            "positions": self.positions_rows,
            "breakouts": self.breakouts,
            "alerts": self.alerts,
            "prices": self.prices,
            "ema8": self.ema8,
            "ema21": self.ema21,
            "heartbeat": asdict(self.heartbeat),
        }

    def get(self) -> Dict[str, Any]:
        return self.snapshot()

# Global singleton
STATE = StateBus()
