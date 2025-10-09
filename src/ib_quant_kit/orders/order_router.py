# Add to ib_client.py or create new order_router.py

def submit_limit_with_checks(
    ib_client,
    risk_state,
    contract,
    side: str,
    qty: float,
    limit: float,
    tif: str,
    outside_rth: bool,
    idempotency_key: str
):
    """Submit order with full risk checks"""
    from .market.guards import stale_guard, is_equity_rth_now
    from .safety.circuit_breaker import breaker
    from .config import settings
    
    symbol = contract.symbol
    
    # 1. Kill switch check
    if breaker and breaker.check():
        console.log(f"[bold red]BLOCKED[/]: Kill switch active for {symbol}")
        return None
    
    # 2. Quote staleness check
    if stale_guard.is_stale(symbol):
        console.log(f"[bold yellow]BLOCKED[/]: Stale quote for {symbol}")
        return None
    
    # 3. RTH guard (if enabled for equities)
    if settings.ENABLE_RTH_GUARD and contract.secType == "STK":
        if not is_equity_rth_now():
            console.log(f"[bold yellow]BLOCKED[/]: Outside RTH for {symbol}")
            return None
    
    # 4. Risk limits check
    if not risk_state.allowed_order(symbol, side, limit, qty):
        console.log(f"[bold red]BLOCKED[/]: Risk limits for {symbol}")
        return None
    
    # 5. Submit order
    try:
        order_id = ib_client.submit_limit(
            contract=contract,
            side=side,
            qty=qty,
            limit=limit,
            tif=tif,
            outside_rth=outside_rth,
            idempotency_key=idempotency_key
        )
        console.log(f"[bold green]SUBMITTED[/]: {side} {qty} {symbol} @ {limit} (oid={order_id})")
        return order_id
    except Exception as e:
        console.log(f"[bold red]ERROR[/]: Failed to submit {symbol}: {e}")
        return None
