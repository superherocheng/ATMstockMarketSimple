"""Compare three-factor vs four-factor — use best-populated date."""
import os, sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from src.core.db_manager_postgresql import init_db_manager, get_conn, close_db_manager
from sqlalchemy import text
from config.config import SECTOR_ETF

db_url = os.getenv("DATABASE_URL", "")
init_db_manager(db_url)
conn = get_conn()

try:
    # Find the date with MOST complete data (max ETFs with z_quality)
    best_date = conn.execute(text("""
        SELECT trade_date, COUNT(*) as cnt
        FROM factor_daily WHERE preset_id='short' AND z_quality IS NOT NULL
        GROUP BY trade_date ORDER BY cnt DESC, trade_date DESC LIMIT 1
    """)).fetchone()
    if not best_date:
        print("No data found")
        sys.exit(0)
    target_date = best_date[0]
    print(f"Using date: {target_date} ({best_date[1]} ETFs)\n")

    rows = conn.execute(text("""
        SELECT etf_code, z_rsrs, z_flow, z_mom, z_quality, factor, quadrant
        FROM factor_daily
        WHERE preset_id = 'short' AND trade_date = :d
        ORDER BY factor DESC
    """), {"d": target_date}).fetchall()

    records = []
    for r in rows:
        records.append({
            "code": r[0],
            "name": SECTOR_ETF.get(r[0], r[0]),
            "z_rsrs": float(r[1]) if r[1] else 0,
            "z_flow": float(r[2]) if r[2] else 0,
            "z_mom": float(r[3]) if r[3] else 0,
            "z_quality": float(r[4]) if r[4] else 0,
            "factor_4f": float(r[5]) if r[5] else 0,
            "quadrant": int(r[6]) if r[6] else 0,
        })
    df = pd.DataFrame(records)
    df["factor_3f"] = (df["z_rsrs"] + df["z_flow"] + df["z_mom"]) / 3.0

    print("=" * 65)
    print("  四因子 vs 三因子 — 对比分析报告")
    print(f"  基准日期: {target_date}  |  ETF数量: {len(df)}")
    print("=" * 65)

    print("\n── 1. 因子间相关性矩阵 ──")
    factor_cols = ["z_rsrs", "z_flow", "z_mom", "z_quality"]
    corr_matrix = df[factor_cols].corr()
    for c1 in factor_cols:
        for c2 in factor_cols:
            if c1 < c2:
                corr_val = corr_matrix.loc[c1, c2]
                strength = "偏高" if abs(corr_val) > 0.7 else ("中等" if abs(corr_val) > 0.3 else "较低")
                print(f"  {c1:14s} vs {c2:14s}: {corr_val:+.4f}  ({strength})")

    avg_corr = corr_matrix.loc["z_quality", ["z_rsrs", "z_flow", "z_mom"]].abs().mean()
    print(f"\n  → F_Quality vs 其他三因子 | 平均 |{avg_corr:.4f}")
    if avg_corr < 0.3:
        print(f"  ✅ 强正交性 — F_Quality 提供独立信息增量")
    else:
        print(f"  ⚡ 中等相关 — 部分信息重叠，仍需独立计算")

    print("\n── 2. 排名变化 ──")
    df["rank_3f"] = df["factor_3f"].rank(ascending=False)
    df["rank_4f"] = df["factor_4f"].rank(ascending=False)
    df["rank_delta"] = df["rank_3f"] - df["rank_4f"]
    df["abs_delta"] = df["rank_delta"].abs()

    n_changed = (df["abs_delta"] > 0).sum()
    avg_delta = df["abs_delta"].mean()
    max_delta = df["abs_delta"].max()
    print(f"  排名变化 ETF: {n_changed}/{len(df)}  |  平均变动 {avg_delta:.1f} 位  |  最大变动 {max_delta:.0f} 位")

    print("\n  全量排名对比:")
    print(f"  {'ETF':12s} {'Q':3s} {'3F分':8s} {'R3':4s} {'→':3s} {'4F分':8s} {'R4':4s} {'Z_Qual':8s}")
    print(f"  {'-'*12} {'-'*3} {'-'*8} {'-'*4} {'-'*3} {'-'*8} {'-'*4} {'-'*8}")
    df_sorted = df.sort_values("rank_4f")
    for _, r2 in df_sorted.iterrows():
        d = int(r2["rank_delta"])
        arrow = "↑" if d > 0 else ("↓" if d < 0 else "━")
        print(f"  {r2['name']:10s}  {int(r2['quadrant']):<3d} {r2['factor_3f']:+.4f} {int(r2['rank_3f']):<4d} {arrow}{abs(d):>2s} {r2['factor_4f']:+.4f} {int(r2['rank_4f']):<4d} {r2['z_quality']:+.4f}")

    print("\n── 3. 区分度分析 ──")
    std_3f = df["factor_3f"].std()
    std_4f = df["factor_4f"].std()
    range_3f = df["factor_3f"].max() - df["factor_3f"].min()
    range_4f = df["factor_4f"].max() - df["factor_4f"].min()
    spread_change = (std_4f / std_3f - 1) * 100
    print(f"  3F 标准差: {std_3f:.4f}  |  4F 标准差: {std_4f:.4f}  |  变化: {spread_change:+.1f}%")
    if abs(spread_change) > 15:
        print(f"  {'✅ 区分度提升' if spread_change > 0 else '⚠️ 区分度下降'}")

    print(f"\n── 4. 综合得分相关性 ──")
    score_corr = df["factor_3f"].corr(df["factor_4f"])
    print(f"  Pearson r(3F得分, 4F得分) = {score_corr:.4f}")
    qual_weight = 0.25
    expected_r = (1 - qual_weight) / np.sqrt((1 - qual_weight)**2 + qual_weight**2 * 1 + 2 * (1 - qual_weight) * qual_weight * avg_corr)
    print(f"  理论期望 r ≈ {expected_r:.4f}（假设权重{qual_weight}，平均相关{avg_corr:.3f}）")
    if score_corr < 0.9:
        print(f"  ⚡ F_Quality 实质性改变了排名秩序")
    else:
        print(f"  → 排名基本一致")

finally:
    conn.close()
close_db_manager()
