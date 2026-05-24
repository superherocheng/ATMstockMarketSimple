"""Factor analysis parameter presets.

Each preset defines:
- rsrs_lookback: RSRS regression window (N)
- flow_lookback: Share flow trend window (N)
- mom_lookback: Momentum lookback (M)
- forward_periods: Evaluation horizon(s) (H)
- factor_weights: Five-factor combination weights

V4: Added financial quality factor (f_quality).
V5: Added intraday efficiency factor (efficiency).

Weight design:
  Base weights from README (3-factor) are proportionally scaled to 70%,
  with quality=0.20 and efficiency=0.10 filling the remaining 30%.
  This preserves the original strategy differentiation while fairly
  allocating to the two new auxiliary factors.
"""
PRESETS = {
    "short": {
        "id": "short",
        "label": "Short-term",
        "description": "RSRS=20, Flow=10, Mom=20, H=10 — Short-term parameter set",
        "rsrs_lookback": 20,
        "flow_lookback": 10,
        "mom_lookback": 20,
        "forward_periods": [10],
        "factor_weights": {"rsrs": 0.28, "flow": 0.14, "mom": 0.28, "quality": 0.20, "efficiency": 0.10},
        "eff_sma_window": 0,
        "reversal_lookback": 5,
    },
    "medium": {
        "id": "medium",
        "label": "Medium-term",
        "description": "RSRS=20, Flow=20, Mom=60, H=20 — Medium-term holding reference",
        "rsrs_lookback": 20,
        "flow_lookback": 20,
        "mom_lookback": 60,
        "forward_periods": [20],
        "factor_weights": {"rsrs": 0.21, "flow": 0.21, "mom": 0.28, "quality": 0.20, "efficiency": 0.10},
        "eff_sma_window": 5,
        "reversal_lookback": 5,
    },
    "long": {
        "id": "long",
        "label": "Long-term",
        "description": "RSRS=30, Flow=40, Mom=120, H=40 — Long-cycle trend judgment",
        "rsrs_lookback": 30,
        "flow_lookback": 40,
        "mom_lookback": 120,
        "forward_periods": [40],
        "factor_weights": {"rsrs": 0.175, "flow": 0.175, "mom": 0.35, "quality": 0.20, "efficiency": 0.10},
        "eff_sma_window": 5,
        "reversal_lookback": 5,
    },
    "rsrs_aggressive": {
        "id": "rsrs_aggressive",
        "label": "RSRS Aggressive",
        "description": "RSRS=15, Flow=10, Mom=10, H=10 — RSRS-heavy weighting",
        "rsrs_lookback": 15,
        "flow_lookback": 10,
        "mom_lookback": 10,
        "forward_periods": [10],
        "factor_weights": {"rsrs": 0.35, "flow": 0.14, "mom": 0.21, "quality": 0.20, "efficiency": 0.10},
        "eff_sma_window": 0,
        "reversal_lookback": 5,
    },
}

DEFAULT_PRESET = "short"


def get_preset(preset_id: str) -> dict:
    """Return preset config or the default if not found."""
    return PRESETS.get(preset_id, PRESETS[DEFAULT_PRESET])


def all_preset_ids() -> list:
    """Return all preset IDs in display order."""
    return ["short", "medium", "long", "rsrs_aggressive"]
