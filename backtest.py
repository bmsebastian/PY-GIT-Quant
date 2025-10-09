# Offline CSV backtest runner
import argparse, os, json
from src.ib_quant_kit.backtest.engine import load_csv_bars, run_backtest
from src.ib_quant_kit.backtest.strategies import ema_cross

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--csv", required=True, help="CSV with columns: ts,open,high,low,close,volume")
    ap.add_argument("--short", type=int, default=9)
    ap.add_argument("--long", type=int, default=21)
    ap.add_argument("--lot", type=int, default=1)
    args = ap.parse_args()

    bars = load_csv_bars(args.csv)
    strat = ema_cross(args.short, args.long)
    res = run_backtest(args.symbol, bars, strat, lot=args.lot)
    print(json.dumps({
        "symbol": args.symbol,
        "trades": [t.__dict__ for t in res.trades],
        "pnl": res.pnl,
        "max_drawdown": res.max_drawdown
    }, indent=2))

if __name__ == "__main__":
    main()
