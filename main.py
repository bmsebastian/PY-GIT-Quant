import time
import logging
from config import ENV, DRY_RUN, HEARTBEAT_SEC, DASHBOARD_HOST, DASHBOARD_PORT
from trade_manager import TradeManager
from dashboard_server import start_dashboard
from state_bus import STATE

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def main():
    logging.info(f"Booting QTrade v13.5 ENV={ENV} DRY_RUN={DRY_RUN}")
    # Start dashboard first so it's ready
    start_dashboard(DASHBOARD_HOST, DASHBOARD_PORT)
    logging.info(f"Dashboard at http://{DASHBOARD_HOST}:{DASHBOARD_PORT}")

    tm = TradeManager()
    tm.start()
    try:
        while True:
            tm.heartbeat()
            # Also expose a minimal heartbeat for the dashboard
            STATE.update(env=ENV, dry_run=DRY_RUN)
            time.sleep(HEARTBEAT_SEC)
    except KeyboardInterrupt:
        logging.warning("Shutting down (Ctrl-C)")
        tm.stop()

if __name__ == "__main__":
    main()
