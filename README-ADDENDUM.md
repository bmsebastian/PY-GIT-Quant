# Addendum: Consolidated Improvements (Generated 2025-10-07T21:16:46)

This addendum introduces the following modules into `src/ib_quant_kit/`:

- `selection_engine.py` – Live candidate selection with IB scanner and cached fallback
- `options_factory.py` – Options Δ-window + expiry regime (0DTE/weekly/monthly) via Greeks snapshots
- `lifecycle.py` – Centralized order state machine (timeouts, cancel-on-timeout)
- `symbol_watch.py` – Per-symbol staleness guard for ticks/news
- `pnl_fees.py` – Commission accrual from `commissionReport` and net PnL snapshot
- `fusion.py` – Event fusion scoring (news burst × earnings proximity)
- `normalizer.py` – Cross-asset z-score ranking
- `ops_alerts.py` – Minimal notifier (stdout)
- `compliance.py` – Ban/whitelist + min price guardrails
- `sizing.py` – Per-instrument notional caps

## Wiring Hints

- **Lifecycle:** Instantiate `OrderLifecycle(ib_client)` in your live runner and call `lifecycle.heartbeat()` each main loop cycle.
- **Staleness:** Update watch on tick/news and gate order generation via `watch.is_fresh(symbol)`.
- **PnL/Fees:** Instantiate `PnLTracker(ib_client)` and surface `snapshot()` in your dashboard/logs.
- **Options Targeting:** From top underlyings, call `OptionsFactory(ib).build(underlying, regime='0DTE', delta_window=(0.30,0.45))`.
- **Selection:** Use `SelectionEngine(ib, Compliance(...), ClassNormalizer())` then `.select(top_n=25)`.
- **Fusion:** Compute `fused_score(...)` and add it to your ranking if you have news/earnings adapters.
- **Contract Hygiene:** Before placing orders, verify `reqContractDetails` fields (exchange/currency/expiry) in your existing order path.

## Reproducibility

- Added a basic `Makefile` with `lint`, `test`, `run-paper`, `run-live`, and `backtest` targets.
- Appended common scientific stack pins to `requirements.txt`.

## Notes

- New modules are self-contained and avoid environment variables by default.
- Adjust integration points in your `app/*` runners and `ib_client` where noted.
