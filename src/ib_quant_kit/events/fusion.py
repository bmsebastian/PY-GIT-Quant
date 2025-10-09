from dataclasses import dataclass
from typing import Optional

@dataclass
class EventScore:
    news_burst: float  # 0..1
    earnings_proximity: float  # 0..1
    sentiment: float  # -1..1
    delta_target_fit: float  # 0..1
    score: float  # 0..1

def blend_event_signal(news_burst: float, earnings_proximity: float, sentiment: float, delta_target_fit: float,
                       w_news=0.35, w_earn=0.30, w_sent=0.15, w_delta=0.20) -> EventScore:
    # Normalize sentiment to [0..1]
    s01 = (sentiment + 1.0) / 2.0
    raw = w_news*news_burst + w_earn*earnings_proximity + w_sent*s01 + w_delta*delta_target_fit
    score = max(0.0, min(1.0, raw))
    return EventScore(news_burst, earnings_proximity, sentiment, delta_target_fit, score)

def earnings_window_proximity(days_to_earnings: Optional[float]) -> float:
    if days_to_earnings is None:
        return 0.0
    # peak at 0 day, fade by 15-day half-life
    d = abs(days_to_earnings)
    return max(0.0, min(1.0, 1.0 - d/15.0))

def simple_delta_fit(abs_delta: float, target: float = 0.30, tol: float = 0.05) -> float:
    # 1.0 when within tol of target, linearly drops to 0.0 by 2*tol
    diff = abs(abs_delta - target)
    if diff <= tol: return 1.0
    if diff >= 2*tol: return 0.0
    return 1.0 - (diff - tol)/tol
