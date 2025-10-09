import math

def earnings_proximity_score(days_to_announce: float) -> float:
    return math.exp(-abs(days_to_announce)/3.0)

def news_burst_score(headlines_last_60m: int) -> float:
    return min(1.0, headlines_last_60m / 5.0)

def fused_score(z_momo: float, z_volume: float, news_burst: float, earn_prox: float, w=(0.35,0.25,0.25,0.15)):
    wm, wv, wn, we = w
    return wm*z_momo + wv*z_volume + wn*news_burst + we*earn_prox
