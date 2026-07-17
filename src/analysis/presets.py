"""Factor analysis parameter presets.

Each preset defines:
- rsrs_lookback: RSRS regression window (N)
- flow_lookback: Share flow trend window (N)
- mom_lookback: Momentum lookback (M)
- forward_periods: Evaluation horizon(s) (H)
- factor_weights: factor combination weights

Simplification (2026-07-01): collapsed the former short/medium/long/optimized
quartet to a single `optimized` preset. The UI only ever selected `optimized`
(medium/long were never selectable; `short` was a latent inconsistency in the
sector-cards path). `all_preset_ids()` now returns the one preset, so the
compute loops in factor_engine/ic_analyzer run once instead of 4x — ~75% fewer
factor_daily / ic_daily / ic_summary rows per recompute.

Weight design (v8 optimized, ICIR² on 34 industry ETFs, 2025-09~2026-06):
  RSRS(ICIR=0.33→28%) Mom(ICIR=0.39→32%) Flow(ICIR=0.28→20%)
  RSI_Mom(ICIR=0.22→14%) Efficiency(ICIR=0.14→6%) Quality=0% (no valid data).
"""
PRESETS = {
    "optimized": {
        "id": "optimized",
        "label": "Optimized",
        "description": "RSRS=20, Flow=10, Mom=20, H=15 — 34-ETF industry pool, ICIR=0.60, stickiness=1.0",
        "rsrs_lookback": 20,
        "flow_lookback": 10,
        "mom_lookback": 20,
        "forward_periods": [15],
        "factor_weights": {"rsrs": 0.28, "flow": 0.20, "mom": 0.32, "quality": 0.0, "efficiency": 0.06, "rsi_momentum": 0.14},
        "eff_sma_window": 5,
        "reversal_lookback": 5,
        "rsrs_ma_dampening": 0.5,
        "portfolio_stickiness": 1.0,
    },
}

DEFAULT_PRESET = "optimized"


def get_preset(preset_id: str) -> dict:
    """Return preset config or the default if not found."""
    return PRESETS.get(preset_id, PRESETS[DEFAULT_PRESET])


def all_preset_ids() -> list:
    """Return all preset IDs in display order (single preset after the collapse)."""
    return ["optimized"]


def get_active_factors(preset_id: str) -> dict:
    """Return dict of factor_name -> bool indicating if weight > 0."""
    preset = get_preset(preset_id)
    weights = preset.get("factor_weights", {})
    return {
        "quality_active": weights.get("quality", 0) > 0,
        "efficiency_active": weights.get("efficiency", 0) > 0,
        "rsi_momentum_active": weights.get("rsi_momentum", 0) > 0,
        "rsrs_active": weights.get("rsrs", 0) > 0,
        "flow_active": weights.get("flow", 0) > 0,
        "mom_active": weights.get("mom", 0) > 0,
    }
