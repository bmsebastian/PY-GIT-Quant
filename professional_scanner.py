# professional_scanner.py - Professional-grade breakout scanner
"""
Multi-factor breakout scanner using institutional trading techniques:
1. Relative Strength vs market (25 pts)
2. Volume Profile analysis (20 pts)
3. Price Action quality (20 pts)
4. Momentum confluence (15 pts)
5. Institutional flow (10 pts)
6. Volatility expansion (10 pts)

Total: 100 point scoring system
Threshold: 60+ to qualify, 80+ exceptional
"""

import logging
import time
import math
from typing import List, Dict, Optional, Tuple
from collections import deque
from datetime import datetime

from config import *
from indicators import ema, sma, true_atr, rsi, macd, bollinger_bands
from state_bus import STATE

logger = logging.getLogger(__name__)


class ProfessionalScanner:
    """
    Professional-grade multi-factor breakout scanner.
    Returns top 10 symbols by composite score each scan.
    """
    
    def __init__(self, ib, market_bus):
        self.ib = ib
        self.market_bus = market_bus
        
        # Tracking
        self._last_scan_time = 0
        self._last_scan_symbols = set()
        self._symbol_scores: Dict[str, Dict] = {}
        self._symbol_history: Dict[str, deque] = {}
        
        # Benchmark tracking (SPY for relative strength)
        self._benchmark_symbol = RS_BENCHMARK
        self._benchmark_history = deque(maxlen=100)
        
        logger.info(f"Professional scanner initialized - looking for 60+ scores")
    
    def _ensure_benchmark_subscribed(self):
        """Ensure SPY is subscribed for relative strength calculations."""
        if self._benchmark_symbol not in self.market_bus.tickers:
            try:
                from ib_insync import Stock
                spy_contract = Stock(self._benchmark_symbol, 'SMART', 'USD')
                self.market_bus.subscribe(self._benchmark_symbol, spy_contract)
                logger.info(f"Subscribed to benchmark {self._benchmark_symbol}")
            except Exception as e:
                logger.warning(f"Could not subscribe to {self._benchmark_symbol}: {e}")
    
    def _get_market_scanner_results(self) -> List[Dict]:
        """
        Get candidates from IB market scanner.
        Returns list of dicts with symbol, contract, volume, etc.
        """
        try:
            # Use IB scanner to find high volume breakout candidates
            from ib_insync import ScannerSubscription
            
            scanner_sub = ScannerSubscription(
                instrument='STK',
                locationCode='STK.US',
                scanCode='TOP_PERC_GAIN',  # Top % gainers
                numberOfRows=50,  # Get 50 candidates
            )
            
            scanner_data = self.ib.reqScannerData(scanner_sub)
            
            candidates = []
            for item in scanner_data:
                contract = item.contractDetails.contract
                symbol = contract.symbol
                
                # Basic filters
                if not self._passes_basic_filters(item):
                    continue
                
                candidates.append({
                    'symbol': symbol,
                    'contract': contract,
                    'rank': item.rank,
                    'volume': getattr(item, 'volume', 0),
                })
            
            logger.info(f"Market scanner found {len(candidates)} candidates")
            return candidates
            
        except Exception as e:
            logger.error(f"Market scanner error: {e}")
            return []
    
    def _passes_basic_filters(self, scan_item) -> bool:
        """Apply basic filters before detailed scoring."""
        try:
            # Price filter
            price = getattr(scan_item, 'lastPrice', 0) or 0
            if price < SCANNER_MIN_PRICE or price > SCANNER_MAX_PRICE:
                return False
            
            # Volume filter
            volume = getattr(scan_item, 'volume', 0) or 0
            if volume < SCANNER_MIN_VOLUME:
                return False
            
            # Dollar volume filter
            dollar_vol = price * volume
            if dollar_vol < SCANNER_MIN_DOLLAR_VOLUME:
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Filter error: {e}")
            return False
    
    def _score_relative_strength(self, symbol: str) -> float:
        """
        Score relative strength vs benchmark (SPY).
        Returns 0-25 points.
        """
        try:
            # Get symbol price history
            symbol_prices = self._symbol_history.get(symbol, deque())
            if len(symbol_prices) < RS_LOOKBACK_BARS:
                return 0.0
            
            # Get benchmark history
            if len(self._benchmark_history) < RS_LOOKBACK_BARS:
                return 0.0
            
            # Calculate returns
            symbol_return = ((symbol_prices[-1] / symbol_prices[-RS_LOOKBACK_BARS]) - 1) * 100
            benchmark_return = ((self._benchmark_history[-1] / self._benchmark_history[-RS_LOOKBACK_BARS]) - 1) * 100
            
            # Relative strength = symbol return - benchmark return
            rs = symbol_return - benchmark_return
            
            # Score: 25 pts if +2% better, 0 if equal or worse
            if rs >= RS_MIN_OUTPERFORMANCE:
                score = min(25.0, (rs / RS_MIN_OUTPERFORMANCE) * 12.5)
            else:
                score = 0.0
            
            return score
            
        except Exception as e:
            logger.debug(f"RS scoring error for {symbol}: {e}")
            return 0.0
    
    def _score_volume_profile(self, symbol: str) -> float:
        """
        Score volume characteristics.
        Returns 0-20 points.
        """
        try:
            bar_data = self.market_bus._bar_data.get(symbol)
            if not bar_data:
                return 0.0
            
            volumes = list(bar_data.get('volumes', []))
            if len(volumes) < 20:
                return 0.0
            
            current_vol = volumes[-1] if volumes else 0
            avg_vol = sum(volumes[-20:]) / 20
            
            points = 0.0
            
            # Volume surge (10 pts)
            if avg_vol > 0:
                surge_ratio = current_vol / avg_vol
                if surge_ratio >= VOLUME_SURGE_MULTIPLIER:
                    points += min(10.0, (surge_ratio / VOLUME_SURGE_MULTIPLIER) * 5.0)
            
            # Volume trend increasing (5 pts)
            if len(volumes) >= VOLUME_TREND_BARS:
                recent_vols = volumes[-VOLUME_TREND_BARS:]
                if all(recent_vols[i] < recent_vols[i+1] for i in range(len(recent_vols)-1)):
                    points += 5.0
            
            # Float rotation estimate (5 pts)
            # This would need float data from IB, using volume as proxy
            if current_vol > avg_vol * 3:  # 3x average = likely high rotation
                points += 5.0
            
            return points
            
        except Exception as e:
            logger.debug(f"Volume scoring error for {symbol}: {e}")
            return 0.0
    
    def _score_price_action(self, symbol: str) -> float:
        """
        Score price action quality.
        Returns 0-20 points.
        """
        try:
            bar_data = self.market_bus._bar_data.get(symbol)
            if not bar_data:
                return 0.0
            
            highs = list(bar_data.get('highs', []))
            lows = list(bar_data.get('lows', []))
            closes = list(bar_data.get('closes', []))
            
            if len(closes) < CONSOLIDATION_BARS:
                return 0.0
            
            points = 0.0
            current_price = closes[-1]
            
            # Clean breakout above consolidation (10 pts)
            consolidation_high = max(highs[-CONSOLIDATION_BARS:-1])
            consolidation_low = min(lows[-CONSOLIDATION_BARS:-1])
            consolidation_range = consolidation_high - consolidation_low
            
            if current_price > consolidation_high:
                breakout_strength = (current_price - consolidation_high) / consolidation_range
                points += min(10.0, breakout_strength * 10.0)
            
            # No false breakouts recently (5 pts)
            false_breaks = 0
            for i in range(-FALSE_BREAKOUT_BARS, -1):
                if highs[i] > consolidation_high and closes[i] < consolidation_high:
                    false_breaks += 1
            
            if false_breaks == 0:
                points += 5.0
            
            # Near 52-week high (5 pts)
            # Would need 52-week data, using recent data as proxy
            recent_high = max(highs[-60:]) if len(highs) >= 60 else consolidation_high
            distance_from_high = (recent_high - current_price) / recent_high
            
            if distance_from_high <= DISTANCE_52W_HIGH:
                points += 5.0 * (1 - (distance_from_high / DISTANCE_52W_HIGH))
            
            return points
            
        except Exception as e:
            logger.debug(f"Price action scoring error for {symbol}: {e}")
            return 0.0
    
    def _score_momentum(self, symbol: str) -> float:
        """
        Score momentum confluence.
        Returns 0-15 points.
        """
        try:
            bar_data = self.market_bus._bar_data.get(symbol)
            if not bar_data:
                return 0.0
            
            closes = list(bar_data.get('closes', []))
            if len(closes) < 30:
                return 0.0
            
            points = 0.0
            
            # MACD bullish (5 pts)
            macd_line, signal_line = macd(closes, MACD_FAST, MACD_SLOW, MACD_SIGNAL)
            if not math.isnan(macd_line) and not math.isnan(signal_line):
                if macd_line > signal_line and macd_line > 0:
                    points += 5.0
            
            # RSI bullish (5 pts)
            rsi_val = rsi(closes, 14)
            if not math.isnan(rsi_val):
                if rsi_val > RSI_BULLISH:
                    points += 5.0
                elif rsi_val > 50:  # Partial credit
                    points += 2.5
            
            # Price above EMAs (5 pts)
            ema8 = ema(closes, 8)
            ema21 = ema(closes, 21)
            current = closes[-1]
            
            if not math.isnan(ema8) and not math.isnan(ema21):
                if current > ema8 > ema21:
                    points += 5.0
                elif current > ema8:  # Partial credit
                    points += 2.5
            
            return points
            
        except Exception as e:
            logger.debug(f"Momentum scoring error for {symbol}: {e}")
            return 0.0
    
    def _score_institutional_flow(self, symbol: str) -> float:
        """
        Score institutional activity indicators.
        Returns 0-10 points.
        """
        try:
            bar_data = self.market_bus._bar_data.get(symbol)
            if not bar_data:
                return 0.0
            
            volumes = list(bar_data.get('volumes', []))
            if len(volumes) < 5:
                return 0.0
            
            points = 0.0
            
            # Large volume bars = potential block trades (5 pts)
            avg_vol = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else sum(volumes) / len(volumes)
            recent_vols = volumes[-5:]
            large_bars = sum(1 for v in recent_vols if v > avg_vol * 2)
            
            if large_bars >= 2:
                points += 5.0
            elif large_bars == 1:
                points += 2.5
            
            # Volume acceleration (5 pts)
            if len(volumes) >= 10:
                early_avg = sum(volumes[-10:-5]) / 5
                recent_avg = sum(volumes[-5:]) / 5
                
                if recent_avg > early_avg * 1.5:
                    points += 5.0
                elif recent_avg > early_avg:
                    points += 2.5
            
            return points
            
        except Exception as e:
            logger.debug(f"Institutional flow scoring error for {symbol}: {e}")
            return 0.0
    
    def _score_volatility_expansion(self, symbol: str) -> float:
        """
        Score volatility expansion.
        Returns 0-10 points.
        """
        try:
            bar_data = self.market_bus._bar_data.get(symbol)
            if not bar_data:
                return 0.0
            
            highs = list(bar_data.get('highs', []))
            lows = list(bar_data.get('lows', []))
            closes = list(bar_data.get('closes', []))
            
            if len(closes) < 20:
                return 0.0
            
            points = 0.0
            
            # ATR expansion (5 pts)
            if len(closes) >= ATR_EXPANSION_BARS + 14:
                recent_atr = true_atr(highs, lows, closes, 14)
                earlier_atr = true_atr(
                    highs[:-ATR_EXPANSION_BARS],
                    lows[:-ATR_EXPANSION_BARS],
                    closes[:-ATR_EXPANSION_BARS],
                    14
                )
                
                if not math.isnan(recent_atr) and not math.isnan(earlier_atr):
                    if earlier_atr > 0 and recent_atr > earlier_atr * 1.2:
                        points += 5.0
            
            # Bollinger Band width expansion (5 pts)
            upper, middle, lower = bollinger_bands(closes, 20, 2)
            if not math.isnan(upper) and not math.isnan(lower) and middle > 0:
                bb_width = (upper - lower) / middle
                
                if bb_width > BB_WIDTH_THRESHOLD / 100:  # Convert to decimal
                    points += 5.0
                elif bb_width > (BB_WIDTH_THRESHOLD / 100) * 0.5:
                    points += 2.5
            
            return points
            
        except Exception as e:
            logger.debug(f"Volatility scoring error for {symbol}: {e}")
            return 0.0
    
    def _calculate_composite_score(self, symbol: str) -> Dict:
        """
        Calculate composite score from all factors.
        Returns dict with breakdown.
        """
        scores = {
            'relative_strength': self._score_relative_strength(symbol),
            'volume': self._score_volume_profile(symbol),
            'price_action': self._score_price_action(symbol),
            'momentum': self._score_momentum(symbol),
            'institutional': self._score_institutional_flow(symbol),
            'volatility': self._score_volatility_expansion(symbol),
        }
        
        total = sum(scores.values())
        
        return {
            'symbol': symbol,
            'total_score': round(total, 2),
            'breakdown': scores,
            'grade': self._get_grade(total),
            'timestamp': time.time()
        }
    
    def _get_grade(self, score: float) -> str:
        """Convert numeric score to letter grade."""
        if score >= 80:
            return 'A'
        elif score >= 70:
            return 'B'
        elif score >= 60:
            return 'C'
        elif score >= 50:
            return 'D'
        else:
            return 'F'
    
    def scan(self) -> List[Dict]:
        """
        Execute professional scan.
        Returns top 10 symbols by composite score.
        """
        now = time.time()
        
        # Rate limit
        if now - self._last_scan_time < SCANNER_INTERVAL_SECONDS:
            return []
        
        self._last_scan_time = now
        
        # Ensure benchmark is subscribed
        self._ensure_benchmark_subscribed()
        
        # Update benchmark history
        bench_price, _ = self.market_bus.get_last(self._benchmark_symbol)
        if bench_price:
            self._benchmark_history.append(bench_price)
        
        logger.info("=== Professional Scan Starting ===")
        
        # Get candidates from IB market scanner
        candidates = self._get_market_scanner_results()
        
        if not candidates:
            logger.warning("No candidates from market scanner")
            return []
        
        # Score each candidate
        scored = []
        for candidate in candidates:
            symbol = candidate['symbol']
            
            try:
                # Ensure symbol has price history
                if symbol not in self._symbol_history:
                    self._symbol_history[symbol] = deque(maxlen=100)
                
                # Get current price and update history
                price, _ = self.market_bus.get_last(symbol)
                if price:
                    self._symbol_history[symbol].append(price)
                
                # Calculate composite score
                score_data = self._calculate_composite_score(symbol)
                
                # Filter by minimum score
                if score_data['total_score'] >= SCANNER_MIN_SCORE:
                    scored.append(score_data)
                    logger.info(f"  {symbol}: {score_data['total_score']:.1f} ({score_data['grade']})")
                
            except Exception as e:
                logger.warning(f"Scoring error for {symbol}: {e}")
                continue
        
        # Sort by score descending
        scored.sort(key=lambda x: x['total_score'], reverse=True)
        
        # Take top 10
        top_10 = scored[:10]
        
        logger.info(f"=== Scan Complete: {len(top_10)}/10 qualified ===")
        
        # Update STATE for dashboard
        STATE.scanner_results = top_10
        
        # Track what changed from last scan
        current_symbols = {s['symbol'] for s in top_10}
        new_symbols = current_symbols - self._last_scan_symbols
        dropped_symbols = self._last_scan_symbols - current_symbols
        
        if new_symbols:
            logger.info(f"NEW in top 10: {', '.join(new_symbols)}")
        if dropped_symbols:
            logger.info(f"DROPPED from top 10: {', '.join(dropped_symbols)}")
        
        self._last_scan_symbols = current_symbols
        
        return top_10
    
    def get_score_breakdown(self, symbol: str) -> Optional[Dict]:
        """Get detailed score breakdown for a symbol."""
        return self._symbol_scores.get(symbol)
