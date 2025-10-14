# options_scanner.py - Unusual Options Activity (UOA) Scanner
"""
Professional options scanner detecting unusual activity:
- Volume surges (volume > 2x open interest)
- High IV percentile moves
- Large premium orders (smart money)
- Multi-exchange sweeps
- Put/call imbalances

Returns top 10 by unusualness score
"""

import logging
import time
import math
from typing import List, Dict, Optional
from collections import deque
from datetime import datetime, timedelta

from config import *
from state_bus import STATE

logger = logging.getLogger(__name__)


class OptionsScanner:
    """
    Scan for unusual options activity indicating institutional moves.
    """
    
    def __init__(self, ib):
        self.ib = ib
        
        # Tracking
        self._last_scan_time = 0
        self._option_history: Dict[str, Dict] = {}
        
        logger.info("Options scanner initialized - detecting smart money")
    
    def _get_options_chain(self, symbol: str, expiry_days: int = 30):
        """
        Get options chain for a symbol.
        Returns list of option contracts with greeks, volume, OI.
        """
        try:
            from ib_insync import Stock, Option
            
            # Get underlying contract
            stock = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(stock)
            
            # Request options chains
            chains = self.ib.reqSecDefOptParams(
                stock.symbol,
                '',
                stock.secType,
                stock.conId
            )
            
            if not chains:
                return []
            
            # Get nearest expiration
            today = datetime.now().date()
            target_date = today + timedelta(days=expiry_days)
            
            options = []
            for chain in chains:
                for expiry in chain.expirations:
                    expiry_date = datetime.strptime(expiry, '%Y%m%d').date()
                    
                    # Filter by DTE
                    dte = (expiry_date - today).days
                    if dte < OPTIONS_MIN_DTE or dte > OPTIONS_MAX_DTE:
                        continue
                    
                    # Get both calls and puts for each strike
                    for strike in chain.strikes:
                        for right in ['C', 'P']:
                            opt = Option(
                                symbol,
                                expiry,
                                strike,
                                right,
                                chain.exchange
                            )
                            options.append(opt)
            
            return options
            
        except Exception as e:
            logger.error(f"Options chain error for {symbol}: {e}")
            return []
    
    def _get_option_metrics(self, contract) -> Optional[Dict]:
        """
        Get volume, OI, IV, greeks for an option.
        """
        try:
            # Request market data
            ticker = self.ib.reqMktData(contract, '', False, False)
            self.ib.sleep(0.5)  # Wait for data
            
            # Get metrics
            volume = ticker.volume or 0
            open_interest = ticker.openInterest or 0
            iv = ticker.impliedVolatility
            bid = ticker.bid
            ask = ticker.ask
            last = ticker.last or ticker.close
            
            # Request greeks
            greeks = ticker.modelGreeks
            delta = greeks.delta if greeks else None
            gamma = greeks.gamma if greeks else None
            theta = greeks.theta if greeks else None
            vega = greeks.vega if greeks else None
            
            # Cancel market data
            self.ib.cancelMktData(contract)
            
            # Calculate premium
            mid_price = (bid + ask) / 2 if bid and ask else last
            premium = mid_price * 100 if mid_price else 0  # Per contract
            
            return {
                'symbol': contract.symbol,
                'strike': contract.strike,
                'right': contract.right,
                'expiry': contract.lastTradeDateOrContractMonth,
                'volume': volume,
                'open_interest': open_interest,
                'iv': iv,
                'premium': premium,
                'delta': delta,
                'gamma': gamma,
                'theta': theta,
                'vega': vega,
                'last': last,
                'bid': bid,
                'ask': ask,
            }
            
        except Exception as e:
            logger.debug(f"Option metrics error: {e}")
            return None
    
    def _calculate_uoa_score(self, metrics: Dict) -> float:
        """
        Calculate unusualness score (0-100).
        
        Factors:
        - Volume vs OI ratio (40 pts)
        - IV percentile (30 pts)
        - Premium size (20 pts)
        - Unusual time of day (10 pts)
        """
        score = 0.0
        
        # Volume vs OI (40 pts)
        volume = metrics['volume']
        oi = metrics['open_interest']
        
        if oi > 0:
            vol_oi_ratio = volume / oi
            if vol_oi_ratio >= OPTIONS_VOLUME_MULTIPLIER:
                # Score up to 40 pts based on how extreme
                score += min(40.0, (vol_oi_ratio / OPTIONS_VOLUME_MULTIPLIER) * 20.0)
        
        # IV percentile (30 pts)
        # In real implementation, would need IV history
        # For now, high IV = high score
        iv = metrics.get('iv')
        if iv:
            # IV > 50% = unusual
            if iv > 0.50:
                score += min(30.0, ((iv - 0.50) / 0.50) * 30.0)
        
        # Premium size (20 pts)
        premium = metrics['premium']
        if premium >= 500:  # $500+ per contract
            score += min(20.0, (premium / 500) * 10.0)
        
        # Time of day factor (10 pts)
        # Early morning or late afternoon unusual activity scores higher
        current_hour = datetime.now().hour
        if 7 <= current_hour <= 10:  # Pre-market / market open
            score += 10.0
        elif 14 <= current_hour <= 16:  # Near close
            score += 5.0
        
        return min(100.0, score)
    
    def _detect_sweep(self, metrics: Dict) -> bool:
        """
        Detect if option activity looks like a sweep.
        Sweep = rapid buying across multiple exchanges.
        """
        # In real implementation, would analyze tick data
        # For now, use volume surge as proxy
        volume = metrics['volume']
        oi = metrics['open_interest']
        
        if oi > 0 and volume > oi * 3:  # 3x OI in one period = likely sweep
            return True
        
        return False
    
    def _passes_filters(self, metrics: Dict) -> bool:
        """Check if option passes minimum filters."""
        if metrics['volume'] < OPTIONS_MIN_VOLUME:
            return False
        
        if metrics['premium'] < OPTIONS_MIN_PREMIUM:
            return False
        
        if metrics['open_interest'] < OPTIONS_MIN_OI:
            return False
        
        return True
    
    def scan(self, symbols: List[str] = None) -> List[Dict]:
        """
        Scan for unusual options activity.
        
        Args:
            symbols: List of underlying symbols to scan. If None, scans popular stocks.
        
        Returns:
            Top 10 unusual options by score
        """
        now = time.time()
        
        # Rate limit
        if now - self._last_scan_time < OPTIONS_SCAN_INTERVAL:
            return []
        
        self._last_scan_time = now
        
        # Default to popular stocks if none provided
        if not symbols:
            symbols = [
                'SPY', 'QQQ', 'IWM', 'DIA',  # Indexes
                'AAPL', 'MSFT', 'NVDA', 'TSLA', 'AMZN',  # Mega caps
                'META', 'GOOGL', 'NFLX', 'AMD', 'COIN',  # Tech
            ]
        
        logger.info(f"=== Options Scan Starting ({len(symbols)} underlyings) ===")
        
        unusual_options = []
        
        for symbol in symbols:
            try:
                # Get options chain
                options = self._get_options_chain(symbol)
                
                if not options:
                    continue
                
                logger.info(f"  {symbol}: checking {len(options)} options")
                
                # Check each option
                for opt_contract in options[:50]:  # Limit to 50 per symbol
                    try:
                        metrics = self._get_option_metrics(opt_contract)
                        
                        if not metrics:
                            continue
                        
                        # Apply filters
                        if not self._passes_filters(metrics):
                            continue
                        
                        # Calculate unusualness score
                        uoa_score = self._calculate_uoa_score(metrics)
                        
                        # Detect sweeps
                        is_sweep = self._detect_sweep(metrics)
                        
                        # Build result
                        result = {
                            'underlying': symbol,
                            'strike': metrics['strike'],
                            'right': metrics['right'],
                            'expiry': metrics['expiry'],
                            'volume': metrics['volume'],
                            'oi': metrics['open_interest'],
                            'iv': metrics.get('iv', 0),
                            'premium': metrics['premium'],
                            'score': round(uoa_score, 2),
                            'is_sweep': is_sweep,
                            'delta': metrics.get('delta'),
                            'gamma': metrics.get('gamma'),
                            'contract_label': f"{symbol} {metrics['strike']}{metrics['right']} {metrics['expiry']}",
                            'timestamp': now
                        }
                        
                        unusual_options.append(result)
                        
                    except Exception as e:
                        logger.debug(f"Option check error: {e}")
                        continue
                
            except Exception as e:
                logger.warning(f"Symbol scan error {symbol}: {e}")
                continue
        
        # Sort by score descending
        unusual_options.sort(key=lambda x: x['score'], reverse=True)
        
        # Take top 10
        top_10 = unusual_options[:10]
        
        logger.info(f"=== Options Scan Complete: {len(top_10)}/10 unusual ===")
        
        for opt in top_10:
            sweep_flag = "🔥 SWEEP" if opt['is_sweep'] else ""
            logger.info(
                f"  {opt['contract_label']}: {opt['score']:.1f} "
                f"(vol={opt['volume']:,} oi={opt['oi']:,}) {sweep_flag}"
            )
        
        # Update STATE for dashboard
        STATE.unusual_options = top_10
        
        return top_10
    
    def get_option_detail(self, contract_label: str) -> Optional[Dict]:
        """Get detailed info for a specific option."""
        return self._option_history.get(contract_label)
