# trade_manager.py — v15D FIX: Add exchange to futures contracts before subscribing
import logging, time, math
from typing import Dict, List, Tuple
from state_bus import STATE
from ib_client import IBClient, Contract
from market_data import MarketDataBus
from indicators import ema
from config import PRIORITY_POSITION, FUTURES_EXCHANGES

logger = logging.getLogger(__name__)

POS_SYNC_SEC = 300
WARMUP_DURATION_SEC = 60
WARMUP_SYNC_INTERVAL = 10

class TradeManager:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.ibc = IBClient()
        self.ib = None
        self.mdb: MarketDataBus = None
        self.positions: Dict[str, Dict] = {}
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
            
            self._warmup_end = time.time() + WARMUP_DURATION_SEC
            logger.info(f"Warmup period: {WARMUP_DURATION_SEC}s (faster position sync)")
            
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
                pass
            
            self.ibc.disconnect()
            STATE.ib_connected = False
            logger.info("TradeManager stopped")
        except Exception as e:
            logger.warning(f"TradeManager stop error: {e}")

    def _fix_futures_contract(self, contract):
        """
        v15D FIX: Add exchange to futures contracts if missing.
        IB positions() sometimes returns contracts without exchange field.
        """
        from ib_insync import Future
        
        sec_type = getattr(contract, 'secType', None)
        
        if sec_type != 'FUT':
            return contract  # Not a future, return as-is
        
        # Check if exchange already set
        exchange = getattr(contract, 'exchange', None)
        primary_exchange = getattr(contract, 'primaryExchange', None)
        
        if exchange and exchange != '':
            return contract  # Already has exchange
        
        # Get symbol and look up exchange
        symbol = getattr(contract, 'symbol', '')
        correct_exchange = FUTURES_EXCHANGES.get(symbol)
        
        if not correct_exchange:
            logger.warning(f"No exchange mapping for futures {symbol}")
            return contract
        
        # Create new contract with exchange
        fixed_contract = Future(
            symbol=symbol,
            exchange=correct_exchange,
            currency=getattr(contract, 'currency', 'USD'),
            lastTradeDateOrContractMonth=getattr(contract, 'lastTradeDateOrContractMonth', ''),
            multiplier=getattr(contract, 'multiplier', ''),
            localSymbol=getattr(contract, 'localSymbol', ''),
        )
        
        # Preserve conId if available
        if hasattr(contract, 'conId'):
            fixed_contract.conId = contract.conId
        
        logger.info(f"[FIX] Added exchange={correct_exchange} to {symbol} contract")
        return fixed_contract

    def _sync_positions(self, initial: bool = False):
        """Sync positions from IB and update subscriptions."""
        from contracts import looks_nontradable_symbol, get_contract_multiplier
        
        try:
            rows = self.ibc.fetch_positions()
            
            if initial:
                logger.info(f"Initial position sync: {len(rows)} positions found")
            
            new_syms = []
            skipped = []
            
            for r in rows:
                sym = r["symbol"]
                
                if looks_nontradable_symbol(sym):
                    skipped.append(sym)
                    logger.info(f"Skipping non-tradable: {sym}")
                    continue
                
                multiplier = get_contract_multiplier(r["contract"])
                
                # Store position data
                self.positions[sym] = {
                    "qty": r["qty"],
                    "avg": r["avgCost"],
                    "contract": r["contract"],
                    "sec_type": r.get("sec_type", "STK"),
                    "local_symbol": r.get("local_symbol", sym),
                    "multiplier": multiplier,
                }
                new_syms.append(sym)
                
                # Subscribe if not already subscribed
                if sym not in self.mdb._subs:
                    try:
                        # v15D FIX: Fix futures contract BEFORE subscribing!
                        fixed_contract = self._fix_futures_contract(r["contract"])
                        
                        self.mdb.subscribe(sym, fixed_contract)
                        logger.info(f"Subscribed to {sym} (POSITION priority)")
                    except Exception as e:
                        logger.warning(f"Subscribe failed for {sym}: {e}")
            
            self._last_pos_sync = time.time()
            STATE.mark_pos_sync()
            
            if skipped:
                logger.info(f"Filtered {len(skipped)} non-tradable symbols")
            logger.info(f"Tracking {len(self.positions)} tradable positions: {', '.join(list(self.positions.keys()))}")
            
            # Build position rows for STATE/dashboard
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
                    closes = self.mdb.get_series(sym, 50)
                    if len(closes) >= 21:
                        ema8_val = ema(closes, 8)
                        ema21_val = ema(closes, 21)
                        if ema8_val is not None and math.isnan(ema8_val):
                            ema8_val = None
                        if ema21_val is not None and math.isnan(ema21_val):
                            ema21_val = None
                except Exception as e:
                    logger.debug(f"EMA calc failed for {sym}: {e}")
                
                # Adjust avg cost for display
                avg_display = p["avg"]
                if p["sec_type"] == "FUT" and p["multiplier"] > 1:
                    avg_display = p["avg"] / p["multiplier"]
                
                pos_rows.append({
                    "symbol": sym,
                    "qty": p["qty"],
                    "avg": avg_display,
                    "last": last,
                    "ema8": ema8_val,
                    "ema21": ema21_val,
                    "sec_type": p["sec_type"],
                    "multiplier": p["multiplier"],
                    "local_symbol": p["local_symbol"],
                    "contract": p["contract"],
                })
            
            STATE.positions_rows = pos_rows
            
            if rows:
                logger.debug(f"Position sync complete: {len(rows)} positions")
            
        except Exception as e:
            logger.warning(f"Position sync failed: {e}")

    def heartbeat(self):
        """Main heartbeat loop."""
        now = time.time()
        
        # Warmup period logic
        if now < self._warmup_end:
            if now - self._last_pos_sync >= WARMUP_SYNC_INTERVAL:
                logger.debug("Warmup: resyncing positions")
                self._sync_positions()
        elif now - self._last_pos_sync >= POS_SYNC_SEC:
            logger.info("Periodic position resync")
            self._sync_positions()

        # Quick price update
        try:
            out = []
            for sym, p in self.positions.items():
                try:
                    last, _ = self.mdb.get_last(sym)
                except Exception:
                    last = None
                
                ema8_val = None
                ema21_val = None
                try:
                    closes = self.mdb.get_series(sym, 50)
                    if len(closes) >= 21:
                        ema8_val = ema(closes, 8)
                        ema21_val = ema(closes, 21)
                        if ema8_val is not None and math.isnan(ema8_val):
                            ema8_val = None
                        if ema21_val is not None and math.isnan(ema21_val):
                            ema21_val = None
                except Exception as e:
                    logger.debug(f"EMA calc failed for {sym}: {e}")
                
                avg_display = p["avg"]
                if p["sec_type"] == "FUT" and p["multiplier"] > 1:
                    avg_display = p["avg"] / p["multiplier"]
                
                out.append({
                    "symbol": sym,
                    "qty": p["qty"],
                    "avg": avg_display,
                    "last": last,
                    "ema8": ema8_val,
                    "ema21": ema21_val,
                    "sec_type": p["sec_type"],
                    "multiplier": p["multiplier"],
                    "local_symbol": p["local_symbol"],
                    "contract": p["contract"],
                })
            
            if out:
                STATE.positions_rows = out
                
        except Exception as e:
            logger.debug(f"Heartbeat pricing update failed: {e}")

    def metrics(self) -> dict:
        """Return current metrics."""
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
