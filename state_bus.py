# state_bus.py - v15 compatible (with v14 backward compatibility)
from dataclasses import dataclass, asdict, field
from time import time
from typing import Dict, Set, Optional, Any
from threading import RLock

@dataclass
class Heartbeat:
    seq: int = 0
    ts: str = ""  # Always string for consistency
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
    """
    Thread-safe singleton state bus for sharing data between components.
    All public methods use locks to prevent race conditions.
    v15 compatible with v14 backward compatibility.
    """
    def __init__(self):
        self._lock = RLock()  # Thread safety
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
        
        # v15 additions
        self.market_phase: str = "unknown"
        self.scanner_results: list[dict] = []
        self.unusual_options: list[dict] = []

    # --- v15 compatibility: positions property ---
    @property
    def positions(self) -> Dict[str, Dict]:
        """
        v15 compatibility: Convert positions_rows list to dict.
        Returns: {symbol: {qty, avg, contract, ...}}
        """
        with self._lock:
            positions_dict = {}
            for row in self.positions_rows:
                symbol = row.get('symbol')
                if symbol:
                    positions_dict[symbol] = row
            return positions_dict

    # --- mutation helpers ---
    def mark_tick(self, symbol: str, price: float):
        """Thread-safe tick marker."""
        with self._lock:
            self.prices[symbol] = float(price)
            self.last_tick_at = time()

    def mark_pos_sync(self):
        """Thread-safe position sync marker."""
        with self._lock:
            self.last_pos_sync_at = time()

    def update(self, **kwargs):
        """Thread-safe state update."""
        with self._lock:
            # Basic shallow update for known fields
            for k, v in kwargs.items():
                if k == "subs_symbols" and isinstance(v, set):
                    self.symbols_subscribed = set(v)
                elif hasattr(self, k):
                    setattr(self, k, v)

    def update_heartbeat(self, **kwargs):
        """Thread-safe heartbeat update."""
        with self._lock:
            # Ensure ts is always string
            ts_val = kwargs.get("ts", time())
            if isinstance(ts_val, (int, float)):
                from datetime import datetime
                ts_val = datetime.utcfromtimestamp(ts_val).isoformat(timespec="seconds") + "Z"
            
            # Build a new heartbeat struct from kwargs
            hb = Heartbeat(
                seq=int(kwargs.get("seq", self.heartbeat.seq)),
                ts=str(ts_val),
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

    def uptime_seconds(self) -> int:
        """Get uptime in seconds."""
        with self._lock:
            return int(time() - self.started_at)

    # --- views ---
    def snapshot(self) -> Dict[str, Any]:
        """Create snapshot of current state."""
        return {
            "env": "prod" if self.live_mode else "dev",
            "dry_run": self.dry_run,
            "ib_connected": self.ib_connected,
            "subs": len(self.symbols_subscribed),
            "live_mode": self.live_mode,
            "pnl_day": self.pnl_today,
            "open_orders": self.open_orders,
            "positions": list(self.positions_rows),  # Copy to avoid mutation
            "breakouts": list(self.breakouts),
            "alerts": list(self.alerts),
            "prices": dict(self.prices),
            "ema8": dict(self.ema8),
            "ema21": dict(self.ema21),
            "heartbeat": asdict(self.heartbeat),
            "market_phase": self.market_phase,
            "scanner_results": list(self.scanner_results),
            "unusual_options": list(self.unusual_options),
        }

    def get(self) -> Dict[str, Any]:
        """Thread-safe snapshot retrieval."""
        with self._lock:
            return self.snapshot()

    def clear_alerts(self):
        """Clear all alerts."""
        with self._lock:
            self.alerts = []

    def add_alert(self, text: str, kind: str = "info"):
        """Add a new alert."""
        with self._lock:
            alert_id = len(self.alerts) + 1
            self.alerts.append({
                "id": alert_id,
                "text": text,
                "kind": kind,
                "timestamp": time()
            })

# Global singleton
STATE = StateBus()
