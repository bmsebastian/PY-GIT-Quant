
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
try:
    import pandas_market_calendars as mcal
except Exception:
    mcal = None

@dataclass
class SessionInfo:
    is_open: bool
    open_time: datetime | None
    close_time: datetime | None

def nyse_session(now: datetime) -> SessionInfo:
    if mcal is None:
        h = now.hour
        is_open = 13 <= h < 20
        base = now.replace(hour=13, minute=30, second=0, microsecond=0)
        return SessionInfo(is_open, base, base.replace(hour=20, minute=0))
    cal = mcal.get_calendar("XNYS")
    sched = cal.schedule(start_date=now.date(), end_date=now.date())
    if sched.empty:
        return SessionInfo(False, None, None)
    o = sched.iloc[0]["market_open"].to_pydatetime().replace(tzinfo=timezone.utc)
    c = sched.iloc[0]["market_close"].to_pydatetime().replace(tzinfo=timezone.utc)
    return SessionInfo(o <= now <= c, o, c)
