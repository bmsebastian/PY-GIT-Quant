# Example EMA crossover strategy for backtesting
from collections import deque

def ema_cross(short=9, long=21):
    alpha_s = 2 / (short + 1)
    alpha_l = 2 / (long + 1)
    ema_s = None
    ema_l = None
    last_signal = None

    def strat(state, bar):
        nonlocal ema_s, ema_l, last_signal
        price = bar.close
        ema_s = price if ema_s is None else alpha_s * price + (1 - alpha_s) * ema_s
        ema_l = price if ema_l is None else alpha_l * price + (1 - alpha_l) * ema_l
        if ema_s is None or ema_l is None:
            return None
        if ema_s > ema_l and last_signal != "BUY":
            last_signal = "BUY"
            return "BUY"
        if ema_s < ema_l and last_signal != "SELL":
            last_signal = "SELL"
            return "SELL"
        return None
    return strat
