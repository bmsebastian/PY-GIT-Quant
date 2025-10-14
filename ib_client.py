# ib_client.py — v15B with readonly mode fix
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

try:
    from ib_insync import IB, Contract, Stock, Option, Future, Forex, util
    _IB_AVAILABLE = True
except Exception as e:
    _IB_AVAILABLE = False
    # Minimal stubs
    class IB:
        def __init__(self): self._connected = False
        def connect(self, host, port, clientId, readonly=False): self._connected=True; return self
        def disconnect(self): self._connected=False
        def isConnected(self): return self._connected
        def serverVersion(self): return 0
        def serverTime(self): return None
        def qualifyContracts(self, c): return [c]
        def positions(self): return []
        def reqPositions(self): return []
        def reqMarketDataType(self, *_a, **_k): pass
        def reqAccountSummary(self, *_a, **_k): return []
    class Contract:
        def __init__(self, **k): self.__dict__.update(k)
    class Stock(Contract):
        def __init__(self, symbol, exchange="SMART", currency="USD"):
            super().__init__(symbol=symbol, secType="STK", exchange=exchange, currency=currency)
    class Option(Contract): ...
    class Future(Contract): ...
    class Forex(Contract): ...
    def util_datetime(_): return None

from config import IB_HOST, IB_PORT, IB_CLIENT_ID

@dataclass
class IBConnectionInfo:
    host: str
    port: int
    client_id: int

class IBClient:
    """Thin wrapper around ib_insync.IB for QTrade v15B."""
    def __init__(self, info: Optional[IBConnectionInfo] = None):
        self.info = info or IBConnectionInfo(IB_HOST, IB_PORT, IB_CLIENT_ID)
        self.ib = IB()
        self._md_type_set = False

    # ---------- connection ----------
    def connect(self):
        """
        Connect with readonly=True to skip slow execution requests.
        This prevents timeout errors when TWS is slow to respond.
        """
        if self.ib.isConnected():
            return self.ib
        try:
            # FIX: Use readonly=True to skip execution requests
            # This prevents timeout errors with many positions
            self.ib.connect(
                self.info.host, 
                self.info.port, 
                clientId=self.info.client_id,
                readonly=True  # <-- KEY FIX
            )
            
            if hasattr(self.ib, "reqMarketDataType"):
                try:
                    self.ib.reqMarketDataType(1)  # 1=LIVE
                    self._md_type_set = True
                except Exception as e:
                    logger.warning(f"reqMarketDataType(1) failed: {e}")
            
            sv = getattr(self.ib, 'serverVersion', lambda: None)()
            st = getattr(self.ib, 'serverTime', lambda: None)()
            logger.info(f"Connected to IB @ {self.info.host}:{self.info.port} cid={self.info.client_id} sv={sv} (readonly)")
            
        except Exception as e:
            logger.exception("IB connect failed")
            raise
        
        return self.ib

    def is_connected(self) -> bool:
        return bool(getattr(self.ib, 'isConnected', lambda: False)())

    def disconnect(self):
        try:
            self.ib.disconnect()
        except Exception:
            pass

    # ---------- contract helpers ----------
    def qualify_contract(self, contract: Contract) -> Contract:
        """Qualify any IB Contract; falls back to the same contract on failure."""
        try:
            q = self.ib.qualifyContracts(contract)
            if q:
                return q[0]
        except Exception as e:
            logger.warning(f"qualifyContracts failed: {e}")
        return contract

    def stock(self, symbol: str, exchange: str = "SMART", currency: str = "USD") -> Contract:
        return self.qualify_contract(Stock(symbol, exchange=exchange, currency=currency))

    # ---------- account/positions ----------
    def fetch_positions(self) -> List[Dict[str, Any]]:
        """Return a list of positions as dicts."""
        data = []
        try:
            positions = []
            if hasattr(self.ib, 'positions'):
                try:
                    positions = list(self.ib.positions())
                except Exception:
                    positions = []
            if not positions and hasattr(self.ib, 'reqPositions'):
                try:
                    positions = list(self.ib.reqPositions())
                except Exception:
                    positions = []

            for p in positions:
                contract = getattr(p, 'contract', None)
                sym = getattr(contract, 'localSymbol', None) or getattr(contract, 'symbol', None) or "?"
                
                # Get security type for v15 compatibility
                sec_type = getattr(contract, 'secType', 'STK')
                
                data.append({
                    "symbol": sym,
                    "conId": getattr(contract, 'conId', None),
                    "qty": float(getattr(p, 'position', 0.0)),
                    "avgCost": float(getattr(p, 'avgCost', 0.0)),
                    "contract": contract,
                    "sec_type": sec_type,  # Add for v15
                    "local_symbol": getattr(contract, 'localSymbol', sym),  # Add for v15
                })
        except Exception as e:
            logger.warning(f"fetch_positions failed: {e}")
        return data

    # ---------- historical snapshot helper ----------
    def last_close_from_history(self, contract: Contract, duration: str = "1 D", bar: str = "5 mins") -> Optional[float]:
        """Fetch the most recent bar close as a snapshot last price."""
        try:
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime="",
                durationStr=duration,
                barSizeSetting=bar,
                whatToShow="TRADES",
                useRTH=0,
                formatDate=1,
                keepUpToDate=False,
                chartOptions=[],
            )
            if bars:
                return float(bars[-1].close)
        except Exception as e:
            logger.warning(f"last_close_from_history failed: {e}")
        return None

    # ---------- passthroughs ----------
    def req_mkt_data(self, contract: Contract, genericTickList: str = "", snapshot: bool = False, regulatorySnapshot: bool = False):
        return self.ib.reqMktData(contract, genericTickList, snapshot, regulatorySnapshot)

    def ib_handle(self) -> IB:
        """Return underlying IB handle for components."""
        return self.ib
