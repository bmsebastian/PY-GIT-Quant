from dataclasses import dataclass, field
from typing import Dict, Optional

@dataclass
class OrderStatus:
    orderId: Optional[int]
    status: str = "PendingSubmit"
    permId: Optional[int] = None

class OrderBook:
    def __init__(self):
        self._by_id: Dict[int, OrderStatus] = {}
    def update_status(self, orderId: int, status: str, permId: Optional[int] = None):
        st = self._by_id.get(orderId) or OrderStatus(orderId=orderId)
        st.status = status
        if permId is not None:
            st.permId = permId
        self._by_id[orderId] = st

order_book = OrderBook()
