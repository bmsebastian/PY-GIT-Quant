from typing import Dict, Any, List
# Lightweight ML stub: moving-average crossover + event score threshold
def ml_signal(features: Dict[str, Any]) -> float:
    # features: { 'fast': float, 'slow': float, 'event_score': float, ... }
    fast = float(features.get('fast', 0.0))
    slow = float(features.get('slow', 0.0))
    ev = float(features.get('event_score', 0.0))
    base = 1.0 if fast > slow else 0.0
    # Boost by event score; produce confidence 0..1
    return max(0.0, min(1.0, 0.5*base + 0.5*ev))

def decide(features: Dict[str, Any], buy_thr=0.65, sell_thr=0.35) -> str:
    conf = ml_signal(features)
    if conf >= buy_thr:
        return 'BUY'
    if conf <= sell_thr:
        return 'SELL'
    return 'HOLD'
