import os

# Dashboard (not required; placeholders so imports don't fail)
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "127.0.0.1")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8052"))

# IBKR connection
IB_GATEWAY_HOST = os.getenv("IB_GATEWAY_HOST", "127.0.0.1")
IB_GATEWAY_PORT = int(os.getenv("IB_GATEWAY_PORT", "7497"))  # TWS=7497, GW=4002
IB_CLIENT_ID    = int(os.getenv("IB_CLIENT_ID", "13"))

# Environment
ENV = os.getenv("ENV", "paper")         # paper|live
DRY_RUN = int(os.getenv("DRY_RUN", "1")) # 1=simulate, 0=real orders

# Timers (seconds)
POSITION_RECON_SEC = int(os.getenv("POSITION_RECON_SEC", "15"))
HEARTBEAT_SEC      = int(os.getenv("HEARTBEAT_SEC", "5"))
QUOTE_STALE_SEC    = int(os.getenv("QUOTE_STALE_SEC", "3"))
ORDER_TIMEOUT_SEC  = int(os.getenv("ORDER_TIMEOUT_SEC", "30"))

# Risk limits
MAX_DAILY_LOSS   = float(os.getenv("MAX_DAILY_LOSS", "2500"))
MAX_OPEN_ORDERS  = int(os.getenv("MAX_OPEN_ORDERS", "20"))

# Watchlist (quick start)
WATCHLIST = os.getenv("WATCHLIST", "AAPL,MSFT,SPY").split(",")
