# contracts.py - Contract helper functions (v15 FIXED)
"""
Helper functions for identifying and filtering contracts.
"""

import logging

logger = logging.getLogger(__name__)

# Non-tradable symbol patterns
NON_TRADABLE_PATTERNS = [
    'Q',      # Bankruptcy/delisted (but NOT futures like NQZ5)
    'W',      # Warrants
    '.CVR',   # Contingent Value Rights
    '.OLD',   # Old/delisted
    '.WS',    # Warrants
    'REF',    # Reference symbols
]

def looks_nontradable_symbol(symbol: str) -> bool:
    """
    Check if a symbol looks non-tradable (OTC, delisted, CVR, etc).
    
    Args:
        symbol: Stock symbol to check
        
    Returns:
        True if symbol appears non-tradable
        
    Examples:
        >>> looks_nontradable_symbol("AAPL")
        False
        >>> looks_nontradable_symbol("TOGI")  # OTC
        False  # Would need more context
        >>> looks_nontradable_symbol("ALPSQ")  # Bankruptcy
        True
        >>> looks_nontradable_symbol("NQZ5")  # Futures
        False
    """
    if not symbol:
        return True
    
    symbol_upper = symbol.upper()
    
    # Check for explicit non-tradable patterns
    for pattern in NON_TRADABLE_PATTERNS:
        if pattern in symbol_upper:
            # Special case: 'Q' in symbol
            # Allow futures (NQZ5, QQQ, etc) but block bankruptcy (ALPSQ, etc)
            if pattern == 'Q':
                # If Q is at the end and preceded by letters, likely bankruptcy
                if symbol_upper.endswith('Q') and len(symbol_upper) > 3:
                    # But allow QQQ, NQ, etc
                    if symbol_upper not in ['QQQ', 'NQ', 'NQH', 'NQM', 'NQU', 'NQZ']:
                        # Check if it's a futures code (e.g., NQZ5, ESH5)
                        if not (len(symbol_upper) >= 3 and symbol_upper[-1].isdigit()):
                            return True
            else:
                return True
    
    return False


def is_futures_symbol(symbol: str) -> bool:
    """
    Check if symbol appears to be a futures contract.
    
    Args:
        symbol: Symbol to check
        
    Returns:
        True if appears to be futures
        
    Examples:
        >>> is_futures_symbol("NQZ5")
        True
        >>> is_futures_symbol("ESH25")
        True
        >>> is_futures_symbol("AAPL")
        False
    """
    if not symbol:
        return False
    
    symbol_upper = symbol.upper()
    
    # Common futures root symbols
    futures_roots = ['NQ', 'ES', 'CL', 'GC', 'ZB', 'RTY', 'YM', 'SI', 'HG']
    
    for root in futures_roots:
        if symbol_upper.startswith(root):
            # Check if followed by month code + year
            if len(symbol_upper) > len(root):
                return True
    
    # General pattern: letters + month code + year digit(s)
    # Example: NQZ5, ESH25, CLM24
    if len(symbol_upper) >= 4:
        # Last char should be digit (year)
        if symbol_upper[-1].isdigit():
            # Second to last should be letter (month code)
            if symbol_upper[-2].isalpha():
                return True
    
    return False


def get_contract_type(contract) -> str:
    """
    Get contract security type.
    
    Args:
        contract: IB contract object
        
    Returns:
        Security type string: 'STK', 'FUT', 'OPT', 'FOP', 'CASH', etc.
    """
    if not contract:
        return 'UNKNOWN'
    
    sec_type = getattr(contract, 'secType', None)
    if sec_type:
        return str(sec_type)
    
    return 'UNKNOWN'


def format_contract_symbol(contract) -> str:
    """
    Format contract symbol for display.
    Prefers localSymbol for futures, symbol for stocks.
    
    Args:
        contract: IB contract object
        
    Returns:
        Formatted symbol string
    """
    if not contract:
        return "?"
    
    sec_type = get_contract_type(contract)
    
    if sec_type == 'FUT':
        # Use localSymbol for futures (e.g., NQZ5)
        return getattr(contract, 'localSymbol', None) or getattr(contract, 'symbol', '?')
    else:
        # Use symbol for stocks
        return getattr(contract, 'symbol', None) or getattr(contract, 'localSymbol', '?')


def get_contract_multiplier(contract) -> float:
    """
    Get contract multiplier.
    
    Args:
        contract: IB contract object
        
    Returns:
        Multiplier as float (1.0 for stocks, varies for futures/options)
    """
    if not contract:
        return 1.0
    
    multiplier = getattr(contract, 'multiplier', None)
    
    if multiplier:
        try:
            return float(multiplier)
        except (ValueError, TypeError):
            pass
    
    # Default multipliers by type
    sec_type = get_contract_type(contract)
    
    if sec_type == 'STK':
        return 1.0
    elif sec_type == 'FUT':
        # Try to infer from symbol
        symbol = getattr(contract, 'symbol', '')
        from config import FUTURES_MULTIPLIERS
        return FUTURES_MULTIPLIERS.get(symbol, 1.0)
    elif sec_type == 'OPT':
        return 100.0  # Standard option contract
    
    return 1.0


def build_and_qualify(ib, symbol: str):
    """
    Build and qualify a stock contract.
    Used by scanners to create contracts from symbols.
    
    Args:
        ib: IB connection instance
        symbol: Stock symbol
        
    Returns:
        Qualified contract or None if failed
    """
    try:
        from ib_insync import Stock
        
        contract = Stock(symbol, 'SMART', 'USD')
        
        # Qualify the contract
        qualified = ib.qualifyContracts(contract)
        
        if qualified and len(qualified) > 0:
            return qualified[0]
        
        # Fallback to unqualified
        return contract
        
    except Exception as e:
        logger.warning(f"Failed to build contract for {symbol}: {e}")
        return None
