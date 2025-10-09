# src/ib_quant_kit/execx/quote_aware.py

def quote_aware_limit(bid: float, ask: float, side: str, max_slip_bps: int = 20, fallback: float = 0.0) -> float:
    """
    Calculate limit price with controlled slippage.
    
    Args:
        bid: Current bid price
        ask: Current ask price  
        side: 'BUY' or 'SELL'
        max_slip_bps: Maximum slippage in basis points
        fallback: Fallback price if no quotes available
    
    Returns:
        Limit price
    """
    if not bid or not ask:
        return fallback
    
    mid = (bid + ask) / 2.0
    slip = mid * (max_slip_bps / 10000.0)
    
    if side.upper() in ("BUY", "BOT"):
        # Willing to pay up to ask + slippage
        return min(ask + slip, ask * 1.01)  # Cap at 1% above ask
    else:
        # Willing to sell down to bid - slippage  
        return max(bid - slip, bid * 0.99)  # Cap at 1% below bid
