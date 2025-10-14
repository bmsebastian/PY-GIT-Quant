# trade_manager.py — v14A with priority subscriptions and EMA calculations (FIXED)
import logging, time, math
from typing import Dict, List, Tuple
from state_bus import STATE
from ib_client import IBClient, Contract
from market_data import MarketDataBus
from indicators import ema
from config import PRIORITY_POSITION

logger = logging.getLogger(__name__)

POS_SYNC_SEC = 300  # refresh positions every 5 minutes
WARMUP_DURATION_SEC = 60  # Warmup period duration
WARMUP_SYNC_INTERVAL = 10  # Sync every 10s during warmup

class TradeManager:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.ibc = IBClient()          # wrapper
        self.ib = None                 # ib_insync.IB handle
        self.mdb: MarketDataBus = None
        self.positions: Dict[str, Dict] = {}  # sym -> {qty, avg, contract}
        self._last_pos_sync = 0.0
        self._warmup_end = 0.0

    def start(self):
        """Start the trading system."""
        logger.info("TradeManager starting...")
        
        try:
            self.ib = self.ibc.connect()
            STATE.ib_connected = True
            STATE.live_mode = (not self.dry_run)
            
            self.mdb = MarketDataBus(self.ib)
            
            # Set warmup end time
            self._warmup_end = time.time() + WARMUP_DURATION_SEC
            logger.info(f"Warmup period: {WARMUP_DURATION_SEC}s (faster position sync)")
            
            # Initial position sync
            self._sync_positions(initial=True)
            
            logger.info("TradeManager started successfully")
        except Exception as e:
            logger.exception("TradeManager start failed")
            STATE.ib_connected = False
            raise

    def stop(self):
        """Stop the trading system gracefully."""
        logger.info("TradeManager stopping...")
        try:
            if self.mdb:
                # Clean up subscriptions
                pass
            
            self.ibc.disconnect()
            STATE.ib_connected = False
            logger.info("TradeManager stopped")
        except Exception as e:
            logger.warning(f"TradeManager stop error: {e}")

    def _sync_positions(self, initial: bool = False):
        """
        Sync positions from IB and update subscriptions with PRIORITY.
        
        Args:
            initial: If True, this is the first sync on startup
        """
        from contracts import looks_nontradable_symbol
        
        try:
            rows = self.ibc.fetch_positions()
            
            if initial:
                logger.info(f"Initial position sync: {len(rows)} positions found")
            
            new_syms = []
            skipped = []
            
            for r in rows:
                sym = r["symbol"]
                
                # Filter non-tradable symbols
                if looks_nontradable_symbol(sym):
                    skipped.append(sym)
                    logger.info(f"Skipping non-tradable: {sym}")
                    continue
                
                self.positions[sym] = {
                    "qty": r["qty"],
                    "avg": r["avgCost"],
                    "contract": r["contract"]
                }
                new_syms.append(sym)
                
                # Subscribe to market data with POSITION PRIORITY
                if sym not in self.mdb._subs:
                    try:
                        self.mdb.subscribe(sym, r["contract"])
                        logger.info(f"Subscribed to {sym} (POSITION priority)")
                    except Exception as e:
                        logger.warning(f"Subscribe failed for {sym}: {e}")
                else:
                    # Already subscribed, update priority to ensure positions are protected
                    try:
                        self.mdb._tracker.set_priority(sym, PRIORITY_POSITION)
                        logger.debug(f"Updated {sym} to POSITION priority")
                    except Exception as e:
                        logger.warning(f"Priority update failed for {sym}: {e}")
            
            self._last_pos_sync = time.time()
            STATE.mark_pos_sync()
            
            # Log summary
            if skipped:
                logger.info(f"Filtered {len(skipped)} non-tradable symbols: {', '.join(skipped[:5])}")
            logger.info(f"Tracking {len(self.positions)} tradable positions: {', '.join(list(self.positions.keys())[:5])}")
            
            # Build position rows for dashboard WITH EMA CALCULATIONS
            pos_rows = []
            for sym, p in self.positions.items():
                try:
                    last, _ = self.mdb.get_last(sym)
                except Exception as e:
                    logger.debug(f"get_last failed for {sym}: {e}")
                    last = None
                
                # Calculate EMAs
                ema8_val = None
                ema21_val = None
                try:
                    closes = self.mdb.get_series(sym, 50)  # Get last 50 prices
                    if len(closes) >= 21:
                        ema8_val = ema(closes, 8)
                        ema21_val = ema(closes, 21)
                        # Convert nan to None for dashboard
                        if ema8_val is not None and math.isnan(ema8_val):
                            ema8_val = None
                        if ema21_val is not None and math.isnan(ema21_val):
                            ema21_val = None
                except Exception as e:
                    logger.debug(f"EMA calc failed for {sym}: {e}")
                
                pos_rows.append({
                    "symbol": sym,
                    "qty": p["qty"],
                    "avg": p["avg"],
                    "last": last,
                    "ema8": ema8_val,
                    "ema21": ema21_val
                })
            
            STATE.positions_rows = pos_rows
            
            if rows:
                logger.debug(f"Position sync complete: {len(rows)} positions")
            
        except Exception as e:
            logger.warning(f"Position sync failed: {e}")

    def heartbeat(self):
        """
        Main heartbeat loop - called every ~1s from main.py.
        Handles periodic position syncs and price updates WITH EMA CALCULATIONS.
        """
        now = time.time()
        
        # Warmup period logic - resync every 10s for first minute
        if now < self._warmup_end:
            if now - self._last_pos_sync >= WARMUP_SYNC_INTERVAL:
                logger.debug("Warmup: resyncing positions")
                self._sync_positions()
        # Normal operation - resync every 5 minutes
        elif now - self._last_pos_sync >= POS_SYNC_SEC:
            logger.info("Periodic position resync")
            self._sync_positions()

        # Quick price update for dashboard (with EMA calculations)
        try:
            out = []
            for sym, p in self.positions.items():
                try:
                    last, _ = self.mdb.get_last(sym)
                except Exception:
                    last = None
                
                # Calculate EMAs on every heartbeat
                ema8_val = None
                ema21_val = None
                try:
                    closes = self.mdb.get_series(sym, 50)
                    if len(closes) >= 21:
                        ema8_val = ema(closes, 8)
                        ema21_val = ema(closes, 21)
                        # Convert nan to None for dashboard
                        if ema8_val is not None and math.isnan(ema8_val):
                            ema8_val = None
                        if ema21_val is not None and math.isnan(ema21_val):
                            ema21_val = None
                except Exception as e:
                    logger.debug(f"EMA calc failed for {sym}: {e}")
                
                out.append({
                    "symbol": sym,
                    "qty": p["qty"],
                    "avg": p["avg"],
                    "last": last,
                    "ema8": ema8_val,
                    "ema21": ema21_val
                })
            
            if out:
                STATE.positions_rows = out
                
        except Exception as e:
            logger.debug(f"Heartbeat pricing update failed: {e}")

    def metrics(self) -> dict:
        """
        Return current metrics for dashboard and logging.
        
        Returns:
            Dict with current system metrics
        """
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
