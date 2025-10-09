
# Quant Trading v11 (focused fixes)

**What’s fixed**
- **DRY_RUN** is a single source of truth (env `DRY_RUN=0/1`). No more “ghost dry-run” pathways.
- **Non-tradable filtering:** At session start we reconcile positions and **do not subscribe** to non‑tradable symbols. We still monitor live positions (risk first), but unsubscribe once they go flat.
- **Market/position subscriptions:** Subscribes only when `check_tradable()` is true **or** there’s an open position.
- **Farm & connectivity watchdog:** Standardized log lines (similar to your screenshot) plus heartbeat for the dashboard.

## Quick start
```bash
# (optional) create a positions file for demo
echo '{"ES":1,"NQ":0,"CL":-1}' > positions.json

# run the bot
export DRY_RUN=0
python main.py
```

## Dashboard
Run in another terminal:
```bash
python dashboard.py
```
Open your browser to `http://localhost:8765`

## Integrations to wire in your env
- Replace `IBClient.connect/refresh_positions/subscribe_symbol/place_order` with real ibapi calls.
- Feed `on_error_code(code, msg)` from `error()` callback to update farm flags.
- Feed contract details to set `ContractInfo.tradable` accordingly.
