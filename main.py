#!/usr/bin/env python3
# main.py - QTrade v15B with scanner in main thread
import logging
import sys
import time
import signal
from datetime import datetime, UTC
from typing import Set

from config import (
    ENV, DRY_RUN, HEARTBEAT_SEC,
    DASHBOARD_HOST, DASHBOARD_PORT,
    LOG_LEVEL,
    IB_MAX_SUBSCRIPTIONS,
    SCANNER_MAX_WARN_THRESHOLD,
)
from state_bus import STATE
from trade_manager import TradeManager
from dashboard_server import run_dashboard
from scanner_coordinator import SubscriptionManager
import threading

# Logging setup
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("qtrade.log")
    ]
)
logger = logging.getLogger(__name__)

# Globals
tm: TradeManager = None
subscription_manager: SubscriptionManager = None
running = True

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    global running
    logger.info("Shutdown signal received...")
    running = False

def get_position_symbols(ib) -> Set[str]:
    """Get current position symbols from IB (excluding non-tradable)."""
    position_symbols = set()
    
    # Non-tradable filters
    filters = ['Q', 'W', '.CVR', '.OLD', '.WS', 'REF']
    
    try:
        positions = ib.positions()
        for pos in positions:
            if pos.position != 0:  # Active position
                # Handle both stocks and futures
                symbol = pos.contract.localSymbol or pos.contract.symbol
                if symbol:
                    symbol_upper = symbol.upper()
                    
                    # Skip non-tradable symbols (but allow futures)
                    sec_type = pos.contract.secType
                    skip = False
                    
                    if sec_type != 'FUT':  # Don't filter futures
                        for filt in filters:
                            if filt in symbol_upper:
                                skip = True
                                break
                    
                    if not skip:
                        position_symbols.add(symbol_upper)
                        
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
    
    return position_symbols

def start_dashboard_thread():
    """Start dashboard in background thread."""
    dashboard_thread = threading.Thread(
        target=run_dashboard,
        daemon=True,
        name="DashboardThread"
    )
    dashboard_thread.start()
    logger.info(f"Dashboard started at http://{DASHBOARD_HOST}:{DASHBOARD_PORT}")

def main():
    global tm, subscription_manager, running
    
    logger.info("=" * 60)
    logger.info(f"QTrade v15B Professional Multi-Asset System")
    logger.info(f"ENV={ENV} | DRY_RUN={DRY_RUN}")
    logger.info(f"Dashboard: http://{DASHBOARD_HOST}:{DASHBOARD_PORT}")
    logger.info(f"Subscription limit: {IB_MAX_SUBSCRIPTIONS}")
    logger.info("=" * 60)
    
    # Signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize TradeManager
    logger.info("Initializing TradeManager...")
    tm = TradeManager(dry_run=bool(DRY_RUN))
    
    try:
        tm.start()
        logger.info("✓ TradeManager started")
    except Exception as e:
        logger.exception("✗ TradeManager failed to start")
        sys.exit(1)
    
    # Start dashboard in background thread
    try:
        start_dashboard_thread()
        time.sleep(1)  # Give dashboard a moment to start
        logger.info("✓ Dashboard started")
    except Exception as e:
        logger.warning(f"Dashboard failed to start: {e}")
    
    # Initialize Subscription Manager (NO BACKGROUND THREAD)
    logger.info("Initializing v15B Subscription Manager...")
    try:
        subscription_manager = SubscriptionManager(
            ib=tm.ib,
            market_bus=tm.mdb
        )
        subscription_manager.start()
        logger.info("✓ Subscription Manager started (main thread mode)")
        logger.info("  - Professional breakout scanner active")
        logger.info("  - Smart 50-subscription management active")
    except Exception as e:
        logger.warning(f"Subscription Manager initialization failed: {e}")
        subscription_manager = None
    
    # Update market phase in STATE
    try:
        phase_info = tm.mdb.get_market_phase()
        STATE.market_phase = phase_info['phase']
        logger.info(f"Market phase: {phase_info['phase']} (tradable: {phase_info['is_tradable']})")
    except Exception as e:
        logger.warning(f"Could not determine market phase: {e}")
    
    # Main loop
    logger.info("=" * 60)
    logger.info("Main loop starting...")
    logger.info("=" * 60)
    
    hb_seq = 0
    started_at = time.time()
    last_hb_emit = 0
    last_scanner_tick = 0
    HB_EMIT_INTERVAL = 60  # Emit heartbeat log every 60s
    SCANNER_TICK_INTERVAL = 10  # Call scanner tick every 10s
    
    try:
        while running:
            loop_start = time.time()
            
            # Get current positions for tracking
            position_symbols = get_position_symbols(tm.ib)
            
            # TradeManager heartbeat
            try:
                tm.heartbeat()
            except Exception as e:
                logger.warning(f"TradeManager heartbeat failed: {e}")
            
            # Scanner tick (every 10 seconds) - RUNS IN MAIN THREAD
            now = time.time()
            if subscription_manager and (now - last_scanner_tick >= SCANNER_TICK_INTERVAL):
                try:
                    subscription_manager.tick()
                    last_scanner_tick = now
                except Exception as e:
                    logger.warning(f"Scanner tick failed: {e}")
            
            # Update market phase periodically
            try:
                phase_info = tm.mdb.get_market_phase()
                STATE.market_phase = phase_info['phase']
            except Exception as e:
                pass  # Don't spam logs
            
            # Emit heartbeat log periodically
            if now - last_hb_emit >= HB_EMIT_INTERVAL:
                hb_seq += 1
                uptime = int(now - started_at)
                
                # Calculate ages
                tick_age = int(now - STATE.last_tick_at) if STATE.last_tick_at else None
                pos_age = int(now - STATE.last_pos_sync_at) if STATE.last_pos_sync_at else None
                
                # Get subscription stats
                if subscription_manager:
                    status = subscription_manager.get_status()
                    sub_count = status['total']
                    sub_breakdown = f"pos={status['positions']} fut={status['futures']} scan={status['scanner']}"
                else:
                    sub_count = len(tm.mdb._subs)
                    sub_breakdown = "legacy"
                
                # Update heartbeat in STATE
                STATE.update_heartbeat(
                    seq=hb_seq,
                    ts=datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
                    uptime_s=uptime,
                    last_tick_age_s=tick_age,
                    last_pos_sync_age_s=pos_age,
                    subs=sub_count,
                    ib_connected=STATE.ib_connected,
                    live_mode=STATE.live_mode,
                    dry_run=STATE.dry_run,
                    loop_lag_ms=STATE.loop_lag_ms,
                    prices=len(STATE.prices)
                )
                
                # Get scanner stats
                scanner_stats = ""
                if subscription_manager:
                    scanner_results = getattr(STATE, 'scanner_results', [])
                    scanner_stats = f" | scanner={len(scanner_results)}"
                
                # Build subscription status indicator
                if sub_count > IB_MAX_SUBSCRIPTIONS:
                    sub_status = "[OVER!]"
                elif sub_count >= SCANNER_MAX_WARN_THRESHOLD:
                    sub_status = "[NEAR]"
                else:
                    sub_status = "[OK]"
                
                # Get market phase
                market_phase = getattr(STATE, 'market_phase', 'unknown')
                
                logger.info(
                    f"HB #{hb_seq} | up={uptime//3600:02d}:{(uptime%3600)//60:02d}:{uptime%60:02d} | "
                    f"phase={market_phase} | "
                    f"subs={sub_count}/{IB_MAX_SUBSCRIPTIONS} {sub_status} ({sub_breakdown}) | "
                    f"pos={len(position_symbols)} | "
                    f"prices={len(STATE.prices)} | "
                    f"tick_age={tick_age}s | pos_age={pos_age}s | "
                    f"ib={STATE.ib_connected} | "
                    f"lag={STATE.loop_lag_ms}ms{scanner_stats}"
                )
                
                last_hb_emit = now
            
            # Calculate loop lag
            loop_elapsed = time.time() - loop_start
            STATE.loop_lag_ms = int(loop_elapsed * 1000)
            
            # Sleep to maintain interval
            sleep_time = max(0, HEARTBEAT_SEC - loop_elapsed)
            time.sleep(sleep_time)
            
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.exception("Main loop crashed")
    finally:
        logger.info("=" * 60)
        logger.info("Shutting down...")
        logger.info("=" * 60)
        
        if subscription_manager:
            subscription_manager.stop()
            logger.info("✓ Subscription Manager stopped")
        
        if tm:
            tm.stop()
            logger.info("✓ TradeManager stopped")
        
        logger.info("Shutdown complete")

if __name__ == "__main__":
    main()
