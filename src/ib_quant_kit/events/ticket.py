
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
@dataclass
class EventTicket:
    ts: datetime
    kind: str           # 'earnings','headline','macro','vol_spike'
    symbol: str
    urgency: int        # 1..5
    half_life_min: int
    session_hint: Optional[str] = None
