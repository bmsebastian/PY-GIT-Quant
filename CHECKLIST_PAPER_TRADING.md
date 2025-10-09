# Paper Trading Readiness Checklist

## Critical
- [x] Position callbacks wired (`position`, `positionEnd`, `accountSummary*`, `commissionReport`)
- [x] `reqPositions()` called on start
- [x] PnL tracker implemented and subscribed to fills & marks
- [x] Risk checks enforced in order routing
- [x] Circuit breaker present and referenced
- [x] Config `dry_run` (lowercase) + `data_dir` exists
- [x] Duplicate orders module removed

## Nice-to-have
- [ ] Web dashboard: positions, orders, PnL
- [ ] Event fusion: news/earnings/scanner score
- [ ] Unit tests for reconnection & idempotent order flow

- [x] Options delta/expiry selection helper present
- [x] Flask+WS dashboard scaffold present
