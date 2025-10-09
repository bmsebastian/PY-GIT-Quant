import time
from datetime import datetime
import pytz
from ..config import settings

class StalenessGuard:
    def __init__(self, max_age=settings.max_quote_age_secs):
        self.max_age = max_age
        self.last_ts_by_symbol = {}

    def mark(self, symbol: str):
        self.last_ts_by_symbol[symbol] = time.time()

    def is_stale(self, symbol: str) -> bool:
        ts = self.last_ts_by_symbol.get(symbol)
        if ts is None:
            return True
        return (time.time() - ts) > self.max_age

stale_guard = StalenessGuard()

def is_equity_rth_now() -> bool:
    if not settings.ENABLE_RTH_GUARD:
        return True
    et = pytz.timezone("America/New_York")
    now = datetime.now(et).time()
    start = datetime.strptime("09:30","%H:%M").time()
    end = datetime.strptime("16:00","%H:%M").time()
    return start <= now <= end
