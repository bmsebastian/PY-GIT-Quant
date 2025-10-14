# market_data.py - v15D FIX: Add missing exchange to futures contracts
"""
Enhanced market data with full 24/7 coverage.

v15D FIX: Position contracts sometimes missing exchange field.
We must add it before requesting historical data.
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
    """Check if we're in trading hours and return market phase."""
    now = datetime.now()
    current_time = now.time()
    
    premarket_start = dt_time(*[int(x) for x in PREMARKET_START.split(':')])
    regular_start = dt_time(*[int(x) for x in REGULAR_START.split(':')])
    regular_end = dt_time(*[int(x) for x in REGULAR_END.split(':')])
    afterhours_end = dt_time(*[int(x) for x in AFTERHOURS_END.split(':')])
    
    if now.weekday() >= 5:
        return (False, 'closed')
    
    if premarket_start <= current_time < regular_start:
        return (True, 'pre')
    elif regular_start <= current_time < regular_end:
        return (True, 'regular')
    elif regular_end <= current_time < afterhours_end:
        return (True, 'after')
    else:
        return (False, 'closed')


class MarketDataBus:
    """Enhanced market data bus with 24/7 support."""
    
    def __init__(self, ib, window: int = 600):
        ensure_ib_connected(ib)
        self.ib = ib
        self.tickers: Dict[str, Dict] = {}
        self.history: Dict[str, deque] = {}
        self.window = int(window)
        self._subs: Dict[str, Tuple] = {}
        self._last_hist_fetch: Dict[str, float] = {}
        self._bar_data: Dict[str, Dict] = {}
        
        self.extended_hours_enabled = EXTENDED_HOURS_ENABLED
        
        try:
            self.ib.reqMarketDataType(MARKET_DATA_TYPE)
            logger.info(f"Market data type set to {MARKET_DATA_TYPE} (1=LIVE)")
        except Exception as e:
            logger.warning(f"reqMarketDataType failed: {e}")
        
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
        STATE.mark_tick(symbol, px)
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
        """Subscribe to real-time market data."""
        if not symbol or contract is None:
            raise ValueError("subscribe() requires symbol and a valid IB Contract")
        
        ensure_ib_connected(self.ib)
        symbol = symbol.strip().upper()
        
        self.tickers.setdefault(symbol, {"last": None, "ts": None})
        self.history.setdefault(symbol, deque(maxlen=self.window))
        
        try:
            generic_tick_list = ""
            if self.extended_hours_enabled:
                generic_tick_list = "375"
            
            ticker = self.ib.reqMktData(
                contract,
                generic_tick_list,
                False,
                False,
            )
            
            self._subs[symbol] = (contract, ticker)
            STATE.symbols_subscribed.add(symbol)
            
            is_tradable, phase = is_market_hours()
            phase_str = f"({phase} hours)" if is_tradable else "(closed - fallback mode)"
            
            logger.info(f"Subscribed {symbol} {phase_str}")
            
        except Exception as e:
            logger.exception(f"Subscribe failed for {symbol}: {e}")
            raise
    
    def subscribe_with_contract(self, symbol: str, contract):
        """Alias for subscribe()."""
        return self.subscribe(symbol, contract)
    
    def _live_tick(self, symbol: str) -> Tuple[Optional[float], float]:
        """Get live tick, converting NaN to None."""
        contract, ticker = self._subs.get(symbol, (None, None))
        if not ticker:
            raise RuntimeError(f"{symbol} not subscribed")
        
        px = (
            ticker.last or
            ticker.close or
            ticker.marketPrice() or
            ticker.midpoint()
        )
        
        ts = self._now()
        
        if px is not None and isinstance(px, float) and math.isnan(px):
            px = None
        
        if px is None:
            last = self.tickers[symbol].get("last")
            self.tickers[symbol] = {"last": last, "ts": ts}
            return last, ts
        
        px = float(px)
        self._record_tick(symbol, px, ts)
        return px, ts
    
    def _fix_contract_exchange(self, contract):
        """
        v15D FIX: Ensure contract has exchange field.
        IB positions sometimes return contracts without exchange,
        but historical data API requires it!
        """
        # Check if exchange is missing
        exchange = getattr(contract, 'exchange', None)
        primary_exchange = getattr(contract, 'primaryExchange', None)
        
        # If both missing, we need to add it
        if not exchange and not primary_exchange:
            sec_type = getattr(contract, 'secType', None)
            
            if sec_type == 'FUT':
                # Map futures by symbol to exchange
                symbol = getattr(contract, 'symbol', '')
                
                exchange_map = {
                    'NQ': 'CME',
                    'ES': 'CME',
                    'RTY': 'CME',
                    'YM': 'CBOT',
                    'CL': 'NYMEX',
                    'GC': 'COMEX',
                    'ZB': 'CBOT',
                }
                
                correct_exchange = exchange_map.get(symbol)
                
                if correct_exchange:
                    # Create new contract with exchange
                    from ib_insync import Future
                    
                    fixed_contract = Future(
                        symbol=symbol,
                        exchange=correct_exchange,
                        currency=getattr(contract, 'currency', 'USD'),
                        lastTradeDateOrContractMonth=getattr(contract, 'lastTradeDateOrContractMonth', ''),
                        multiplier=getattr(contract, 'multiplier', ''),
                        localSymbol=getattr(contract, 'localSymbol', ''),
                    )
                    
                    # Copy conId if available
                    if hasattr(contract, 'conId'):
                        fixed_contract.conId = contract.conId
                    
                    logger.info(f"[FIX] Added exchange={correct_exchange} to {symbol} contract")
                    return fixed_contract
        
        # Exchange exists or we're not a future - return as-is
        return contract
    
    def _historical_fallback(self, symbol: str):
        """
        Fetch historical data as fallback.
        
        v15D FIX: Ensure contract has exchange before requesting!
        """
        if not HISTORICAL_FALLBACK_ENABLED:
            return
        
        last_hist_ts = self._last_hist_fetch.get(symbol)
        now = self._now()
        
        if last_hist_ts and (now - last_hist_ts) < FALLBACK_COOLDOWN_SECONDS:
            return
        
        # Get the subscribed contract
        contract, ticker = self._subs.get(symbol, (None, None))
        if not contract:
            logger.warning(f"No subscribed contract for {symbol}")
            return
        
        try:
            self._last_hist_fetch[symbol] = now
            
            is_tradable, phase = is_market_hours()
            phase_str = f"({phase})" if is_tradable else "(closed)"
            
            logger.info(f"Fetching historical for {symbol} {phase_str}")
            
            # v15D FIX: Ensure contract has exchange!
            fixed_contract = self._fix_contract_exchange(contract)
            
            # Use the fixed contract with exchange
            bars = self.ib.reqHistoricalData(
                fixed_contract,
                endDateTime="",
                durationStr=HISTORICAL_DURATION,
                barSizeSetting=HISTORICAL_BAR_SIZE,
                whatToShow="TRADES",
                useRTH=0,
                formatDate=1,
                keepUpToDate=False,
                chartOptions=[],
            )
            
            if bars and len(bars) > 0:
                last_bar = bars[-1]
                px = float(last_bar.close)
                ts = self._now()
                self._record_tick(symbol, px, ts)
                
                logger.info(
                    f"[OK] Historical {symbol}: ${px:.2f} from {last_bar.date}"
                )
            else:
                logger.warning(f"[WARN] No historical bars for {symbol}")
                
        except Exception as e:
            logger.warning(f"[ERROR] Historical fetch failed for {symbol}: {e}")
    
    def get_last(self, symbol: str) -> Tuple[Optional[float], float]:
        """Get last price with automatic fallback."""
        px, ts = self._live_tick(symbol)
        last_ts = self.tickers.get(symbol, {}).get("ts")
        
        needs_fallback = False
        
        if px is None or (isinstance(px, float) and math.isnan(px)):
            needs_fallback = True
        elif last_ts and (self._now() - last_ts) >= FALLBACK_TRIGGER_SECONDS:
            needs_fallback = True
        
        is_tradable, phase = is_market_hours()
        if not is_tradable:
            needs_fallback = True
        
        if needs_fallback:
            self._historical_fallback(symbol)
            px = self.tickers.get(symbol, {}).get("last")
            ts = self.tickers.get(symbol, {}).get("ts") or ts
        
        if px is not None and isinstance(px, float) and math.isnan(px):
            px = None
        
        if symbol in self.tickers:
            tick_ts = self.tickers[symbol].get('ts', ts)
            age = int(self._now() - tick_ts) if tick_ts else 999
            STATE.prices[symbol] = {'last': px, 'age': age}
        
        return px, ts
    
    def get_series(self, symbol: str, n: int) -> List[float]:
        """Get recent price series."""
        return list(self.history.get(symbol, []))[-n:]
    
    def get_bar_series(self, symbol: str, n: int) -> Tuple[List[float], List[float], List[float]]:
        """Get OHLC bar data for indicators."""
        if symbol not in self._bar_data:
            closes = self.get_series(symbol, n)
            return closes, closes, closes
        
        bar_data = self._bar_data[symbol]
        highs = list(bar_data.get('highs', []))[-n:]
        lows = list(bar_data.get('lows', []))[-n:]
        closes = list(bar_data.get('closes', []))[-n:]
        
        return highs, lows, closes
    
    def snapshot(self) -> Dict:
        """Get snapshot of all subscribed symbols."""
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
        """Get detailed market phase information."""
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
