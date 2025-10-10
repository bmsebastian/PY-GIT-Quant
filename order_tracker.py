import time

class OrderTracker:
    def __init__(self, timeout_sec=30):
        self.timeout = timeout_sec
        self.state = {}  # orderId -> dict(status=..., ts=...)

    def on_order_status(self, orderId, status):
        rec = self.state.setdefault(orderId, {})
        rec["status"] = status
        rec["ts"] = time.time()

    def on_fill(self, orderId, fill):
        rec = self.state.setdefault(orderId, {})
        rec["last_fill"] = fill
        rec["ts"] = time.time()

    def timed_out(self, orderId):
        rec = self.state.get(orderId)
        if not rec: return False
        return (time.time() - rec.get("ts", 0)) > self.timeout

    def open_count(self):
        return sum(1 for v in self.state.values() if v.get("status") not in ("Filled","Canceled"))
