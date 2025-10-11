import logging
import time

from config import (
    WATCHLIST,
    POSITION_RECON_SEC,
    ORDER_TIMEOUT_SEC,
    DRY_RUN,
    MAX_DAILY_LOSS,
    MAX_OPEN_ORDERS,
)
from ib_client import IBClient
from market_data import MarketDataBus
from order_tracker import OrderTracker
from risk import RiskManager
from strategies.ema_crossover import EMACrossover
from contracts import build_and_qualify
from state_bus import STATE

logger = logging.getLogger(__name__)

class TradeManager:
    def __init__(self):
        self.ibc = IBClient()
        self.ib = self.ibc.connect()
        self.md = MarketDataBus(self.ib)
        self.order_tracker = OrderTracker(timeout_sec=ORDER_TIMEOUT_SEC)
        self.risk = RiskManager(max_daily_loss=MAX_DAILY_LOSS, max_open_orders=MAX_OPEN_ORDERS)
        self.strats = [EMACrossover(self.md, self.order_tracker, dry_run=bool(DRY_RUN))]
        self._last_recon = 0.0
        self._started = False
        self._last_px_log = 0.0
        self._px_log_every = 5.0

    def _subscribe_validated(self, sym: str) -> bool:
        sym_u = sym.strip().upper()
        try:
            qc = build_and_qualify(self.ib, sym_u)
            if not qc:
                logger.info(f"Skip {sym_u}: not tradable/qualifiable")
                return False
            self.md.subscribe_with_contract(sym_u, qc)
            return True
        except Exception:
            logger.exception(f"Validation failed for {sym_u}")
            return False

    def start(self):
        logger.info("TradeManager starting...")
        for sym in WATCHLIST:
            self._subscribe_validated(sym)

        pos_added = 0
        try:
            portfolio = self.ib.portfolio() if hasattr(self.ib, "portfolio") else []
            for p in portfolio:
                c = getattr(p, "contract", None)
                sym = getattr(c, "symbol", None)
                if not sym:
                    continue
                if self._subscribe_validated(sym):
                    pos_added += 1
        except Exception:
            logger.exception("Failed to process open positions for subscription")

        if pos_added:
            logger.info(f"Also subscribed {pos_added} symbols from open positions")

        self._started = True
        logger.info(f"Subscribed to {len(self.md.tickers)} symbols: {list(self.md.tickers.keys())}")

    def _collect_prices(self):
        rows = []
        for sym in list(self.md.tickers.keys()):
            last = bid = ask = None
            if self.md._use_live and sym in self.md._subs:
                _, t = self.md._subs.get(sym, (None, None))
                last = getattr(t, "last", None) or getattr(t, "close", None)
                bid  = getattr(t, "bid", None)
                ask  = getattr(t, "ask", None)
                if last is None and hasattr(t, "marketPrice"):
                    try:
                        last = t.marketPrice() or t.midpoint()
                    except Exception:
                        pass
            else:
                # advance sim one step to keep series moving
                last, _ = self.md.get_last(sym)
            rows.append({"symbol": sym, "last": last, "bid": bid, "ask": ask})
        return rows

    def heartbeat(self):
        if not self._started:
            return
        now = time.time()

        if now - self._last_recon > POSITION_RECON_SEC:
            self._last_recon = now
            logger.debug("Reconciling positions (stub)")

        for strat in self.strats:
            try:
                strat.on_bar()
            except Exception:
                logger.exception("Strategy error")

        # Publish snapshot to dashboard every few seconds
        if now - self._last_px_log >= self._px_log_every:
            self._last_px_log = now
            try:
                prices = self._collect_prices()
                STATE.update(
                    env="paper" if bool(DRY_RUN) else "live",
                    dry_run=bool(DRY_RUN),
                    subs=len(self.md.tickers),
                    open_orders=self.order_tracker.open_count(),
                    pnl_day=self.risk.today_pnl,
                    symbols=list(self.md.tickers.keys()),
                    prices=prices,
                    circuit_ok=self.risk.ok(self.order_tracker),
                    live_mode=self.md._use_live,
                )
                # Also log a compact line for the console
                if prices:
                    head = ", ".join([f"{r['symbol']}:{r['last']}" for r in prices[:5]])
                    logger.info(f"PX {head} ...")
            except Exception:
                logger.exception("Snapshot publish failed")

        if not self.risk.ok(self.order_tracker):
            logger.error("Risk breached; stopping trading loop")
            self.stop()

    def stop(self):
        logger.info("TradeManager stopping...")
        try:
            self.ibc.disconnect()
        except Exception:
            pass
