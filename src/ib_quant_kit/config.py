from pydantic import BaseModel
from dotenv import load_dotenv
import os
from .risk.limits import RiskState, RiskLimits

load_dotenv()

class Settings(BaseModel):
    dry_run: bool = os.getenv('DRY_RUN', '1') == '1'
    data_dir: str = os.getenv('DATA_DIR', './data')
    ib_host: str = os.getenv("IB_HOST", "127.0.0.1")
    ib_port: int = int(os.getenv("IB_PORT", "7497"))
    ib_client_id: int = int(os.getenv("IB_CLIENT_ID", "7"))
    market_data_type_default: int = int(os.getenv("IB_MKT_DATA_TYPE", "1"))  # 1=REALTIME, 3=DELAYED
    universe: list[str] = os.getenv("UNIVERSE", "ES,NQ,SPY").split(",")
    max_quote_age_secs: float = float(os.getenv("MAX_QUOTE_AGE_SECS", "2.0"))
    # Risk limits
    per_symbol_notional_cap: float = float(os.getenv("PER_SYMBOL_NOTIONAL_CAP", "50000"))
    max_position_per_symbol: int = int(os.getenv("MAX_POSITION_PER_SYMBOL", "5"))
    max_orders_per_day_per_symbol: int = int(os.getenv("MAX_ORDERS_PER_DAY_PER_SYMBOL", "50"))
    # Safety
    ENABLE_RTH_GUARD: bool = os.getenv("ENABLE_RTH_GUARD", "1") == "1"
    ENABLE_CALENDAR: bool = os.getenv("ENABLE_CALENDAR", "0") == "1"  # requires exchange_calendars
    KILL_SWITCH_FILE: str = os.getenv("KILL_SWITCH_FILE", "./KILL_SWITCH.ON")

    roll_cal_file: str = os.getenv('ROLL_CAL_FILE', '')
    pg_dsn: str = os.getenv('PG_DSN', '')
    def build_risk_state(self) -> "RiskState":
        return RiskState(RiskLimits(
            per_symbol_notional_cap=self.per_symbol_notional_cap,
            max_position_per_symbol=self.max_position_per_symbol,
            max_orders_per_day_per_symbol=self.max_orders_per_day_per_symbol
        ))

settings = Settings()