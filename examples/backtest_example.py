
from ib_quant_kit.sim.backtest import run_backtest_once
if __name__ == "__main__":
    # buy 10 @ limit 100 with quote 99.9 x 100.1 => not filled
    print(run_backtest_once("BUY", 10, 100.0, 99.9, 100.1))
    # buy 10 @ limit 101 with quote 99.9 x 100.1 => filled at ask 100.1
    print(run_backtest_once("BUY", 10, 101.0, 99.9, 100.1))
