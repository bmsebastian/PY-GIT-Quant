# Quick Start — Paper Trading (IBKR)

**Updated:** 2025-10-07T22:47:32.233633Z

## 1) Requirements
- Python 3.10–3.12
- `ibapi` >= 10.19
- TWS or IB Gateway (Paper Account), API enabled

## 2) Install
```bash
python -m venv .venv
# Windows PowerShell: set-executionpolicy bypass -scope process -force
. .venv/bin/activate  # or .venv\Scripts\activate
pip install -r requirements.txt
```

## 3) Env
```bash
export DRY_RUN=0
export IB_HOST=127.0.0.1
export IB_PORT=7497
export IB_CLIENT_ID=7
export ENABLE_RTH_GUARD=1
```

## 4) Start
```bash
python -m ib_quant_kit.bootstrap  # if present
# or call your entrypoint that constructs IBClient and calls start()
```


## Options Module
Use `ib_quant_kit.options.factory.pick_contracts_by_delta(...)` with an `available_chain` you build from IB `tickOptionComputation`.

## Dashboard
Run `python dashboard/app.py` (requires `flask` and `flask-sock`). It will read `./data/positions.json` and `./data/pnl.json` and push updates over WebSocket.
