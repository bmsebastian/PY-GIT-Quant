from typing import Dict, Any, List

DEFAULT_CHECKS = [
    'risk_limits',
    'contract_filters',
    'timeframes',
    'fees_model',
    'slippage_model',
    'strategy_params',
]

def compare_configs(backtest_cfg: Dict[str, Any], live_cfg: Dict[str, Any]) -> List[str]:
    issues = []
    for key in DEFAULT_CHECKS:
        if backtest_cfg.get(key) != live_cfg.get(key):
            issues.append(f"Mismatch in {key}: backtest={backtest_cfg.get(key)} live={live_cfg.get(key)}")
    return issues

def run_parity(backtest_cfg: Dict[str, Any], live_cfg: Dict[str, Any]) -> Dict[str, Any]:
    diffs = compare_configs(backtest_cfg, live_cfg)
    ok = (len(diffs) == 0)
    return {'ok': ok, 'diffs': diffs}
