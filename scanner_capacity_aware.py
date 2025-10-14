# strategies/breakout_scanner.py — v14A with Subscription Capacity Management
import logging
import math
import time
from typing import List, Dict, Optional
from collections import deque

from indicators import ema, true_atr, volume_sma, money_flow_index
from state_bus import STATE
from config import (
    get_scanner_capacity, 
    PRIORITY_POSITION,
    PRIORITY_SCANNER_TOP,
    PRIORITY_SCANNER_NORMAL
)

logger = logging.getLogger(__name__)


class BreakoutScanner:
    """
    Multi-factor breakout scanner with subscription capacity management.
    Automatically limits monitoring to available IB subscription slots.
    """
    
    def __init__(self, ib, market_bus, 
                 k_atr: float = 1.5, 
                 v_mult: float = 1.5,
                 mfi_threshold: float = 50.0,
                 lookback_bars: int = 20,
                 ema_fast: int = 8,
                 ema_slow: int = 21):
        """
        Args:
            ib: IB connection handle
            market_bus: MarketDataBus instance
            k_atr: ATR multiplier for breakout threshold
            v_mult: Volume multiplier for surge detection
            mfi_threshold: MFI threshold for confirmation (50 = neutral)
            lookback_bars: Bars to look back for high/low
            ema_fast: Fast EMA period
            ema_slow: Slow EMA period
        """
        self.ib = ib
        self.market_bus = market_bus
        self.k_atr = k_atr
        self.v_mult = v_mult
        self.mfi_threshold = mfi_threshold
        self.lookback = lookback_bars
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        
        self.universe: List[str] = []
        self._last_scan: Dict[str, float] = {}
        self._min_scan_interval = 5
        self._bar_data: Dict[str, Dict] = {}
        
        # Capacity tracking
        self._last_universe_symbols: set = set()
        self._universe_update_cooldown = 10  # Don't spam updates
        self._last_universe_update = 0
        
    def update_universe(self, symbols_or_contracts, position_symbols: set = None):
        """
        Update the watchlist with capacity management.
        
        Args:
            symbols_or_contracts: List of symbol strings or IB Contracts
            position_symbols: Set of symbols with open positions (always included)
        """
        if position_symbols is None:
            position_symbols = set()
        
        # Extract symbols
        new_symbols = []
        for item in symbols_or_contracts:
            if isinstance(item, str):
                sym = item.upper().strip()
                new_symbols.append(sym)
            else:
                sym = getattr(item, 'symbol', None) or getattr(item, 'localSymbol', None)
                if sym:
                    new_symbols.append(sym.upper())
        
        new_symbols = list(set(new_symbols))
        
        # Check if universe actually changed
        new_set = set(new_symbols)
        if new_set == self._last_universe_symbols:
            # No change, skip update (prevents log spam)
            return
        
        # Rate limit updates
        now = time.time()
        if now - self._last_universe_update < self._universe_update_cooldown:
            if len(new_set.symmetric_difference(self._last_universe_symbols)) < 3:
                # Minor change and too soon, skip
                return
        
        # Calculate capacity
        capacity = get_scanner_capacity(len(position_symbols))
        
        # Separate positions from scanner symbols
        position_list = [s for s in new_symbols if s in position_symbols]
        scanner_list = [s for s in new_symbols if s not in position_symbols]
        
        # Limit scanner symbols to capacity
        if len(scanner_list) > capacity:
            logger.warning(
                f"Scanner wants {len(scanner_list)} symbols but capacity is {capacity}. "
                f"Limiting to top {capacity} opportunities."
            )
            scanner_list = scanner_list[:capacity]
        
        # Final universe: positions + limited scanner
        self.universe = position_list + scanner_list
        self._last_universe_symbols = set(self.universe)
        self._last_universe_update = now
        
        logger.info(
            f"BreakoutScanner universe updated: {len(self.universe)} symbols "
            f"(positions={len(position_list)}, scanner={len(scanner_list)}, "
            f"capacity={capacity})"
        )
    
    def tick(self, symbol: str, price: float):
        """
        Called on every price tick for subscribed symbols.
        Updates internal bar data structures.
        """
        if symbol not in self._bar_data:
            self._bar_data[symbol] = {
                'highs': deque(maxlen=100),
                'lows': deque(maxlen=100),
                'closes': deque(maxlen=100),
                'volumes': deque(maxlen=100),
                'current_bar': {'high': price, 'low': price, 'open': price, 'volume': 0}
            }
        
        bar_data = self._bar_data[symbol]
        current = bar_data['current_bar']
        
        current['high'] = max(current['high'], price)
        current['low'] = min(current['low'], price)
        current['volume'] += 1
    
    def _finalize_bar(self, symbol: str, close_price: float):
        """Close the current bar and start a new one."""
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
            'open': close_price, 
            'volume': 0
        }
    
    def _check_atr_breakout(self, symbol: str, price: float) -> Optional[str]:
        """Check if price breaks prior high/low by k*ATR."""
        if symbol not in self._bar_data:
            return None
        
        bar_data = self._bar_data[symbol]
        highs = list(bar_data['highs'])
        lows = list(bar_data['lows'])
        closes = list(bar_data['closes'])
        
        if len(closes) < self.lookback + 14:
            return None
        
        atr = true_atr(highs, lows, closes, period=14)
        if math.isnan(atr):
            return None
        
        recent_highs = highs[-self.lookback:]
        recent_lows = lows[-self.lookback:]
        
        prior_high = max(recent_highs) if recent_highs else 0
        prior_low = min(recent_lows) if recent_lows else float('inf')
        
        if price > prior_high + self.k_atr * atr:
            return 'UP'
        elif price < prior_low - self.k_atr * atr:
            return 'DOWN'
        
        return None
    
    def _check_volume_surge(self, symbol: str) -> bool:
        """Check if current volume exceeds average by v_mult."""
        if symbol not in self._bar_data:
            return False
        
        bar_data = self._bar_data[symbol]
        volumes = list(bar_data['volumes'])
        
        if len(volumes) < 20:
            return False
        
        vol_avg = volume_sma(volumes, period=20)
        if math.isnan(vol_avg):
            return False
        
        current_vol = bar_data['current_bar']['volume']
        return current_vol > vol_avg * self.v_mult
    
    def _check_ema_trend(self, symbol: str, direction: str) -> bool:
        """Check EMA trend alignment."""
        if symbol not in self._bar_data:
            return False
        
        bar_data = self._bar_data[symbol]
        closes = list(bar_data['closes'])
        
        if len(closes) < max(self.ema_fast, self.ema_slow) * 2:
            return False
        
        fast = ema(closes, self.ema_fast)
        slow = ema(closes, self.ema_slow)
        
        if math.isnan(fast) or math.isnan(slow):
            return False
        
        if direction == 'UP':
            return fast > slow
        elif direction == 'DOWN':
            return fast < slow
        
        return False
    
    def _check_mfi(self, symbol: str, direction: str) -> bool:
        """Check Money Flow Index for confirmation."""
        if symbol not in self._bar_data:
            return True
        
        bar_data = self._bar_data[symbol]
        highs = list(bar_data['highs'])
        lows = list(bar_data['lows'])
        closes = list(bar_data['closes'])
        volumes = list(bar_data['volumes'])
        
        if len(closes) < 15:
            return True
        
        mfi = money_flow_index(highs, lows, closes, volumes, period=14)
        
        if math.isnan(mfi):
            return True
        
        if direction == 'UP':
            return mfi > self.mfi_threshold
        elif direction == 'DOWN':
            return mfi < self.mfi_threshold
        
        return True
    
    def _calculate_score(self, symbol: str, price: float, atr: float, direction: str) -> float:
        """Calculate breakout strength score."""
        if math.isnan(atr) or atr == 0:
            return 0.0
        
        bar_data = self._bar_data.get(symbol, {})
        closes = list(bar_data.get('closes', []))
        
        if not closes:
            return 0.0
        
        slow = ema(closes, self.ema_slow)
        if math.isnan(slow):
            return 0.0
        
        distance = abs(price - slow)
        score = distance / atr
        
        return float(score)
    
    def scan(self, position_symbols: set = None) -> List[Dict]:
        """
        Scan all symbols in universe for breakouts.
        
        Args:
            position_symbols: Set of symbols with open positions
        
        Returns:
            List of breakout signals with scores
        """
        if position_symbols is None:
            position_symbols = set()
        
        now = time.time()
        results = []
        
        for symbol in self.universe:
            # Rate limit per symbol
            last_scan = self._last_scan.get(symbol, 0)
            if now - last_scan < self._min_scan_interval:
                continue
            
            try:
                # Get current price
                price, ts = self.market_bus.get_last(symbol)
                if price is None or math.isnan(price):
                    continue
                
                # Check ATR breakout
                atr_direction = self._check_atr_breakout(symbol, price)
                if not atr_direction:
                    continue
                
                # Check volume surge
                if not self._check_volume_surge(symbol):
                    continue
                
                # Check EMA trend
                if not self._check_ema_trend(symbol, atr_direction):
                    continue
                
                # Check MFI
                if not self._check_mfi(symbol, atr_direction):
                    continue
                
                # All conditions met - calculate score
                bar_data = self._bar_data[symbol]
                closes = list(bar_data['closes'])
                highs = list(bar_data['highs'])
                lows = list(bar_data['lows'])
                
                atr = true_atr(highs, lows, closes, period=14)
                score = self._calculate_score(symbol, price, atr, atr_direction)
                
                label = f"ATR:{self.k_atr} VOL:{self.v_mult}x EMA:{self.ema_fast}/{self.ema_slow}"
                
                # Mark if this is a position
                is_position = symbol in position_symbols
                
                results.append({
                    'symbol': symbol,
                    'direction': atr_direction,
                    'score': score,
                    'last': price,
                    'label': label,
                    'atr': atr,
                    'timestamp': now,
                    'is_position': is_position
                })
                
                self._last_scan[symbol] = now
                logger.info(
                    f"Breakout signal: {symbol} {atr_direction} score={score:.2f}"
                    f"{' [POSITION]' if is_position else ''}"
                )
                
            except Exception as e:
                logger.warning(f"Scan error for {symbol}: {e}")
                continue
        
        # Sort by score descending
        results.sort(key=lambda x: x['score'], reverse=True)
        
        # Update STATE for dashboard
        STATE.breakouts = results
        
        return results
    
    def get_bar_data(self, symbol: str) -> Optional[Dict]:
        """Get bar data for a symbol (for debugging/analysis)."""
        return self._bar_data.get(symbol)
    
    def get_capacity_info(self, position_count: int) -> dict:
        """Get current capacity information."""
        capacity = get_scanner_capacity(position_count)
        return {
            "positions": position_count,
            "capacity": capacity,
            "universe_size": len(self.universe),
            "over_capacity": len(self.universe) > (position_count + capacity)
        }
