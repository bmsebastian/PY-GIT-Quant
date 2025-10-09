
from ib_quant_kit.app.intraday_bot import run_once
from ib_quant_kit.config import settings
if __name__ == "__main__":
    logs = run_once(settings.universe)
    for row in logs: print(row)
