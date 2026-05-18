"""
IC 前视偏差验证脚本
==================
对比两种 IC 计算方式：
  A) 原始方式：T 日因子 → T 到 T+H 收益（有前视偏差）
  B) 严格方式：T-1 日因子 → T 到 T+H 收益（无前视偏差）

用 Tushare 历史数据独立计算，验证因子真实有效性。
"""
import sys
import math
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
import tushare as ts

START_DATE = "20250101"
END_DATE = "20260518"
DATA_START = "20240601"
FORWARD_DAYS = 10  # H=10 (short preset best)

SECTOR_ETF = {
    "512480.SH": "半导体ETF", "515030.SH": "新能源车ETF", "512010.SH": "医药ETF",
    "512800.SH": "银行ETF", "512880.SH": "证券ETF", "159928.SZ": "消费ETF",
    "515880.SH": "通信ETF", "159206.SZ": "卫星ETF", "512400.SH": "有色ETF",
    "562500.SH": "机器人ETF", "159870.SZ": "化工ETF", "561360.SH": "石油ETF",
    "518880.SH": "黄金ETF", "159611.SZ": "电力ETF", "512980.SH": "传媒ETF",
}

FLOW_LOOKBACK = 10
MOM_LOOKBACK = 20
MIN_ETF = 8


def fetch_data(token):
    ts.set_token(token)
    pro = ts.pro_api()

    print(f"Fetching data ({DATA_START} ~ {END_DATE})...")
    kline_parts, share_parts = [], []
    for code in SECTOR_ETF:
        for _ in range(3):
            try:
                df = pro.fund_daily(ts_code=code, start_date=DATA_START, end_date=END_DATE)
                if df is not None and len(df) > 0:
                    kline_parts.append(df)
                break
            except Exception:
                time.sleep(1)
        time.sleep(0.3)
        for _ in range(3):
            try:
                df = pro.fund_share(ts_code=code, start_date=DATA_START, end_date=END_DATE)
                if df is not None and len(df) > 0:
                    share_parts.append(df)
                break
            except Exception:
                time.sleep(1)
        time.sleep(0.3)

    kline_df = pd.concat(kline_parts, ignore_index=True).sort_values(["ts_code", "trade_date"]).reset_index(drop=True)
    share_df = pd.concat(share_parts, ignore_index=True).sort_values(["ts_code", "trade_date"]).reset_index(drop=True)
    print(f"  Kline: {len(kline_df)} rows | Share: {len(share_df)} rows")
    return kline_df, share_df


def _compute_flow_ewma(shares, lookback, halflife=3):
    if len(shares) < lookback + 1:
        return np.nan
    recent = shares.iloc[-lookback:].astype(float).values
    if len(recent) < 2:
        return np.nan
    x = np.arange(len(recent), dtype=float)
    y = recent / recent.mean()
    if np.isnan(y).any():
        return np.nan
    weights = np.exp(-np.log(2) * (len(recent) - 1 - x) / halflife)
    weights /= weights.sum()
    x_w = x - (x * weights).sum()
    y_w = y - (y * weights).sum()
    denom = (weights * x_w * x_w).sum()
    if denom == 0:
        return np.nan
    slope = (weights * x_w * y_w).sum() / denom
    return float(np.tanh(slope * 3))


def _compute_mom(closes, lookback, vol_window=60):
    if len(closes) < lookback + 1:
        return np.nan
    close_today = float(closes.iloc[-1])
    close_past = float(closes.iloc[-(lookback + 1)])
    if close_past == 0:
        return np.nan
    mom = close_today / close_past - 1
    if len(closes) >= vol_window + 1:
        daily_ret = closes.astype(float).pct_change().dropna().tail(vol_window)
        if len(daily_ret) >= 30:
            vol = daily_ret.std()
            if vol > 0:
                return float(mom / vol)
    return float(mom)


def _cross_sectional_zscore(values):
    p10 = values.quantile(0.10)
    p90 = values.quantile(0.90)
    clipped = values.clip(p10, p90)
    std = clipped.std()
    if std == 0 or pd.isna(std):
        return pd.Series(0.0, index=values.index)
    return (clipped - clipped.mean()) / std


def compute_all_factors(kline_df, share_df):
    """Compute factor for every date"""
    lookback_needed = max(FLOW_LOOKBACK, MOM_LOOKBACK) + 1
    all_dates = sorted(kline_df["trade_date"].unique())
    etf_codes = list(kline_df["ts_code"].unique())

    # Build per-ETF sorted data
    kline_sorted = {}
    share_sorted = {}
    for code in etf_codes:
        kline_sorted[code] = kline_df[kline_df["ts_code"] == code].sort_values("trade_date")
        share_sorted[code] = share_df[share_df["ts_code"] == code].sort_values("trade_date") if not share_df.empty else pd.DataFrame()

    computable_dates = []
    for d in all_dates:
        max_len = max(len(kline_sorted[c][kline_sorted[c]["trade_date"] <= d]) for c in etf_codes if c in kline_sorted)
        if max_len >= lookback_needed:
            computable_dates.append(d)

    print(f"  Computing factors for {len(computable_dates)} dates...")
    factor_rows = []
    for i, d in enumerate(computable_dates):
        day_rows = []
        for code in etf_codes:
            kl = kline_sorted[code]
            kl = kl[kl["trade_date"] <= d]
            sh = share_sorted.get(code, pd.DataFrame())
            sh = sh[sh["trade_date"] <= d] if not sh.empty else sh

            if len(kl) < lookback_needed or len(sh) < FLOW_LOOKBACK:
                continue

            flow = _compute_flow_ewma(sh["fd_share"], FLOW_LOOKBACK)
            mom = _compute_mom(kl["close"], MOM_LOOKBACK)
            if pd.isna(flow) or pd.isna(mom):
                continue

            day_rows.append({"etf_code": code, "trade_date": d, "flow": flow, "mom": mom})

        if len(day_rows) < 2:
            continue

        day_df = pd.DataFrame(day_rows)
        day_df["z_flow"] = _cross_sectional_zscore(day_df["flow"]).values
        day_df["z_mom"] = _cross_sectional_zscore(day_df["mom"]).values
        day_df["factor"] = 0.3 * day_df["z_flow"] + 0.7 * day_df["z_mom"]
        factor_rows.extend(day_df.to_dict("records"))

        if (i + 1) % 100 == 0:
            print(f"    {i+1}/{len(computable_dates)}")

    return pd.DataFrame(factor_rows)


def compute_ic(factor_df, kline_df, lag=0):
    """Compute IC series.

    lag=0: T日因子 → T到T+H收益 (原始方式，有前视偏差)
    lag=1: T-1日因子 → T到T+H收益 (严格方式，无前视偏差)
    """
    # Build price lookup
    price_lookup = {}
    for _, row in kline_df.iterrows():
        price_lookup[(row["ts_code"], row["trade_date"])] = float(row["close"])

    all_dates = sorted(kline_df["trade_date"].unique())
    date_idx = {d: i for i, d in enumerate(all_dates)}

    factor_dates = sorted(factor_df["trade_date"].unique())
    factor_by_date = {d: factor_df[factor_df["trade_date"] == d] for d in factor_dates}

    h = FORWARD_DAYS
    ic_values = []

    for t in all_dates:
        if t not in date_idx:
            continue
        idx = date_idx[t]
        if idx + h >= len(all_dates):
            continue

        fwd_date = all_dates[idx + h]

        # Determine which factor date to use
        if lag == 0:
            factor_date = t
        else:
            # Use factor from lag days before t
            if idx - lag < 0:
                continue
            factor_date = all_dates[idx - lag]

        if factor_date not in factor_by_date:
            continue

        day_factors = factor_by_date[factor_date]

        factors_list = []
        returns_list = []
        for _, row in day_factors.iterrows():
            code = row["etf_code"]
            close_t = price_lookup.get((code, t))
            close_fwd = price_lookup.get((code, fwd_date))

            if close_t and close_fwd and close_t > 0 and pd.notna(row["factor"]):
                factors_list.append(row["factor"])
                returns_list.append(close_fwd / close_t - 1)

        if len(factors_list) < MIN_ETF:
            continue

        corr, _ = scipy_stats.spearmanr(factors_list, returns_list)
        if not np.isnan(corr):
            ic_values.append(corr)

    ic_series = pd.Series(ic_values)
    n = len(ic_series)
    if n == 0:
        return {"ic_mean": None, "icir": None, "ic_win_rate": None, "n": 0}

    ic_mean = ic_series.mean()
    ic_std = ic_series.std()
    icir = ic_mean / ic_std if ic_std > 0 else None
    ic_win_rate = (ic_series > 0).mean()

    return {
        "ic_mean": ic_mean,
        "icir": icir,
        "ic_win_rate": ic_win_rate,
        "n": n,
    }


def compute_ic_with_h(factor_df, kline_df, lag=0, forward_h=10):
    """Compute IC with a specific forward period H."""
    price_lookup = {}
    for _, row in kline_df.iterrows():
        price_lookup[(row["ts_code"], row["trade_date"])] = float(row["close"])

    all_dates = sorted(kline_df["trade_date"].unique())
    date_idx = {d: i for i, d in enumerate(all_dates)}

    factor_dates = sorted(factor_df["trade_date"].unique())
    factor_by_date = {d: factor_df[factor_df["trade_date"] == d] for d in factor_dates}

    ic_values = []
    for t in all_dates:
        if t not in date_idx:
            continue
        idx = date_idx[t]
        if idx + forward_h >= len(all_dates):
            continue

        fwd_date = all_dates[idx + forward_h]

        if lag == 0:
            factor_date = t
        else:
            if idx - lag < 0:
                continue
            factor_date = all_dates[idx - lag]

        if factor_date not in factor_by_date:
            continue

        day_factors = factor_by_date[factor_date]

        factors_list = []
        returns_list = []
        for _, row in day_factors.iterrows():
            code = row["etf_code"]
            close_t = price_lookup.get((code, t))
            close_fwd = price_lookup.get((code, fwd_date))

            if close_t and close_fwd and close_t > 0 and pd.notna(row["factor"]):
                factors_list.append(row["factor"])
                returns_list.append(close_fwd / close_t - 1)

        if len(factors_list) < MIN_ETF:
            continue

        corr, _ = scipy_stats.spearmanr(factors_list, returns_list)
        if not np.isnan(corr):
            ic_values.append(corr)

    ic_series = pd.Series(ic_values)
    n = len(ic_series)
    if n == 0:
        return {"ic_mean": None, "icir": None, "ic_win_rate": None, "n": 0}

    ic_mean = ic_series.mean()
    ic_std = ic_series.std()
    icir = ic_mean / ic_std if ic_std > 0 else None
    ic_win_rate = (ic_series > 0).mean()

    return {"ic_mean": ic_mean, "icir": icir, "ic_win_rate": ic_win_rate, "n": n}


def main():
    from dotenv import load_dotenv
    import os

    load_dotenv(PROJECT_ROOT / ".env")
    token = os.getenv("TUSHARE_TOKEN", "")
    if not token or token == "your_tushare_token_here":
        print("ERROR: TUSHARE_TOKEN not configured")
        sys.exit(1)

    print(f"IC Verification: {START_DATE} ~ {END_DATE}, H={FORWARD_DAYS}")
    print()

    kline_df, share_df = fetch_data(token)
    factor_df = compute_all_factors(kline_df, share_df)
    print(f"  Total factor rows: {len(factor_df)}")
    print()

    # Filter to target period
    factor_df = factor_df[(factor_df["trade_date"] >= START_DATE) & (factor_df["trade_date"] <= END_DATE)]
    print(f"  Factor rows in target period: {len(factor_df)}")
    print()

    sep = "=" * 70

    # Test multiple lag values
    results = {}
    for lag in [0, 1, 2]:
        label = f"lag={lag}"
        desc = {
            0: "T日因子 → T到T+H收益 (原始，有前视偏差)",
            1: "T-1日因子 → T到T+H收益 (严格，无前视偏差)",
            2: "T-2日因子 → T到T+H收益 (更保守)",
        }
        print(f"Computing IC ({desc[lag]})...")
        r = compute_ic(factor_df, kline_df, lag=lag)
        results[lag] = r
        print(f"  Done: {r['n']} IC observations")

    # Print comparison
    print()
    print(sep)
    print("  IC 前视偏差验证报告")
    print(f"  回测期: {START_DATE} ~ {END_DATE} | H={FORWARD_DAYS}天")
    print(sep)
    print()
    print(f"  {'方式':<20} {'IC Mean':>10} {'ICIR':>10} {'IC胜率':>10} {'样本数':>8}")
    print("  " + "-" * 60)

    for lag in [0, 1, 2]:
        r = results[lag]
        label_map = {0: "原始(lag=0)", 1: "严格(lag=1)", 2: "保守(lag=2)"}
        ic_m = f"{r['ic_mean']:.4f}" if r['ic_mean'] is not None else "N/A"
        icir = f"{r['icir']:.4f}" if r['icir'] is not None else "N/A"
        ic_wr = f"{r['ic_win_rate']*100:.1f}%" if r['ic_win_rate'] is not None else "N/A"
        print(f"  {label_map[lag]:<20} {ic_m:>10} {icir:>10} {ic_wr:>10} {r['n']:>8}")

    # Calculate decay
    if results[0]['icir'] and results[1]['icir']:
        decay_pct = (1 - results[1]['icir'] / results[0]['icir']) * 100
        print()
        if decay_pct > 50:
            print(f"  >>> ICIR 衰减: {decay_pct:.1f}% — 因子信号前视偏差严重，实际有效性存疑")
        elif decay_pct > 30:
            print(f"  >>> ICIR 衰减: {decay_pct:.1f}% — 有一定衰减，但因子仍有参考价值")
        elif decay_pct > 10:
            print(f"  >>> ICIR 衰减: {decay_pct:.1f}% — 衰减较小，因子有效性基本可靠")
        else:
            print(f"  >>> ICIR 衰减: {decay_pct:.1f}% — 几乎无衰减，因子有效性确认")

    # Also test different forward periods with lag=1
    print()
    print(f"  不同预测周期 IC (严格方式 lag=1)")
    print(f"  {'周期H':>8} {'IC Mean':>10} {'ICIR':>10} {'IC胜率':>10} {'样本数':>8}")
    print("  " + "-" * 50)

    for h in [1, 5, 10, 20]:
        r = compute_ic_with_h(factor_df, kline_df, lag=1, forward_h=h)
        ic_m = f"{r['ic_mean']:.4f}" if r['ic_mean'] is not None else "N/A"
        icir = f"{r['icir']:.4f}" if r['icir'] is not None else "N/A"
        ic_wr = f"{r['ic_win_rate']*100:.1f}%" if r['ic_win_rate'] is not None else "N/A"
        print(f"  {f'H={h}':>8} {ic_m:>10} {icir:>10} {ic_wr:>10} {r['n']:>8}")

    print()
    print(sep)


if __name__ == "__main__":
    main()
