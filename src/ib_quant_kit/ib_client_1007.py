
import threading
import time
from datetime import datetime, timezone
from typing import Optional, Dict, List

from rich.console import Console
from ibapi.wrapper import EWrapper
from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.order import Order

from .config import settings
from .pacing import mkt_pacer, hist_pacer  # noqa: F401 (mkt_pacer kept for parity)
from .contract_cache import contract_cache
from .subscriptions import subscriptions
from .orders import order_book

console = Console()

CONN_DOWN_CODES = {1100}
CONN_RECOVERY_CODES = {1101, 1102}


class IBClient(EWrapper, EClient):
    def __init__(self):
        EWrapper.__init__(self)
        EClient.__init__(self, self)

        # Threads / connection state
        self._thread: Optional[threading.Thread] = None
        self._next_order_id: Optional[int] = None
        self._reconnect_needed = False
        self._last_server_time: Optional[datetime] = None
        self._lock = threading.Lock()

        # Market data caches
        self._req_contracts: Dict[int, Contract] = {}
        self._bid: Dict[int, float] = {}
        self._ask: Dict[int, float] = {}
        self._delta: Dict[int, float] = {}
        self._undPrice: Dict[int, float] = {}

        # SecDef caches
        self._secdef: Dict[int, dict] = {}
        self._secdef_done: Dict[int, bool] = {}

        # Historical data caches
        self._hist: Dict[int, List[dict]] = {}
        self._hist_done: Dict[int, bool] = {}

    # ---- lifecycle ---------------------------------------------------------

    def start(self):
        """Connect, spin reader thread, seed account/position state."""
        self.connect(settings.ib_host, settings.ib_port, settings.ib_client_id)

        self._thread = threading.Thread(target=self.run, name="IBAPI-Loop", daemon=True)
        self._thread.start()

        # Give the socket loop a moment
        time.sleep(1.0)

        # Set market data type and request time
        try:
            self.reqMarketDataType(settings.market_data_type_default)
        except Exception:
            # fallback: default to 1 (RTH) if setting not present
            self.reqMarketDataType(1)

        self.reqCurrentTime()

        # CRITICAL: download positions first thing so bot state = IB truth
        self.reqPositions()

        # Basic account metrics (example set)
        self.reqAccountSummary(
            9001,
            "All",
            "NetLiquidation,TotalCashValue,GrossPositionValue",
        )

        # allow callbacks to land
        time.sleep(2.0)
        console.log("[bold green]Position reconciliation complete[/]")

    def stop(self):
        try:
            self.disconnect()
        except Exception:
            pass

    # ---- core callbacks ----------------------------------------------------

    def nextValidId(self, orderId: int):
        with self._lock:
            self._next_order_id = orderId
        console.log(f"[bold green]nextValidId[/]: {orderId}")

    def error(self, reqId, errorCode, errorString, *args):
        console.log(f"[bold red]ERROR[/] code={errorCode} reqId={reqId} msg={errorString}")
        if errorCode in CONN_DOWN_CODES or errorCode in CONN_RECOVERY_CODES:
            self._reconnect_needed = True

    def currentTime(self, time_from_server: int):
        dt = datetime.fromtimestamp(time_from_server, tz=timezone.utc)
        self._last_server_time = dt
        drift = abs((datetime.now(timezone.utc) - dt).total_seconds())
        if drift > 5.0:
            console.log(f"[bold yellow]Clock drift warning[/]: {drift:.1f}s")

    def openOrder(self, orderId: int, contract: Contract, order: Order, orderState):
        perm_id = getattr(order, "permId", 0) or getattr(orderState, "permId", 0)
        order_book.update_status(orderId, "Submitted", perm_id if perm_id else None)

    def orderStatus(self, orderId: int, status: str, *_):
        order_book.update_status(orderId, status)

    # ---- market data & executions -----------------------------------------

    def tickString(self, reqId, tickType, value):
        # RTVolume (tickType 48) format: "price;size;time;totalVolume;vwap;singleTrade"
        if tickType == 48:
            try:
                parts = value.split(";")
                price = float(parts[0])
                size = float(parts[1])
                ts_ms = int(parts[2])

                from .rtbar import rtbars
                rtbars.on_trade(reqId, price, size, ts_ms)

                # mark price for PnL
                c = self._req_contracts.get(reqId)
                if c:
                    from .pnl import pnl
                    pnl.mark_price(c.symbol, price)
            except Exception:
                pass

    def execDetails(self, reqId, contract, execution):
        # update order book status + record fills + pnl tracking
        try:
            order_book.update_status(execution.orderId, "Filled", execution.permId)
            side = execution.side
            qty = float(execution.shares)
            price = float(execution.price)

            from .store.fills_logger import append_fill
            append_fill(
                {
                    "symbol": contract.symbol,
                    "side": side,
                    "qty": qty,
                    "price": price,
                    "permId": execution.permId,
                }
            )

            from .pnl import pnl
            pnl.on_fill(contract.symbol, side, qty, price)
        except Exception:
            pass

    # ---- contract details --------------------------------------------------

    def contractDetails(self, reqId, contractDetails):
        contract_cache.on_contract_details(reqId, contractDetails)

    def contractDetailsEnd(self, reqId):
        contract_cache.on_contract_details_end(reqId)

    # ---- quotes / greeks ---------------------------------------------------

    def tickPrice(self, reqId, tickType, price, attrib):
        if tickType == 1:
            self._bid[reqId] = price
        elif tickType == 2:
            self._ask[reqId] = price

    def tickOptionComputation(
        self, reqId, tickType, impliedVol, delta, gamma, vega, theta, undPrice
    ):
        if delta is not None:
            self._delta[reqId] = float(delta)
        if undPrice is not None:
            self._undPrice[reqId] = float(undPrice)

    def securityDefinitionOptionParameter(
        self, reqId: int, exchange: str, underlyingConId: int, tradingClass: str, multiplier: str, expirations, strikes
    ):
        d = self._secdef.setdefault(
            reqId,
            {
                "exchanges": set(),
                "tradingClass": set(),
                "expirations": set(),
                "strikes": set(),
                "multiplier": set(),
            },
        )
        d["exchanges"].add(exchange)
        d["tradingClass"].add(tradingClass)
        d["multiplier"].add(multiplier)
        d["expirations"].update(expirations)
        d["strikes"].update(strikes)

    def securityDefinitionOptionParameterEnd(self, reqId: int):
        self._secdef_done[reqId] = True

    # ---- historical data ---------------------------------------------------

    def historicalData(self, reqId, bar):
        row = {
            "time": str(bar.date),
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        }
        self._hist.setdefault(reqId, []).append(row)

    def historicalDataEnd(self, reqId, start, end):
        self._hist_done[reqId] = True

    def fetch_hist_bars(
        self,
        contract: Contract,
        durationStr="30 M",
        barSizeSetting="1 min",
        whatToShow="TRADES",
        useRTH=1,
    ):
        hist_pacer.wait()
        reqId = contract_cache.next_req_id()
        self._hist.pop(reqId, None)
        self._hist_done.pop(reqId, None)
        self.reqHistoricalData(
            reqId, contract, "", durationStr, barSizeSetting, whatToShow, useRTH, 1, False, []
        )
        t0 = time.time()
        while (time.time() - t0) < 10.0:
            if self._hist_done.get(reqId):
                break
            time.sleep(0.05)
        return self._hist.get(reqId, [])

    # ---- utilities ---------------------------------------------------------

    def next_client_order_id(self) -> int:
        for _ in range(100):
            with self._lock:
                if self._next_order_id is not None:
                    oid = self._next_order_id
                    self._next_order_id += 1
                    return oid
            time.sleep(0.05)
        raise RuntimeError("nextValidId not received.")

    def ensure_connected(self):
        if self._reconnect_needed or (not self.isConnected()):
            console.log("[bold yellow]Reconnecting...[/]")
            try:
                self.disconnect()
            except Exception:
                pass
            time.sleep(0.5)
            self.start()
            self._reconnect_needed = False
            self.reqAllOpenOrders()
            self.reqPositions()
            self.resubscribe_all()

    def set_market_data_type_for_session(self, session: str):
        # both paths set 1 (RTH) here; adjust if you want delayed (3) or frozen (2)
        mdt = 1 if session == "RTH" else 1
        self.reqMarketDataType(mdt)

    # ---- subscriptions -----------------------------------------------------

    def subscribe_stock_nbbo(self, contract: Contract):
        reqId = contract_cache.next_req_id()
        self._req_contracts[reqId] = contract
        self.reqMktData(reqId, contract, "233", False, False, [])
        subscriptions.add(reqId, "STK", contract, "")
        return reqId

    def subscribe_option_greeks(
        self, contract: Contract, genericTicks="100,101,104,106,165,221,225,233"
    ):
        reqId = contract_cache.next_req_id()
        self._req_contracts[reqId] = contract
        self.reqMktData(reqId, contract, genericTicks, False, False, [])
        subscriptions.add(reqId, "OPT", contract, genericTicks)
        return reqId

    def resubscribe_all(self):
        for reqId, (kind, contract, genericTicks) in subscriptions.items():
            try:
                self.reqMktData(
                    reqId,
                    contract,
                    genericTicks if kind == "OPT" else "",
                    False,
                    False,
                    [],
                )
            except Exception as e:
                console.log(f"[bold yellow]Resubscribe failed[/]: {e}")

    # ---- qualification & orders -------------------------------------------

    def qualify(self, contract: Contract, timeout=3.0) -> Contract:
        cached = contract_cache.get(contract)
        if cached:
            return cached
        reqId = contract_cache.next_req_id()
        self.reqContractDetails(reqId, contract)
        details = contract_cache.await_details(reqId, timeout=timeout)
        if not details:
            raise RuntimeError("Contract qualification failed.")
        qual = details[0].contract
        contract_cache.put(qual)
        return qual

    def submit_limit(
        self,
        contract: Contract,
        side: str,
        qty: float,
        limit: float,
        tif: str,
        outside_rth: bool,
        idempotency_key: str,
    ):
        client_order_id = order_book.get_or_assign(
            idempotency_key, self.next_client_order_id()
        )

        if settings.dry_run:
            console.log(
                f"[bold cyan]DRY_RUN[/] Would submit {side} {qty} {contract.symbol} @ {limit} [{tif}] oid={client_order_id}"
            )
            return client_order_id

        ord = Order()
        ord.action = "BUY" if side.upper() == "BUY" else "SELL"
        ord.totalQuantity = abs(qty)
        ord.orderType = "LMT"
        ord.lmtPrice = float(limit)
        ord.tif = tif
        # IB API attribute is 'outsideRth' (camelCase)
        try:
            setattr(ord, "outsideRth", bool(outside_rth))
        except Exception:
            pass

        self.placeOrder(client_order_id, contract, ord)
        return client_order_id

    # ---- positions / account ----------------------------------------------

    def position(self, account: str, contract: Contract, position: float, avgCost: float):
        """EWrapper callback for position updates from IBKR"""
        try:
            from .positions import positions
            positions.update_from_ib(account, contract, position, avgCost)
            console.log(f"[bold blue]Position[/]: {contract.symbol} qty={position} avg={avgCost:.2f}")
        except Exception as e:
            console.log(f"[bold red]Error in position callback[/]: {e}")

    def positionEnd(self):
        """Called after all positions received"""
        console.log("[bold green]Position download complete[/]")

    def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str):
        """Track account metrics"""
        if tag == "NetLiquidation":
            console.log(f"[bold blue]Account Value[/]: {value} {currency}")

    def accountSummaryEnd(self, reqId: int):
        pass

    def commissionReport(self, commissionReport):
        try:
            from .pnl import pnl
            pnl.on_commission(commissionReport)
        except Exception as e:
            console.log(f"[bold yellow]commissionReport error[/]: {e}")

    # ---- health ------------------------------------------------------------

    def heartbeat(self):
        now = datetime.now(timezone.utc)
        if self._last_server_time and (now - self._last_server_time).total_seconds() > 10:
            console.log("[bold yellow]No server time in 10s[/]")
