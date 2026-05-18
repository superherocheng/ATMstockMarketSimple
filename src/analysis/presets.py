"""Factor analysis parameter presets.

Each preset defines:
- rsrs_lookback: RSRS regression window (N)
- flow_lookback: Share flow trend window (N)
- mom_lookback: Momentum lookback (M)
- forward_periods: Evaluation horizon(s) (H)
- factor_weights: Three-factor combination weights
"""

PRESETS = {
    "short": {
        "id": "short",
        "label": "短期",
        "description": "RSRS=20, Flow=10, Mom=20, H=10 — 短线参数组合",
        "rsrs_lookback": 20,
        "flow_lookback": 10,
        "mom_lookback": 20,
        "forward_periods": [10],
        "factor_weights": {"rsrs": 0.4, "flow": 0.2, "mom": 0.4},
    },
    "medium": {
        "id": "medium",
        "label": "中期",
        "description": "RSRS=20, Flow=20, Mom=60, H=20 — 中线持仓参考",
        "rsrs_lookback": 20,
        "flow_lookback": 20,
        "mom_lookback": 60,
        "forward_periods": [20],
        "factor_weights": {"rsrs": 0.3, "flow": 0.3, "mom": 0.4},
    },
    "long": {
        "id": "long",
        "label": "长期",
        "description": "RSRS=30, Flow=40, Mom=120, H=40 — 长周期趋势判断",
        "rsrs_lookback": 30,
        "flow_lookback": 40,
        "mom_lookback": 120,
        "forward_periods": [40],
        "factor_weights": {"rsrs": 0.25, "flow": 0.25, "mom": 0.5},
    },
    "rsrs_aggressive": {
        "id": "rsrs_aggressive",
        "label": "RSRS进取",
        "description": "RSRS=15, Flow=10, Mom=10, H=10 — 偏RSRS权重(0.5/0.2/0.3)",
        "rsrs_lookback": 15,
        "flow_lookback": 10,
        "mom_lookback": 10,
        "forward_periods": [10],
        "factor_weights": {"rsrs": 0.5, "flow": 0.2, "mom": 0.3},
    },
}

DEFAULT_PRESET = "short"


def get_preset(preset_id: str) -> dict:
    """Return preset config or the default if not found."""
    return PRESETS.get(preset_id, PRESETS[DEFAULT_PRESET])


def all_preset_ids() -> list:
    """Return all preset IDs in display order."""
    return ["short", "medium", "long", "rsrs_aggressive"]
