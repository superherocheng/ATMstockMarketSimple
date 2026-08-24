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

Weight design (v9 optimized, 2026-08-24):
  Efficiency 权重清零（泛化测试中 ICIR=-0.19，负贡献还占 6% 权重），
  剩余四因子按原 V8 比例归一化：RSRS .298/.212/.341/.149 ≈ .30/.21/.34/.15。
  Quality=0%（无有效数据，2026-07-01 移除）。
  注意：权重标定样本仅 2025-09~2026-06 单一 regime，属样本内数字，
  待 ≥3 年数据 walk-forward 复验后再固化。
"""
PRESETS = {
    "optimized": {
        "id": "optimized",
        "label": "Optimized",
        "description": "RSRS=20, Flow=10, Mom=20, H=15 — 4-factor (efficiency removed 2026-08), stickiness=1.0",
        "rsrs_lookback": 20,
        "flow_lookback": 10,
        "mom_lookback": 20,
        "forward_periods": [15],
        "factor_weights": {"rsrs": 0.298, "flow": 0.212, "mom": 0.341, "quality": 0.0, "efficiency": 0.0, "rsi_momentum": 0.149},
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
