# scanner_coordinator.py - v15B Simplified (Main Thread)
"""
Manages 50 IB subscription limit across multiple asset classes:
1. Positions (always subscribed)
2. Futures watchlist (7 fixed symbols)
3. Scanner stocks (top 10-30 rotating)

Runs in main thread to avoid asyncio complications.
"""

import logging
import time
from typing import Dict, Set, List
from collections import defaultdict
from ib_insync import Stock, Future

from config import *
from state_bus import STATE
from professional_scanner import ProfessionalScanner

logger = logging.getLogger(__name__)


class SubscriptionManager:
    """
    Centralized manager for IB market data subscriptions.
    Enforces 50-subscription limit with priority tracking.
    
    Runs in main thread - call tick() from main loop.
    """
    
    def __init__(self, ib, market_bus):
        self.ib = ib
        self.market_bus = market_bus
        
        # Subscription tracking
        self._subscriptions: Dict[str, Dict] = {}  # symbol -> {priority, contract, timestamp}
        self._capacity = IB_MAX_SUBSCRIPTIONS
        
        # Scanners
        self.pro_scanner = ProfessionalScanner(ib, market_bus)
        
        # Timing
        self._last_stock_scan = 0
        self._last_futures_sync = 0
        self._last_cleanup = 0
        self._last_log = 0
        
        logger.info(f"Subscription Manager initialized - {self._capacity} slots")
    
    def start(self):
        """Start scanner (no thread needed)."""
        logger.info("✓ Scanner coordinator started (main thread mode)")
    
    def stop(self):
        """Stop scanner."""
        logger.info("✓ Scanner coordinator stopped")
    
    def tick(self):
        """
        Main tick function - call this from main loop every ~1-10 seconds.
        Handles all scanning and subscription management.
        """
        now = time.time()
        
        try:
            # 1. Always ensure positions subscribed first
            self._sync_positions()
            
            # 2. Ensure futures watchlist subscribed (every 30s)
            if now - self._last_futures_sync >= 30:
                self._sync_futures_watchlist()
                self._last_futures_sync = now
            
            # 3. Run stock scanner (every 60s)
            if now - self._last_stock_scan >= SCANNER_INTERVAL_SECONDS:
                self._run_stock_scanner()
                self._last_stock_scan = now
            
            # 4. Cleanup stale subscriptions (every 60s)
            if now - self._last_cleanup >= 60:
                self._cleanup_stale()
                self._last_cleanup = now
            
            # 5. Log status (every 30s)
            if now - self._last_log >= 30:
                self._log_status()
                self._last_log = now
                
        except Exception as e:
            logger.error(f"Tick error: {e}", exc_info=True)
    
    def _get_current_capacity(self) -> int:
        """Calculate available subscription slots."""
        return self._capacity - len(self._subscriptions)
    
    def _subscribe(self, symbol: str, contract, priority: int) -> bool:
        """
        Subscribe with priority tracking.
        Returns True if successful.
        """
        # Already subscribed?
        if symbol in self._subscriptions:
            # Update priority if higher
            if priority > self._subscriptions[symbol]['priority']:
                self._subscriptions[symbol]['priority'] = priority
                logger.debug(f"Updated {symbol} priority to {priority}")
            # Update activity
            self._subscriptions[symbol]['last_activity'] = time.time()
            return True
        
        # Check capacity
        if self._get_current_capacity() <= 0:
            # Try to free space
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
            logger.info(f"Subscribed {symbol} (pri {priority}) - {len(self._subscriptions)}/{self._capacity}")
            return True
            
        except Exception as e:
            logger.error(f"Subscribe error {symbol}: {e}")
            return False
    
    def _unsubscribe(self, symbol: str):
        """Unsubscribe from symbol."""
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
            logger.error(f"Unsubscribe error {symbol}: {e}")
    
    def _make_room(self, required_priority: int) -> bool:
        """
        Free slots by removing lowest priority items.
        Returns True if space freed.
        """
        # Find lower priority subscriptions
        candidates = [
            (symbol, info) for symbol, info in self._subscriptions.items()
            if info['priority'] < required_priority
        ]
        
        if not candidates:
            return False
        
        # Sort by priority (lowest first), then by activity
        candidates.sort(key=lambda x: (x[1]['priority'], x[1]['last_activity']))
        
        # Remove lowest
        symbol_to_remove = candidates[0][0]
        self._unsubscribe(symbol_to_remove)
        
        return True
    
    def _sync_positions(self):
        """
        Ensure all positions are subscribed with highest priority.
        Positions NEVER get removed.
        """
        positions = STATE.positions
        
        for symbol, pos_data in positions.items():
            if symbol not in self._subscriptions:
                # Need to subscribe
                contract = self._get_contract_for_position(pos_data)
                if contract:
                    self._subscribe(symbol, contract, PRIORITY_POSITION)
            else:
                # Update activity
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
            else:
                return None
                
        except Exception as e:
            logger.error(f"Contract creation error: {e}")
            return None
    
    def _sync_futures_watchlist(self):
        """
        Ensure futures watchlist is subscribed.
        Fixed set of 7 futures.
        """
        for symbol in FUTURES_WATCHLIST:
            if symbol not in self._subscriptions:
                try:
                    contract = Future(symbol, FUTURES_EXCHANGE, FUTURES_CURRENCY)
                    # Qualify the contract first
                    qualified = self.ib.qualifyContracts(contract)
                    if qualified:
                        contract = qualified[0]
                    
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
                STATE.scanner_results = []
                return
            
            # Calculate capacity
            available = self._get_current_capacity()
            
            max_stocks = min(
                len(top_stocks),
                SCANNER_MAX_SLOTS,
                max(SCANNER_MIN_SLOTS, available - 5)  # Keep 5 slot buffer
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
                    # Update activity
                    self._subscriptions[symbol]['last_activity'] = time.time()
            
            # Remove scanner symbols that dropped out
            scanner_subs = [
                sym for sym, info in self._subscriptions.items()
                if info['priority'] == PRIORITY_SCANNER
            ]
            
            for symbol in scanner_subs:
                if symbol not in current_scanner_symbols:
                    logger.info(f"Removing {symbol} - dropped out of top {max_stocks}")
                    self._unsubscribe(symbol)
            
            # Update STATE for dashboard
            STATE.scanner_results = stocks_to_subscribe
            
        except Exception as e:
            logger.error(f"Stock scanner error: {e}", exc_info=True)
            STATE.scanner_results = []
    
    def _cleanup_stale(self):
        """
        Remove scanner subscriptions with no recent activity.
        Positions and futures never removed.
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
            logger.info(f"Cleaning up {len(to_remove)} stale symbols: {', '.join(to_remove[:3])}")
            for symbol in to_remove:
                self._unsubscribe(symbol)
    
    def _log_status(self):
        """Log subscription status."""
        breakdown = defaultdict(int)
        for symbol, info in self._subscriptions.items():
            priority = info['priority']
            breakdown[priority] += 1
        
        positions = breakdown.get(PRIORITY_POSITION, 0)
        futures = breakdown.get(PRIORITY_FUTURES, 0)
        scanner = breakdown.get(PRIORITY_SCANNER, 0)
        
        total = len(self._subscriptions)
        available = self._get_current_capacity()
        
        logger.info(
            f"Subscriptions: {total}/{self._capacity} "
            f"(pos={positions} fut={futures} scan={scanner} free={available})"
        )
    
    def get_status(self) -> Dict:
        """Get detailed status for monitoring."""
        breakdown = defaultdict(int)
        for symbol, info in self._subscriptions.items():
            priority = info['priority']
            breakdown[priority] += 1
        
        return {
            'total': len(self._subscriptions),
            'capacity': self._capacity,
            'available': self._get_current_capacity(),
            'positions': breakdown.get(PRIORITY_POSITION, 0),
            'futures': breakdown.get(PRIORITY_FUTURES, 0),
            'options': 0,  # Disabled in v15B
            'scanner': breakdown.get(PRIORITY_SCANNER, 0),
            'subscriptions': list(self._subscriptions.keys())
        }
