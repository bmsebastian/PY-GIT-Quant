import logging
from dataclasses import dataclass
from typing import Optional, Any

logger = logging.getLogger(__name__)

try:
    from ib_insync import IB, Contract, Stock, Option, util
    _IB_AVAILABLE = True
except Exception as e:
    _IB_AVAILABLE = False
    # Define tiny stubs so the program can still run
    class IB:  # type: ignore
        def __init__(self): self.connected = False
        def connect(self, host, port, clientId, readonly=False): self.connected=True; return self
        def disconnect(self): self.connected=False
        def isConnected(self): return self.connected
        def reqMktData(self, *a, **k): return type("T", (), {"last":None,"bid":None,"ask":None})
        def sleep(self, _): pass
        def qualifyContracts(self, c): return [c]
    class Contract:  # type: ignore
        def __init__(self, **k): self.__dict__.update(k)
    class Stock(Contract):  # type: ignore
        def __init__(self, symbol, exchange="SMART", currency="USD"):
            super().__init__(symbol=symbol, secType="STK", exchange=exchange, currency=currency)
    class Option(Contract): ...  # type: ignore

from config import IB_GATEWAY_HOST, IB_GATEWAY_PORT, IB_CLIENT_ID

@dataclass
class IBConnectionInfo:
    host: str
    port: int
    client_id: int

class IBClient:
    def __init__(self, info: Optional[IBConnectionInfo]=None):
        self.info = info or IBConnectionInfo(IB_GATEWAY_HOST, IB_GATEWAY_PORT, IB_CLIENT_ID)
        self.ib = IB()

    def connect(self):
        if self.ib.isConnected():
            return self.ib
        try:
            self.ib.connect(self.info.host, self.info.port, clientId=self.info.client_id)
            logger.info(f"Connected to IB @ {self.info.host}:{self.info.port} cid={self.info.client_id}")
        except Exception as e:
            logger.exception("IB connect failed; running in stub mode")
        return self.ib

    def disconnect(self):
        try:
            self.ib.disconnect()
        except Exception:
            pass

    def qualify_stock(self, symbol: str):
        c = Stock(symbol, exchange="SMART", currency="USD")
        try:
            qc = self.ib.qualifyContracts(c)
            return qc[0] if qc else c
        except Exception:
            return c
