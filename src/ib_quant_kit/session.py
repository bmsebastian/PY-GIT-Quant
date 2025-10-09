
from datetime import datetime
def resolve_session(now: datetime) -> str:
    h = now.hour
    if 13 <= h < 20: return "RTH"
    elif 9 <= h < 13 or 20 <= h or h < 1: return "ETH"
    else: return "GTH"
