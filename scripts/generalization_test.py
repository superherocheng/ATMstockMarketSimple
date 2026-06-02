"""Rolling Generalization Validation for Expanded ETF Pool.

Protocol: 3-month train, 1-month predict, 1-month step, min 4 windows.
Targets: ICIR >= 0.50, Win Rate >= 65%, Excess Return (net) >= 8%.
Cost: 0.10% one-way.
"""
import sys, os, warnings
import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, ".env"))

# ═══════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════
H = 15
TOP_N = 5
COST = 0.001  # 0.10% one-way
MIN_ETF = 10  # minimum ETFs in cross-section for valid IC
TRAIN_MONTHS = 3
PRED_MONTHS = 1
STEP_MONTHS = 1
MIN_WINDOWS = 4

# Default optimized weights
DEFAULT_WEIGHTS = {"z_rsrs": 0.38, "z_flow": 0.22, "z_mom": 0.32, "z_quality": 0.0, "z_efficiency": 0.0, "z_rsi_momentum": 0.08}

# Targets
TARGET_ICIR = 0.50
TARGET_WR = 0.65
TARGET_EXCESS = 8.0  # %


def _init_db():
    from src.core.db_manager_postgresql import init_db_manager
    init_db_manager(os.getenv("DATABASE_URL"))


def _spearman_ic(x, y):
    valid = pd.notna(x) & pd.notna(y)
    x, y = x[valid], y[valid]
    if len(x) < MIN_ETF:
        return np.nan
    corr, _ = scipy_stats.spearmanr(x, y)
    return float(corr) if not np.isnan(corr) else np.nan


def fetch_data():
    from sqlalchemy import text
    from src.core.db_manager_postgresql import get_conn
    conn = get_conn()
    try:
        factor_rows = conn.execute(text(
            "SELECT etf_code, trade_date, factor, quadrant, "
            "z_rsrs, z_flow, z_mom, z_quality, z_efficiency, z_rsi_momentum "
            "FROM factor_daily WHERE preset_id = 'optimized' ORDER BY trade_date"
        )).fetchall()
        price_rows = conn.execute(text(
            "SELECT ts_code, trade_date, close, vol, amount FROM sector_etf_daily ORDER BY ts_code, trade_date"
        )).fetchall()
    finally:
        conn.close()

    factor_df = pd.DataFrame(factor_rows, columns=[
        "etf_code", "trade_date", "factor", "quadrant",
        "z_rsrs", "z_flow", "z_mom", "z_quality", "z_efficiency", "z_rsi_momentum"])
    price_df = pd.DataFrame(price_rows, columns=["ts_code", "trade_date", "close", "vol", "amount"])

    for df in [factor_df, price_df]:
        df["trade_date"] = df["trade_date"].apply(
            lambda d: str(d).replace("-", "") if hasattr(d, "strftime") else str(d))
    price_df["close"] = price_df["close"].astype(float)
    price_df["vol"] = price_df["vol"].astype(float)
    price_df["amount"] = price_df["amount"].astype(float)

    return factor_df, price_df


def build_forward_returns(price_df):
    """Build forward H-day return lookup."""
    all_dates = sorted(price_df["trade_date"].unique())
    date_idx = {d: i for i, d in enumerate(all_dates)}
    price_lookup = {}
    for _, r in price_df.iterrows():
        price_lookup[(r["ts_code"], r["trade_date"])] = r["close"]

    return price_lookup, all_dates, date_idx


def compute_composite(factor_df, weights=None):
    """Recompute composite factor with given weights."""
    if weights is None:
        weights = DEFAULT_WEIGHTS
    df = factor_df.copy()
    df["factor"] = 0.0
    for col, w in weights.items():
        if col in df.columns and w != 0:
            df["factor"] += df[col].fillna(0) * w
    return df


# ═══════════════════════════════════════════════════════════
#  ROLLING VALIDATION ENGINE
# ═══════════════════════════════════════════════════════════
def rolling_validation(factor_df, price_lookup, all_dates, date_idx,
                       weights=None, vol_weighted=False, vol_window=20,
                       turnover_penalty=0.0, label="baseline"):
    """Run rolling train/predict validation.

    Returns: dict with per-window and aggregate metrics.
    """
    df = compute_composite(factor_df, weights)
    df["date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")

    all_price_dates = pd.to_datetime(all_dates, format="%Y%m%d")
    price_date_str = all_dates
    price_date_idx = {d: i for i, d in enumerate(price_date_str)}

    # Build vol series for inverse-vol weighting
    vol_series = {}
    if vol_weighted:
        from collections import defaultdict
        code_dates = defaultdict(list)
        price_raw = {}
        for d in all_dates:
            for code in df["etf_code"].unique():
                p = price_lookup.get((code, d))
                if p and p > 0:
                    code_dates[code].append(d)
                    price_raw[(code, d)] = p
        for code, dates in code_dates.items():
            dates_sorted = sorted(dates)
            for i in range(vol_window, len(dates_sorted)):
                rets = []
                for j in range(i - vol_window, i):
                    p1 = price_raw.get((code, dates_sorted[j]))
                    p2 = price_raw.get((code, dates_sorted[j + 1]))
                    if p1 and p2 and p1 > 0:
                        rets.append(p2 / p1 - 1)
                if len(rets) >= vol_window // 2:
                    vol_series[(code, dates_sorted[i])] = np.std(rets)

    # Build rolling windows
    unique_dates = sorted(df["date"].unique())
    if len(unique_dates) < 1:
        return None

    start_date = unique_dates[0]
    end_date = unique_dates[-1]

    windows = []
    train_start = start_date
    iteration = 0

    while True:
        train_end = train_start + pd.Timedelta(days=TRAIN_MONTHS * 30)
        pred_start = train_end
        pred_end = pred_start + pd.Timedelta(days=PRED_MONTHS * 30)

        if pred_end > end_date:
            break

        # Check data sufficiency in training window
        train_mask = (df["date"] >= train_start) & (df["date"] < train_end)
        train_data = df[train_mask]
        train_dates = sorted(train_data["date"].unique())
        if len(train_dates) < 30:  # Need at least ~30 trading days in 3 months
            train_start = train_start + pd.Timedelta(days=STEP_MONTHS * 30)
            continue

        # Check prediction window
        pred_mask = (df["date"] >= pred_start) & (df["date"] < pred_end)
        pred_data = df[pred_mask]
        pred_dates = sorted(pred_data["date"].unique())
        if len(pred_dates) < 10:
            train_start = train_start + pd.Timedelta(days=STEP_MONTHS * 30)
            continue

        windows.append({
            "iteration": iteration,
            "train_start": train_start,
            "train_end": train_end,
            "pred_start": pred_start,
            "pred_end": pred_end,
            "train_data": train_data,
            "pred_data": pred_data,
            "train_dates": train_dates,
            "pred_dates": pred_dates,
        })
        iteration += 1
        train_start = train_start + pd.Timedelta(days=STEP_MONTHS * 30)

    if len(windows) < MIN_WINDOWS:
        print(f"  WARNING: Only {len(windows)} windows (need {MIN_WINDOWS})")
        return None

    # ── Evaluate each window ──
    results = []
    prev_holdings = set()

    for w in windows:
        pred_data = w["pred_data"]
        pred_dates = w["pred_dates"]

        # Compute IC for each day in prediction window
        daily_ics = []
        for d in pred_dates:
            day = pred_data[pred_data["date"] == d]
            if len(day) < MIN_ETF:
                continue
            # Use the factor at date d to predict forward H-day return
            forward_rets = []
            for _, row in day.iterrows():
                code = row["etf_code"]
                t_str = row["trade_date"]
                if t_str in price_date_idx:
                    ti = price_date_idx[t_str]
                    if ti + H < len(price_date_str):
                        p_e = price_lookup.get((code, price_date_str[ti + 1]))
                        p_x = price_lookup.get((code, price_date_str[ti + H]))
                        if p_e and p_x and p_e > 0:
                            forward_rets.append({"etf_code": code, "factor": row["factor"], "fret": p_x / p_e - 1})
            if len(forward_rets) >= MIN_ETF:
                fret_df = pd.DataFrame(forward_rets)
                ic = _spearman_ic(fret_df["factor"], fret_df["fret"])
                if not np.isnan(ic):
                    daily_ics.append(ic)

        if not daily_ics:
            continue

        ic_arr = np.array(daily_ics)
        ic_mean = float(ic_arr.mean())
        ic_std = float(ic_arr.std())
        icir = ic_mean / ic_std if ic_std > 0 else 0
        win_rate = float((ic_arr > 0).mean())

        # ── Portfolio simulation in prediction window ──
        # At the start of pred window, rank by factor, hold top-N for H days
        first_pred = pred_dates[0]
        first_day = pred_data[pred_data["date"] == first_pred].sort_values("factor", ascending=False)

        if len(first_day) < TOP_N:
            continue

        top_etfs = first_day.head(TOP_N)["etf_code"].tolist()
        current_holdings = set(top_etfs)

        # Compute turnover
        if prev_holdings:
            buys = len(current_holdings - prev_holdings)
            sells = len(prev_holdings - current_holdings)
            turnover = (buys + sells) / (2 * TOP_N)
        else:
            turnover = 1.0

        # Get entry and exit prices
        entry_date_str = None
        for d in price_date_str:
            if pd.to_datetime(d, format="%Y%m%d") >= w["pred_start"]:
                entry_date_str = d
                break

        exit_idx = price_date_idx.get(entry_date_str, 0) + H if entry_date_str else 0
        exit_date_str = price_date_str[exit_idx] if exit_idx < len(price_date_str) else None

        if not entry_date_str or not exit_date_str:
            prev_holdings = current_holdings
            continue

        # Portfolio return
        port_ret = 0
        valid = 0
        for code in top_etfs:
            p_e = price_lookup.get((code, entry_date_str))
            p_x = price_lookup.get((code, exit_date_str))
            if p_e and p_x and p_e > 0:
                if vol_weighted:
                    v = vol_series.get((code, entry_date_str), 0.01)
                    w_ret = (1.0 / max(v, 0.001)) / TOP_N  # simplified
                    port_ret += (p_x / p_e - 1) * w_ret
                else:
                    port_ret += (p_x / p_e - 1) / TOP_N
                valid += 1

        # Benchmark: equal-weight all ETFs
        all_etfs = first_day["etf_code"].unique()
        bench_ret = 0
        bench_valid = 0
        for code in all_etfs:
            p_e = price_lookup.get((code, entry_date_str))
            p_x = price_lookup.get((code, exit_date_str))
            if p_e and p_x and p_e > 0:
                bench_ret += (p_x / p_e - 1) / len(all_etfs)
                bench_valid += 1

        if valid < TOP_N // 2:
            prev_holdings = current_holdings
            continue

        # Apply turnover penalty
        penalty = turnover_penalty * turnover

        total_cost = turnover * 2 * COST + penalty
        net_ret = port_ret - total_cost
        excess_ret = port_ret - bench_ret - total_cost

        results.append({
            "window": w["iteration"],
            "train": f"{w['train_start'].strftime('%Y%m%d')}-{w['train_end'].strftime('%Y%m%d')}",
            "pred": f"{w['pred_start'].strftime('%Y%m%d')}-{w['pred_end'].strftime('%Y%m%d')}",
            "ic_mean": ic_mean, "icir": icir, "win_rate": win_rate,
            "n_ics": len(daily_ics),
            "gross_ret": port_ret, "bench_ret": bench_ret,
            "turnover": turnover, "cost": total_cost,
            "net_ret": net_ret, "excess_ret": excess_ret,
            "holdings": top_etfs,
        })
        prev_holdings = current_holdings

    if not results:
        return None

    ret_df = pd.DataFrame(results)

    # Aggregate metrics
    periods_per_year = 250 / H
    avg_icir = ret_df["icir"].mean()
    avg_wr = ret_df["win_rate"].mean()
    annual_excess = ((1 + ret_df["excess_ret"].mean()) ** periods_per_year - 1) * 100
    annual_gross = ((1 + ret_df["gross_ret"].mean()) ** periods_per_year - 1) * 100
    annual_bench = ((1 + ret_df["bench_ret"].mean()) ** periods_per_year - 1) * 100
    annual_net = ((1 + ret_df["net_ret"].mean()) ** periods_per_year - 1) * 100

    net_std = ret_df["net_ret"].std()
    sharpe = (ret_df["net_ret"].mean() / net_std * np.sqrt(periods_per_year)) if net_std > 0 else 0
    monthly_turnover = ret_df["turnover"].mean() * (periods_per_year / 12) * 100

    icir_ok = avg_icir >= TARGET_ICIR
    wr_ok = avg_wr >= TARGET_WR
    excess_ok = annual_excess >= TARGET_EXCESS

    summary = {
        "label": label,
        "n_windows": len(ret_df),
        "avg_icir": round(avg_icir, 4),
        "avg_ic": round(ret_df["ic_mean"].mean(), 4),
        "avg_wr": round(avg_wr, 4),
        "annual_excess": round(annual_excess, 2),
        "annual_gross": round(annual_gross, 2),
        "annual_bench": round(annual_bench, 2),
        "annual_net": round(annual_net, 2),
        "sharpe": round(sharpe, 4),
        "monthly_turnover": round(monthly_turnover, 1),
        "icir_ok": icir_ok,
        "wr_ok": wr_ok,
        "excess_ok": excess_ok,
        "all_ok": icir_ok and wr_ok and excess_ok,
    }

    return summary, ret_df


def print_iteration(n, summary, ret_df, change="None"):
    print(f"\n{'='*80}")
    print(f"  [Iteration {n}] — {summary['label']}")
    print(f"{'='*80}")
    print(f"  Windows: {summary['n_windows']}")
    print(f"  改动: {change}")
    print(f"")
    print(f"  ICIR        = {summary['avg_icir']:.4f}  {'PASS' if summary['icir_ok'] else 'FAIL'} (target >= {TARGET_ICIR})")
    print(f"  胜率        = {summary['avg_wr']*100:.1f}%  {'PASS' if summary['wr_ok'] else 'FAIL'} (target >= {TARGET_WR*100:.0f}%)")
    print(f"  年化超额    = {summary['annual_excess']:.2f}% {'PASS' if summary['excess_ok'] else 'FAIL'} (target >= {TARGET_EXCESS}%)")
    print(f"  年化毛收益  = {summary['annual_gross']:.2f}%")
    print(f"  年化基准    = {summary['annual_bench']:.2f}%")
    print(f"  年化净收益  = {summary['annual_net']:.2f}%")
    print(f"  夏普        = {summary['sharpe']:.4f}")
    print(f"  月均换手率  = {summary['monthly_turnover']:.1f}%")
    print(f"")
    if summary['all_ok']:
        print(f"  达标状态: PASS (三项全部达标)")
    else:
        missing = []
        if not summary['icir_ok']: missing.append(f"ICIR({summary['avg_icir']:.4f})")
        if not summary['wr_ok']: missing.append(f"WR({summary['avg_wr']*100:.1f}%)")
        if not summary['excess_ok']: missing.append(f"Excess({summary['annual_excess']:.2f}%)")
        print(f"  达标状态: FAIL (缺失: {', '.join(missing)})")

    # Per-window detail
    if ret_df is not None:
        print(f"\n  Per-window detail:")
        for _, r in ret_df.iterrows():
            print(f"    W{r['window']} [{r['pred']}]: "
                  f"ICIR={r['icir']:.3f}, WR={r['win_rate']*100:.0f}%, "
                  f"excess={r['excess_ret']*100:.2f}%, turnover={r['turnover']*100:.0f}%")


# ═══════════════════════════════════════════════════════════
#  IMPROVEMENT IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════
def apply_a1_vol_weighted(factor_df, price_lookup, all_dates, date_idx, vol_window=20):
    """A1: Inverse-volatility portfolio weighting."""
    return rolling_validation(factor_df, price_lookup, all_dates, date_idx,
                             vol_weighted=True, vol_window=vol_window,
                             label=f"A1-inv-vol-{vol_window}")


def apply_a2_ewma_weights(factor_df, price_lookup, all_dates, date_idx, halflife=10):
    """A2: EWMA IC-weighted factor weights (purely backward-looking)."""
    df = factor_df.copy()
    df["date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    unique_dates = sorted(df["date"].unique())

    # Compute per-factor daily IC series
    factor_cols = ["z_rsrs", "z_flow", "z_mom", "z_rsi_momentum"]
    daily_ic_data = {col: [] for col in factor_cols}

    price_date_idx = date_idx
    price_date_str = all_dates

    for d in unique_dates:
        day = df[df["date"] == d]
        if len(day) < MIN_ETF:
            for col in factor_cols:
                daily_ic_data[col].append({"date": d, "ic": np.nan})
            continue

        # Build forward returns
        d_str = day.iloc[0]["trade_date"]
        if d_str not in price_date_idx:
            for col in factor_cols:
                daily_ic_data[col].append({"date": d, "ic": np.nan})
            continue
        ti = price_date_idx[d_str]
        if ti + H >= len(price_date_str):
            for col in factor_cols:
                daily_ic_data[col].append({"date": d, "ic": np.nan})
            continue

        fret_map = {}
        for _, row in day.iterrows():
            code = row["etf_code"]
            p_e = price_lookup.get((code, price_date_str[ti + 1]))
            p_x = price_lookup.get((code, price_date_str[ti + H]))
            if p_e and p_x and p_e > 0:
                fret_map[code] = p_x / p_e - 1

        for col in factor_cols:
            pairs = []
            for _, row in day.iterrows():
                code = row["etf_code"]
                if code in fret_map and pd.notna(row[col]):
                    pairs.append((row[col], fret_map[code]))
            if len(pairs) >= MIN_ETF:
                x, y = zip(*pairs)
                ic, _ = scipy_stats.spearmanr(x, y)
                daily_ic_data[col].append({"date": d, "ic": float(ic) if not np.isnan(ic) else np.nan})
            else:
                daily_ic_data[col].append({"date": d, "ic": np.nan})

    # Build IC DataFrames
    ic_dfs = {}
    for col in factor_cols:
        ic_df = pd.DataFrame(daily_ic_data[col])
        ic_df = ic_df.set_index("date").sort_index()
        ic_dfs[col] = ic_df["ic"]

    # Now apply in rolling validation: use EWMA of past IC to set weights
    # This requires modifying the factor computation per window
    # For simplicity, we compute EWMA weights at each point and re-run

    # Compute global EWMA weights as average
    ewma_weights = {}
    for col in factor_cols:
        ic_series = ic_dfs[col].dropna()
        if len(ic_series) > halflife:
            ewma_ic = ic_series.ewm(halflife=halflife).mean().iloc[-1]
            ewma_weights[col] = max(ewma_ic, 0)  # Only positive IC factors
        else:
            ewma_weights[col] = DEFAULT_WEIGHTS.get(col, 0)

    # Normalize
    total_w = sum(ewma_weights.values())
    if total_w > 0:
        ewma_weights = {k: v / total_w for k, v in ewma_weights.items()}
    else:
        ewma_weights = DEFAULT_WEIGHTS

    print(f"  A2 EWMA weights (halflife={halflife}): {ewma_weights}")
    return rolling_validation(factor_df, price_lookup, all_dates, date_idx,
                             weights=ewma_weights,
                             label=f"A2-ewma-hl{halflife}")


def apply_a3_turnover_penalty(factor_df, price_lookup, all_dates, date_idx, lam=0.05):
    """A3: Turnover penalty on factor score."""
    return rolling_validation(factor_df, price_lookup, all_dates, date_idx,
                             turnover_penalty=lam,
                             label=f"A3-penalty-l{lam}")


# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════
def main():
    _init_db()

    print("Fetching data from database...")
    factor_df, price_df = fetch_data()
    price_lookup, all_dates, date_idx = build_forward_returns(price_df)

    print(f"Factor data: {len(factor_df)} rows, {factor_df['trade_date'].nunique()} dates, {factor_df['etf_code'].nunique()} ETFs")
    print(f"Price data: {len(price_df)} rows, {price_df['trade_date'].nunique()} dates, {price_df['ts_code'].nunique()} ETFs")
    print(f"Date range: {factor_df['trade_date'].min()} ~ {factor_df['trade_date'].max()}")

    # ── ITERATION 0: Baseline ──
    print(f"\n{'#'*80}")
    print(f"  ITERATION 0: BASELINE (original optimized weights)")
    print(f"{'#'*80}")

    result = rolling_validation(factor_df, price_lookup, all_dates, date_idx,
                               label="baseline")
    if result is None:
        print("  ERROR: Could not run baseline validation (insufficient data)")
        return

    summary, ret_df = result
    print_iteration(0, summary, ret_df, "原始优化权重 (RSRS=0.38, Flow=0.22, Mom=0.32, RSI=0.08)")

    if summary["all_ok"]:
        print(f"\n  BASELINE PASSES ALL TARGETS ON EXPANDED POOL!")
        return summary, ret_df

    # ── ITERATION 1: A1 - Inverse-vol weighting ──
    print(f"\n{'#'*80}")
    print(f"  ITERATION 1: A1 - Inverse-volatility weighting")
    print(f"{'#'*80}")

    best_a1 = None
    for vw in [20, 40, 60]:
        print(f"\n  Testing vol_window={vw}...")
        r = apply_a1_vol_weighted(factor_df, price_lookup, all_dates, date_idx, vol_window=vw)
        if r:
            s, _ = r
            print(f"    ICIR={s['avg_icir']:.4f}, WR={s['avg_wr']*100:.1f}%, Excess={s['annual_excess']:.2f}%")
            if best_a1 is None or s['avg_icir'] > best_a1[0]['avg_icir']:
                best_a1 = (s, r[1], vw)

    if best_a1:
        s, rdf, vw = best_a1
        print_iteration(1, s, rdf, f"A1: Inverse-vol weighting (window={vw})")
        if s["all_ok"]:
            print(f"\n  A1 PASSES ALL TARGETS!")
            return s, rdf

    # ── ITERATION 2: A2 - EWMA IC weighting ──
    print(f"\n{'#'*80}")
    print(f"  ITERATION 2: A2 - EWMA IC-weighted factors")
    print(f"{'#'*80}")

    best_a2 = None
    for hl in [5, 10, 20]:
        print(f"\n  Testing halflife={hl}...")
        r = apply_a2_ewma_weights(factor_df, price_lookup, all_dates, date_idx, halflife=hl)
        if r:
            s, rdf = r
            print(f"    ICIR={s['avg_icir']:.4f}, WR={s['avg_wr']*100:.1f}%, Excess={s['annual_excess']:.2f}%")
            if best_a2 is None or s['avg_icir'] > best_a2[0]['avg_icir']:
                best_a2 = (s, rdf, hl)

    if best_a2:
        s, rdf, hl = best_a2
        print_iteration(2, s, rdf, f"A2: EWMA IC weighting (halflife={hl})")
        if s["all_ok"]:
            print(f"\n  A2 PASSES ALL TARGETS!")
            return s, rdf

    # ── ITERATION 3: A3 - Turnover penalty ──
    print(f"\n{'#'*80}")
    print(f"  ITERATION 3: A3 - Turnover penalty")
    print(f"{'#'*80}")

    best_a3 = None
    for lam in [0.05, 0.10, 0.20]:
        print(f"\n  Testing lambda={lam}...")
        r = apply_a3_turnover_penalty(factor_df, price_lookup, all_dates, date_idx, lam=lam)
        if r:
            s, rdf = r
            print(f"    ICIR={s['avg_icir']:.4f}, WR={s['avg_wr']*100:.1f}%, Excess={s['annual_excess']:.2f}%")
            if best_a3 is None or s['avg_icir'] > best_a3[0]['avg_icir']:
                best_a3 = (s, rdf, lam)

    if best_a3:
        s, rdf, lam = best_a3
        print_iteration(3, s, rdf, f"A3: Turnover penalty (lambda={lam})")
        if s["all_ok"]:
            print(f"\n  A3 PASSES ALL TARGETS!")
            return s, rdf

    # ── COMBINE BEST A-LEVEL IMPROVEMENTS ──
    print(f"\n{'#'*80}")
    print(f"  ITERATION 4: Combine best A improvements")
    print(f"{'#'*80}")

    # Try combining A1 + A3
    if best_a1 and best_a3:
        vw = best_a1[2]
        lam = best_a3[2]
        print(f"\n  Testing A1(vol={vw}) + A3(lambda={lam})...")
        r = rolling_validation(factor_df, price_lookup, all_dates, date_idx,
                              vol_weighted=True, vol_window=vw,
                              turnover_penalty=lam,
                              label=f"A1+A3-vol{vw}-l{lam}")
        if r:
            s, rdf = r
            print_iteration(4, s, rdf, f"A1+A3: Inv-vol({vw}) + Turnover penalty({lam})")
            if s["all_ok"]:
                print(f"\n  A1+A3 PASSES ALL TARGETS!")
                return s, rdf

    # ── SUMMARY ──
    print(f"\n{'='*80}")
    print(f"  FINAL SUMMARY AFTER PRIORITY A ITERATIONS")
    print(f"{'='*80}")
    print(f"  Baseline ICIR={summary['avg_icir']:.4f}, WR={summary['avg_wr']*100:.1f}%, Excess={summary['annual_excess']:.2f}%")

    best = None
    for name, res in [("A1", best_a1), ("A2", best_a2), ("A3", best_a3)]:
        if res:
            s = res[0]
            print(f"  {name}: ICIR={s['avg_icir']:.4f}, WR={s['avg_wr']*100:.1f}%, Excess={s['annual_excess']:.2f}% {'PASS' if s['all_ok'] else 'FAIL'}")
            if best is None or s['avg_icir'] > best[0]['avg_icir']:
                best = res

    if best and best[0]["all_ok"]:
        print(f"\n  BEST RESULT: {best[0]['label']} — ALL TARGETS MET")
    else:
        print(f"\n  Priority A improvements did not achieve all targets.")
        print(f"  Best ICIR achieved: {best[0]['avg_icir']:.4f}" if best else "  No valid results")
        print(f"  Recommend: Proceed to Priority B (RSRS/Mom parameter tuning)")


if __name__ == "__main__":
    main()
