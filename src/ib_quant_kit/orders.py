
from dataclasses import dataclass
from typing import Dict, Optional
from threading import Lock
@dataclass
class OrderRecord:
    client_order_id: int; idempotency_key: str; perm_id: Optional[int] = None; status: str = "Unknown"
class OrderBook:
    def __init__(self):
        self._by_client_id: Dict[int, OrderRecord] = {}; self._by_idem: Dict[str, int] = {}; self._lock = Lock()
    def get_or_assign(self, idempotency_key: str, next_id: int) -> int:
        with self._lock:
            if idempotency_key in self._by_idem: return self._by_idem[idempotency_key]
            self._by_idem[idempotency_key] = next_id; self._by_client_id[next_id] = OrderRecord(next_id, idempotency_key); return next_id
    def update_status(self, client_order_id: int, status: str, perm_id: Optional[int] = None):
        with self._lock:
            rec = self._by_client_id.get(client_order_id)
            if rec:
                rec.status = status
                if perm_id is not None: rec.perm_id = perm_id
    def find_by_perm(self, perm_id: int) -> Optional[int]:
        with self._lock:
            for cid, rec in self._by_client_id.items():
                if rec.perm_id == perm_id: return cid
        return None
order_book = OrderBook()
