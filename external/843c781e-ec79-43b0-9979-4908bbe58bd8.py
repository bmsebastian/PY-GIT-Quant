# Add these methods to IBClient class in ib_client.py

def position(self, account: str, contract: Contract, position: float, avgCost: float):
    """EWrapper callback for position updates"""
    from .positions import positions
    positions.update_from_ib(account, contract, position, avgCost)
    console.log(f"[bold blue]Position[/]: {contract.symbol} qty={position} avg={avgCost:.2f}")

def positionEnd(self):
    """Called after all positions received"""
    console.log("[bold green]Position download complete[/]")

def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str):
    """Track account metrics"""
    if tag == "NetLiquidation":
        try:
            from .risk.limits import RiskState
            # Update equity in global state if you maintain one
            console.log(f"[bold blue]Account Value[/]: {value} {currency}")
        except Exception:
            pass

def accountSummaryEnd(self, reqId: int):
    console.log("[bold green]Account summary complete[/]")

def start(self):
    """Enhanced start with position reconciliation"""
    self.connect(settings.ib_host, settings.ib_port, settings.ib_client_id)
    self._thread = threading.Thread(target=self.run, name="IBAPI-Loop", daemon=True)
    self._thread.start()
    time.sleep(1.0)
    
    self.reqMarketDataType(settings.market_data_type_default)
    self.reqCurrentTime()
    
    # Request positions on startup
    self.reqPositions()
    
    # Request account summary
    self.reqAccountSummary(9001, "All", "NetLiquidation,TotalCashValue,GrossPositionValue")
    
    time.sleep(2.0)  # Give time for position download

def execDetails(self, reqId, contract, execution):
    """Enhanced with position tracking"""
    try:
        from .orders import order_book
        order_book.update_status(execution.orderId, "Filled", execution.permId)
        
        side = execution.side
        qty = float(execution.shares)
        price = float(execution.price)
        
        # Log fill
        from .store.fills_logger import append_fill
        append_fill({
            "symbol": contract.symbol, 
            "side": side, 
            "qty": qty, 
            "price": price, 
            "permId": execution.permId,
            "execId": execution.execId,
            "time": execution.time
        })
        
        # Update PnL tracker
        from .pnl import pnl
        pnl.on_fill(contract.symbol, side, qty, price)
        
        # Update position tracker
        from .positions import positions
        positions.update_from_fill(contract.symbol, side, qty, price)
        
        console.log(f"[bold green]FILL[/]: {side} {qty} {contract.symbol} @ {price}")
        
    except Exception as e:
        console.log(f"[bold red]Error in execDetails[/]: {e}")
