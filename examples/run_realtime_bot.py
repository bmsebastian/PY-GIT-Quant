
from ib_quant_kit.app.runbot import run_once
if __name__ == "__main__":
    logs = run_once()
    for row in logs: print(row)
