
from __future__ import annotations
from datetime import datetime, timezone
import yaml, os, time
from ..ib_client import IBClient
from ..cal.market_calendar import nyse_session
from ..strategy.intraday import bars_to_df
from ..strategy.library import run_pipeline
from ..risk.limits import RiskState, RiskLimits
from ..risk.helpers import allowed_order, DEFAULT_LIMITS
from ..execx.quote_aware import quote_aware_limit
from ..store.parquet_store import append_jsonl
from ..rtbar import rtbars
from ..pnl import pnl
from ..store.pnl_logger import append_pnl
from ..alerts.slack_alerts import send_slack

def load_pipeline():
    path = os.path.join(os.path.dirname(__file__), "..", "data", "strategies.yaml")
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg.get("symbols", {}).get("default", [])

def run_once(symbols=None):
    from ..config import settings
    symbols = symbols or settings.universe
    ib = IBClient(); ib.start()
    import threading
    threading.Thread(target=ib.heartbeat, daemon=True).start()

    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    sess = nyse_session(now)
    logs = []
    state = RiskState(start_equity=100000.0, curr_equity=100000.0)
    pipeline = load_pipeline()

    for sym in symbols:
        from ibapi.contract import Contract
        c = Contract(); c.symbol, c.secType, c.exchange, c.currency = sym, "STK", "SMART", "USD"
        qc = ib.qualify(c)
        # prefer RT bars; fall back to historical
        reqId = ib.subscribe_stock_nbbo(qc)
        time.sleep(0.3)
        rt_rows = rtbars.get_bars_1min(reqId, int(time.time()*1000), lookback_min=30)
        if rt_rows:
            df = bars_to_df(rt_rows)
        else:
            bars = ib.fetch_hist_bars(qc, durationStr="30 M", barSizeSetting="1 min", whatToShow="TRADES", useRTH=1)
            df = bars_to_df(bars)
        side, trigger = run_pipeline(df, pipeline)
        bid = ib._bid.get(reqId); ask = ib._ask.get(reqId)
        limit = quote_aware_limit(bid, ask, side, max_slip_bps=20, fallback=trigger or (bid or ask or 0.01))
        notional = (limit or 0.0) * 1.0
        ok, reason = allowed_order(sym, "RTH", notional, portfolio_gross=0.0, state=state, limits=DEFAULT_LIMITS, now=datetime.utcnow())
        if side != "FLAT" and ok:
            oid = ib.submit_limit(qc, side=side, qty=1.0, limit=limit, tif="DAY", outside_rth=True, idempotency_key=f"INTRADAY-{sym}-{now.isoformat()}")
            row = {"ts": now.isoformat(), "symbol": sym, "side": side, "limit": limit, "oid": oid}
            logs.append(row)
        else:
            logs.append({"ts": now.isoformat(), "symbol": sym, "side": "FLAT", "reason": reason})

    append_jsonl(logs, "logs/intraday_decisions.jsonl")
    # PnL snapshot
    snap = pnl.snapshot()
    append_pnl(snap)
    if snap["net"] < -1000:
        send_slack(f"Warning: Net PnL {snap['net']:.2f}")
    return logs
