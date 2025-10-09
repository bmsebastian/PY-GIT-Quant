
# Quant Trading — Unified v4 (cont-4)

This bundle applies Claude's 11-point review and adds the "nice-to-have" scaffolds.
**Positions & average cost are sourced from IBKR** via EWrapper callbacks.

## What changed (highlights)
- Added IB **position/account callbacks** and **heartbeat()**, and call **reqPositions**/**reqAccountSummary** in `ib_client.py`.
- Implemented **PnL tracker** with `mark_price`, `on_ib_position`, `on_fill`, and `snapshot`.
- Deduped `requirements.txt`.
- Ensured `config.py` exposes `data_dir` with `DATA_DIR` env default.
- Removed duplicate `order_book.py` when `orders.py` exists.
- Introduced **commission model** (`costs/commission.py`) and **circuit breaker** (`safety/circuit_breaker.py`).
- Added **event fusion score**, **options delta picker** scaffold, and **dashboard** stub.
- Replaced `main.py` with a safe loop that treats IBKR positions as the sole source of truth.
- Extended `.env.example` with missing vars.
- Created `data/` folder.

## Pre-implementation checklist
- [ ] Verify `ib_client.py` paths/imports match your package layout.
- [ ] Wire `execDetails` to pass commissions into `pnl.on_fill(..., commission=...)`.
- [ ] In market data callbacks, call `pnl.mark_price(symbol, price)`.
- [ ] Route EWrapper `position(...)` into `pnl.on_ib_position(...)` if you want PnL to mirror IB immediately.
- [ ] Integrate `safety/circuit_breaker.py` into your risk checks.
- [ ] For options, connect `tickOptionComputation` to populate deltas for `options/delta_picker.py`.

## Running (paper mode suggested)
```bash
python bootstrap.py setup
# Launch IB Gateway/TWS in paper mode (port 7497)
export DRY_RUN=1
python main.py
```

## Notes
- Keep IBKR as **source of truth for position monitoring**, do not infer from local orders.
- Extend the dashboard (FastAPI) only after core wiring is stable.
- Add unit tests for: position reconciliation, staleness guard, circuit breaker, and order lifecycle.
