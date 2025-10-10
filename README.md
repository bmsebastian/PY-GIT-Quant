# QTrade v13.5 (Clean Rebuild)

A minimal, runnable scaffold of your quant trading app with:
- Clean `config.py` (no PowerShell lines)
- `TradeManager` orchestration
- IB client wrapper (works with `ib_insync` if installed; otherwise stubs so app still boots)
- Tradability/staleness guards
- Order lifecycle tracker
- Simple EMA crossover strategy
- `scripts/smoke_ib.py` sanity script

## Quick Start
```bash
# (optional) create venv
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt

# Run main (paper + dry-run by default)
python main.py
```

### IBKR Notes
If `ib_insync` is installed and TWS/Gateway is running, the app will connect.
If not installed or not running, the app will use a safe stub so the process still starts.

### Files
- `config.py`: settings & risk limits
- `ib_client.py`: IBKR wrapper (real or stub)
- `trade_manager.py`: main orchestrator loop
- `market_data.py`: subscriptions + tick handling (real or simulated)
- `data_guard.py`: per-symbol staleness guard
- `order_tracker.py`: order lifecycle tracking
- `risk.py`: circuit-breakers
- `contracts.py`: qualification & symbol hygiene
- `strategies/ema_crossover.py`: simple example strategy
- `scripts/smoke_ib.py`: quick market data check
