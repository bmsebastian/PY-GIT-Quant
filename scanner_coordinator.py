# scanner_coordinator.py - v15 Multi-Asset Subscription Manager
"""
Manages 50 IB subscription limit across 4 asset classes:
1. Positions (priority 100) - unlimited, takes precedence
2. Futures watchlist (priority 90) - fixed 7 symbols
3. Unusual options (priority 60) - top 10 rotating
4. Scanner stocks (priority 25) - top 10-30 rotating

Dynamic allocation based on available capacity.
"""

import logging
import time
import threading
from typing import Dict, Set, List, Optional
from collections import defaultdict
from ib_insync import Stock, Future, Option

from config import *
from state_bus import STATE
from professional_scanner import ProfessionalScanner
from options_scanner import OptionsScanner

logger = logging.getLogger(__name__)


class SubscriptionManager:
    """
    Centralized manager for all IB market data subscriptions.
    Enforces 50-subscription limit with priority system.
    """
    
    def __init__(self, ib, market_bus):
        self.ib = ib
        self.market_bus = market_bus
        
        # Subscription tracking
        self._subscriptions: Dict[str, Dict] = {}  # symbol -> {priority, contract, timestamp}
        self._capacity = IB_MAX_SUBSCRIPTIONS
        
        # Scanners
        self.pro_scanner = ProfessionalScanner(ib, market_bus)
        self.options_scanner = OptionsScanner(ib)
        
        # Background thread for scanning
        self._running = False
        self._scan_thread = None
        
        # Timing
        self._last_stock_scan = 0
        self._last_options_scan = 0
        self._last_cleanup = 0
        
        logger.info(f"Subscription Manager initialized - {self._capacity} slots available")
    
    def start(self):
        """Start background scanning threads."""
        if self._running:
            return
        
        self._running = True
        self._scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._scan_thread.start()
        
        logger.info("Scanner coordinator started")
    
    def stop(self):
        """Stop scanning threads."""
        self._running = False
        if self._scan_thread:
            self._scan_thread.join(timeout=5)
        logger.info("Scanner coordinator stopped")
    
    def _scan_loop(self):
        """Background loop for all scanning operations."""
        while self._running:
            try:
                now = time.time()
                
                # 1. Always ensure positions are subscribed first
                self._sync_positions()
                
                # 2. Ensure futures watchlist is subscribed
                self._sync_futures_watchlist()
                
                # 3. Run stock scanner (every 60s)
                if now - self._last_stock_scan >= SCANNER_INTERVAL_SECONDS:
                    self._run_stock_scanner()
                    self._last_stock_scan = now
                
                # 4. Run options scanner (every 120s)
                if now - self._last_options_scan >= OPTIONS_SCAN_INTERVAL:
                    self._run_options_scanner()
                    self._last_options_scan = now
                
                # 5. Cleanup stale subscriptions (every 60s)
                if now - self._last_cleanup >= 60:
                    self._cleanup_stale()
                    self._last_cleanup = now
                
                # Log status
                self._log_status()
                
                # Sleep between iterations
                time.sleep(10)
                
            except Exception as e:
                logger.error(f"Scan loop error: {e}", exc_info=True)
                time.sleep(10)
    
    def _get_current_capacity(self) -> int:
        """Calculate current available subscription slots."""
        return self._capacity - len(self._subscriptions)
    
    def _get_priority_breakdown(self) -> Dict[int, int]:
        """Get count of subscriptions by priority level."""
        breakdown = defaultdict(int)
        for symbol, info in self._subscriptions.items():
            priority = info['priority']
            breakdown[priority] += 1
        return dict(breakdown)
    
    def _subscribe(self, symbol: str, contract, priority: int) -> bool:
        """
        Subscribe to a symbol with given priority.
        Returns True if successful, False if at capacity.
        """
        # Already subscribed?
        if symbol in self._subscriptions:
            # Update priority if higher
            if priority > self._subscriptions[symbol]['priority']:
                self._subscriptions[symbol]['priority'] = priority
                logger.debug(f"Updated {symbol} priority to {priority}")
            return True
        
        # Check capacity
        if self._get_current_capacity() <= 0:
            # Try to free space by removing lowest priority
            if not self._make_room(priority):
                logger.warning(f"Cannot subscribe {symbol}: at capacity")
                return False
        
        # Subscribe via market bus
        try:
            self.market_bus.subscribe(symbol, contract)
            self._subscriptions[symbol] = {
                'priority': priority,
                'contract': contract,
                'timestamp': time.time(),
                'last_activity': time.time()
            }
            logger.info(f"Subscribed {symbol} (priority {priority}) - {len(self._subscriptions)}/{self._capacity}")
            return True
            
        except Exception as e:
            logger.error(f"Subscribe error for {symbol}: {e}")
            return False
    
    def _unsubscribe(self, symbol: str):
        """Unsubscribe from a symbol."""
        if symbol not in self._subscriptions:
            return
        
        try:
            contract = self._subscriptions[symbol]['contract']
            # Cancel market data
            self.ib.cancelMktData(contract)
            
            # Remove from tracking
            del self._subscriptions[symbol]
            
            logger.info(f"Unsubscribed {symbol} - {len(self._subscriptions)}/{self._capacity}")
            
        except Exception as e:
            logger.error(f"Unsubscribe error for {symbol}: {e}")
    
    def _make_room(self, required_priority: int) -> bool:
        """
        Free up subscription slots by removing lowest priority items.
        Returns True if space was freed.
        """
        # Find subscriptions with lower priority
        candidates = [
            (symbol, info) for symbol, info in self._subscriptions.items()
            if info['priority'] < required_priority
        ]
        
        if not candidates:
            return False
        
        # Sort by priority (lowest first), then by last activity
        candidates.sort(key=lambda x: (x[1]['priority'], x[1]['last_activity']))
        
        # Remove the lowest priority item
        symbol_to_remove = candidates[0][0]
        self._unsubscribe(symbol_to_remove)
        
        return True
    
    def _sync_positions(self):
        """
        Ensure all open positions are subscribed with highest priority.
        Positions NEVER get removed.
        """
        # Get positions from STATE
        positions = STATE.positions
        
        for symbol, pos_data in positions.items():
            if symbol not in self._subscriptions:
                # Need to subscribe to this position
                contract = self._get_contract_for_position(pos_data)
                if contract:
                    self._subscribe(symbol, contract, PRIORITY_POSITION)
            else:
                # Update activity timestamp
                self._subscriptions[symbol]['last_activity'] = time.time()
    
    def _get_contract_for_position(self, pos_data: Dict):
        """Create IB contract from position data."""
        try:
            sec_type = pos_data.get('sec_type', 'STK')
            symbol = pos_data.get('symbol')
            
            if sec_type == 'STK':
                return Stock(symbol, 'SMART', 'USD')
            elif sec_type == 'FUT':
                local_symbol = pos_data.get('local_symbol', symbol)
                return Future(local_symbol, FUTURES_EXCHANGE, FUTURES_CURRENCY)
            elif sec_type == 'OPT':
                # Would need more details for options
                return None
            else:
                return None
                
        except Exception as e:
            logger.error(f"Contract creation error: {e}")
            return None
    
    def _sync_futures_watchlist(self):
        """
        Ensure all futures in watchlist are subscribed.
        Fixed set of 7 futures.
        """
        for symbol in FUTURES_WATCHLIST:
            if symbol not in self._subscriptions:
                contract = Future(symbol, FUTURES_EXCHANGE, FUTURES_CURRENCY)
                try:
                    self.ib.qualifyContracts(contract)
                    self._subscribe(symbol, contract, PRIORITY_FUTURES)
                except Exception as e:
                    logger.warning(f"Could not subscribe to future {symbol}: {e}")
            else:
                # Update activity
                self._subscriptions[symbol]['last_activity'] = time.time()
    
    def _run_stock_scanner(self):
        """
        Run professional stock scanner.
        Subscribe to top 10-30 depending on capacity.
        """
        logger.info("--- Running Stock Scanner ---")
        
        try:
            # Get top breakout stocks
            top_stocks = self.pro_scanner.scan()
            
            if not top_stocks:
                logger.info("No stocks qualified (need 60+ score)")
                return
            
            # Calculate how many we can subscribe to
            available = self._get_current_capacity()
            reserved_for_options = OPTIONS_SLOTS
            
            max_stocks = min(
                len(top_stocks),
                SCANNER_MAX_SLOTS,
                max(SCANNER_MIN_SLOTS, available - reserved_for_options)
            )
            
            # Get top N
            stocks_to_subscribe = top_stocks[:max_stocks]
            current_scanner_symbols = {s['symbol'] for s in stocks_to_subscribe}
            
            logger.info(f"Top {len(stocks_to_subscribe)} stocks to monitor")
            
            # Subscribe to new symbols
            for stock_data in stocks_to_subscribe:
                symbol = stock_data['symbol']
                
                if symbol not in self._subscriptions:
                    contract = Stock(symbol, 'SMART', 'USD')
                    self._subscribe(symbol, contract, PRIORITY_SCANNER)
                else:
                    # Update activity for existing
                    self._subscriptions[symbol]['last_activity'] = time.time()
            
            # Remove scanner symbols that dropped out of top N
            scanner_subs = [
                sym for sym, info in self._subscriptions.items()
                if info['priority'] == PRIORITY_SCANNER
            ]
            
            for symbol in scanner_subs:
                if symbol not in current_scanner_symbols:
                    logger.info(f"Removing {symbol} - dropped out of top {max_stocks}")
                    self._unsubscribe(symbol)
            
        except Exception as e:
            logger.error(f"Stock scanner error: {e}", exc_info=True)
    
    def _run_options_scanner(self):
        """
        Run unusual options activity scanner.
        Subscribe to top 10 options.
        """
        logger.info("--- Running Options Scanner ---")
        
        try:
            # Get symbols to scan for options
            # Priority: positions, then high-scoring scanner results
            underlying_symbols = []
            
            # Add position symbols
            for symbol in STATE.positions.keys():
                if len(underlying_symbols) < 5:
                    underlying_symbols.append(symbol)
            
            # Add top scanner symbols
            scanner_results = getattr(STATE, 'scanner_results', [])
            for result in scanner_results[:5]:
                symbol = result.get('symbol')
                if symbol and symbol not in underlying_symbols:
                    underlying_symbols.append(symbol)
            
            # Scan for unusual options
            top_options = self.options_scanner.scan(underlying_symbols)
            
            if not top_options:
                logger.info("No unusual options detected")
                return
            
            logger.info(f"Top {len(top_options)} unusual options to monitor")
            
            # For now, just log them (actual option subscription would need contracts)
            # In production, would subscribe to option contracts here
            
            # Update STATE
            STATE.unusual_options = top_options
            
        except Exception as e:
            logger.error(f"Options scanner error: {e}", exc_info=True)
    
    def _cleanup_stale(self):
        """
        Remove scanner subscriptions with no recent activity.
        Positions and futures are never removed.
        """
        now = time.time()
        stale_threshold = 600  # 10 minutes
        
        to_remove = []
        
        for symbol, info in self._subscriptions.items():
            # Never remove positions or futures
            if info['priority'] >= PRIORITY_FUTURES:
                continue
            
            # Check last activity
            last_activity = info.get('last_activity', info['timestamp'])
            age = now - last_activity
            
            if age > stale_threshold:
                to_remove.append(symbol)
        
        if to_remove:
            logger.info(f"Cleaning up {len(to_remove)} stale symbols: {', '.join(to_remove)}")
            for symbol in to_remove:
                self._unsubscribe(symbol)
    
    def _log_status(self):
        """Log current subscription status."""
        breakdown = self._get_priority_breakdown()
        
        positions = breakdown.get(PRIORITY_POSITION, 0)
        futures = breakdown.get(PRIORITY_FUTURES, 0)
        options = breakdown.get(PRIORITY_OPTIONS, 0)
        scanner = breakdown.get(PRIORITY_SCANNER, 0)
        
        total = len(self._subscriptions)
        available = self._get_current_capacity()
        
        logger.info(
            f"Subscriptions: {total}/{self._capacity} "
            f"(pos={positions} fut={futures} opt={options} scan={scanner} free={available})"
        )
    
    def get_status(self) -> Dict:
        """Get detailed status for dashboard/monitoring."""
        breakdown = self._get_priority_breakdown()
        
        return {
            'total': len(self._subscriptions),
            'capacity': self._capacity,
            'available': self._get_current_capacity(),
            'positions': breakdown.get(PRIORITY_POSITION, 0),
            'futures': breakdown.get(PRIORITY_FUTURES, 0),
            'options': breakdown.get(PRIORITY_OPTIONS, 0),
            'scanner': breakdown.get(PRIORITY_SCANNER, 0),
            'subscriptions': list(self._subscriptions.keys())
        }