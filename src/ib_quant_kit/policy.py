
from dataclasses import dataclass
@dataclass
class ExecPolicy:
    session: str; limit_only: bool; clip_qty: float; max_slip_bps: int; tif: str; outside_rth: bool
DEFAULT_POLICIES = {
    "RTH": ExecPolicy("RTH", False, 1.0, 20, "DAY", True),
    "ETH": ExecPolicy("ETH", True,  0.5, 60, "GTC", True),
    "GTH": ExecPolicy("GTH", True,  0.3, 90, "GTC", True),
}
