# ib_client.py — CRITICAL PATCH (callbacks must be inside IBClient)

## What to change
Move these methods INSIDE `class IBClient(EWrapper, EClient):` near the end of the class (and ensure only one `start()` exists):

    def position(self, account: str, contract: Contract, position: float, avgCost: float):
        try:
            from .positions import positions
            positions.update_from_ib(account, contract, position, avgCost)
        except Exception as e:
            console.log(f"[bold red]Error in position callback[/]: {e}")

    def positionEnd(self):
        console.log("[bold green]Position download complete[/]")

    def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str):
        if tag == "NetLiquidation":
            console.log(f"[bold blue]Account Value[/]: {value} {currency}")

    def accountSummaryEnd(self, reqId: int):
        console.log("[bold green]Account summary complete[/]")

    def commissionReport(self, commissionReport):
        try:
            console.log(f"[bold cyan]Commission[/]: {commissionReport.commission} {commissionReport.currency}")
            # Optional: wire to pnl
            # from .pnl import pnl
            # pnl.add_commission(commissionReport.commission)
        except Exception as e:
            console.log(f"[bold red]Error in commission callback[/]: {e}")

    def start(self):
        self.connect(settings.ib_host, settings.ib_port, settings.ib_client_id)
        self._thread = threading.Thread(target=self.run, name="IBAPI-Loop", daemon=True)
        self._thread.start()
        time.sleep(1.0)
        self.reqMarketDataType(settings.market_data_type_default)
        self.reqCurrentTime()
        self.reqPositions()
        self.reqAccountSummary(9001, "All", "NetLiquidation,TotalCashValue,GrossPositionValue")
        time.sleep(2.0)
        console.log("[bold green]Position reconciliation complete[/]")

    def heartbeat(self):
        while True:
            time.sleep(30)
            if not self.isConnected():
                console.log("[bold yellow]Heartbeat: reconnecting...[/]")
                self.ensure_connected()
            else:
                self.reqCurrentTime()

## Also remove ANY duplicate top-level (non-indented) definitions of these names at the bottom of the file.

## Why
IBKR will never call top-level functions for EWrapper callbacks; they must be instance methods on your client class.