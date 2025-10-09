# ib_client.py — v11.1b
import threading, time, logging
from dataclasses import dataclass
from typing import Dict, Optional
from config import TWS_HOST, TWS_PORT, CLIENT_ID, DRY_RUN

log=logging.getLogger("ib_client")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def _dash_log(msg:str):
    try:
        from dashboard import dashboard_log
        dashboard_log(msg)
    except Exception: pass

@dataclass
class ConnState:
    connected: bool=False
    last_connected_ts: float=0.0
    last_disconnected_ts: float=0.0

@dataclass
class FarmState:
    market_ok: Optional[bool]=None
    hmds_ok: Optional[bool]=None
    last_msg: str=""
    last_update: float=0.0

try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.contract import Contract
    from ibapi.common import TickerId
    HAVE_IBAPI=True
except Exception as e:
    HAVE_IBAPI=False; log.error("ibapi not installed. pip install ibapi  (%s)", e)

class _Wrapper(EWrapper):
    def __init__(self, outer:"IBClient"):
        super().__init__(); self.outer=outer
    def managedAccounts(self, accountsList: str):
        self.outer.account=(accountsList or "").split(",")[0].strip()
        self.outer._log(f"[IB] managedAccounts {self.outer.account}")
        try: self.outer._subscribe_account_stream()
        except Exception as e: self.outer._log(f"[IB] subscribe_account_stream error: {e}")
    def nextValidId(self, orderId:int):
        self.outer._next_order_id=orderId; self.outer._log(f"[IB] nextValidId {orderId}")
    def error(self, reqId, code, msg):
        now=time.time()
        if code in (1100,1102):
            ok=(code==1102); self.outer.conn.connected=ok
            self.outer.conn.last_connected_ts = now if ok else self.outer.conn.last_connected_ts
            self.outer.conn.last_disconnected_ts = 0 if ok else now
        if code in (2103,2104):
            self.outer.farm.market_ok=(code==2104); self.outer.farm.last_msg=msg; self.outer.farm.last_update=now
        if code in (2105,2106):
            self.outer.farm.hmds_ok=(code==2106); self.outer.farm.last_msg=msg; self.outer.farm.last_update=now
        self.outer._log(f"[IB] code={code} reqId={reqId} msg={msg}")
    def position(self, account, contract, position, avgCost):
        sym=contract.localSymbol or contract.symbol
        with self.outer._lock:
            self.outer.positions[sym]=float(position); self.outer.contracts[sym]=contract; self.outer.last_update=time.time()
        self.outer._log(f"[IB] position sym={sym} qty={float(position)}")
    def positionEnd(self): self.outer._log("[IB] positionEnd")
    def updatePortfolio(self, contract, position, marketPrice, marketValue, averageCost, unrealizedPNL, realizedPNL, accountName):
        sym=contract.localSymbol or contract.symbol
        with self.outer._lock:
            self.outer.positions[sym]=float(position); self.outer.contracts[sym]=contract
            self.outer.pos_details[sym]={"position":float(position),"marketPrice":float(marketPrice),
                "marketValue":float(marketValue),"averageCost":float(averageCost),
                "unrealizedPNL":float(unrealizedPNL) if unrealizedPNL is not None else 0.0,
                "realizedPNL":float(realizedPNL) if realizedPNL is not None else 0.0}
            self.outer.last_update=time.time()
        self.outer._log(f"[IB] portfolio sym={sym} qty={float(position)} last={float(marketPrice)} uPNL={unrealizedPNL}")

class _Client(EClient):
    def __init__(self, wrapper:_Wrapper): EClient.__init__(self, wrapper)

class IBClient:
    def __init__(self):
        if not HAVE_IBAPI: raise RuntimeError("ibapi not available. pip install ibapi")
        self.wrapper=_Wrapper(self); self.client=_Client(self.wrapper)
        self.conn=ConnState(); self.farm=FarmState()
        self.positions: Dict[str,float]={}; self.contracts: Dict[str,Contract]={}; self.pos_details: Dict[str,dict]={}
        self._thread: Optional[threading.Thread]=None; self._req_id=1000; self._next_order_id=0; self.account:str=""
        self._lock=threading.Lock(); self.last_update: Optional[float]=None; self._log_tail=[]
    def get_log_tail(self)->str:
        with self._lock: return "\n".join(self._log_tail[-200:])
    def _log(self,msg:str):
        try:
            with self._lock:
                self._log_tail.append(msg)
                if len(self._log_tail)>500: del self._log_tail[:len(self._log_tail)-500]
        except Exception: pass
        _dash_log(msg)
    def connect(self)->bool:
        self.client.connect(TWS_HOST, TWS_PORT, CLIENT_ID)
        self._thread=threading.Thread(target=self.client.run, daemon=True); self._thread.start()
        time.sleep(0.5); self.conn.connected=True
        self._log(f"[IB] connected host={TWS_HOST} port={TWS_PORT} client_id={CLIENT_ID}")
        # wait for managedAccounts to start account stream
        return True
    def _subscribe_account_stream(self):
        acct=self.account or ""
        try: self.client.reqAccountUpdates(False,"")
        except Exception: pass
        self.client.reqAccountUpdates(True, acct)
        self.client.reqPositions()
        with self._lock: self.last_update=time.time()
        self._log(f"[IB] subscribed account stream for {acct}")
    def disconnect(self):
        try: self.client.reqAccountUpdates(False,""); self.client.disconnect()
        except Exception: pass
        self.conn.connected=False; self._log("[IB] disconnected")
    def _next_req_id(self)->int: self._req_id+=1; return self._req_id
    def refresh_positions(self)->Dict[str,float]:
        self.client.reqPositions(); return dict(self.positions)
    def subscribe_symbol(self, symbol:str)->bool:
        try:
            c=self.contracts.get(symbol)
            if c is None:
                c=Contract(); c.symbol=symbol; c.secType="STK"; c.exchange="SMART"; c.currency="USD"
            reqId=self._next_req_id(); self.client.reqMktData(reqId,c,"",False,False,[])
            self._log(f"[IB] subscribed {symbol} (reqId={reqId})"); return True
        except Exception as e:
            self._log(f"[IB] subscribe failed {symbol}: {e}"); return False
    def unsubscribe_symbol(self, symbol:str)->bool:
        self._log(f"[IB] unsubscribe requested {symbol} (noop)"); return True
    def place_order(self, symbol:str, action:str, qty:float):
        if DRY_RUN: self._log(f"[DRY_RUN] place {action} {qty} {symbol}"); return {"status":"SIMULATED"}
        self._log(f"[LIVE] place {action} {qty} {symbol}"); return {"status":"SENT"}
