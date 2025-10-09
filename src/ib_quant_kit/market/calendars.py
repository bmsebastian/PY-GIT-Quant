from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

try:
    import exchange_calendars as xcals
except Exception:
    xcals = None

@dataclass
class SessionChecker:
    calendar: Optional[object]

    def is_open_now(self) -> bool:
        if self.calendar is None:
            return True
        now = datetime.utcnow()
        sched = self.calendar.schedule.index
        if len(sched) == 0:
            return True
        # Simplified check: is today in schedule and within open/close window
        today = now.date()
        if today not in self.calendar.sessions:
            return False
        # For brevity, return True when session exists; detailed timestamp check omitted
        return True

def get_calendar(name: str) -> SessionChecker:
    if xcals is None:
        return SessionChecker(None)
    try:
        cal = xcals.get_calendar(name)
        return SessionChecker(cal)
    except Exception:
        return SessionChecker(None)
