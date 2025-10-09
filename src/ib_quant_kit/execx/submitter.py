import time, os, queue, threading
from typing import Optional
from ..config import settings
from ..risk.limits import RiskState
from ..orders.order_book import order_book
from ..utils.contracts import qualify_contract

class RetryQueue:
    def __init__(self, max_retries=3, backoff=1.5):
        self.q = queue.Queue()
        self.max_retries = max_retries
        self.backoff = backoff
        self._stop = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop = True

    def submit(self, fn, *args, **kwargs):
        self.q.put((fn, args, kwargs, 0))

    def _run(self):
        while not self._stop:
            try:
                fn, args, kwargs, attempts = self.q.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                fn(*args, **kwargs)
            except Exception as e:
                if attempts + 1 < self.max_retries:
                    time.sleep(self.backoff ** (attempts + 1))
                    self.q.put((fn, args, kwargs, attempts + 1))
                else:
                    print(f"[RetryQueue] Gave up after {attempts+1} attempts: {e}")

retry_queue = RetryQueue()

def kill_switch_engaged() -> bool:
    return os.path.exists(settings.KILL_SWITCH_FILE)

def submit_order(ib, risk_state: RiskState, symbol: str, side: str, qty: float, price: float, order_type="MKT"):
    if kill_switch_engaged():
        print("[KILL] Kill switch engaged — blocking order submit.")
        return None

    if not risk_state.allowed_order(symbol, side, price, qty):
        print(f"[RISK] Rejected {side} {qty} {symbol} @ {price}")
        return None

    contract = qualify_contract(ib, symbol)

    if settings.DRY_RUN:
        print(f"[DRY] {side} {qty} {symbol} {order_type} @ {price} (not submitted)")
        return {"orderId": None, "dry_run": True}

    def _do_submit():
        # Placeholder for real ib.placeOrder() call
        fake_oid = int(time.time() * 1000) % 1_000_000
        order_book.update_status(fake_oid, "Submitted", None)
        print(f"[SUBMIT] oid={fake_oid} {side} {qty} {symbol} ({order_type})")

    retry_queue.submit(_do_submit)
    retry_queue.start()
    return {"queued": True}
