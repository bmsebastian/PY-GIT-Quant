import logging, time
from typing import List

from config import WATCHLIST, POSITION_RECON_SEC, QUOTE_STALE_SEC, ORDER_TIMEOUT_SEC, DRY_RUN, MAX_DAILY_LOSS, MAX_OPEN_ORDERS
from ib_client import IBClient
from market_data import MarketDataBus
from order_tracker import OrderTracker
from risk import RiskManager
from strategies.ema_crossover import EMACrossover

logger = logging.getLogger(__name__)

class TradeManager:
    def __init__(self):
        self.ibc = IBClient()
        self.ib = self.ibc.connect()
        self.md = MarketDataBus(self.ib)
        self.order_tracker = OrderTracker(timeout_sec=ORDER_TIMEOUT_SEC)
        self.risk = RiskManager(max_daily_loss=MAX_DAILY_LOSS, max_open_orders=MAX_OPEN_ORDERS)
        self.strats = [EMACrossover(self.md, self.order_tracker, dry_run=bool(DRY_RUN))]
        self._last_recon = 0
        self._started = False

    def start(self):
        logger.info("TradeManager starting...")
        # Subscribe to watchlist
        for sym in WATCHLIST:
            self.md.subscribe(sym.strip())
        self._started = True
        logger.info(f"Subscribed to {len(WATCHLIST)} symbols: {WATCHLIST}")

    def heartbeat(self):
        if not self._started:
            return
        # Recon positions periodically (stubbed for now)
        now = time.time()
        if now - self._last_recon > POSITION_RECON_SEC:
            self._last_recon = now
            logger.debug("Reconciling positions (stub)")

        # Run strategies
        for strat in self.strats:
            try:
                strat.on_bar()  # simple time-based evaluation
            except Exception as e:
                logger.exception("Strategy error")

        # Risk checks
        if not self.risk.ok(self.order_tracker):
            logger.error("Risk breached; stopping trading loop")
            self.stop()

    def stop(self):
        logger.info("TradeManager stopping...")
        try:
            self.ibc.disconnect()
        except Exception:
            pass
