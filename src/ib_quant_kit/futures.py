
from datetime import date, timedelta
from typing import Tuple
QUARTER_CODES = ["H","M","U","Z"]
CODE_TO_MONTH = {"H":3, "M":6, "U":9, "Z":12}
def quarterly_code(d: date) -> Tuple[int, str]:
    y = d.year
    for code in QUARTER_CODES:
        m = CODE_TO_MONTH[code]
        if d.month <= m: return y, code
    return y+1, "H"
def third_friday(y: int, m: int) -> date:
    d = date(y, m, 1)
    while d.weekday() != 4: d += timedelta(days=1)
    return d + timedelta(days=14)
def roll_window_for_quarterly(y: int, code: str, pre_days: int = 7) -> Tuple[date, date]:
    m = CODE_TO_MONTH[code]; expiry_est = third_friday(y, m); roll_start = expiry_est - timedelta(days=pre_days)
    return roll_start, expiry_est
def choose_front_month(today: date, roll_pre_days: int = 7) -> Tuple[int, str]:
    y, code = quarterly_code(today)
    roll_start, _ = roll_window_for_quarterly(y, code, pre_days=roll_pre_days)
    if today >= roll_start:
        idx = QUARTER_CODES.index(code); next_code = QUARTER_CODES[(idx+1)%4]
        next_year = y + (1 if next_code == "H" and code == "Z" else 0)
        return next_year, next_code
    return y, code
