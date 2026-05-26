"""Factor analysis parameter presets.

Each preset defines:
- rsrs_lookback: RSRS regression window (N)
- flow_lookback: Share flow trend window (N)
- mom_lookback: Momentum lookback (M)
- forward_periods: Evaluation horizon(s) (H)
- factor_weights: Six-factor combination weights

V4: Added financial quality factor (f_quality).
V5: Added intraday efficiency factor (efficiency).
V6: Added RSI momentum factor (rsi_momentum).

Weight design:
  Base weights from README (3-factor) are proportionally scaled,
  with quality=0.184, efficiency=0.092, rsi_momentum=0.08 filling
  the remaining share. This preserves the original strategy differentiation
  while fairly allocating to the three auxiliary factors.
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
        "factor_weights": {"rsrs": 0.258, "flow": 0.129, "mom": 0.258, "quality": 0.184, "efficiency": 0.092, "rsi_momentum": 0.08},
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
        "factor_weights": {"rsrs": 0.193, "flow": 0.193, "mom": 0.258, "quality": 0.184, "efficiency": 0.092, "rsi_momentum": 0.08},
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
        "factor_weights": {"rsrs": 0.161, "flow": 0.161, "mom": 0.322, "quality": 0.184, "efficiency": 0.092, "rsi_momentum": 0.08},
        "eff_sma_window": 5,
        "reversal_lookback": 5,
    },
}

DEFAULT_PRESET = "short"


def get_preset(preset_id: str) -> dict:
    """Return preset config or the default if not found."""
    return PRESETS.get(preset_id, PRESETS[DEFAULT_PRESET])


def all_preset_ids() -> list:
    """Return all preset IDs in display order."""
    return ["short", "medium", "long"]
