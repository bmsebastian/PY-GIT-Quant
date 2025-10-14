# config.py - Add this section for futures exchange mapping

# ... existing config ...

# ============================================================================
# FUTURES EXCHANGE MAPPING (v15D FIX)
# ============================================================================

FUTURES_EXCHANGES = {
    'NQ': 'CME',
    'ES': 'CME',
    'RTY': 'CME',
    'YM': 'CBOT',
    'CL': 'NYMEX',
    'GC': 'COMEX',
    'ZB': 'CBOT',
    'ZN': 'CBOT',
    'ZF': 'CBOT',
    'ZT': 'CBOT',
    'SI': 'COMEX',
    'HG': 'COMEX',
    'NG': 'NYMEX',
    'HO': 'NYMEX',
    'RB': 'NYMEX',
    'ZC': 'CBOT',
    'ZS': 'CBOT',
    'ZW': 'CBOT',
}

# Existing multipliers section
FUTURES_MULTIPLIERS = {
    'NQ': 20,
    'ES': 50,
    'CL': 1000,
    'GC': 100,
    'ZB': 1000,
    'RTY': 50,
    'YM': 5,
}
