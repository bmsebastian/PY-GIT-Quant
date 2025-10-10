import logging
logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(self, max_daily_loss: float, max_open_orders: int):
        self.max_daily_loss = max_daily_loss
        self.max_open_orders = max_open_orders
        self.today_pnl = 0.0  # placeholder; wire to account PnL later

    def ok(self, order_tracker) -> bool:
        if self.today_pnl <= -abs(self.max_daily_loss):
            logger.error(f"Circuit breaker: PnL {self.today_pnl} <= -{self.max_daily_loss}")
            return False
        oc = order_tracker.open_count()
        if oc > self.max_open_orders:
            logger.error(f"Too many open orders: {oc} > {self.max_open_orders}")
            return False
        return True
