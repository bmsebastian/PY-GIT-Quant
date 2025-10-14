# QTrade v14A - Quantitative Trading Platform

A production-ready quantitative trading system with subscription capacity management, dual-scanner architecture, and real-time dashboard monitoring.

## 🚀 Features

### Core Trading System
- **IB Integration**: Full Interactive Brokers TWS/Gateway connectivity via ib_insync
- **Subscription Management**: Smart 50-subscription limit handling with priority system
- **Position Tracking**: Real-time position monitoring with automatic EMA calculations
- **Market Data**: Live tick streaming with historical fallback for paper trading

### Scanning & Strategy
- **Dual Scanner System**:
  - **Position Scanner**: Fast monitoring of existing holdings (10s intervals)
  - **Market Scanner**: IB scanner API integration for new opportunities (60s intervals)
- **Breakout Scanner**: Multi-factor technical analysis
  - ATR breakout detection (k*ATR threshold)
  - Volume surge confirmation (v_mult multiplier)
  - EMA trend alignment (8/21 periods)
  - MFI money flow index filter
- **Capacity-Aware**: Automatically limits monitoring to available subscription slots

### Dashboard & Monitoring
- **Web Dashboard**: Real-time monitoring at http://localhost:8052
  - Subscription capacity gauge with visual alerts
  - Live position P&L with EMA trend indicators
  - Breakout signal list with scoring
  - System health metrics
- **Clean White UI**: Professional light theme (not dark mode)
- **Auto-refresh**: 2-second update intervals

### Technical Indicators
- EMA (Exponential Moving Average)
- SMA (Simple Moving Average)
- ATR (Average True Range with Wilder's smoothing)
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Bollinger Bands
- MFI (Money Flow Index)
- Volume SMA

### Risk Management
- Circuit breaker on daily loss threshold
- Maximum open orders limit
- Non-tradable symbol filtering (CVR, OTC, warrants)
- Position priority protection in subscription cleanup

## 📋 Requirements

```
Python 3.8+
Interactive Brokers TWS or Gateway (Paper or Live)
```

## 🔧 Installation

```bash
# 1. Clone repository
git clone <your-repo>
cd qtrade

# 2. Create virtual environment
python -m venv .venv

# Activate (Windows)
.\.venv\Scripts\activate

# Activate (macOS/Linux)
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

## ⚙️ Configuration

Edit `config.py` to customize:

```python
# Connection
IB_GATEWAY_HOST = "127.0.0.1"
IB_GATEWAY_PORT = 7497  # 7497=Paper, 7496=Live

# Subscription Management
MAX_IB_SUBSCRIPTIONS = 50  # IB limit for paper trading
POSITION_BUFFER = 5  # Reserve slots for new positions

# Scanner Settings
BREAKOUT_K_ATR = 1.5  # ATR breakout multiplier
BREAKOUT_V_MULT = 1.5  # Volume surge multiplier
BREAKOUT_MFI_THRESHOLD = 50.0  # Money flow threshold

# Risk Management
MAX_DAILY_LOSS = 1000.0  # Circuit breaker
MAX_OPEN_ORDERS = 10  # Concurrent order limit
```

## 🏃 Running QTrade

### 1. Start TWS/Gateway
- Open Interactive Brokers TWS or Gateway
- Enable API connections (Configure → API → Settings)
- Note the port (7497 for paper, 7496 for live)

### 2. Launch QTrade
```bash
python main.py
```

### 3. Access Dashboard
Open browser to: **http://localhost:8052**

You should see:
- IB connection status (green = connected)
- Subscription capacity gauge
- Live positions with P&L
- Breakout signals (when detected)

## 📊 Dashboard Guide

### Subscription Capacity Gauge
- **Green (OK)**: < 45 subscriptions (safe zone)
- **Yellow (NEAR)**: 45-50 subscriptions (approaching limit)
- **Red (OVER)**: > 50 subscriptions (auto-cleanup triggered)

### Position Table
- Real-time P&L with color coding
- EMA8/EMA21 trend indicators
- Triangle symbols: ▲ (bullish), ▼ (bearish), ● (neutral)

### Breakout Signals
- Sorted by score (higher = stronger signal)
- Direction: UP (long) or DOWN (short)
- Label shows parameters used (ATR, VOL multipliers)

## 🏗️ Architecture

```
main.py
├── TradeManager (position sync + market data orchestration)
│   ├── IBClient (connection wrapper)
│   └── MarketDataBus (subscriptions + tick streaming)
│
├── ScannerCoordinator (dual scanner system)
│   ├── BreakoutScanner (position monitoring)
│   └── MarketScanner (IB scanner API)
│
├── DashboardServer (Flask web UI)
└── StateBus (thread-safe global state)
```

### Subscription Priority System
1. **PRIORITY_POSITION (100)**: Open positions - never removed
2. **PRIORITY_SCANNER_TOP (50)**: High-scoring breakout signals
3. **PRIORITY_SCANNER_NORMAL (25)**: Regular scanner results

When over 50 subscriptions, lowest priority symbols are auto-removed.

## 🐛 Troubleshooting

### "Not in a git repository" error
The auto_commit script requires git. Either:
- Initialize git: `git init`
- Or manually commit: `git add . && git commit -m "v14A"`

### Dashboard shows "No positions" but you have positions
- Check symbol filters in `contracts.py`
- Verify symbols aren't CVR, OTC, or warrants
- Look for filtering logs: `grep "Dashboard filtering" qtrade.log`

### Subscription limit warnings
- **Expected behavior** in scanner mode
- System auto-removes lowest priority subscriptions
- Positions are always protected (highest priority)

### No market data / NaN prices
**Paper Trading:**
- Normal on weekends (markets closed)
- System uses historical data as fallback
- Check logs for "Historical data" messages

**Live Trading:**
- Verify IB subscription entitlements
- Check TWS market data settings
- Ensure `reqMarketDataType(1)` succeeded

### Scanner finds no signals
- **Market conditions**: Breakouts are rare
- **Adjust parameters**: Lower `BREAKOUT_K_ATR` to 1.0
- **Check universe**: Verify symbols in scanner config

## 📁 File Reference

### Core Files
- `main.py` - Entry point and main loop
- `config.py` - All configuration settings
- `trade_manager.py` - Position tracking and orchestration
- `market_data.py` - Subscription management and tick streaming
- `ib_client.py` - IB connection wrapper
- `state_bus.py` - Thread-safe global state
- `contracts.py` - Contract qualification and filtering

### Scanning & Strategy
- `scanner_coordinator.py` - Dual scanner orchestrator
- `strategies/breakout_scanner.py` - Multi-factor breakout detection
- `scanner.py` - IB scanner API integration
- `indicators.py` - Technical indicator library

### Dashboard & Tools
- `dashboard_server.py` - Flask web dashboard
- `subscription_monitor.py` - CLI monitoring tool
- `check_positions.py` - Quick position checker

### Support
- `risk.py` - Risk management rules
- `requirements.txt` - Python dependencies
- `scripts/` - Utility scripts

## 🔐 Security Notes

**Never commit sensitive data:**
- IB account credentials
- API keys
- Trade logs with real positions

Add to `.gitignore`:
```
qtrade.log
*.log
.env
secrets.py
```

## 📈 Performance Tips

### Optimize Subscription Usage
- Position scanner: 10-20 positions = plenty of capacity
- Market scanner: Limited to available slots after positions
- Typical usage: 5 positions + 40 scanner slots = 45 total

### Reduce Log Spam
Set in `config.py`:
```python
LOG_LEVEL = "WARNING"  # Change from INFO
```

### Scanner Intervals
Faster scans = more signals but more API calls:
```python
position_scan_interval = 10  # Fast (positions)
market_scan_interval = 60    # Slower (market-wide)
```

## 🤝 Contributing

Pull requests welcome! Please:
1. Follow existing code style
2. Add docstrings to new functions
3. Update README for new features
4. Test with paper trading first

## 📄 License

[Your License Here]

## 📞 Support

Issues: [GitHub Issues](your-repo/issues)
Docs: [Full Documentation](your-docs-url)

---

**QTrade v14A** - Built with ❤️ for quantitative traders
