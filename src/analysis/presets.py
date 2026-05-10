"""Factor analysis parameter presets."""

PRESETS = {
    "short": {
        "id": "short",
        "label": "短期",
        "description": "N=10, M=20 — 适合短线因子验证",
        "flow_lookback": 10,
        "mom_lookback": 20,
        "forward_periods": [1, 5, 10, 20],
    },
    "medium": {
        "id": "medium",
        "label": "中期",
        "description": "N=20, M=60 — 适合中线持仓参考",
        "flow_lookback": 20,
        "mom_lookback": 60,
        "forward_periods": [1, 5, 10, 20, 40, 60],
    },
    "long": {
        "id": "long",
        "label": "长期",
        "description": "N=40, M=120 — 适合长周期趋势判断",
        "flow_lookback": 40,
        "mom_lookback": 120,
        "forward_periods": [5, 10, 20, 40, 60],
    },
}

DEFAULT_PRESET = "short"


def get_preset(preset_id: str) -> dict:
    """Return preset config or the default if not found."""
    return PRESETS.get(preset_id, PRESETS[DEFAULT_PRESET])


def all_preset_ids() -> list:
    """Return all preset IDs in display order."""
    return ["short", "medium", "long"]
