import logging
from ib_client import IBClient
from trade_manager import TradeManager
from dashboard import start_dashboard
from config import DASHBOARD_HOST, DASHBOARD_PORT
def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ib=IBClient(); tm=TradeManager(ib)
    start_dashboard(ib, tm, host=DASHBOARD_HOST, port=DASHBOARD_PORT)
    tm.run_forever()
if __name__=='__main__': main()
