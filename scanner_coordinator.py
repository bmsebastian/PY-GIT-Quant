# scanner_coordinator.py - v15C SIMPLIFIED
"""
SIMPLIFIED APPROACH:
- Don't try to find front month for futures watchlist
- Just subscribe to position futures directly (CLZ5, NQZ5 work)
- Use simple continuous contract subscription for non-position futures
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
    """Centralized manager for IB market data subscriptions."""
    
    def __init__(self, ib, market_bus):
        self.ib = ib
        self.market_bus = market_bus
        
        self._subscriptions: Dict[str, Dict] = {}
        self._capacity = IB_MAX_SUBSCRIPTIONS
        
        # Track which futures we've successfully subscribed to
        self._subscribed_futures = set()
        
        self.pro_scanner = ProfessionalScanner(ib, market_bus)
        
        # Timing
        self._last_stock_scan = 0
        self._last_futures_sync = 0
        self._last_cleanup = 0
        self._last_log = 0
        
        logger.info(f"Subscription Manager initialized - {self._capacity} slots")
    
    def start(self):
        """Start scanner."""
        logger.info("[OK] Scanner coordinator started (main thread mode)")
    
    def stop(self):
        """Stop scanner."""
        logger.info("[OK] Scanner coordinator stopped")
    
    def tick(self):
        """Main tick function."""
        now = time.time()
        
        try:
            # Always ensure positions subscribed first
            self._sync_positions()
            
            # Also sync futures watchlist every 30s
            if now - self._last_futures_sync >= 30:
                self._sync_futures_watchlist()
                self._last_futures_sync = now
            
            # Run scanner every 60s
            if now - self._last_stock_scan >= SCANNER_INTERVAL_SECONDS:
                self._run_stock_scanner()
                self._last_stock_scan = now
            
            # Cleanup stale every 60s
            if now - self._last_cleanup >= 60:
                self._cleanup_stale()
                self._last_cleanup = now
            
            # Log status every 30s
            if now - self._last_log >= 30:
                self._log_status()
                self._last_log = now
                
        except Exception as e:
            logger.error(f"Tick error: {e}", exc_info=True)
    
    def _get_current_capacity(self) -> int:
        """Calculate available slots."""
        return self._capacity - len(self._subscriptions)
    
    def _subscribe(self, symbol: str, contract, priority: int) -> bool:
        """Subscribe with priority tracking."""
        # Already subscribed?
        if symbol in self._subscriptions:
            if priority > self._subscriptions[symbol]['priority']:
                self._subscriptions[symbol]['priority'] = priority
            self._subscriptions[symbol]['last_activity'] = time.time()
            return True
        
        # Check capacity
        if self._get_current_capacity() <= 0:
            if not self._make_room(priority):
                logger.warning(f"Cannot subscribe {symbol}: at capacity")
                return False
        
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
            self.ib.cancelMktData(contract)
            del self._subscriptions[symbol]
            logger.info(f"Unsubscribed {symbol} - {len(self._subscriptions)}/{self._capacity}")
        except Exception as e:
            logger.error(f"Unsubscribe error {symbol}: {e}")
    
    def _make_room(self, required_priority: int) -> bool:
        """Free slots by removing lowest priority items."""
        candidates = [
            (symbol, info) for symbol, info in self._subscriptions.items()
            if info['priority'] < required_priority
        ]
        
        if not candidates:
            return False
        
        candidates.sort(key=lambda x: (x[1]['priority'], x[1]['last_activity']))
        self._unsubscribe(candidates[0][0])
        return True
    
    def _sync_positions(self):
        """
        Ensure ALL positions subscribed - stocks AND futures.
        
        v15C FIX: Use the ACTUAL contract from positions, not a recreated one!
        This is critical for futures which need conId and lastTradeDateOrContractMonth.
        """
        positions = STATE.positions
        
        for symbol, pos_data in positions.items():
            # Use the exact symbol from positions (CLZ5, NQZ5, etc.)
            if symbol not in self._subscriptions:
                try:
                    # CRITICAL FIX: Use the actual contract object from the position
                    # This has ALL fields: conId, lastTradeDateOrContractMonth, etc.
                    contract = pos_data.get('contract')
                    
                    if contract:
                        # Subscribe using the position's contract directly
                        # This ensures we have all the IB fields needed for historical data
                        logger.info(f"Subscribing position {symbol} ({pos_data.get('sec_type', 'STK')}) with full contract")
                        self._subscribe(symbol, contract, PRIORITY_POSITION)
                    else:
                        # Fallback: create contract from position data
                        # This should rarely happen
                        logger.warning(f"No contract in position data for {symbol}, creating new one")
                        contract = self._create_contract_from_position(pos_data)
                        if contract:
                            self._subscribe(symbol, contract, PRIORITY_POSITION)
                
                except Exception as e:
                    logger.error(f"Error subscribing to position {symbol}: {e}")
            else:
                # Update activity
                self._subscriptions[symbol]['last_activity'] = time.time()
    
    def _create_contract_from_position(self, pos_data: Dict):
        """Create contract from position data."""
        try:
            sec_type = pos_data.get('sec_type', 'STK')
            symbol = pos_data.get('symbol')
            local_symbol = pos_data.get('local_symbol', symbol)
            
            if sec_type == 'STK':
                return Stock(symbol, 'SMART', 'USD')
            elif sec_type == 'FUT':
                # For futures, use local_symbol (CLZ5, NQZ5, etc.)
                # Try to determine exchange from symbol
                root = symbol[:2] if len(symbol) >= 2 else symbol
                
                exchange_map = {
                    'NQ': 'CME', 'ES': 'CME', 'RTY': 'CME',
                    'CL': 'NYMEX', 'GC': 'COMEX',
                    'ZB': 'CBOT', 'YM': 'CBOT'
                }
                
                exchange = exchange_map.get(root, 'CME')
                return Future(local_symbol, exchange=exchange, currency='USD')
            
            return None
            
        except Exception as e:
            logger.error(f"Contract creation error: {e}")
            return None
    
    def _sync_futures_watchlist(self):
        """
        Sync futures watchlist using root symbols.
        Subscribe to continuous contracts for monitoring.
        """
        for root_symbol in FUTURES_WATCHLIST:
            # Skip if already subscribed (from positions)
            if root_symbol in self._subscriptions:
                self._subscriptions[root_symbol]['last_activity'] = time.time()
                continue
            
            try:
                # Map to correct exchange
                exchange_map = {
                    'NQ': 'CME', 'ES': 'CME', 'RTY': 'CME',
                    'CL': 'NYMEX', 'GC': 'COMEX',
                    'ZB': 'CBOT', 'YM': 'CBOT'
                }
                exchange = exchange_map.get(root_symbol, 'CME')
                
                # Create continuous contract (empty expiry = front month)
                contract = Future(root_symbol, exchange=exchange, currency='USD')
                
                # Try to qualify
                try:
                    qualified = self.ib.qualifyContracts(contract)
                    if qualified and len(qualified) > 0:
                        contract = qualified[0]
                        logger.info(f"Qualified {root_symbol} -> {contract.localSymbol}")
                except Exception as e:
                    logger.debug(f"Qualification failed for {root_symbol}, using unqualified")
                
                # Subscribe with FUTURES priority
                self._subscribe(root_symbol, contract, PRIORITY_FUTURES)
                
            except Exception as e:
                logger.warning(f"Could not subscribe to {root_symbol}: {e}")
    
    def _run_stock_scanner(self):
        """Run professional stock scanner."""
        logger.info("--- Running Stock Scanner ---")
        
        try:
            top_stocks = self.pro_scanner.scan()
            
            if not top_stocks:
                logger.info(f"No stocks qualified (need {SCANNER_MIN_SCORE}+ score)")
                STATE.scanner_results = []
                return
            
            available = self._get_current_capacity()
            
            max_stocks = min(
                len(top_stocks),
                SCANNER_MAX_SLOTS,
                max(SCANNER_MIN_SLOTS, available - 5)
            )
            
            stocks_to_subscribe = top_stocks[:max_stocks]
            current_scanner_symbols = {s['symbol'] for s in stocks_to_subscribe}
            
            logger.info(f"Top {len(stocks_to_subscribe)} stocks to monitor")
            
            for stock_data in stocks_to_subscribe:
                symbol = stock_data['symbol']
                
                if symbol not in self._subscriptions:
                    contract = Stock(symbol, 'SMART', 'USD')
                    self._subscribe(symbol, contract, PRIORITY_SCANNER)
                else:
                    self._subscriptions[symbol]['last_activity'] = time.time()
            
            # Remove dropped scanner symbols
            scanner_subs = [
                sym for sym, info in self._subscriptions.items()
                if info['priority'] == PRIORITY_SCANNER
            ]
            
            for symbol in scanner_subs:
                if symbol not in current_scanner_symbols:
                    self._unsubscribe(symbol)
            
            STATE.scanner_results = stocks_to_subscribe
            
        except Exception as e:
            logger.error(f"Stock scanner error: {e}", exc_info=True)
            STATE.scanner_results = []
    
    def _cleanup_stale(self):
        """Remove stale subscriptions."""
        now = time.time()
        stale_threshold = 600
        
        to_remove = []
        
        for symbol, info in self._subscriptions.items():
            # Never remove positions or futures
            if info['priority'] >= PRIORITY_FUTURES:
                continue
            
            last_activity = info.get('last_activity', info['timestamp'])
            age = now - last_activity
            
            if age > stale_threshold:
                to_remove.append(symbol)
        
        if to_remove:
            logger.info(f"Cleaning up {len(to_remove)} stale symbols")
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
        """Get detailed status."""
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
            'options': 0,
            'scanner': breakdown.get(PRIORITY_SCANNER, 0),
            'subscriptions': list(self._subscriptions.keys())
        }
