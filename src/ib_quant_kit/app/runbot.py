
from datetime import datetime
from typing import List
from ..ib_client import IBClient
from ..session import resolve_session
from ..policy import DEFAULT_POLICIES
from ..events.ticket import EventTicket
from ..events.router import resolve_instrument_for_event
from ..risk.helpers import allowed_notional, DEFAULT_LIMITS
from ..store.parquet_store import append_jsonl

def _mock_events() -> List[EventTicket]:
    now = datetime.utcnow()
    return [
        EventTicket(ts=now, kind="headline", symbol="SPY", urgency=3, half_life_min=30),
        EventTicket(ts=now, kind="vol_spike", symbol="AAPL", urgency=4, half_life_min=20),
    ]

def run_once():
    ib = IBClient(); ib.start()
    import threading, time
    threading.Thread(target=ib.heartbeat, daemon=True).start()

    now = datetime.utcnow()
    session = resolve_session(now)
    pol = DEFAULT_POLICIES[session]
    ib.set_market_data_type_for_session(session)

    tickets = _mock_events()
    logs = []

    for ev in tickets:
        c = resolve_instrument_for_event(ev.symbol, now)
        qc = ib.qualify(c)
        reqId = ib.subscribe_stock_nbbo(qc) if qc.secType != "OPT" else ib.subscribe_option_greeks(qc)
        time.sleep(0.25)
        notional = 10000.0
        if not allowed_notional(notional, session, DEFAULT_LIMITS):
            logs.append({"ts": now.isoformat(), "msg": f"Risk gate blocked {ev.symbol} {session}", "notional": notional}); continue
        oid = ib.submit_limit(qc, side="BUY", qty=pol.clip_qty, limit=100.0, tif=pol.tif, outside_rth=pol.outside_rth, idempotency_key=f"{ev.symbol}-{session}-{now.isoformat()}")
        logs.append({"ts": now.isoformat(), "symbol": ev.symbol, "session": session, "oid": oid})

    append_jsonl(logs, "logs/decisions.jsonl")
    time.sleep(3)
    return logs
