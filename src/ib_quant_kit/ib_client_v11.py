# ib_client.py — Quant v11 live IB wrapper (paper-account ready)
# - Uses ibapi (paper or live; defaults to paper port 7497)
# - Maintains:
#     ib.conn.connected     (1100/1102)
#     ib.farm.market_ok     (2103/2104)
#     ib.farm.hmds_ok       (2105/2106)
#     ib.positions          { localSymbol/symbol : qty }
# - Grabs positions from reqPositions() (works on paper accounts)
# - Also enables account updates (some TWS configs need this for positions to flow quickly)
# - Subscribes market data using the exact Contract received from positions (best for futures)
# - Feeds messages to the dashboard if present

import threading
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

from config import TWS_HOST, TWS_PORT, CLIENT_ID, DRY_RUN

log = logging.getLogger("ib_client")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ---------- optional dashboard hook ----------
def _dash_log(msg: str) -> None:
    try:
        from dashboard import dashboard_log
        dashboard_log(msg)
    except Exception:
        pass

# ---------- simple state holders ----------
@dataclass
class ConnState:
    connected: bool = False
    last_connected_ts: float = 0.0
    last_disconnected_ts: float = 0.0

@dataclass
class FarmState:
    market_ok: Optional[bool] = None
    hmds_ok: Optional[bool] = None
    last_msg: str = ""
    last_update: float = 0.0

# ---------- ibapi ----------
try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.contract import Contract
    from ibapi.common import TickerId
    HAVE_IBAPI = True
except Exception as e:
    HAVE_IBAPI = False
    log.error("ibapi not installed. Run: pip install ibapi  (%s)", e)


class _Wrapper(EWrapper):
    def __init__(self, outer: "IBClient"):
        super().__init__()
        self.outer = outer

    # ---- IB connection/handshake events (helpful for paper accounts)
    def managedAccounts(self, accountsList: str):
        self.outer.account = (accountsList or "").split(",")[0].strip()
        _dash_log(f"[IB] managedAccounts {self.outer.account}")

    def nextValidId(self, orderId: int):
        self.outer._next_order_id = orderId
        _dash_log(f"[IB] nextValidId {orderId}")

    # ---- Error & farm/connection status
    def error(self, reqId, code, msg):
        now = time.time()
        if code in (1100, 1102):  # connectivity lost / restored
            ok = (code == 1102)
            self.outer.conn.connected = ok
            self.outer.conn.last_connected_ts = now if ok else self.outer.conn.last_connected_ts
            self.outer.conn.last_disconnected_ts = 0 if ok else now

        if code in (2103, 2104):  # market farm
            self.outer.farm.market_ok = (code == 2104)
            self.outer.farm.last_msg = msg
            self.outer.farm.last_update = now

        if code in (2105, 2106):  # HMDS farm
            self.outer.farm.hmds_ok = (code == 2106)
            self.outer.farm.last_msg = msg
            self.outer.farm.last_update = now

        txt = f"[IB] code={code} reqId={reqId} msg={msg}"
        log.info(txt)
        _dash_log(txt)

    # ---- Positions (works on paper)
    def position(self, account, contract, position, avgCost):
        # Prefer localSymbol where present (great for futures like "NQZ5")
        sym = contract.localSymbol or contract.symbol
        qty = float(position)
        self.outer.positions[sym] = qty
        # Remember the *exact* contract so market-data subs use the correct conId/expiry/exchange
        self.outer.contracts[sym] = contract

    def positionEnd(self):
        _dash_log("[IB] positionEnd")

    # ---- Market data callbacks (no-op by default; extend as needed)
    def tickPrice(self, reqId: TickerId, tickType, price, attrib):
        pass

    def tickSize(self, reqId: TickerId, tickType, size):
        pass


class _Client(EClient):
    def __init__(self, wrapper: _Wrapper):
        EClient.__init__(self, wrapper)


class IBClient:
    def __init__(self):
        if not HAVE_IBAPI:
            raise RuntimeError("ibapi not available. Install with: pip install ibapi")

        self.wrapper = _Wrapper(self)
        self.client = _Client(self.wrapper)

        # public state that dashboard reads
        self.conn = ConnState()
        self.farm = FarmState()
        self.positions: Dict[str, float] = {}
        self.contracts: Dict[str, Contract] = {}  # cached from position() for accurate subs

        # internals
        self._thread: Optional[threading.Thread] = None
        self._req_id: int = 1000
        self._next_order_id: int = 0
        self.account: str = ""

    # ---------- lifecycle ----------
    def connect(self) -> bool:
        """
        Connects to TWS/IBG (paper: 7497). Starts the API thread, requests positions and account updates.
        """
        self.client.connect(TWS_HOST, TWS_PORT, CLIENT_ID)
        self._thread = threading.Thread(target=self.client.run, daemon=True)
        self._thread.start()

        # Give IB a moment to establish (paper tends to be snappy but we wait briefly)
        time.sleep(0.5)
        self.conn.connected = True  # optimistic; error(1100/1102) will correct
        _dash_log(f"[IB] connected host={TWS_HOST} port={TWS_PORT} client_id={CLIENT_ID}")

        # Ask for positions (paper accounts support this) and enable account updates (helps some configs)
        self.client.reqPositions()
        self.client.reqAccountUpdates(True, "")  # empty = primary account
        return True

    def disconnect(self):
        try:
            self.client.reqAccountUpdates(False, "")
            self.client.disconnect()
        except Exception:
            pass
        self.conn.connected = False
        _dash_log("[IB] disconnected")

    # ---------- utilities ----------
    def _next_req_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def refresh_positions(self) -> Dict[str, float]:
        """Manually re-requests positions (useful for periodic recon)."""
        self.client.reqPositions()
        return dict(self.positions)

    # ---------- market data subscriptions ----------
    def subscribe_symbol(self, symbol: str) -> bool:
        """
        Subscribes using the *exact* Contract we saw in positions.
        If we have never seen the contract, fall back to a SMART stock contract.
        """
        try:
            c = self.contracts.get(symbol)
            if c is None:
                # fallback generic stock contract; fine for equities like TSLA/MRAI
                c = Contract()
                c.symbol = symbol
                c.secType = "STK"
                c.exchange = "SMART"
                c.currency = "USD"

            reqId = self._next_req_id()
            self.client.reqMktData(reqId, c, "", False, False, [])
            _dash_log(f"[IB] subscribed {symbol} (reqId={reqId})")
            return True
        except Exception as e:
            log.error("subscribe_symbol(%s) failed: %s", symbol, e)
            _dash_log(f"[IB] subscribe failed {symbol}: {e}")
            return False

    def unsubscribe_symbol(self, symbol: str) -> bool:
        # We didn’t persist reqIds per-symbol here; cancel is optional.
        # If you want precise unsubs per symbol, track reqIds in a dict.
        try:
            # No specific reqId → no-op; safe to leave subscribed until process ends.
            _dash_log(f"[IB] unsubscribe requested {symbol} (noop)")
        except Exception:
            pass
        return True

    # ---------- orders ----------
    def place_order(self, symbol: str, action: str, qty: float):
        """
        Ready for you to wire a real Order if needed. DRY_RUN honored.
        """
        if DRY_RUN:
            msg = f"[DRY_RUN] place {action} {qty} {symbol}"
            log.info(msg); _dash_log(msg)
            return {"status": "SIMULATED"}

        # Example placeholder; implement with ibapi Order + placeOrder when you’re ready.
        msg = f"[LIVE] place {action} {qty} {symbol}"
        log.info(msg); _dash_log(msg)
        return {"status": "SENT"}
