from enum import Enum, auto
import time

class OrderState(Enum):
    NEW = auto()
    SUBMITTED = auto()
    PARTIALLY_FILLED = auto()
    FILLED = auto()
    CANCELLED = auto()
    REJECTED = auto()
    TIMEOUT = auto()

class OrderLifecycle:
    """
    Centralized order state machine with timeouts tied to IB/TWS callbacks.
    Expects ib_client to expose:
      - on_order_status(callback)
      - on_exec_details(callback)
      - on_open_order(callback)
      - cancel_by_perm_id(perm_id)
    """
    def __init__(self, ib_client, place_timeout_s=5, fill_timeout_s=120):
        self.ib = ib_client
        self.place_timeout_s = place_timeout_s
        self.fill_timeout_s = fill_timeout_s
        self._state = {}
        self._t0 = {}

        ib_client.on_order_status(self._on_status)
        ib_client.on_exec_details(self._on_exec)
        ib_client.on_open_order(self._on_open)

    def _on_open(self, order_id, order, contract):
        perm = getattr(order, "permId", None)
        if perm is None: return
        self._state[perm] = OrderState.SUBMITTED
        self._t0[perm] = time.time()

    def _on_status(self, order_id, status, filled, remaining, avg_fill_price, perm_id, **_):
        st = self._state.get(perm_id, OrderState.NEW)
        if status in ('Rejected','ApiCancelled'):
            self._state[perm_id] = OrderState.REJECTED if status=='Rejected' else OrderState.CANCELLED
            return
        if remaining == 0 and filled and filled > 0:
            self._state[perm_id] = OrderState.FILLED
        elif filled and filled > 0:
            self._state[perm_id] = OrderState.PARTIALLY_FILLED
        else:
            self._state[perm_id] = OrderState.SUBMITTED

    def _on_exec(self, exec_details):
        # Extend if per-fill aggregation is needed
        pass

    def heartbeat(self):
        now = time.time()
        for perm_id, st in list(self._state.items()):
            t0 = self._t0.get(perm_id, now)
            age = now - t0
            if st == OrderState.SUBMITTED and age > self.place_timeout_s:
                self.ib.cancel_by_perm_id(perm_id)
                self._state[perm_id] = OrderState.TIMEOUT
            elif st in (OrderState.SUBMITTED, OrderState.PARTIALLY_FILLED) and age > self.fill_timeout_s:
                self.ib.cancel_by_perm_id(perm_id)
                self._state[perm_id] = OrderState.TIMEOUT
