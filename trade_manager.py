
# trade_manager.py — v14 minimal glue for IB + MarketData + STATE
import logging, time
from typing import Dict, List, Tuple
from state_bus import STATE
from ib_client import IBClient, Contract
from market_data import MarketDataBus

logger = logging.getLogger(__name__)

POS_SYNC_SEC = 300  # refresh positions every 5 minutes

class TradeManager:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.ibc = IBClient()          # wrapper
        self.ib = None                 # ib_insync.IB handle
        self.mdb: MarketDataBus = None
        self.positions: Dict[str, Dict] = {}  # sym -> {qty, avg, contract}
        self._last_pos_sync = 0.0

    def start(self):
        self.ib = self.ibc.connect()
        STATE.ib_connected = True
        STATE.live_mode = (not self.dry_run)
        self.mdb = MarketDataBus(self.ib)
        self._sync_positions(initial=True)

    def stop(self):
        try:
            self.ibc.disconnect()
            STATE.ib_connected = False
        except Exception:
            pass

    def _sync_positions(self, initial: bool = False):
        try:
            rows = self.ibc.fetch_positions()
            new_syms = []
            for r in rows:
                sym = r["symbol"]
                self.positions[sym] = {"qty": r["qty"], "avg": r["avgCost"], "contract": r["contract"]}
                new_syms.append(sym)
                # subscribe if new
                try:
                    self.mdb.subscribe(sym, r["contract"])
                except Exception as e:
                    logger.warning(f"subscribe failed for {sym}: {e}")
            self._last_pos_sync = time.time()
            STATE.mark_pos_sync()
            # build position rows for dashboard
            pos_rows = []
            for sym, p in self.positions.items():
                last, _ = self.mdb.get_last(sym)
                ema8 = None
                ema21 = None
                pos_rows.append({"symbol": sym, "qty": p["qty"], "avg": p["avg"], "last": last, "ema8": ema8, "ema21": ema21})
            STATE.positions_rows = pos_rows
        except Exception as e:
            logger.warning(f"position sync failed: {e}")

    def heartbeat(self):
        # Periodically resync positions
        if time.time() - self._last_pos_sync > POS_SYNC_SEC:
            self._sync_positions()

        # Recompute dashboard rows' last prices quickly
        try:
            out = []
            for sym, p in self.positions.items():
                last, _ = self.mdb.get_last(sym)
                out.append({"symbol": sym, "qty": p["qty"], "avg": p["avg"], "last": last, "ema8": None, "ema21": None})
            if out:
                STATE.positions_rows = out
        except Exception as e:
            logger.debug(f"heartbeat pricing update failed: {e}")

    def metrics(self) -> dict:
        subs = list(STATE.symbols_subscribed)
        return {
            "ib_connected": STATE.ib_connected,
            "pnl_today": STATE.pnl_today,
            "open_orders": STATE.open_orders,
            "subscriptions": subs,
            "prices": dict(STATE.prices),
            "ema8": dict(STATE.ema8),
            "ema21": dict(STATE.ema21),
            "positions": STATE.positions_rows,
            "last_tick_at": STATE.last_tick_at,
            "last_pos_sync_at": STATE.last_pos_sync_at,
        }
