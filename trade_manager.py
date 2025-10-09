import time, logging
from typing import Set
from config import POSITION_RECON_SEC, HEARTBEAT_SEC
from ib_client import IBClient
log=logging.getLogger("trade_manager")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
class TradeManager:
    def __init__(self, ib:IBClient):
        self.ib=ib; self.monitoring:Set[str]=set()
    def start(self):
        self.ib.connect(); time.sleep(1.0); self._reconcile()
        log.info("TradeManager started. Monitoring=%s", sorted(list(self.monitoring)))
    def _reconcile(self):
        for sym, qty in self.ib.refresh_positions().items():
            if qty!=0: self._ensure_monitored(sym)
    def _ensure_monitored(self, symbol:str):
        if symbol in self.monitoring: return
        self.ib.subscribe_symbol(symbol); self.monitoring.add(symbol)
    def _unmonitor_if_flat(self, symbol:str):
        if self.ib.positions.get(symbol,0.0)==0.0 and symbol in self.monitoring:
            self.monitoring.remove(symbol)
    def run_forever(self):
        try:
            self.start(); t_pos=time.time()
            while True:
                now=time.time()
                if now-t_pos>=POSITION_RECON_SEC:
                    self.ib.refresh_positions()
                    for s in list(self.monitoring): self._unmonitor_if_flat(s)
                    t_pos=now
                time.sleep(HEARTBEAT_SEC)
        except KeyboardInterrupt: pass
        finally: self.ib.disconnect()
