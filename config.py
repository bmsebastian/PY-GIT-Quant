
# config.py — v14 minimal configuration
ENV = "paper"
DRY_RUN = 0  # 0 => live/paper, 1 => dry-run
HEARTBEAT_SEC = 1.0  # inner loop pace; heartbeat emission is fixed at 60s in main
DASHBOARD_HOST = "127.0.0.1"
DASHBOARD_PORT = 8052

# IB connection
IB_GATEWAY_HOST = "127.0.0.1"
IB_GATEWAY_PORT = 7497  # TWS paper default
IB_CLIENT_ID = 19
