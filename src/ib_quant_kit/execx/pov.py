
def calc_pov_qty(adv_per_sec: float, target_pov: float, seconds: float) -> float:
    """Very rough: qty = ADV_per_sec * target_pov * seconds."""
    return adv_per_sec * target_pov * max(0.0, seconds)
