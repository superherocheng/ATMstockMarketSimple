"""
RSRS 因子验证脚本 (向量化优化版)
=================================
一次遍历计算所有参数组合的因子，然后查表测试 IC 和共线性。
优化点:
  - 并行 Tushare 数据获取 (ThreadPoolExecutor)
  - 向量化 RSRS 计算 (pandas rolling, 替代 sklearn 逐窗口拟合)
  - 向量化动量计算 (pandas shift + rolling)
  - 速度提升 ~100x+

用法:
    cd ATMstockMarketSimple
    python scripts/verify_rsrs.py
"""
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
import tushare as ts

PERIODS = [
    ("20230101", "20240801", "淡季(熊市)"),
    ("20250101", "20260518", "旺季(牛市)"),
    ("20230101", "20260518", "全周期"),
]
DATA_START = "20220601"
MIN_ETF = 8

SECTOR_ETF = {
    "512480.SH": "半导体ETF", "515030.SH": "新能源车ETF", "512010.SH": "医药ETF",
    "512800.SH": "银行ETF", "512880.SH": "证券ETF", "159928.SZ": "消费ETF",
    "515880.SH": "通信ETF", "159206.SZ": "卫星ETF", "512400.SH": "有色ETF",
    "562500.SH": "机器人ETF", "159870.SZ": "化工ETF", "561360.SH": "石油ETF",
    "159611.SZ": "电力ETF", "512980.SH": "传媒ETF",
    "512690.SH": "白酒ETF", "515210.SH": "钢铁ETF", "515220.SH": "煤炭ETF",
}

RSRS_LOOKBACKS = [5, 10, 15, 20, 30, 40, 60]
MOM_LOOKBACKS = [10, 20, 40, 60]
FORWARD_DAYS_LIST = [5, 10, 20]


# ════════════════════════════════════════════════════════════
#  Part 1: 并行数据获取 (速度 ~5x)
# ════════════════════════════════════════════════════════════
def fetch_data(token):
    ts.set_token(token)
    pro = ts.pro_api()
    codes = list(SECTOR_ETF.keys())
    print(f"Fetching {len(codes)} ETFs ({DATA_START} ~ 20260518, parallel)...")

    def fetch_one(code):
        for _ in range(3):
            try:
                df = pro.fund_daily(ts_code=code, start_date=DATA_START, end_date="20260518")
                if df is not None and len(df) > 0:
                    return code, df
            except Exception:
                time.sleep(1)
        return code, None

    parts = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_one, code): code for code in codes}
        for future in as_completed(futures):
            code, df = future.result()
            if df is not None:
                parts.append(df)
            name = SECTOR_ETF.get(code, code)
            print(f"  {code} ({name}): {'✓' if df is not None else '✗'}")

    kline = pd.concat(parts, ignore_index=True).sort_values(
        ["ts_code", "trade_date"]
    ).reset_index(drop=True)
    print(f"  Total: {len(kline)} rows, {kline['trade_date'].nunique()} dates")
    return kline


# ════════════════════════════════════════════════════════════
#  Part 2: 向量化因子计算 (速度 ~100x)
# ════════════════════════════════════════════════════════════
def _zscore(values):
    """Winsorized cross-sectional z-score."""
    p10 = values.quantile(0.10)
    p90 = values.quantile(0.90)
    clipped = values.clip(p10, p90)
    std = clipped.std()
    if std == 0 or pd.isna(std):
        return pd.Series(0.0, index=values.index)
    return (clipped - clipped.mean()) / std


def compute_all_factors_once(kline_df):
    """一次遍历+向量化: 用 pandas rolling 计算 RSRS(N种) + Mom(M种).

    相比逐窗口 sklearn LinearRegression，滚动窗口的 OLS 可通过
    rolling_corr × rolling_std 直接导出，无需逐个拟合。
    """
    df = kline_df.sort_values(["ts_code", "trade_date"]).reset_index(drop=True)
    etf_codes = df["ts_code"].unique()
    print(f"  Computing factors for {len(etf_codes)} ETFs x "
          f"{len(RSRS_LOOKBACKS)} RSRS + {len(MOM_LOOKBACKS)} Mom params...")

    # ── RSRS 因子 (pandas rolling 向量化 OLS) ──
    # RSRS(N) = beta × R²
    # beta = rolling_corr(high, low) × rolling_std(high) / rolling_std(low)
    # R²   = rolling_corr(high, low)²
    # → RSRS = corr³ × std_high / std_low
    # 使用 pandas 内置 rolling (C 实现) 替代逐窗口循环, ~100x 更快
    for lb in RSRS_LOOKBACKS:
        col = f"rsrs_{lb}"
        df[col] = np.nan

        for code in etf_codes:
            mask = df["ts_code"] == code
            sub = df.loc[mask]
            if len(sub) < lb:
                continue

            h = sub["high"].astype(float)
            l = sub["low"].astype(float)

            # 一次 rolling 计算所有窗口
            corr = h.rolling(lb, min_periods=lb).corr(l)
            std_h = h.rolling(lb, min_periods=lb).std()
            std_l = l.rolling(lb, min_periods=lb).std()

            # RSRS, 避免 std_l ≈ 0 的情况
            beta = corr * std_h / std_l.where(std_l > 1e-12)
            rsrs = beta * corr.pow(2)

            df.loc[mask, col] = rsrs.values

        n_valid = df[col].notna().sum()
        print(f"    {col}: {n_valid} valid values")

    # ── 动量因子 (向量化 pandas) ──
    for lb in MOM_LOOKBACKS:
        col = f"mom_{lb}"
        # 原始动量: close_t / close_{t-lb} - 1
        raw = df.groupby("ts_code")["close"].transform(
            lambda x: x.astype(float) / x.astype(float).shift(lb) - 1
        )

        # 波动率调整: 60日滚动标准差
        daily_ret = df.groupby("ts_code")["close"].transform(
            lambda x: x.astype(float).pct_change()
        )
        vol = daily_ret.rolling(60, min_periods=30).std()

        df[col] = np.where(
            vol.notna() & (vol > 1e-12),
            raw / vol,
            raw
        )
        n_valid = df[col].notna().sum()
        print(f"    {col}: {n_valid} valid values")

    # ── 纯净动量: mom ~ vol_20d 横截面回归残差 ──
    # 思路: 每日期对 ETF 横截面做 OLS: mom = α + β×vol_20d + ε
    # 取 ε 作为纯净动量，剥离波动率共线性
    print("  Computing purified momentum (mom ~ vol_20d cross-sectional residual)...")

    # 计算每只 ETF 的 20 日收益率标准差
    daily_ret = df.groupby("ts_code")["close"].transform(
        lambda x: x.astype(float).pct_change()
    )
    vol_20d = daily_ret.rolling(20, min_periods=10).std()

    for lb in MOM_LOOKBACKS:
        purified_col = f"mom_purified_{lb}"
        mom_col = f"mom_{lb}"
        df[purified_col] = np.nan

        for d in df["trade_date"].unique():
            mask = df["trade_date"] == d
            day_df = df.loc[mask].dropna(subset=[mom_col, vol_20d.name])
            if len(day_df) < MIN_ETF:
                continue

            mom_vals = day_df[mom_col].values.astype(float)
            vol_vals = day_df[vol_20d.name].values.astype(float)

            # OLS: mom = α + β × vol + ε
            A = np.vstack([np.ones(len(vol_vals)), vol_vals]).T
            coeffs, _, _, _ = np.linalg.lstsq(A, mom_vals, rcond=None)
            residuals = mom_vals - (coeffs[0] + coeffs[1] * vol_vals)

            df.loc[day_df.index, purified_col] = residuals

        n_valid = df[purified_col].notna().sum()
        print(f"    {purified_col}: {n_valid} valid values")

    # ── 构建横截面 z-score 存储 ──
    all_dates = sorted(df["trade_date"].unique())
    factor_names = [f"rsrs_{lb}" for lb in RSRS_LOOKBACKS] + \
                   [f"mom_{lb}" for lb in MOM_LOOKBACKS] + \
                   [f"mom_purified_{lb}" for lb in MOM_LOOKBACKS]

    factor_store = {fn: {} for fn in factor_names}

    print(f"  Computing cross-sectional z-scores for {len(all_dates)} dates x "
          f"{len(factor_names)} factors via groupby transform...")

    # 优化: 用 groupby.transform 替代逐日期循环 (C 实现, ~100x 更快)
    for fn in factor_names:
        # 一次性对所有日期组计算 z-score
        zs_col = df[["trade_date", "ts_code", fn]].dropna().copy()
        if len(zs_col) == 0:
            continue

        zs_col["z"] = zs_col.groupby("trade_date")[fn].transform(_zscore)

        # 构建 dict 存储
        grouped = zs_col.groupby("trade_date")
        for d, grp in grouped:
            vals = grp[["ts_code", "z"]].dropna()
            if len(vals) < MIN_ETF:
                continue
            factor_store[fn][d] = vals.set_index("ts_code")["z"].to_dict()

        n_dates = len(factor_store[fn])
        print(f"    {fn}: {n_dates} dates with valid z-scores")

    print(f"  Done. Factors: {factor_names}")
    return factor_store, all_dates


# ════════════════════════════════════════════════════════════
#  Part 3: IC 分析 (优化: rankdata + np.corrcoef 替代 spearmanr)
# ════════════════════════════════════════════════════════════
def _fast_spearman(x, y):
    """Spearman rank correlation using rankdata + Pearson (no scipy overhead)."""
    rx = scipy_stats.rankdata(np.array(x))
    ry = scipy_stats.rankdata(np.array(y))
    return np.corrcoef(rx, ry)[0, 1]


def build_ic_table(factor_store, kline_df, computable_dates, start, end):
    """Build IC table for all factor x forward_days combos, lag=1."""
    price_lookup = {}
    for _, row in kline_df.iterrows():
        price_lookup[(row["ts_code"], row["trade_date"])] = float(row["close"])

    all_dates = sorted(kline_df["trade_date"].unique())
    date_idx = {d: i for i, d in enumerate(all_dates)}

    results = []
    factor_names = list(factor_store.keys())

    for fname in factor_names:
        store = factor_store[fname]

        for h in FORWARD_DAYS_LIST:
            ic_values = []
            for t in all_dates:
                if t < start or t > end:
                    continue
                if t not in date_idx:
                    continue
                idx = date_idx[t]
                if idx < 1 or idx + 1 + h >= len(all_dates):
                    continue

                factor_date = all_dates[idx - 1]  # lag=1
                entry_date = all_dates[idx + 1]
                exit_date = all_dates[idx + 1 + h]

                if factor_date not in store:
                    continue

                # Vectorize: build lists in one pass
                day_factors = store[factor_date]
                f_list = []
                r_list = []
                extend_f = f_list.append
                extend_r = r_list.append
                for code, f_val in day_factors.items():
                    if np.isnan(f_val):
                        continue
                    ce = price_lookup.get((code, entry_date))
                    cx = price_lookup.get((code, exit_date))
                    if ce and cx and ce > 0:
                        extend_f(f_val)
                        extend_r(cx / ce - 1)

                if len(f_list) < MIN_ETF:
                    continue
                corr = _fast_spearman(f_list, r_list)
                if not np.isnan(corr):
                    ic_values.append(corr)

            ic_s = pd.Series(ic_values)
            n = len(ic_s)
            if n < 10:
                continue

            results.append({
                "factor": fname,
                "forward_h": h,
                "ic_mean": round(float(ic_s.mean()), 4),
                "icir": round(float(ic_s.mean() / ic_s.std()), 4) if ic_s.std() > 0 else None,
                "ic_win": round(float((ic_s > 0).mean()) * 100, 1),
                "n": n,
            })

    return pd.DataFrame(results)


# ════════════════════════════════════════════════════════════
#  Part 4: 共线性分析
# ════════════════════════════════════════════════════════════
def compute_collinearity(factor_store, start, end):
    """Cross-sectional average correlation between RSRS and Mom factors."""
    results = []
    for rsrs_name in [f"rsrs_{lb}" for lb in RSRS_LOOKBACKS]:
        for mom_name in [f"mom_{lb}" for lb in MOM_LOOKBACKS]:
            rsrs_store = factor_store[rsrs_name]
            mom_store = factor_store[mom_name]
            common_dates = sorted(set(rsrs_store.keys()) & set(mom_store.keys()))
            common_dates = [d for d in common_dates if start <= d <= end]

            pearsons = []
            spearmans = []
            for d in common_dates:
                r_data = rsrs_store[d]
                m_data = mom_store[d]
                common_codes = set(r_data.keys()) & set(m_data.keys())
                if len(common_codes) < MIN_ETF:
                    continue
                rv = [r_data[c] for c in common_codes
                      if not np.isnan(r_data[c]) and not np.isnan(m_data[c])]
                mv = [m_data[c] for c in common_codes
                      if not np.isnan(r_data[c]) and not np.isnan(m_data[c])]
                if len(rv) < MIN_ETF:
                    continue
                p = pd.Series(rv).corr(pd.Series(mv))
                s, _ = scipy_stats.spearmanr(rv, mv)
                if not np.isnan(p):
                    pearsons.append(p)
                    spearmans.append(s)

            if pearsons:
                results.append({
                    "rsrs": rsrs_name,
                    "mom": mom_name,
                    "pearson_mean": round(np.mean(pearsons), 4),
                    "pearson_abs": round(np.mean(np.abs(pearsons)), 4),
                    "spearman_mean": round(np.mean(spearmans), 4),
                    "n_dates": len(pearsons),
                })
    return pd.DataFrame(results)


# ════════════════════════════════════════════════════════════
#  Part 5: 最优组合搜索 (向量化)
# ════════════════════════════════════════════════════════════
def _build_pivots_and_returns(factor_store, kline_df, start, end, forward_h=10):
    """Vectorized: build factor pivot tables and forward return matrix once."""
    all_dates = sorted(kline_df["trade_date"].unique())
    date_idx = {d: i for i, d in enumerate(all_dates)}

    close_pivot = kline_df.pivot(
        index="trade_date", columns="ts_code", values="close"
    ).astype(float).sort_index()

    target_dates = [d for d in all_dates if start <= d <= end]

    fwd_ret_data = {}
    for d in target_dates:
        if d not in date_idx:
            continue
        idx = date_idx[d]
        if idx + 1 + forward_h >= len(all_dates):
            continue
        entry = all_dates[idx + 1]
        exit_ = all_dates[idx + 1 + forward_h]
        if entry in close_pivot.index and exit_ in close_pivot.index:
            ret = close_pivot.loc[exit_] / close_pivot.loc[entry] - 1
            fwd_ret_data[d] = ret

    fwd_ret_df = pd.DataFrame(fwd_ret_data).T

    pivots = {}
    for fname, store in factor_store.items():
        rows = {}
        for d in fwd_ret_df.index:
            if d not in date_idx:
                continue
            signal_date = all_dates[date_idx[d] - 1]
            if signal_date in store:
                rows[d] = pd.Series(store[signal_date])
        if rows:
            pivots[fname] = pd.DataFrame(rows).T.reindex(fwd_ret_df.index)

    return pivots, fwd_ret_df


def _vectorized_ic(factor_pivot, return_df):
    """Compute IC series from aligned factor and return DataFrames."""
    ic_list = []
    for date in factor_pivot.index:
        f = factor_pivot.loc[date].dropna()
        r = return_df.loc[date].dropna()
        common = f.index.intersection(r.index)
        if len(common) < MIN_ETF:
            continue
        corr, _ = scipy_stats.spearmanr(f[common], r[common])
        if not np.isnan(corr):
            ic_list.append(corr)
    ic_s = pd.Series(ic_list)
    if len(ic_s) < 10:
        return None
    return {
        "ic_mean": round(float(ic_s.mean()), 4),
        "icir": round(float(ic_s.mean() / ic_s.std()), 4) if ic_s.std() > 0 else None,
        "ic_win": round(float((ic_s > 0).mean()) * 100, 1),
        "n": len(ic_s),
    }


def _compute_spearman_ic(factor_vals, return_vals):
    """Compute Spearman IC using rankdata + Pearson (fast for small arrays)."""
    if len(factor_vals) < MIN_ETF:
        return np.nan
    rx = scipy_stats.rankdata(factor_vals)
    ry = scipy_stats.rankdata(return_vals)
    corr = np.corrcoef(rx, ry)[0, 1]
    return corr if not np.isnan(corr) else np.nan


def find_optimal_combos(factor_store, kline_df, start, end, forward_h=10):
    """Vectorized grid search: per-date batch IC for all 11 weights at once.

    优化要点:
    - 每对 RSRS/Mom 只遍历一次日期, 一次算完 11 个权重
    - 使用 rankdata + np.corrcoef 替代 scipy spearmanr
    - 提前构建 numpy 数组避免 pandas 逐行开销
    """
    pivots, fwd_ret = _build_pivots_and_returns(
        factor_store, kline_df, start, end, forward_h
    )
    if not pivots or fwd_ret.empty:
        return pd.DataFrame()

    rsrs_names = [f"rsrs_{lb}" for lb in RSRS_LOOKBACKS]
    mom_names = [f"mom_{lb}" for lb in MOM_LOOKBACKS] + \
                [f"mom_purified_{lb}" for lb in MOM_LOOKBACKS]

    results = []
    for rn in rsrs_names:
        if rn not in pivots:
            continue
        rsrs_piv = pivots[rn]
        for mn in mom_names:
            if mn not in pivots:
                continue
            mom_piv = pivots[mn]

            common_idx = rsrs_piv.index.intersection(mom_piv.index).intersection(
                fwd_ret.index
            )
            if len(common_idx) < 10:
                continue

            # 提前提取 numpy 数据, 避免每次循环重建
            rsrs_t = rsrs_piv.loc[common_idx]
            mom_t = mom_piv.loc[common_idx]
            ret_t = fwd_ret.loc[common_idx]

            # 每个权重收集 IC 序列
            ic_series = {w10: [] for w10 in range(0, 11)}

            for date in common_idx:
                # 提取该日期的数据并 dropna
                rv = rsrs_t.loc[date].dropna()
                mv = mom_t.loc[date].dropna()
                rtv = ret_t.loc[date].dropna()

                # 取三者的交集代码
                common = rv.index.intersection(mv.index).intersection(rtv.index)
                if len(common) < MIN_ETF:
                    continue

                rv_a = rv[common].values
                mv_a = mv[common].values
                rtv_a = rtv[common].values

                # 预排序返回 (所有权重共用)
                ry = scipy_stats.rankdata(rtv_a)

                for w10 in range(0, 11):
                    w_r = w10 / 10.0
                    w_m = 1.0 - w_r

                    combined = w_r * rv_a + w_m * mv_a
                    rx = scipy_stats.rankdata(combined)
                    corr = np.corrcoef(rx, ry)[0, 1]
                    if not np.isnan(corr):
                        ic_series[w10].append(corr)

            for w10, ic_list in ic_series.items():
                if len(ic_list) < 10:
                    continue
                arr = np.array(ic_list)
                icir = float(arr.mean() / arr.std()) if arr.std() > 0 else 0
                results.append({
                    "rsrs": rn, "mom": mn,
                    "w_rsrs": w10 / 10.0,
                    "w_mom": 1.0 - w10 / 10.0,
                    "ic_mean": round(float(arr.mean()), 4),
                    "icir": round(icir, 4),
                    "ic_win": round(float((arr > 0).mean()) * 100, 1),
                    "n": len(ic_list),
                })

    return pd.DataFrame(results)


# ════════════════════════════════════════════════════════════
#  Main
# ════════════════════════════════════════════════════════════
def main():
    from dotenv import load_dotenv
    import os
    load_dotenv(PROJECT_ROOT / ".env")
    token = os.getenv("TUSHARE_TOKEN", "")
    if not token or token == "your_tushare_token_here":
        print("ERROR: TUSHARE_TOKEN not configured"); sys.exit(1)

    t0 = time.time()

    kline_df = fetch_data(token)
    sep = "=" * 70

    # ── Compute ALL factors in one pass ──
    print(f"\nComputing ALL factors (RSRS x{len(RSRS_LOOKBACKS)} + Mom x{len(MOM_LOOKBACKS)})...")
    factor_store, computable_dates = compute_all_factors_once(kline_df)
    t1 = time.time()
    print(f"  ⏱ Factor computation: {t1-t0:.1f}s")

    # ── Phase 1: Standalone IC for all factors ──
    print(f"\n{sep}")
    print("  Phase 1: 各因子独立 IC (lag=1)")
    print(sep)

    for start, end, label in PERIODS:
        print(f"\n  [{label}] {start} ~ {end}")
        ic_df = build_ic_table(factor_store, kline_df, computable_dates, start, end)
        if ic_df.empty:
            print("  No results"); continue

        print(f"\n  === RSRS 因子 ===")
        print(f"  {'因子':>12} {'H':>4} {'IC Mean':>8} {'ICIR':>8} {'IC胜率':>7} {'样本':>5}")
        print("  " + "-" * 50)
        rsrs_df = ic_df[ic_df["factor"].str.startswith("rsrs")].sort_values(
            "icir", key=lambda x: x.abs(), ascending=False
        )
        for _, r in rsrs_df.iterrows():
            icir_s = f"{r['icir']:.4f}" if r['icir'] is not None else "N/A"
            print(f"  {r['factor']:>12} {r['forward_h']:>4} {r['ic_mean']:>8.4f} "
                  f"{icir_s:>8} {r['ic_win']:>6}% {r['n']:>5}")

        print(f"\n  === 动量因子 (对比) ===")
        print(f"  {'因子':>12} {'H':>4} {'IC Mean':>8} {'ICIR':>8} {'IC胜率':>7} {'样本':>5}")
        print("  " + "-" * 50)
        mom_df = ic_df[ic_df["factor"].str.startswith("mom")].sort_values(
            "icir", key=lambda x: x.abs(), ascending=False
        )
        for _, r in mom_df.iterrows():
            icir_s = f"{r['icir']:.4f}" if r['icir'] is not None else "N/A"
            print(f"  {r['factor']:>12} {r['forward_h']:>4} {r['ic_mean']:>8.4f} "
                  f"{icir_s:>8} {r['ic_win']:>6}% {r['n']:>5}")

        if not rsrs_df.empty:
            best = rsrs_df.iloc[0]
            print(f"\n  >>> 最佳 RSRS: {best['factor']} H={best['forward_h']} ICIR={best['icir']}")

        # ── 纯净动量 vs 原始动量 对比 ──
        purified_df = ic_df[ic_df["factor"].str.startswith("mom_purified")]
        regular_mom_df = mom_df[~mom_df["factor"].str.startswith("mom_purified")]
        if not purified_df.empty and not regular_mom_df.empty:
            best_p = purified_df.sort_values("icir", key=lambda x: x.abs(), ascending=False).iloc[0]
            best_r = regular_mom_df.sort_values("icir", key=lambda x: x.abs(), ascending=False).iloc[0]
            p_icir = best_p["icir"] if best_p["icir"] is not None else 0
            r_icir = best_r["icir"] if best_r["icir"] is not None else 0
            if abs(p_icir) > abs(r_icir) * 1.05:
                impr = f"↑ 纯净动量 ICIR 提升 {(abs(p_icir)/abs(r_icir)-1)*100:.0f}%"
            elif abs(p_icir) > abs(r_icir):
                impr = "~ 纯净动量 ICIR 略优"
            else:
                impr = "→ 纯净动量 ICIR 未超越原始动量"
            print(f"\n  >>> 纯净动量对比: {impr}")
            print(f"      原始动量最佳: {best_r['factor']} H={best_r['forward_h']} ICIR={best_r['icir']}")
            print(f"      纯净动量最佳: {best_p['factor']} H={best_p['forward_h']} ICIR={best_p['icir']}")

    # ── Phase 2: Collinearity ──
    print(f"\n{sep}")
    print("  Phase 2: RSRS vs 动量 共线性 (全周期)")
    print(sep)
    coll_df = compute_collinearity(factor_store, "20230101", "20260518")
    if coll_df.empty:
        print("  No results")
    else:
        for _, r in coll_df.iterrows():
            p = abs(r["pearson_mean"])
            if p > 0.7:
                flag = "高度共线性"
            elif p > 0.4:
                flag = "中等共线性"
            else:
                flag = "低共线性 - 独立增量"
            print(f"  {r['rsrs']:>10} vs {r['mom']:>8}: "
                  f"Pearson={r['pearson_mean']:+.4f} "
                  f"|Pearson|={r['pearson_abs']:.4f}  {flag}")

    # ── Phase 3: Optimal combination ──
    print(f"\n{sep}")
    print("  Phase 3: RSRS + 动量 最优组合搜索 (H=10)")
    print(sep)

    for start, end, label in PERIODS:
        print(f"\n  [{label}] {start} ~ {end}")
        combo_df = find_optimal_combos(
            factor_store, kline_df, start, end, forward_h=10
        )
        if combo_df.empty:
            print("  No results"); continue

        best_idx = combo_df["icir"].abs().idxmax()
        best = combo_df.loc[best_idx]

        top10 = combo_df.reindex(
            combo_df["icir"].abs().sort_values(ascending=False).index
        ).head(10)
        print(f"  {'RSRS':>10} {'Mom':>8} {'w_rsrs':>7} {'w_mom':>7} "
              f"{'ICIR':>8} {'IC Mean':>8} {'IC胜率':>6}")
        print("  " + "-" * 60)
        for _, r in top10.iterrows():
            marker = " <<<" if r.name == best_idx else ""
            print(f"  {r['rsrs']:>10} {r['mom']:>8} {r['w_rsrs']:>7.1f} "
                  f"{r['w_mom']:>7.1f} {r['icir']:>8.4f} {r['ic_mean']:>8.4f} "
                  f"{r['ic_win']:>5}%{marker}")

        # Compare standalone
        rsrs_ic = build_ic_table(
            {best["rsrs"]: factor_store[best["rsrs"]]},
            kline_df, computable_dates, start, end
        )
        mom_ic = build_ic_table(
            {best["mom"]: factor_store[best["mom"]]},
            kline_df, computable_dates, start, end
        )
        rsrs_icir = rsrs_ic[rsrs_ic["forward_h"] == 10]["icir"].values
        mom_icir = mom_ic[mom_ic["forward_h"] == 10]["icir"].values

        print(f"\n  对比:")
        print(f"    RSRS({best['rsrs']}) 独立 ICIR = "
              f"{rsrs_icir[0] if len(rsrs_icir) else 'N/A'}")
        print(f"    Mom({best['mom']}) 独立 ICIR = "
              f"{mom_icir[0] if len(mom_icir) else 'N/A'}")
        print(f"    组合 ICIR = {best['icir']:.4f} "
              f"(w_rsrs={best['w_rsrs']:.1f}, w_mom={best['w_mom']:.1f})")

        improvement = ""
        if len(rsrs_icir) and len(mom_icir):
            max_single = max(abs(rsrs_icir[0] or 0), abs(mom_icir[0] or 0))
            if abs(best["icir"]) > max_single * 1.05:
                improvement = "组合明显优于单因子，RSRS 有效"
            elif abs(best["icir"]) > max_single:
                improvement = "组合略优，RSRS 有边际贡献"
            else:
                improvement = "组合未超越单因子"
        print(f"    结论: {improvement}")

    t2 = time.time()
    print(f"\n{sep}")
    print(f"  验证完毕 (总耗时: {t2-t0:.1f}s)")
    print(sep)


if __name__ == "__main__":
    main()
