# scanner.py - Market scanner with subscription limit management (FIXED)
import logging, math, time
from typing import List, Dict

from ib_insync import ScannerSubscription
from indicators import ema, true_atr
from contracts import build_and_qualify
from state_bus import STATE
from config import (
    MAX_IB_SUBSCRIPTIONS,
    PRIORITY_SCANNER_NORMAL,
    get_scanner_capacity
)

logger = logging.getLogger(__name__)

class MarketScanner:
    """
    Market scanner using IB's scanner API with subscription capacity management.
    """
    
    def __init__(self, ib, md_bus, publish_cb=None, interval_sec=60, top_n=15, k_atr=1.5):
        self.ib = ib
        self.md = md_bus
        self.publish = publish_cb or (lambda rows: None)
        self.interval = interval_sec
        self.top_n = top_n
        self._last_scan = 0
        self.k_atr = k_atr
        self._alert_id = 100000

    def _alert(self, symbol, direction, label):
        self._alert_id += 1
        alerts = STATE.get().get("alerts", [])
        alerts.append({
            "id": self._alert_id, 
            "text": f"{symbol} {direction} ({label})", 
            "kind": "up" if direction=='UP' else "down"
        })
        STATE.update(alerts=alerts)

    def _get_position_symbols(self) -> set:
        """Get current position symbols to reserve capacity."""
        position_symbols = set()
        try:
            positions = self.ib.positions()
            for pos in positions:
                if pos.position != 0:
                    symbol = pos.contract.symbol or pos.contract.localSymbol
                    if symbol:
                        position_symbols.add(symbol.upper())
        except Exception as e:
            logger.warning(f"Error getting positions: {e}")
        return position_symbols

    def _scan_once(self) -> List[Dict]:
        """Run scan with capacity management."""
        cands = []
        
        # Get current capacity
        position_symbols = self._get_position_symbols()
        capacity = get_scanner_capacity(len(position_symbols))
        current_subs = len(self.md._subs)
        available_slots = MAX_IB_SUBSCRIPTIONS - current_subs
        
        logger.info(
            f"MarketScanner starting: capacity={capacity}, "
            f"current_subs={current_subs}, available={available_slots}"
        )
        
        if available_slots <= 0:
            logger.warning("No subscription slots available for market scanner")
            return []

        def process_scan(instr, loc, code, label):
            try:
                sub = ScannerSubscription(instrument=instr, locationCode=loc, scanCode=code)
                rows = self.ib.reqScannerData(sub)
                
                subscribed_count = 0
                
                for r in rows:
                    # Check capacity before each subscription
                    current_subs = len(self.md._subs)
                    if current_subs >= MAX_IB_SUBSCRIPTIONS:
                        logger.warning(f"Hit subscription limit during {label} scan")
                        break
                    
                    sym = getattr(r.contractDetails.contract, "symbol", None)
                    if not sym:
                        continue
                    
                    qc = build_and_qualify(self.ib, sym)
                    if not qc:
                        continue
                    
                    key = sym.upper()
                    
                    # Subscribe if not already subscribed and under limit
                    if key not in self.md._subs:
                        try:
                            self.md.subscribe(key, qc, priority=PRIORITY_SCANNER_NORMAL)
                            subscribed_count += 1
                            logger.debug(f"Subscribed to {key} from {label}")
                        except Exception as e:
                            logger.warning(f"Failed to subscribe to {key}: {e}")
                            continue
                    
                    # Analyze for breakout signals
                    try:
                        closes = self.md.get_series(key, 200)
                        highs, lows, bar_closes = self.md.get_bar_series(key, 60)
                        
                        if len(closes) < 50 or len(bar_closes) < 15:
                            continue
                        
                        last = closes[-1]
                        f = ema(closes, 8)
                        s = ema(closes, 21)
                        atr = true_atr(highs, lows, bar_closes, 14)
                        
                        if any(map(lambda x: x != x, [f, s, atr])):
                            continue
                        
                        signal = None
                        score = None
                        
                        if last > s + self.k_atr * atr and f > s:
                            signal = "UP"
                            score = (last - s) / max(atr, 1e-6)
                        elif last < s - self.k_atr * atr and f < s:
                            signal = "DOWN"
                            score = (s - last) / max(atr, 1e-6)
                        
                        if signal:
                            cands.append({
                                "symbol": key, 
                                "label": label, 
                                "signal": signal, 
                                "score": float(score), 
                                "last": last, 
                                "atr": atr
                            })
                            self._alert(key, signal, label)
                    
                    except Exception as e:
                        logger.debug(f"Analysis failed for {key}: {e}")
                        continue
                
                if subscribed_count > 0:
                    logger.info(f"{label}: subscribed to {subscribed_count} new symbols")
                    
            except Exception as e:
                logger.exception(f"Scanner failed: {label}")

        # Run scans
        process_scan("STK", "STK.US.MAJOR", "TOP_PERC_GAIN", "STK_GAIN")
        process_scan("STK", "STK.US.MAJOR", "TOP_PERC_LOSE", "STK_LOSE")
        process_scan("FUT", "FUT.US", "HOT_BY_VOLUME", "FUT_VOL")

        # Sort by score and limit to top_n
        cands.sort(key=lambda x: x["score"], reverse=True)
        return cands[:self.top_n]

    def tick(self):
        """Run scan at specified interval."""
        now = time.time()
        if now - self._last_scan < self.interval:
            return
        
        self._last_scan = now
        logger.info("MarketScanner: starting scan...")
        
        rows = self._scan_once()
        
        logger.info(f"MarketScanner: found {len(rows)} opportunities")
        
        try:
            self.publish(rows)
        except Exception as e:
            logger.exception("MarketScanner publish failed")
