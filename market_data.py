# market_data.py - v15C (24/7 Extended Hours + Windows Compatible)
"""
Enhanced market data with full 24/7 coverage:
- Pre-market: 4:00 AM - 9:30 AM ET
- Regular: 9:30 AM - 4:00 PM ET
- After-hours: 4:00 PM - 8:00 PM ET
- Overnight/Weekend: Historical fallback

v15C FIXES:
- Remove unicode checkmarks for Windows compatibility
- Ensure prices flow to STATE.prices correctly
"""

import logging
import time
import math
from datetime import datetime, time as dt_time
from typing import Dict, Tuple, Optional, List
from collections import deque

from config import *
from state_bus import STATE

logger = logging.getLogger(__name__)


def ensure_ib_connected(ib):
    """Ensure IB instance is connected before any requests."""
    if ib is None:
        raise RuntimeError("IB instance is None")
    if not getattr(ib, "isConnected", lambda: False)():
        try:
            ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID)
            logger.info(f"Reconnected to IBKR on {IB_HOST}:{IB_PORT}")
        except Exception as e:
            raise RuntimeError(f"Unable to connect to IBKR: {e}")


def is_market_hours() -> Tuple[bool, str]:
    """
    Check if we're in trading hours and return market phase.
    
    Returns:
        (is_tradable, phase) where phase is:
        'pre', 'regular', 'after', 'closed'
    """
    now = datetime.now()
    current_time = now.time()
    
    # Convert config strings to time objects
    premarket_start = dt_time(*[int(x) for x in PREMARKET_START.split(':')])
    regular_start = dt_time(*[int(x) for x in REGULAR_START.split(':')])
    regular_end = dt_time(*[int(x) for x in REGULAR_END.split(':')])
    afterhours_end = dt_time(*[int(x) for x in AFTERHOURS_END.split(':')])
    
    # Weekend check
    if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return (False, 'closed')
    
    # Determine phase
    if premarket_start <= current_time < regular_start:
        return (True, 'pre')
    elif regular_start <= current_time < regular_end:
        return (True, 'regular')
    elif regular_end <= current_time < afterhours_end:
        return (True, 'after')
    else:
        return (False, 'closed')


class MarketDataBus:
    """
    Enhanced market data bus with 24/7 support.
    Handles live data during trading hours and historical fallback.
    """
    
    def __init__(self, ib, window: int = 600):
        ensure_ib_connected(ib)
        self.ib = ib
        self.tickers: Dict[str, Dict] = {}
        self.history: Dict[str, deque] = {}
        self.window = int(window)
        self._subs: Dict[str, Tuple] = {}
        self._last_hist_fetch: Dict[str, float] = {}
        self._bar_data: Dict[str, Dict] = {}
        
        # Extended hours settings
        self.extended_hours_enabled = EXTENDED_HOURS_ENABLED
        
        # Set market data type
        try:
            self.ib.reqMarketDataType(MARKET_DATA_TYPE)
            logger.info(f"Market data type set to {MARKET_DATA_TYPE} (1=LIVE)")
        except Exception as e:
            logger.warning(f"reqMarketDataType failed: {e}")
        
        # Log current market phase
        is_tradable, phase = is_market_hours()
        if is_tradable:
            logger.info(f"Market is OPEN - phase: {phase}")
        else:
            logger.info(f"Market is CLOSED - will use historical fallback")
    
    def _now(self) -> float:
        return time.time()
    
    def _record_tick(self, symbol: str, px: float, ts: float):
        """Record a price tick and update STATE."""
        self.tickers[symbol] = {"last": px, "ts": ts}
        self.history[symbol].append(px)
        
        # CRITICAL: Update STATE.prices for dashboard
        STATE.mark_tick(symbol, px)
        
        # Also update STATE.prices dict directly for dashboard API
        STATE.prices[symbol] = {'last': px, 'age': 0}
        
        self._update_bar_data(symbol, px)
    
    def _update_bar_data(self, symbol: str, price: float):
        """Update running bar data for OHLC calculations."""
        if symbol not in self._bar_data:
            self._bar_data[symbol] = {
                'highs': deque(maxlen=100),
                'lows': deque(maxlen=100),
                'closes': deque(maxlen=100),
                'volumes': deque(maxlen=100),
                'current_bar': {'high': price, 'low': price, 'volume': 0}
            }
        
        current = self._bar_data[symbol]['current_bar']
        current['high'] = max(current.get('high', price), price)
        current['low'] = min(current.get('low', price), price)
        current['volume'] = current.get('volume', 0) + 1
    
    def _finalize_bar(self, symbol: str, close_price: float):
        """Close current bar and start new one."""
        if symbol not in self._bar_data:
            return
        
        bar_data = self._bar_data[symbol]
        current = bar_data['current_bar']
        
        bar_data['highs'].append(current['high'])
        bar_data['lows'].append(current['low'])
        bar_data['closes'].append(close_price)
        bar_data['volumes'].append(current['volume'])
        
        bar_data['current_bar'] = {
            'high': close_price,
            'low': close_price,
            'volume': 0
        }
    
    def subscribe(self, symbol: str, contract):
        """
        Subscribe to real-time market data for a symbol.
        Handles extended hours automatically.
        """
        if not symbol or contract is None:
            raise ValueError("subscribe() requires symbol and a valid IB Contract")
        
        ensure_ib_connected(self.ib)
        symbol = symbol.strip().upper()
        
        self.tickers.setdefault(symbol, {"last": None, "ts": None})
        self.history.setdefault(symbol, deque(maxlen=self.window))
        
        try:
            # Subscribe with extended hours if enabled
            generic_tick_list = ""
            if self.extended_hours_enabled:
                # Request extended hours data
                generic_tick_list = "375"  # RT Volume for extended hours
            
            ticker = self.ib.reqMktData(
                contract,
                generic_tick_list,
                False,  # snapshot
                False,  # regulatorySnapshot
            )
            
            self._subs[symbol] = (contract, ticker)
            STATE.symbols_subscribed.add(symbol)
            
            # Log market phase for context
            is_tradable, phase = is_market_hours()
            phase_str = f"({phase} hours)" if is_tradable else "(closed - fallback mode)"
            
            logger.info(f"Subscribed {symbol} {phase_str}")
            
        except Exception as e:
            logger.exception(f"Subscribe failed for {symbol}: {e}")
            raise
    
    def subscribe_with_contract(self, symbol: str, contract):
        """Alias for subscribe() to support scanner usage."""
        return self.subscribe(symbol, contract)
    
    def _live_tick(self, symbol: str) -> Tuple[Optional[float], float]:
        """
        Get live tick, converting NaN to None.
        Works in pre-market, regular, and after-hours.
        """
        contract, ticker = self._subs.get(symbol, (None, None))
        if not ticker:
            raise RuntimeError(f"{symbol} not subscribed")
        
        # Try multiple price sources
        px = (
            ticker.last or
            ticker.close or
            ticker.marketPrice() or
            ticker.midpoint()
        )
        
        ts = self._now()
        
        # Convert nan to None
        if px is not None and isinstance(px, float) and math.isnan(px):
            px = None
        
        if px is None:
            # Keep last known price
            last = self.tickers[symbol].get("last")
            self.tickers[symbol] = {"last": last, "ts": ts}
            return last, ts
        
        px = float(px)
        self._record_tick(symbol, px, ts)
        return px, ts
    
    def _historical_fallback(self, symbol: str):
        """
        Fetch historical data as fallback.
        Used when markets closed or no live data available.
        
        v15C FIX: Use the ACTUAL subscribed contract, not a new one!
        """
        if not HISTORICAL_FALLBACK_ENABLED:
            return
        
        last_hist_ts = self._last_hist_fetch.get(symbol)
        now = self._now()
        
        # Respect cooldown
        if last_hist_ts and (now - last_hist_ts) < FALLBACK_COOLDOWN_SECONDS:
            return
        
        # CRITICAL FIX: Use the actual subscribed contract
        # Don't create a new one - use the one with all fields populated
        contract, ticker = self._subs.get(symbol, (None, None))
        if not contract:
            logger.warning(f"No subscribed contract for {symbol}")
            return
        
        try:
            self._last_hist_fetch[symbol] = now
            
            is_tradable, phase = is_market_hours()
            phase_str = f"({phase})" if is_tradable else "(closed)"
            
            logger.info(f"Fetching historical for {symbol} {phase_str}")
            
            # Use the EXACT contract we're subscribed to
            # This has all fields: conId, lastTradeDateOrContractMonth, etc.
            bars = self.ib.reqHistoricalData(
                contract,  # This is the key - use the subscribed contract!
                endDateTime="",
                durationStr=HISTORICAL_DURATION,
                barSizeSetting=HISTORICAL_BAR_SIZE,
                whatToShow="TRADES",
                useRTH=0,  # 0 = include extended hours
                formatDate=1,
                keepUpToDate=False,
                chartOptions=[],
            )
            
            if bars and len(bars) > 0:
                last_bar = bars[-1]
                px = float(last_bar.close)
                ts = self._now()
                self._record_tick(symbol, px, ts)
                
                # FIX: Remove unicode checkmark - use [OK] instead
                logger.info(
                    f"[OK] Historical {symbol}: ${px:.2f} from {last_bar.date}"
                )
            else:
                logger.warning(f"[WARN] No historical bars for {symbol}")
                
        except Exception as e:
            logger.warning(f"[ERROR] Historical fetch failed for {symbol}: {e}")
    
    def get_last(self, symbol: str) -> Tuple[Optional[float], float]:
        """
        Get last price with automatic fallback.
        Works 24/7 with live data when available, historical when not.
        """
        px, ts = self._live_tick(symbol)
        last_ts = self.tickers.get(symbol, {}).get("ts")
        
        # Determine if we need fallback
        needs_fallback = False
        
        # Check 1: No price at all
        if px is None or (isinstance(px, float) and math.isnan(px)):
            needs_fallback = True
        
        # Check 2: Stale quote
        elif last_ts and (self._now() - last_ts) >= FALLBACK_TRIGGER_SECONDS:
            needs_fallback = True
        
        # Check 3: Market closed
        is_tradable, phase = is_market_hours()
        if not is_tradable:
            needs_fallback = True
        
        # Execute fallback if needed
        if needs_fallback:
            self._historical_fallback(symbol)
            px = self.tickers.get(symbol, {}).get("last")
            ts = self.tickers.get(symbol, {}).get("ts") or ts
        
        # Final nan check
        if px is not None and isinstance(px, float) and math.isnan(px):
            px = None
        
        # Update STATE.prices with age calculation
        if symbol in self.tickers:
            tick_ts = self.tickers[symbol].get('ts', ts)
            age = int(self._now() - tick_ts) if tick_ts else 999
            STATE.prices[symbol] = {'last': px, 'age': age}
        
        return px, ts
    
    def get_series(self, symbol: str, n: int) -> List[float]:
        """Get recent price series."""
        return list(self.history.get(symbol, []))[-n:]
    
    def get_bar_series(self, symbol: str, n: int) -> Tuple[List[float], List[float], List[float]]:
        """
        Get OHLC bar data for indicators.
        Returns (highs, lows, closes) for last n bars.
        """
        if symbol not in self._bar_data:
            # Fallback to closes only
            closes = self.get_series(symbol, n)
            return closes, closes, closes
        
        bar_data = self._bar_data[symbol]
        highs = list(bar_data.get('highs', []))[-n:]
        lows = list(bar_data.get('lows', []))[-n:]
        closes = list(bar_data.get('closes', []))[-n:]
        
        return highs, lows, closes
    
    def snapshot(self) -> Dict:
        """
        Get snapshot of all subscribed symbols with market phase info.
        """
        now = self._now()
        is_tradable, phase = is_market_hours()
        
        out = {
            'market_phase': phase,
            'market_open': is_tradable,
            'timestamp': now,
            'symbols': {}
        }
        
        for sym, rec in self.tickers.items():
            ts = rec.get("ts")
            last = rec.get("last")
            
            # Convert nan to None
            if last is not None and isinstance(last, float) and math.isnan(last):
                last = None
            
            age_s = int(now - ts) if ts else None
            
            out['symbols'][sym] = {
                "last": last,
                "age_s": age_s,
                "stale": age_s > QUOTE_STALE_SEC if age_s else True
            }
        
        return out
    
    def get_market_phase(self) -> Dict:
        """
        Get detailed market phase information.
        """
        is_tradable, phase = is_market_hours()
        now = datetime.now()
        
        return {
            'phase': phase,
            'is_tradable': is_tradable,
            'extended_hours_enabled': self.extended_hours_enabled,
            'current_time': now.strftime('%H:%M:%S'),
            'day_of_week': now.strftime('%A'),
            'is_weekend': now.weekday() >= 5
        }
