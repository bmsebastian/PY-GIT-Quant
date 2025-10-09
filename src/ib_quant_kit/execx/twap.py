
import time
def run_twap(submit_fn, total_qty: float, slices: int, delay_sec: float):
    """Call submit_fn(qty) 'slices' times with delay in between."""
    per = total_qty / max(1, slices)
    order_ids = []
    for i in range(slices):
        oid = submit_fn(per)
        order_ids.append(oid)
        time.sleep(max(0.0, delay_sec))
    return order_ids
