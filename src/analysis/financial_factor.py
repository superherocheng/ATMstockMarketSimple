"""
Financial Quality Factor Module (F_Quality)
=============================================

Composites three sub-factors from constituent stock financial data:
1. F_ROE — Consensus/projected ROE (circ_mv weighted, industry aggregate)
2. F_PB_Pct — Inverse PB_TTM 5-year percentile (low → high score)
3. F_Earnings_YoY — Single-quarter net profit YoY growth (Z-scored)

All sub-factors undergo cross-sectional Z-scoring before equal-weight synthesis.
Commodity ETFs (黄金ETF, 石油ETF) are assigned the cross-sectional median.

Data sources (all from Tushare via existing DB tables):
- stock_fina_indicator: roe, netprofit_yoy
- stock_daily_basic: pb, circ_mv
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sqlalchemy import text

from config.config import SECTOR_ETF

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────
#  成分股映射 (ETF → 代表性成分股)
# ────────────────────────────────────────────────────────────

def _stock_code_to_tushare(code: str) -> str:
    """将 6 位数字代码转为 Tushare 格式（含交易所后缀）。"""
    code = code.strip()
    if len(code) != 6:
        raise ValueError(f"Invalid stock code: {code}")
    prefix = code[0]
    # 87xxxx → Beijing Stock Exchange (BSE)
    if code.startswith("87"):
        return f"{code}.BJ"
    if prefix in ("6", "9"):
        return f"{code}.SH"
    elif prefix in ("0", "3", "2"):
        return f"{code}.SZ"
    else:
        logger.warning(f"Unknown market prefix for {code}, defaulting to .SH")
        return f"{code}.SH"


SECTOR_CONSTITUENTS: Dict[str, List[str]] = {
    "512480.SH": [  # 半导体ETF
        _stock_code_to_tushare(c) for c in [
            "688981", "688012", "002371", "600584", "603986",
            "603501", "688041", "688256", "688008", "301269",
        ]
    ],
    "515030.SH": [  # 新能源车ETF
        _stock_code_to_tushare(c) for c in [
            "002594", "300750", "300014", "601633", "002466",
            "002460", "603799", "002812", "300450", "002709",
        ]
    ],
    "512010.SH": [  # 医药ETF
        _stock_code_to_tushare(c) for c in [
            "600276", "603259", "688235", "300015", "300122",
            "300760", "688271", "600436", "000538", "002821",
        ]
    ],
    "512800.SH": [  # 银行ETF
        _stock_code_to_tushare(c) for c in [
            "601398", "601939", "601288", "601988", "600036",
            "601166", "000001", "601658", "601328", "002142",
        ]
    ],
    "512880.SH": [  # 证券ETF
        _stock_code_to_tushare(c) for c in [
            "600030", "300059", "601688", "601211", "600999",
            "000166", "000776", "601995", "300033", "300803",
        ]
    ],
    "159928.SZ": [  # 消费ETF
        _stock_code_to_tushare(c) for c in [
            "600519", "000858", "600887", "603288", "000333",
            "000568", "600809", "000651", "000895", "600690",
        ]
    ],
    "515880.SH": [  # 通信ETF
        _stock_code_to_tushare(c) for c in [
            "600941", "601728", "600050", "000063", "300308",
            "300394", "300502", "300628", "600487", "002281",
        ]
    ],
    "159206.SZ": [  # 卫星ETF
        _stock_code_to_tushare(c) for c in [
            "600118", "600879", "002179", "600893", "600760",
            "000768", "002025", "688311", "002151", "002829",
        ]
    ],
    "512400.SH": [  # 有色ETF
        _stock_code_to_tushare(c) for c in [
            "601899", "601600", "603993", "002466", "002460",
            "600219", "601168", "000630", "600111", "600547",
        ]
    ],
    "562500.SH": [  # 机器人ETF
        _stock_code_to_tushare(c) for c in [
            "300124", "688017", "002747", "300607", "002472",
            "300024", "603728", "688320", "601100", "873593",
        ]
    ],
    "159870.SZ": [  # 化工ETF
        _stock_code_to_tushare(c) for c in [
            "600309", "600346", "002493", "600989", "002601",
            "600426", "603260", "601233", "002648", "000703",
        ]
    ],
    "561360.SH": [  # 石油ETF — 商品类，无成分股
    ],
    "159611.SZ": [  # 电力ETF
        _stock_code_to_tushare(c) for c in [
            "600900", "601985", "600905", "600011", "600795",
            "600886", "600025", "003816", "600023", "001289",
        ]
    ],
    "512980.SH": [  # 传媒ETF
        _stock_code_to_tushare(c) for c in [
            "002027", "300413", "002555", "300418", "002624",
            "300251", "002517", "601921", "601928", "600373",
        ]
    ],
    "512690.SH": [  # 白酒ETF
        _stock_code_to_tushare(c) for c in [
            "600519", "000858", "000568", "600809", "000596",
            "603369", "603198", "600779", "600559", "002304",
        ]
    ],
    "515210.SH": [  # 钢铁ETF
        _stock_code_to_tushare(c) for c in [
            "600019", "000932", "600010", "000898", "600282",
            "000708", "600808", "000761", "600581", "002110",
        ]
    ],
    "515220.SH": [  # 煤炭ETF
        _stock_code_to_tushare(c) for c in [
            "601088", "600188", "601225", "600985", "000983",
            "600546", "600348", "601898", "600395", "600123",
        ]
    ],
}

# 商品类 ETF — 不计算财务因子，赋值为截面中位数
COMMODITY_ETF_CODES = {"561360.SH", "518880.SH"}  # 石油ETF, 黄金ETF


# ────────────────────────────────────────────────────────────
#  工具函数
# ────────────────────────────────────────────────────────────

def _get_conn():
    from src.core.db_manager_postgresql import get_conn
    return get_conn()


# 复用 factor_engine 的 Z-Score 实现，避免重复
from src.analysis.factor_engine import _cross_sectional_zscore


# ────────────────────────────────────────────────────────────
#  子因子: F_ROE（预期ROE）
# ────────────────────────────────────────────────────────────

def _fetch_latest_roe(stock_codes: list, conn) -> dict:
    """获取每只成分股最新 ROE。"""
    if not stock_codes:
        return {}
    placeholders = ",".join(f":c{i}" for i in range(len(stock_codes)))
    params = {f"c{i}": c for i, c in enumerate(stock_codes)}
    rows = conn.execute(text(f"""
        SELECT DISTINCT ON (ts_code) ts_code, roe
        FROM stock_fina_indicator
        WHERE ts_code IN ({placeholders})
          AND roe IS NOT NULL
        ORDER BY ts_code, end_date DESC
    """), params).fetchall()
    return {r[0]: float(r[1]) for r in rows if r[1] is not None}


# ────────────────────────────────────────────────────────────
#  子因子: F_PB_Pct（PB估值分位反向指标）
# ────────────────────────────────────────────────────────────

def _fetch_pb_data(stock_codes: list, conn) -> dict:
    """获取 5 年 PB 历史数据。

    Returns dict {stock_code: {"latest_pb": float, "pb_5yr": list[float]}}.
    """
    if not stock_codes:
        return {}
    five_years_ago = (datetime.now() - timedelta(days=5 * 365)).strftime("%Y%m%d")
    placeholders = ",".join(f":c{i}" for i in range(len(stock_codes)))
    params = {f"c{i}": c for i, c in enumerate(stock_codes)}
    params["start"] = five_years_ago
    rows = conn.execute(text(f"""
        SELECT ts_code, trade_date, pb
        FROM stock_daily_basic
        WHERE ts_code IN ({placeholders})
          AND trade_date >= :start
          AND pb IS NOT NULL
          AND pb > 0
        ORDER BY ts_code, trade_date DESC
    """), params).fetchall()
    result = {}
    for r in rows:
        code = r[0]
        pb_val = float(r[2]) if r[2] is not None else None
        if pb_val is None or pb_val <= 0:
            continue
        if code not in result:
            result[code] = {"latest_pb": pb_val, "pb_5yr": []}
        result[code]["pb_5yr"].append(pb_val)
    for code, data in result.items():
        if data["pb_5yr"]:
            data["latest_pb"] = data["pb_5yr"][0]
    return result


# ────────────────────────────────────────────────────────────
#  子因子: F_Earnings_YoY（盈利加速度）
# ────────────────────────────────────────────────────────────

def _fetch_latest_netprofit_yoy(stock_codes: list, conn) -> dict:
    """获取每只成分股最新季度归母净利润同比增长率。"""
    if not stock_codes:
        return {}
    placeholders = ",".join(f":c{i}" for i in range(len(stock_codes)))
    params = {f"c{i}": c for i, c in enumerate(stock_codes)}
    rows = conn.execute(text(f"""
        SELECT DISTINCT ON (ts_code) ts_code, netprofit_yoy
        FROM stock_fina_indicator
        WHERE ts_code IN ({placeholders})
          AND netprofit_yoy IS NOT NULL
        ORDER BY ts_code, end_date DESC
    """), params).fetchall()
    return {r[0]: float(r[1]) for r in rows if r[1] is not None}


# ────────────────────────────────────────────────────────────
#  权重: 流通市值
# ────────────────────────────────────────────────────────────

def _fetch_latest_circ_mv(stock_codes: list, conn) -> dict:
    """获取每只成分股最新流通市值。"""
    if not stock_codes:
        return {}
    placeholders = ",".join(f":c{i}" for i in range(len(stock_codes)))
    params = {f"c{i}": c for i, c in enumerate(stock_codes)}
    rows = conn.execute(text(f"""
        SELECT DISTINCT ON (ts_code) ts_code, circ_mv
        FROM stock_daily_basic
        WHERE ts_code IN ({placeholders})
          AND circ_mv IS NOT NULL
          AND circ_mv > 0
        ORDER BY ts_code, trade_date DESC
    """), params).fetchall()
    return {r[0]: float(r[1]) for r in rows if r[1] is not None}


# ────────────────────────────────────────────────────────────
#  行业聚合
# ────────────────────────────────────────────────────────────

def _aggregate_by_sector(
    constituent_codes: List[str],
    factor_dict: Dict[str, float],
    weight_dict: Optional[Dict[str, float]] = None,
) -> Optional[float]:
    """将成分股因子值聚合成行业层面因子值。

    优先使用流通市值加权，否则等权。
    有效成分股少于 3 只时返回 None。
    """
    valid = {code: val for code, val in factor_dict.items()
             if val is not None and code in constituent_codes}
    if len(valid) < 3:
        return None
    if weight_dict:
        weights = {}
        total_w = 0.0
        for code in valid:
            w = weight_dict.get(code, 1.0)
            if w is not None and w > 0:
                weights[code] = w
                total_w += w
        if total_w > 0:
            return sum(valid[code] * weights.get(code, 1.0) for code in valid) / total_w
    return float(np.mean(list(valid.values())))


# ────────────────────────────────────────────────────────────
#  主计算函数
# ────────────────────────────────────────────────────────────

def _build_overlap_weights(stock_codes: set, weight_dict: dict) -> dict:
    """Detect stocks appearing in multiple sector ETFs and reduce their weight.

    If a stock appears in N sectors, its circ_mv is divided by N in each sector
    to avoid double-counting. This prevents overlapping constituents (e.g.
    天齐锂业 in both 有色ETF and 新能源车ETF) from unfairly biasing results.

    Returns adjusted weight_dict with overlap-penalized weights.
    """
    # Count how many sectors each stock belongs to
    stock_sector_count = {}
    for etf_code in SECTOR_CONSTITUENTS:
        if etf_code in COMMODITY_ETF_CODES:
            continue
        for stock in SECTOR_CONSTITUENTS.get(etf_code, []):
            stock_sector_count[stock] = stock_sector_count.get(stock, 0) + 1

    overlapped = {s: c for s, c in stock_sector_count.items() if c > 1}
    if not overlapped:
        return weight_dict

    logger.info(f"Overlap detected: {len(overlapped)} stocks appear in multiple ETFs")
    for s, c in sorted(overlapped.items()):
        raw_w = weight_dict.get(s, np.nan)
        adjusted_w = raw_w / c if raw_w is not None and raw_w > 0 else raw_w
        logger.info(f"  {s}: appears in {c} ETFs, weight {raw_w} -> {adjusted_w}")

    adjusted = dict(weight_dict)
    for s, c in overlapped.items():
        if s in adjusted and adjusted[s] is not None and adjusted[s] > 0:
            adjusted[s] = adjusted[s] / c
    return adjusted


def compute_financial_factors(calc_date: Optional[str] = None) -> dict:
    """计算所有行业 ETF 的财务质量因子。

    1. 获取成分股 ROE / PB / YoY / circ_mv
    2. 重叠成分股检测（跨行业股票权重去重）
    3. 按行业聚合（流通市值加权，重叠股降权）
    4. 计算 PB 历史分位（1 - 分位 → 低PB得高分）
    5. 横截面 Z-Score 标准化三个子因子
    6. 等权合成 F_Quality
    7. 商品类 ETF 赋值为中位数

    Returns:
        dict[etf_code] -> {
            f_roe, f_pb_pct, f_earnings_yoy, f_quality,
            is_commodity, num_constituents, missing_constituents
        }
    """
    from src.core.trading_calendar import now_beijing

    if calc_date is None:
        calc_date = now_beijing().strftime("%Y%m%d")

    logger.info(f"Computing financial quality factors for date={calc_date}")

    conn = _get_conn()
    try:
        # 1. 收集成分股
        all_stock_codes = set()
        etf_constituents = {}
        for etf_code in SECTOR_ETF:
            if etf_code in COMMODITY_ETF_CODES:
                continue
            stocks = SECTOR_CONSTITUENTS.get(etf_code, [])
            if stocks:
                etf_constituents[etf_code] = stocks
                all_stock_codes.update(stocks)

        if not all_stock_codes:
            logger.warning("No constituent stock data available")
            return {}

        stock_list = list(all_stock_codes)
        logger.info(f"Processing {len(stock_list)} stocks across "
                     f"{len(etf_constituents)} sector ETFs")

        # 2. 获取财务数据
        roe_dict = _fetch_latest_roe(stock_list, conn)
        pb_dict = _fetch_pb_data(stock_list, conn)
        earnings_dict = _fetch_latest_netprofit_yoy(stock_list, conn)
        weight_dict = _fetch_latest_circ_mv(stock_list, conn)

        logger.info(
            f"Data loaded: ROE={len(roe_dict)}, PB={len(pb_dict)}, "
            f"EarningsYoY={len(earnings_dict)}, CircMV={len(weight_dict)}"
        )

        # 3. 计算 PB 5年分位
        pb_pct_dict = {}
        for code, data in pb_dict.items():
            pb_5yr = data["pb_5yr"]
            latest_pb = data["latest_pb"]
            if len(pb_5yr) < 20:
                continue
            count_le = sum(1 for v in pb_5yr if v <= latest_pb)
            pct = count_le / len(pb_5yr)
            pb_pct_dict[code] = 1.0 - pct  # 反向：低PB得高分

        # 3b. S2: Overlap weight adjustment for cross-sector stocks
        adjusted_weight_dict = _build_overlap_weights(all_stock_codes, weight_dict)

        # 4. 按行业聚合（使用去重后的权重）
        sector_raw = {}
        for etf_code, stocks in etf_constituents.items():
            f_roe = _aggregate_by_sector(stocks, roe_dict, adjusted_weight_dict)
            f_pb_pct = _aggregate_by_sector(stocks, pb_pct_dict, adjusted_weight_dict)
            f_earnings = _aggregate_by_sector(stocks, earnings_dict, adjusted_weight_dict)
            missing = sum(1 for s in stocks if s not in roe_dict)
            sector_raw[etf_code] = {
                "f_roe_raw": f_roe,
                "f_pb_pct_raw": f_pb_pct,
                "f_earnings_raw": f_earnings,
                "num_constituents": len(stocks),
                "missing_constituents": missing,
            }

        # 5. 横截面标准化
        etf_codes = list(sector_raw.keys())
        roe_series = pd.Series({
            c: sector_raw[c]["f_roe_raw"] for c in etf_codes
            if sector_raw[c]["f_roe_raw"] is not None
        })
        pb_series = pd.Series({
            c: sector_raw[c]["f_pb_pct_raw"] for c in etf_codes
            if sector_raw[c]["f_pb_pct_raw"] is not None
        })
        earn_series = pd.Series({
            c: sector_raw[c]["f_earnings_raw"] for c in etf_codes
            if sector_raw[c]["f_earnings_raw"] is not None
        })

        z_roe = _cross_sectional_zscore(roe_series) if len(roe_series) > 0 else pd.Series(dtype=float)
        z_pb = _cross_sectional_zscore(pb_series) if len(pb_series) > 0 else pd.Series(dtype=float)
        z_earn = _cross_sectional_zscore(earn_series) if len(earn_series) > 0 else pd.Series(dtype=float)

        # 6. 合成 F_Quality（等权）
        composite_values = []
        composite_map = {}
        for code in etf_codes:
            z_vals = []
            if code in z_roe.index and not pd.isna(z_roe.get(code, np.nan)):
                z_vals.append(z_roe[code])
            if code in z_pb.index and not pd.isna(z_pb.get(code, np.nan)):
                z_vals.append(z_pb[code])
            if code in z_earn.index and not pd.isna(z_earn.get(code, np.nan)):
                z_vals.append(z_earn[code])
            if len(z_vals) >= 2:
                composite = float(np.mean(z_vals))
                composite_values.append(composite)
                composite_map[code] = composite
            else:
                composite_map[code] = None

        median_quality = float(np.median([v for v in composite_values if v is not None])) if composite_values else 0.0

        # 7. 构建最终结果
        result = {}
        for code in SECTOR_ETF:
            is_commodity = code in COMMODITY_ETF_CODES
            if is_commodity:
                result[code] = {
                    "f_roe": median_quality,
                    "f_pb_pct": median_quality,
                    "f_earnings_yoy": median_quality,
                    "f_quality": median_quality,
                    "is_commodity": True,
                    "num_constituents": 0,
                    "missing_constituents": 0,
                }
            elif code in sector_raw:
                f_quality = composite_map.get(code, median_quality)
                if f_quality is None:
                    f_quality = median_quality
                result[code] = {
                    "f_roe": float(z_roe.get(code, 0.0)) if code in z_roe.index else 0.0,
                    "f_pb_pct": float(z_pb.get(code, 0.0)) if code in z_pb.index else 0.0,
                    "f_earnings_yoy": float(z_earn.get(code, 0.0)) if code in z_earn.index else 0.0,
                    "f_quality": float(f_quality),
                    "is_commodity": False,
                    "num_constituents": sector_raw[code]["num_constituents"],
                    "missing_constituents": sector_raw[code]["missing_constituents"],
                }
            else:
                result[code] = {
                    "f_roe": median_quality,
                    "f_pb_pct": median_quality,
                    "f_earnings_yoy": median_quality,
                    "f_quality": median_quality,
                    "is_commodity": False,
                    "num_constituents": 0,
                    "missing_constituents": 0,
                }

        logger.info(f"Financial factors computed for {len(result)} ETFs "
                     f"(median_quality={median_quality:.4f})")
        return result
    finally:
        conn.close()


# ────────────────────────────────────────────────────────────
#  DB 持久化 & 加载
# ────────────────────────────────────────────────────────────

def persist_financial_factors(factors: dict, calc_date: str = None) -> int:
    """将计算结果写入 financial_factor 表。"""
    from src.core.trading_calendar import now_beijing
    from src.core.db_manager_postgresql import get_db_manager

    if calc_date is None:
        calc_date = now_beijing().strftime("%Y%m%d")
    if not factors:
        logger.warning("No factors to persist")
        return 0

    rows = []
    for code, data in factors.items():
        rows.append({
            "ts_code": code,
            "calc_date": calc_date,
            "f_roe": data["f_roe"],
            "f_pb_pct": data["f_pb_pct"],
            "f_earnings_yoy": data["f_earnings_yoy"],
            "f_quality": data["f_quality"],
            "is_commodity": data["is_commodity"],
            "num_constituents": data["num_constituents"],
            "missing_constituents": data["missing_constituents"],
        })

    df = pd.DataFrame(rows)
    db = get_db_manager()
    n = db.upsert_dataframe(df, "financial_factor", ["ts_code", "calc_date"])
    logger.info(f"Persisted {n} financial factor rows for date={calc_date}")
    return n


def load_latest_financial_factors(calc_date: str = None) -> dict:
    """从 DB 加载最新财务质量因子数据。"""
    conn = _get_conn()
    try:
        if calc_date:
            where_clause = "calc_date = :d"
            params = {"d": calc_date}
        else:
            where_clause = "calc_date = (SELECT MAX(calc_date) FROM financial_factor)"
            params = {}

        rows = conn.execute(text(f"""
            SELECT ts_code, f_roe, f_pb_pct, f_earnings_yoy, f_quality,
                   is_commodity, num_constituents, missing_constituents
            FROM financial_factor
            WHERE {where_clause}
        """), params).fetchall()

        result = {}
        for r in rows:
            result[r[0]] = {
                "f_roe": float(r[1]) if r[1] is not None else 0.0,
                "f_pb_pct": float(r[2]) if r[2] is not None else 0.0,
                "f_earnings_yoy": float(r[3]) if r[3] is not None else 0.0,
                "f_quality": float(r[4]) if r[4] is not None else 0.0,
                "is_commodity": bool(r[5]) if r[5] is not None else False,
                "num_constituents": int(r[6]) if r[6] is not None else 0,
                "missing_constituents": int(r[7]) if r[7] is not None else 0,
            }
        return result
    finally:
        conn.close()


def compute_and_persist(calc_date: str = None) -> dict:
    """一站式：计算 + 持久化 + 返回结果。"""
    factors = compute_financial_factors(calc_date)
    if factors:
        persist_financial_factors(factors, calc_date)
    return factors


# ════════════════════════════════════════════════════════════
#  独立运行入口
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    result = compute_and_persist()
    print(f"\nComputed {len(result)} sector ETF financial factors:")
    for code, data in sorted(result.items()):
        etf_name = SECTOR_ETF.get(code, code)
        qual = data["f_quality"]
        flag = " [商品]" if data["is_commodity"] else ""
        print(f"  {etf_name:12s} ({code:10s}): "
              f"F_Quality={qual:+.4f}, "
              f"ROE={data['f_roe']:+.4f}, "
              f"PB_Pct={data['f_pb_pct']:+.4f}, "
              f"EarnYoY={data['f_earnings_yoy']:+.4f}"
              f"{flag}")
