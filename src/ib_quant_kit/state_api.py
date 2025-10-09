from typing import Any, Dict, List
from .console import console

# Fixed imports to match actual module structure
_positions = None
try:
    from .positions import positions as _pos_singleton
    _positions = _pos_singleton
except Exception as e:
    console.log(f"[bold yellow]state_api[/] positions not found: {e}")

_order_book = None
try:
    from .orders import order_book  # Use the correct module
    _order_book = order_book
except Exception:
    _order_book = None

_pnl_provider = None
try:
    from .pnl import pnl  # Use your actual pnl module
    _pnl_provider = pnl
except Exception:
    _pnl_provider = None

_circuit_provider = None
try:
    from .safety.circuit_breaker import breaker  # Use correct module
    _circuit_provider = breaker
except Exception:
    _circuit_provider = None

# Fallbacks
_FALLBACK_PNL = {"unrealized": 0.0, "realized": 0.0, "currency": "USD"}
_FALLBACK_CIRCUIT = {"trading_enabled": True, "reason": "", "tripped_at": None}

def get_positions() -> List[Dict[str, Any]]:
    data = []
    if _positions is None:
        return data
    try:
        snap = _positions.snapshot()
        for symbol, rec in snap.items():
            data.append({
                "account": "DU123456",  # You may need to track this
                "symbol": rec.symbol,
                "secType": "STK",  # You may need to track this
                "exchange": "SMART",
                "position": rec.qty,
                "avgCost": rec.avg_price,
            })
        return data
    except Exception as e:
        console.log(f"[bold red]state_api.get_positions error[/]: {e}")
        return data

def get_orders() -> Dict[str, Any]:
    if _order_book is None:
        return {"open_orders": [], "recent_fills": []}
    try:
        # Your order_book structure may differ
        return {
            "open_orders": list(_order_book._by_client_id.values()),
            "recent_fills": []
        }
    except Exception as e:
        console.log(f"[bold red]state_api.get_orders error[/]: {e}")
        return {"open_orders": [], "recent_fills": []}

def get_risk() -> Dict[str, Any]:
    try:
        from .risk.helpers import DEFAULT_LIMITS
        return {
            "per_symbol_notional_cap": DEFAULT_LIMITS.per_symbol_notional_cap,
            "max_position_per_symbol": DEFAULT_LIMITS.max_position_per_symbol,
            "max_orders_per_day_per_symbol": DEFAULT_LIMITS.max_orders_per_day_per_symbol,
            "session_caps": DEFAULT_LIMITS.session_caps,
        }
    except Exception:
        return {}

def get_pnl():
    if _pnl_provider is None:
        return dict(_FALLBACK_PNL)
    try:
        snap = _pnl_provider.snapshot()
        return {
            "unrealized": snap.get("unrealized", 0.0),
            "realized": snap.get("realized", 0.0),
            "currency": "USD",
        }
    except Exception as e:
        console.log(f"[bold yellow]state_api.get_pnl error[/]: {e}")
        return dict(_FALLBACK_PNL)

def get_circuit():
    if _circuit_provider is None:
        return dict(_FALLBACK_CIRCUIT)
    try:
        is_killed = _circuit_provider.check()  # Returns True if blocked
        return {
            "trading_enabled": not is_killed,
            "reason": "manual_kill" if is_killed else "",
            "tripped_at": None,  # You'd need to track this in circuit_breaker
        }
    except Exception as e:
        console.log(f"[bold yellow]state_api.get_circuit error[/]: {e}")
        return dict(_FALLBACK_CIRCUIT)

def set_kill_switch(on: bool, reason: str = "manual"):
    if _circuit_provider is not None:
        try:
            _circuit_provider.kill(on=on)
            return True
        except Exception as e:
            console.log(f"[bold red]state_api.set_kill_switch error[/]: {e}")
            return False
    else:
        _FALLBACK_CIRCUIT["trading_enabled"] = (not on)
        _FALLBACK_CIRCUIT["reason"] = reason
        from datetime import datetime
        _FALLBACK_CIRCUIT["tripped_at"] = datetime.utcnow().isoformat() if on else None
        return True

def get_pnl_symbols():
    if _pnl_provider is None:
        return []
    try:
        snap = _pnl_provider.snapshot()
        by_symbol = snap.get("by_symbol", {})
        return [
            {
                "symbol": sym,
                "unrealized": data.get("unrealized", 0.0),
                "realized": data.get("realized", 0.0),
                "currency": "USD"
            }
            for sym, data in by_symbol.items()
        ]
    except Exception as e:
        console.log(f"[bold yellow]state_api.get_pnl_symbols error[/]: {e}")
        return []

def get_blotter(limit: int = 50):
    # No blotter module exists yet - return empty for now
    return []
