# indicators.py — Technical indicators for QTrade v14
import logging
import math
from typing import List, Optional

logger = logging.getLogger(__name__)

def ema(values: List[float], period: int) -> float:
    """
    Exponential Moving Average.
    Returns NaN if insufficient data.
    """
    if not values or len(values) < period:
        return math.nan
    
    # Filter out NaN values
    clean_values = [v for v in values if not math.isnan(v)]
    if len(clean_values) < period:
        return math.nan
    
    k = 2.0 / (period + 1)
    e = clean_values[0]
    
    for v in clean_values[1:]:
        e = v * k + e * (1 - k)
    
    return e


def sma(values: List[float], period: int) -> float:
    """
    Simple Moving Average.
    Returns NaN if insufficient data.
    """
    if not values or len(values) < period:
        return math.nan
    
    clean_values = [v for v in values if not math.isnan(v)]
    if len(clean_values) < period:
        return math.nan
    
    return sum(clean_values[-period:]) / period


def true_range(high: float, low: float, prev_close: float) -> float:
    """
    Calculate True Range for a single bar.
    TR = max(high - low, abs(high - prev_close), abs(low - prev_close))
    """
    if any(math.isnan(x) for x in [high, low, prev_close]):
        return math.nan
    
    return max(
        high - low,
        abs(high - prev_close),
        abs(low - prev_close)
    )


def true_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
    """
    Average True Range (ATR) using Wilder's smoothing method.
    
    Args:
        highs: List of high prices
        lows: List of low prices
        closes: List of closing prices
        period: ATR period (default 14)
    
    Returns:
        ATR value or NaN if insufficient data
    """
    if not highs or not lows or not closes:
        return math.nan
    
    if len(highs) < period + 1 or len(lows) < period + 1 or len(closes) < period + 1:
        return math.nan
    
    if len(highs) != len(lows) or len(highs) != len(closes):
        logger.warning(f"ATR: Mismatched lengths H={len(highs)} L={len(lows)} C={len(closes)}")
        return math.nan
    
    # Calculate True Range for each bar
    tr_values = []
    for i in range(1, len(closes)):
        tr = true_range(highs[i], lows[i], closes[i-1])
        if not math.isnan(tr):
            tr_values.append(tr)
    
    if len(tr_values) < period:
        return math.nan
    
    # Wilder's smoothing: first ATR is SMA, then exponential smoothing
    atr = sum(tr_values[:period]) / period
    
    for tr in tr_values[period:]:
        atr = ((atr * (period - 1)) + tr) / period
    
    return atr


def rsi(values: List[float], period: int = 14) -> float:
    """
    Relative Strength Index (RSI).
    
    Args:
        values: Price series
        period: RSI period (default 14)
    
    Returns:
        RSI value (0-100) or NaN if insufficient data
    """
    if not values or len(values) < period + 1:
        return math.nan
    
    clean_values = [v for v in values if not math.isnan(v)]
    if len(clean_values) < period + 1:
        return math.nan
    
    # Calculate price changes
    gains = []
    losses = []
    
    for i in range(1, len(clean_values)):
        change = clean_values[i] - clean_values[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    if len(gains) < period:
        return math.nan
    
    # Initial averages
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    # Wilder's smoothing for remaining values
    for i in range(period, len(gains)):
        avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi_val = 100.0 - (100.0 / (1.0 + rs))
    
    return rsi_val


def macd(values: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
    """
    Moving Average Convergence Divergence (MACD).
    
    Args:
        values: Price series
        fast: Fast EMA period (default 12)
        slow: Slow EMA period (default 26)
        signal: Signal line period (default 9)
    
    Returns:
        (macd_line, signal_line, histogram) or (nan, nan, nan)
    """
    if not values or len(values) < slow:
        return (math.nan, math.nan, math.nan)
    
    # Calculate MACD line
    macd_values = []
    for i in range(slow, len(values) + 1):
        window = values[:i]
        fast_ema = ema(window, fast)
        slow_ema = ema(window, slow)
        if not math.isnan(fast_ema) and not math.isnan(slow_ema):
            macd_values.append(fast_ema - slow_ema)
    
    if len(macd_values) < signal:
        return (math.nan, math.nan, math.nan)
    
    # Calculate signal line
    signal_line = ema(macd_values, signal)
    macd_line = macd_values[-1]
    
    if math.isnan(signal_line):
        return (macd_line, math.nan, math.nan)
    
    histogram = macd_line - signal_line
    
    return (macd_line, signal_line, histogram)


def bollinger_bands(values: List[float], period: int = 20, std_dev: float = 2.0) -> tuple:
    """
    Bollinger Bands.
    
    Args:
        values: Price series
        period: Moving average period (default 20)
        std_dev: Standard deviation multiplier (default 2.0)
    
    Returns:
        (upper_band, middle_band, lower_band) or (nan, nan, nan)
    """
    if not values or len(values) < period:
        return (math.nan, math.nan, math.nan)
    
    middle = sma(values, period)
    if math.isnan(middle):
        return (math.nan, math.nan, math.nan)
    
    # Calculate standard deviation
    recent_values = values[-period:]
    variance = sum((v - middle) ** 2 for v in recent_values) / period
    std = math.sqrt(variance)
    
    upper = middle + (std_dev * std)
    lower = middle - (std_dev * std)
    
    return (upper, middle, lower)


def volume_sma(volumes: List[float], period: int = 20) -> float:
    """
    Simple Moving Average of volume.
    
    Args:
        volumes: Volume series
        period: Period (default 20)
    
    Returns:
        Average volume or NaN
    """
    return sma(volumes, period)


def money_flow_index(highs: List[float], lows: List[float], closes: List[float], 
                     volumes: List[float], period: int = 14) -> float:
    """
    Money Flow Index (MFI) - Volume-weighted RSI.
    
    Args:
        highs: High prices
        lows: Low prices
        closes: Closing prices
        volumes: Volume data
        period: MFI period (default 14)
    
    Returns:
        MFI value (0-100) or NaN
    """
    if not all([highs, lows, closes, volumes]):
        return math.nan
    
    min_len = min(len(highs), len(lows), len(closes), len(volumes))
    if min_len < period + 1:
        return math.nan
    
    # Calculate typical price and raw money flow
    positive_flow = []
    negative_flow = []
    
    for i in range(1, min_len):
        typical_price = (highs[i] + lows[i] + closes[i]) / 3.0
        prev_typical = (highs[i-1] + lows[i-1] + closes[i-1]) / 3.0
        raw_money_flow = typical_price * volumes[i]
        
        if typical_price > prev_typical:
            positive_flow.append(raw_money_flow)
            negative_flow.append(0)
        elif typical_price < prev_typical:
            positive_flow.append(0)
            negative_flow.append(raw_money_flow)
        else:
            positive_flow.append(0)
            negative_flow.append(0)
    
    if len(positive_flow) < period:
        return math.nan
    
    # Calculate MFI
    pos_sum = sum(positive_flow[-period:])
    neg_sum = sum(negative_flow[-period:])
    
    if neg_sum == 0:
        return 100.0
    
    money_ratio = pos_sum / neg_sum
    mfi = 100.0 - (100.0 / (1.0 + money_ratio))
    
    return mfi
