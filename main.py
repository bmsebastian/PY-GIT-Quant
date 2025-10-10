import time
import logging
from config import ENV, DRY_RUN, HEARTBEAT_SEC
from trade_manager import TradeManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

def main():
    logging.info(f"Booting QTrade v13.5 ENV={ENV} DRY_RUN={DRY_RUN}")
    tm = TradeManager()
    tm.start()
    try:
        while True:
            tm.heartbeat()
            time.sleep(HEARTBEAT_SEC)
    except KeyboardInterrupt:
        logging.warning("Shutting down (Ctrl-C)")
        tm.stop()

if __name__ == "__main__":
    main()
