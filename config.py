# config.py - QTrade v15C Configuration (Clean)
"""
Complete configuration for QTrade v15 with full backward compatibility.
Includes all v14 constants + v15 enhancements.
"""

import os

# ============================================================================
# CORE SETTINGS
# ============================================================================

ENV = os.getenv("QTRADE_ENV", "paper")  # paper or live
DRY_RUN = int(os.getenv("DRY_RUN", "0"))  # 1 = no actual orders
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ============================================================================
# INTERACTIVE BROKERS CONNECTION
# ============================================================================

# v15 naming (preferred)
IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "7497"))  # 7497=paper, 7496=live
IB_CLIENT_ID = int(os.getenv("IB_CLIENT_ID", "1"))

# v14 backward compatibility aliases
IB_GATEWAY_HOST = IB_HOST
IB_GATEWAY_PORT = IB_PORT

# Market data settings
IB_MAX_SUBSCRIPTIONS = 50  # IB hard limit
MARKET_DATA_TYPE = 1  # 1=LIVE, 2=FROZEN, 3=DELAYED, 4=DELAYED_FROZEN

# ============================================================================
# SUBSCRIPTION ALLOCATION (50 total)
# ============================================================================

# Priority levels (higher = never removed)
PRIORITY_POSITION = 100      # Open positions - NEVER remove
PRIORITY_FUTURES = 90        # Futures watchlist - fixed
PRIORITY_OPTIONS = 60        # Unusual options - rotating top 10
PRIORITY_SCANNER = 25        # Breakout stocks - rotating top 10-30

# Dynamic allocation
POSITIONS_RESERVE = 10       # Reserve slots for future positions
FUTURES_SLOTS = 7           # Fixed futures monitoring
OPTIONS_SLOTS = 10          # Top unusual options
SCANNER_MIN_SLOTS = 10      # Minimum scanner results
SCANNER_MAX_SLOTS = 30      # Maximum scanner results

# v14 backward compatibility
MAX_IB_SUBSCRIPTIONS = IB_MAX_SUBSCRIPTIONS  # Alias
SCANNER_MAX_WARN_THRESHOLD = 45  # Warn when subscriptions >= 45

def get_scanner_capacity(num_positions: int) -> int:
    """
    Calculate available scanner capacity (backward compatibility).
    In v15, this is managed automatically by SubscriptionManager.
    """
    reserved = num_positions + FUTURES_SLOTS
    available = IB_MAX_SUBSCRIPTIONS - reserved
    return max(0, available - 5)  # Keep 5-slot buffer

# ============================================================================
# FUTURES WATCHLIST (Always Monitored)
# ============================================================================

FUTURES_WATCHLIST = [
    'NQ',   # Nasdaq 100 E-mini
    'ES',   # S&P 500 E-mini
    'CL',   # Crude Oil
    'GC',   # Gold
    'ZB',   # 30-Year Treasury Bond
    'RTY',  # Russell 2000 E-mini
    'YM',   # Dow Jones E-mini
]

# Futures contract details
FUTURES_EXCHANGE = 'CME'
FUTURES_CURRENCY = 'USD'
FUTURES_MULTIPLIERS = {
    'NQ': 20,
    'ES': 50,
    'CL': 1000,
    'GC': 100,
    'ZB': 1000,
    'RTY': 50,
    'YM': 5,
}

# ============================================================================
# PROFESSIONAL BREAKOUT SCANNER
# ============================================================================

# Minimum requirements to even consider a stock
SCANNER_MIN_PRICE = 5.0          # $5 minimum (avoid penny stocks)
SCANNER_MAX_PRICE = 1000.0       # $1000 maximum (avoid AMZN/GOOG issues)
SCANNER_MIN_VOLUME = 500000      # 500K daily volume minimum
SCANNER_MIN_DOLLAR_VOLUME = 5_000_000  # $5M daily $ volume

# Scoring thresholds (0-100 scale) - v15C LOWERED FOR TESTING
SCANNER_MIN_SCORE = 40.0         # 40+ to qualify (was 60)
SCANNER_EXCELLENT_SCORE = 70.0   # 70+ = excellent (was 80)

# Relative Strength scoring (25 points max)
RS_BENCHMARK = 'SPY'             # Compare against S&P 500
RS_MIN_OUTPERFORMANCE = 2.0      # Must beat SPY by 2%+
RS_LOOKBACK_BARS = 20            # Compare over 20 bars

# Volume scoring (20 points max)
VOLUME_SURGE_MULTIPLIER = 2.0    # 2x average = surge
VOLUME_TREND_BARS = 3            # Volume increasing over 3 bars
FLOAT_ROTATION_MIN = 0.02        # 2% of float traded = active

# Price Action scoring (20 points max)
CONSOLIDATION_BARS = 10          # Look back 10 bars for base
FALSE_BREAKOUT_BARS = 5          # No false breaks in last 5 bars
DISTANCE_52W_HIGH = 0.10         # Within 10% of 52-week high

# Momentum scoring (15 points max)
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
RSI_BULLISH = 60                 # RSI > 60 = bullish
RSI_BEARISH = 40                 # RSI < 40 = bearish
STOCH_PERIOD = 14

# Institutional Flow scoring (10 points max)
BLOCK_TRADE_MIN = 10000          # 10K shares = block trade
SPREAD_TIGHT_MAX = 0.002         # Bid/ask < 0.2% = tight

# Volatility scoring (10 points max)
ATR_EXPANSION_BARS = 5           # ATR expanding over 5 bars
BB_WIDTH_THRESHOLD = 2.0         # Bollinger Band width

# Scanner timing
SCANNER_INTERVAL_SECONDS = 60    # Scan every 60 seconds
SCANNER_COOLDOWN_SYMBOL = 300    # Don't rescan same symbol for 5 min

# v14 backward compatibility - old scanner constants
BREAKOUT_K_ATR = 1.5            # ATR multiplier (now in professional_scanner)
BREAKOUT_V_MULT = 1.5           # Volume multiplier (now in professional_scanner)
BREAKOUT_MFI_THRESHOLD = 50.0   # MFI threshold (now in professional_scanner)

# ============================================================================
# UNUSUAL OPTIONS ACTIVITY (UOA) SCANNER
# ============================================================================

# Options minimum requirements
OPTIONS_MIN_VOLUME = 500         # 500 contracts minimum
OPTIONS_MIN_PREMIUM = 0.50       # $0.50 minimum premium
OPTIONS_MIN_OI = 100            # 100 open interest minimum

# UOA scoring
OPTIONS_VOLUME_MULTIPLIER = 2.0  # Volume > 2x avg OI = unusual
OPTIONS_IV_PERCENTILE_MIN = 50   # IV rank > 50th percentile
OPTIONS_SWEEP_DETECT = True      # Detect multi-exchange sweeps

# Options filtering
OPTIONS_MAX_DTE = 60             # Max 60 days to expiration
OPTIONS_MIN_DTE = 7              # Min 7 days to expiration
OPTIONS_AVOID_WEEKLIES = False   # True = monthly only

# Scanner timing
OPTIONS_SCAN_INTERVAL = 120      # Scan every 2 minutes

# ============================================================================
# 24/7 MARKET DATA
# ============================================================================

# Extended hours support
EXTENDED_HOURS_ENABLED = True
PREMARKET_START = "04:00"        # 4:00 AM ET
REGULAR_START = "09:30"          # 9:30 AM ET
REGULAR_END = "16:00"            # 4:00 PM ET
AFTERHOURS_END = "20:00"         # 8:00 PM ET

# Historical fallback (for weekends/nights)
HISTORICAL_FALLBACK_ENABLED = True
FALLBACK_TRIGGER_SECONDS = 5     # Use historical if no tick for 5s
FALLBACK_COOLDOWN_SECONDS = 300  # Don't refetch for 5 min
HISTORICAL_DURATION = "1 D"
HISTORICAL_BAR_SIZE = "5 mins"

# Quote staleness
QUOTE_STALE_SEC = 30             # Quote considered stale after 30s

# ============================================================================
# POSITION MANAGEMENT
# ============================================================================

# Position tracking
POSITION_SYNC_INTERVAL = 300     # Sync with IB every 5 minutes
POSITION_WARMUP_INTERVAL = 10    # First 60s, sync every 10s
POSITION_WARMUP_DURATION = 60

# Position filtering
FILTER_DELISTED = True           # Remove delisted stocks
FILTER_OTC = True                # Remove OTC stocks
FILTER_CVR = True                # Remove CVR rights
FILTER_WARRANTS = True           # Remove warrants
FILTER_MIN_PRICE = 1.0           # Filter stocks < $1

# ============================================================================
# DASHBOARD
# ============================================================================

DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 8052
DASHBOARD_DEBUG = False
DASHBOARD_THEME = "light"        # light or dark

# Dashboard refresh rates
DASHBOARD_REFRESH_MS = 2000      # Refresh every 2 seconds
DASHBOARD_HEARTBEAT_MS = 1000    # Heartbeat every 1 second

# ============================================================================
# HEARTBEAT & HEALTH MONITORING
# ============================================================================

HEARTBEAT_SEC = 30               # Send heartbeat every 30 seconds
HEALTH_CHECK_INTERVAL = 60       # Check system health every 60 seconds

# ============================================================================
# RISK MANAGEMENT
# ============================================================================

# Portfolio limits
MAX_POSITION_SIZE = 0.10         # 10% of portfolio max per position
MAX_POSITIONS = 20               # Max 20 open positions
MAX_DAILY_LOSS = 0.05           # Stop trading if -5% daily loss

# Per-trade limits
MAX_POSITION_LOSS = 0.02         # Stop loss at -2% per position
MAX_POSITION_GAIN = 0.10         # Take profit at +10% per position

# ============================================================================
# LOGGING & MONITORING
# ============================================================================

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_FILE = "qtrade.log"
LOG_MAX_BYTES = 10_000_000       # 10 MB
LOG_BACKUP_COUNT = 5

# Alerts
ALERTS_ENABLED = True
ALERT_SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK", "")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL", "")
ALERT_ON_CONNECTION_LOSS = True
ALERT_ON_DAILY_LOSS = True
ALERT_ON_POSITION_STOP = True

# ============================================================================
# ADVANCED FEATURES
# ============================================================================

# Backtesting
BACKTEST_ENABLED = False
BACKTEST_START_DATE = "2024-01-01"
BACKTEST_END_DATE = "2024-12-31"

# Machine learning
ML_ENABLED = False
ML_MODEL_PATH = "models/breakout_classifier.pkl"
ML_RETRAIN_INTERVAL = 86400      # Retrain daily

# ============================================================================
# DEVELOPMENT & TESTING
# ============================================================================

TESTING_MODE = False             # True = use mocked IB
MOCK_MARKET_OPEN = True          # True = simulate market open
PERFORMANCE_PROFILING = False    # True = enable profiling
