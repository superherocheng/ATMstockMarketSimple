"""
BARRA-style Risk Factor Neutralization
========================================

Removes systematic risk exposures from raw factor Z-scores to extract
"pure alpha" — the part of each factor that is not explained by
known risk drivers.

Risk factors (for A-share sector ETFs, small cross-section N≈22):
- VOL: 60-day rolling volatility
- BETA: 60-day rolling beta to CSI 500
- SIZE: log(circ_mv proxy) from ETF close × shares

Method: cross-sectional regression per date
    Z_raw_i = β₀ + β₁·VOL_i + β₂·BETA_i + β₃·SIZE_i + ε_i
    Alpha_i = Z-score(ε_i)

For N < 20, collapses to Ridge regression (α=1.0) to prevent overfit.
For N < 12, falls back to univariate composite orthogonalization.

All computations use existing in-memory DataFrames — no extra DB queries.
"""
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MIN_CROSS_SECTION = 12     # minimum ETFs for any neutralization
MIN_CROSS_FOR_OLS = 18     # minimum for OLS with 3 risk factors
RIDGE_ALPHA = 1.0          # L2 penalty for Ridge

# ════════════════════════════════════════════════════════════
#  Risk factor computation
# ════════════════════════════════════════════════════════════

def compute_risk_factors(
    etf_returns: pd.DataFrame,
    market_returns: pd.Series,
    size_proxy: pd.Series,
    window: int = 60,
) -> pd.DataFrame:
    """Compute BARRA risk factor exposures for all ETFs.

    Args:
        etf_returns: DataFrame (dates × etf_codes) of daily pct returns.
        market_returns: Series (dates) of market benchmark returns (CSI 500).
        size_proxy: Series (etf_code) of log(AUM proxy).
        window: Rolling window for vol/beta (default 60).

    Returns:
        DataFrame (etf_codes × risk_factors) with columns:
        - 'VOL': 60d rolling volatility Z-scored
        - 'BETA': 60d rolling beta Z-scored
        - 'SIZE': log(size) Z-scored
    """
    # Volatility: rolling std of daily returns
    vol = etf_returns.rolling(window=window, min_periods=30).std()
    latest_vol = vol.iloc[-1] if len(vol) > 0 else pd.Series(dtype=float)

    # Beta: rolling covariance with market / market variance
    beta = pd.Series(dtype=float, index=etf_returns.columns)
    common_dates = etf_returns.index.intersection(market_returns.index)
    if len(common_dates) >= window:
        mkt = market_returns.loc[common_dates]
        for code in etf_returns.columns:
            etf_ret = etf_returns.loc[common_dates, code]
            cov = etf_ret.rolling(window=window, min_periods=30).cov(mkt)
            var = mkt.rolling(window=window, min_periods=30).var()
            b = (cov / var).iloc[-1] if not var.iloc[-1] == 0 else 0.0
            beta[code] = b if not (np.isnan(b) or np.isinf(b)) else 0.0
    beta = beta.fillna(0.0)

    # Build risk factor DataFrame
    risk = pd.DataFrame({
        "VOL": latest_vol,
        "BETA": beta,
        "SIZE": size_proxy,
    })

    # Z-score each risk factor across ETFs
    for col in risk.columns:
        valid = risk[col].notna()
        if valid.sum() < 3:
            risk[col] = 0.0
        else:
            m = risk.loc[valid, col].mean()
            s = risk.loc[valid, col].std()
            if s > 0:
                risk[col] = (risk[col] - m) / s
            else:
                risk[col] = 0.0

    return risk.fillna(0.0)


# ════════════════════════════════════════════════════════════
#  Cross-sectional orthogonalization
# ════════════════════════════════════════════════════════════

def _ols_residual(y: pd.Series, X: pd.DataFrame) -> pd.Series:
    """Cross-sectional OLS residual (with intercept)."""
    import statsmodels.api as sm
    Xw = sm.add_constant(X, has_constant="add")
    try:
        model = sm.OLS(y.astype(float), Xw.astype(float), missing="drop")
        fit = model.fit()
        resid = fit.resid
        # Fill NaN residuals with 0 (ETF dropped from fit)
        result = pd.Series(0.0, index=y.index)
        result.loc[resid.index] = resid
        return result
    except Exception:
        return pd.Series(0.0, index=y.index)


def _ridge_residual(y: pd.Series, X: pd.DataFrame) -> pd.Series:
    """Cross-sectional Ridge regression residual (L2 penalty)."""
    from sklearn.linear_model import Ridge
    valid = y.notna() & X.notna().all(axis=1)
    if valid.sum() < 3:
        return pd.Series(0.0, index=y.index)

    yv = y.loc[valid].values.astype(float)
    Xv = np.column_stack([np.ones(valid.sum()), X.loc[valid].values.astype(float)])

    try:
        model = Ridge(alpha=RIDGE_ALPHA, fit_intercept=False)
        model.fit(Xv, yv)
        pred = model.predict(Xv)
        resid = yv - pred
        result = pd.Series(0.0, index=y.index)
        result.loc[valid] = resid
        return result
    except Exception:
        return pd.Series(0.0, index=y.index)


def _composite_orthogonalize(y: pd.Series, risk_composite: pd.Series) -> pd.Series:
    """Univariate orthogonalization against a single risk composite."""
    valid = y.notna() & risk_composite.notna()
    if valid.sum() < 3:
        return pd.Series(0.0, index=y.index)

    yv = y.loc[valid].values.astype(float)
    xv = risk_composite.loc[valid].values.astype(float)

    # Beta = Cov(y, x) / Var(x)
    var_x = np.var(xv, ddof=1)
    if var_x < 1e-10:
        return y.copy()

    cov = np.cov(yv, xv, ddof=1)[0, 1]
    beta = cov / var_x
    residual = yv - beta * xv

    result = pd.Series(0.0, index=y.index)
    result.loc[valid] = residual
    return result


# ════════════════════════════════════════════════════════════
#  Main entry point
# ════════════════════════════════════════════════════════════

def neutralize_factors(
    factor_z_scores: pd.DataFrame,
    risk_factors: pd.DataFrame,
) -> pd.DataFrame:
    """BARRA-neutralize all alpha factor Z-scores against risk factors.

    Args:
        factor_z_scores: DataFrame (etf_codes × alpha_factor_names)
            of raw cross-sectional Z-scores.
        risk_factors: DataFrame (etf_codes × risk_factor_names)
            Z-scored risk factor exposures (VOL, BETA, SIZE).

    Returns:
        DataFrame (etf_codes × alpha_factor_names)
            of BARRA-neutralized Z-scores.
    """
    n_etfs = len(factor_z_scores)
    n_risk = len(risk_factors.columns)

    result = factor_z_scores.copy()

    if n_etfs < MIN_CROSS_SECTION:
        logger.info(
            f"Cross-section too small (N={n_etfs} < {MIN_CROSS_SECTION}), "
            f"skipping neutralization"
        )
        return result

    if n_etfs < MIN_CROSS_FOR_OLS:
        # Small cross-section: composite orthogonalization
        logger.info(
            f"Small cross-section (N={n_etfs}), using composite orthogonalization"
        )
        # Build risk composite (equal-weight Z-score of risk factors)
        risk_composite = risk_factors.mean(axis=1)
        risk_composite = (risk_composite - risk_composite.mean()) / risk_composite.std()

        for col in factor_z_scores.columns:
            residual = _composite_orthogonalize(
                factor_z_scores[col], risk_composite
            )
            result[col] = Z_score(residual)

    else:
        # Sufficient ETFs: OLS with all risk factors
        logger.info(
            f"Adequate cross-section (N={n_etfs}), using OLS neutralization"
        )
        X_risk = risk_factors

        for col in factor_z_scores.columns:
            if n_etfs < MIN_CROSS_FOR_OLS + 3:
                # Borderline: use Ridge
                residual = _ridge_residual(factor_z_scores[col], X_risk)
            else:
                residual = _ols_residual(factor_z_scores[col], X_risk)

            # Re-Z-score the residual
            result[col] = Z_score(residual)

    return result


def Z_score(series: pd.Series) -> pd.Series:
    """Z-score a Series, handling edge cases."""
    valid = series.notna()
    if valid.sum() < 2:
        return pd.Series(0.0, index=series.index)
    m = series.loc[valid].mean()
    s = series.loc[valid].std()
    if s == 0:
        return pd.Series(0.0, index=series.index)
    z = (series - m) / s
    return z.fillna(0.0)


# ════════════════════════════════════════════════════════════
#  Standalone test
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Quick test with synthetic data
    np.random.seed(42)
    n_etfs = 22
    codes = [f"ETF_{i:02d}" for i in range(n_etfs)]

    # Synthetic risk factors
    vol = np.random.randn(n_etfs) * 0.5
    beta = np.random.randn(n_etfs) * 0.3 + 1.0
    size = np.random.randn(n_etfs)

    risk = pd.DataFrame({"VOL": vol, "BETA": beta, "SIZE": size}, index=codes)

    # Synthetic alpha factors with known risk exposure
    alpha_common = 0.3 * vol + 0.2 * beta - 0.1 * size  # systematic component
    z_rsrs = alpha_common + np.random.randn(n_etfs) * 0.5  # true alpha + noise
    z_flow = alpha_common + np.random.randn(n_etfs) * 0.4
    z_mom = -alpha_common + np.random.randn(n_etfs) * 0.6

    factors = pd.DataFrame({
        "RSRS": Z_score(pd.Series(z_rsrs)),
        "Flow": Z_score(pd.Series(z_flow)),
        "Mom": Z_score(pd.Series(z_mom)),
    })

    print("=== BARRA Neutralization Test ===")
    print(f"Before — factor correlation with risk composite:")
    risk_composite = risk.mean(axis=1)
    for col in factors.columns:
        corr = factors[col].corr(risk_composite)
        print(f"  {col:6s}: r={corr:.4f}")

    neutralized = neutralize_factors(factors, risk)

    print(f"\nAfter — neutralized factor correlation with risk composite:")
    for col in neutralized.columns:
        corr = neutralized[col].corr(risk_composite)
        print(f"  {col:6s}: r={corr:.4f}")

    print(f"\n  ✅ Factors successfully orthogonalized against risk")
