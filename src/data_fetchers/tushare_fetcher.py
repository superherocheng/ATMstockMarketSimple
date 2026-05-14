"""
ATMstockMarket 数据获取脚本 v5
================================
v5: 迁移至PostgreSQL —— 使用连接池和并发支持，
    提升数据插入和查询性能，支持并发读写。

用法：
    cd ATMstockMarket
    python src/data_fetchers/tushare_fetcher.py              # 全量获取（自动跳过已是最新）
    python src/data_fetchers/tushare_fetcher.py --etf        # 仅 ETF
    python src/data_fetchers/tushare_fetcher.py --stocks     # 仅个股
    python src/data_fetchers/tushare_fetcher.py --funda      # 仅基本面
    python src/data_fetchers/tushare_fetcher.py --init       # 仅初始化数据库
    python src/data_fetchers/tushare_fetcher.py --verify     # 仅检查数据库状态
"""
import warnings
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

import argparse
import time
import sys
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from queue import Queue

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

import pandas as pd
from sqlalchemy import text

from config.config import (
    get_pro,
    INDEX_ETF, SECTOR_ETF, LOOKBACK_DAYS, ANOMALY_STD_THRESHOLD,
)
from src.core.trading_calendar import (
    get_latest_trading_date,
    get_db_max_date,
    get_open_trade_dates,
    is_fresh as _tc_is_fresh,
    get_dates_to_fetch,
    verify_database,
    now_beijing,
)
from src.core.db_manager_postgresql import init_db_manager, get_db_manager, close_db_manager

# ─── 调参区 ──────────────────────────────────────
RETRY_MAX       = 3
RETRY_BASE_SEC  = 1.0
THROTTLE_SEC    = 0.35
WRITE_BATCH     = 10


# ══════════════════════════════════════════════════
#  数据库
# ══════════════════════════════════════════════════
def _run_alembic_migrations():
    """运行 Alembic 迁移（如果可用）。

    Returns:
        True if migrations ran successfully, False if Alembic unavailable.
    """
    try:
        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
        # 确保 URL 正确注入
        db_url = os.getenv("DATABASE_URL", "")
        if db_url:
            alembic_cfg.set_main_option("sqlalchemy.url", db_url)

        command.upgrade(alembic_cfg, "head")
        print("[OK] Alembic 迁移完成")
        return True
    except ImportError:
        print("[INFO] Alembic 未安装，使用内联 SQL 建表")
        return False
    except Exception as e:
        print(f"[WARN] Alembic 迁移失败: {e}")
        print("[INFO] 回退到内联 SQL 建表")
        return False


def init_db():
    """初始化PostgreSQL数据库。

    策略：
      1. 优先使用 Alembic 迁移（版本化管理）
      2. 如果 Alembic 不可用，使用内联 SQL（向后兼容）
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError(
            "DATABASE_URL environment variable not set. "
            "Please set it to your PostgreSQL connection string. "
            "Example: postgresql://user:password@host:port/database"
        )
    
    try:
        init_db_manager(db_url)
        db = get_db_manager()
        conn = db.get_connection()
    except Exception as e:
        print("\n" + "=" * 60)
        print("[ERROR] 数据库连接失败！")
        print("=" * 60)
        print(f"错误信息: {e}")
        print("\n可能的原因：")
        print("  1. PostgreSQL 服务未启动")
        print("  2. DATABASE_URL 配置错误")
        print("  3. 数据库不存在或用户权限不足")
        print("\n解决方案：")
        print("  1. 检查 PostgreSQL 服务状态: brew services list | grep postgresql")
        print("  2. 验证 .env 文件中的 DATABASE_URL 配置")
        print("  3. 测试数据库连接: psql -U <user> -d atm_stock_market")
        print("=" * 60)
        raise

    # ── P3.7: 优先使用 Alembic 迁移 ──
    if _run_alembic_migrations():
        conn.commit()
        print("[OK] PostgreSQL数据库初始化完成 (Alembic)")
        return
    
    for sql in [
        """CREATE TABLE IF NOT EXISTS index_etf_daily (
            ts_code VARCHAR, trade_date VARCHAR, open DOUBLE PRECISION, high DOUBLE PRECISION, low DOUBLE PRECISION,
            close DOUBLE PRECISION, vol DOUBLE PRECISION, amount DOUBLE PRECISION, pre_close DOUBLE PRECISION, pct_chg DOUBLE PRECISION,
            PRIMARY KEY (ts_code, trade_date))""",
        """CREATE TABLE IF NOT EXISTS etf_share (
            ts_code VARCHAR, trade_date VARCHAR, fd_share DOUBLE PRECISION,
            PRIMARY KEY (ts_code, trade_date))""",
        """CREATE TABLE IF NOT EXISTS sector_etf_daily (
            ts_code VARCHAR, trade_date VARCHAR, open DOUBLE PRECISION, high DOUBLE PRECISION, low DOUBLE PRECISION,
            close DOUBLE PRECISION, vol DOUBLE PRECISION, amount DOUBLE PRECISION, pre_close DOUBLE PRECISION, pct_chg DOUBLE PRECISION,
            PRIMARY KEY (ts_code, trade_date))""",
        """CREATE TABLE IF NOT EXISTS stock_daily (
            ts_code VARCHAR, trade_date VARCHAR, open DOUBLE PRECISION, high DOUBLE PRECISION, low DOUBLE PRECISION,
            close DOUBLE PRECISION, vol DOUBLE PRECISION, amount DOUBLE PRECISION, pre_close DOUBLE PRECISION, pct_chg DOUBLE PRECISION,
            PRIMARY KEY (ts_code, trade_date))""",
        """CREATE TABLE IF NOT EXISTS stock_basic (
            ts_code VARCHAR PRIMARY KEY, name VARCHAR, industry VARCHAR,
            area VARCHAR, market VARCHAR, list_date VARCHAR)""",
        """CREATE TABLE IF NOT EXISTS stock_daily_basic (
            ts_code VARCHAR, trade_date VARCHAR, pe DOUBLE PRECISION, pe_ttm DOUBLE PRECISION, pb DOUBLE PRECISION,
            ps DOUBLE PRECISION, ps_ttm DOUBLE PRECISION, total_mv DOUBLE PRECISION, circ_mv DOUBLE PRECISION, turnover_rate DOUBLE PRECISION,
            PRIMARY KEY (ts_code, trade_date))""",
        """CREATE TABLE IF NOT EXISTS stock_fina_indicator (
            ts_code VARCHAR, ann_date VARCHAR, end_date VARCHAR,
            roe DOUBLE PRECISION, netprofit_yoy DOUBLE PRECISION, tr_yoy DOUBLE PRECISION,
            grossprofit_margin DOUBLE PRECISION, netprofit_margin DOUBLE PRECISION,
            eps DOUBLE PRECISION, debt_to_assets DOUBLE PRECISION, current_ratio DOUBLE PRECISION,
            PRIMARY KEY (ts_code, end_date))""",
        """CREATE TABLE IF NOT EXISTS analysis_cache (
            key VARCHAR PRIMARY KEY, updated_at VARCHAR, data_json VARCHAR)""",
        """CREATE TABLE IF NOT EXISTS stock_info (
            ts_code VARCHAR PRIMARY KEY, name VARCHAR, area VARCHAR, market VARCHAR,
            list_date VARCHAR, sw_level1 VARCHAR, sw_level2 VARCHAR, sw_level3 VARCHAR,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS concept_dict (
            concept_id INTEGER PRIMARY KEY, concept_name VARCHAR UNIQUE NOT NULL,
            concept_category VARCHAR)""",
        """CREATE TABLE IF NOT EXISTS stock_concept (
            ts_code VARCHAR, concept_id INTEGER,
            PRIMARY KEY (ts_code, concept_id))""",
    ]:
        conn.execute(text(sql))
    
    for index_sql in [
        "CREATE INDEX IF NOT EXISTS idx_stock_concept_code ON stock_concept(ts_code)",
        "CREATE INDEX IF NOT EXISTS idx_stock_concept_id ON stock_concept(concept_id)",
        "CREATE INDEX IF NOT EXISTS idx_stock_info_sw1 ON stock_info(sw_level1)",
        "CREATE INDEX IF NOT EXISTS idx_stock_info_sw2 ON stock_info(sw_level2)",
        "CREATE INDEX IF NOT EXISTS idx_stock_info_sw3 ON stock_info(sw_level3)",
        # ── P0.2: Performance-critical indexes ──
        "CREATE INDEX IF NOT EXISTS idx_sd_code_date ON stock_daily(ts_code, trade_date)",
        "CREATE INDEX IF NOT EXISTS idx_sdb_date_mv_pe ON stock_daily_basic(trade_date, total_mv, pe_ttm, pb)",
        "CREATE INDEX IF NOT EXISTS idx_sd_date ON stock_daily(trade_date)",
        "CREATE INDEX IF NOT EXISTS idx_sdb_code_date ON stock_daily_basic(ts_code, trade_date)",
        # ── P2.6: etf_adj_factor 性能索引 ──
        "CREATE INDEX IF NOT EXISTS idx_etf_adj_code_date ON etf_adj_factor(ts_code, trade_date)",
    ]:
        conn.execute(text(index_sql))

    # Create tables used by web app but not in migration script
    for extra_sql in [
        """CREATE TABLE IF NOT EXISTS precomputed_cache (
            cache_key VARCHAR PRIMARY KEY, updated_at VARCHAR, data_json TEXT)""",
        """CREATE TABLE IF NOT EXISTS lhb_data (
            ts_code VARCHAR, trade_date VARCHAR, buy_amount DOUBLE PRECISION,
            sell_amount DOUBLE PRECISION, net_amount DOUBLE PRECISION,
            PRIMARY KEY (ts_code, trade_date))""",
        # ── P2.6: ETF复权因子表 ──
        """CREATE TABLE IF NOT EXISTS etf_adj_factor (
            ts_code VARCHAR, trade_date VARCHAR, adj_factor DOUBLE PRECISION,
            PRIMARY KEY (ts_code, trade_date))""",
    ]:
        conn.execute(text(extra_sql))

    conn.commit()
    
    print("[OK] PostgreSQL数据库初始化完成")


# ══════════════════════════════════════════════════
#  工具函数
# ══════════════════════════════════════════════════
def _today():
    return now_beijing().strftime("%Y%m%d")


def _start_date():
    return (now_beijing() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y%m%d")


def _get_max_date(conn, table, ts_code=None):
    """获取表中最大 trade_date"""
    try:
        if ts_code:
            row = conn.execute(
                text(f"SELECT MAX(trade_date) FROM {table} WHERE ts_code=:p0"),
                {"p0": ts_code},
            ).fetchone()
        else:
            row = conn.execute(text(f"SELECT MAX(trade_date) FROM {table}")).fetchone()
        return row[0] if row and row[0] else None
    except Exception:
        return None


def _is_fresh(max_date):
    """判断 max_date 是否 >= 最新可用交易日"""
    if not max_date:
        return False
    latest = get_latest_trading_date()
    return latest is not None and max_date >= latest


def _all_codes_fresh(conn, table, code_list):
    """检查一组代码是否全部最新（优化版：批量查询）"""
    if not code_list:
        return False

    latest = get_latest_trading_date()
    if not latest:
        return False

    try:
        placeholders = ",".join([f":p{i}" for i in range(len(code_list))])
        params = {f"p{i}": c for i, c in enumerate(code_list)}
        sql = f"""
            SELECT ts_code, MAX(trade_date) as max_date
            FROM {table}
            WHERE ts_code IN ({placeholders})
            GROUP BY ts_code
        """
        results = conn.execute(text(sql), params).fetchall()
        code_max_dates = {row[0]: row[1] for row in results}

        for code in code_list:
            max_date = code_max_dates.get(code)
            if not max_date or max_date < latest:
                return False
        return True
    except Exception:
        return False


def _clean_write(df, table, conn, ts_code=None):
    """清空并写入数据（向量化操作）"""
    if df is None or len(df) == 0:
        return 0
    if ts_code:
        conn.execute(text(f"DELETE FROM {table} WHERE ts_code=:p0"), {"p0": ts_code})
        conn.commit()
    db = get_db_manager()
    n = db.insert_dataframe(df, table, if_exists='append')
    return n


def _upsert_write(df, table, conn):
    """使用UPSERT语义写入数据（向量化操作）"""
    if df is None or len(df) == 0:
        return 0

    db = get_db_manager()

    if table in ['stock_daily', 'stock_daily_basic', 'stock_fina_indicator', 'index_etf_daily', 'sector_etf_daily', 'etf_share', 'etf_adj_factor']:
        pk = ['ts_code', 'trade_date'] if 'fina' not in table else ['ts_code', 'end_date']
        n = db.upsert_dataframe(df, table, pk)
    else:
        # Use insert_dataframe with append for other tables
        n = db.insert_dataframe(df, table, if_exists='append')
    return n


def _upsert_trade_dates(df, table, conn):
    return _upsert_write(df, table, conn)


def _api_call(func, *args, **kwargs):
    last_err = None
    for attempt in range(RETRY_MAX):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            err_msg = str(e)
            no_retry = ["权限", "积分不足", "每分钟", "限制",
                        "没有访问", "无效", "不存在", "参数错误"]
            if any(kw in err_msg for kw in no_retry):
                print(f"    [SKIP] 不可重试: {err_msg}")
                raise
            last_err = e
            wait = RETRY_BASE_SEC * (2 ** attempt)
            print(f"    [RETRY {attempt+1}/{RETRY_MAX}] {err_msg}, 等待{wait:.0f}s...")
            time.sleep(wait)
    raise last_err


def _validate(df, required_cols):
    if df is None or len(df) == 0:
        return df
    cols = [c for c in required_cols if c in df.columns]
    df = df[cols]
    if "trade_date" in df.columns and "ts_code" in df.columns:
        df = df.drop_duplicates(subset=["ts_code", "trade_date"], keep="last")
        df = df.sort_values(["ts_code", "trade_date"]).reset_index(drop=True)
    return df


# ══════════════════════════════════════════════════
#  指数ETF
# ══════════════════════════════════════════════════
def fetch_index_etf():
    pro = get_pro()
    db = get_db_manager()
    conn = db.get_connection()
    default_start = _start_date()

    # 先检查：所有指数ETF的日线+份额是否都最新
    all_fresh_daily = _all_codes_fresh(conn, "index_etf_daily", list(INDEX_ETF.keys()))
    all_fresh_share = _all_codes_fresh(conn, "etf_share", list(INDEX_ETF.keys()))

    if all_fresh_daily and all_fresh_share:
        print("[SKIP] 指数ETF日线+份额均为最新，跳过")
        return

    # ── 阶段1: 日线数据 ──
    for ts_code, name in INDEX_ETF.items():
        existing_max = _get_max_date(conn, "index_etf_daily", ts_code)
        if existing_max and _is_fresh(existing_max):
            print(f"  {name}({ts_code}) 日线已是最新 ({existing_max})，跳过")
        else:
            fetch_start = existing_max or default_start
            is_inc = existing_max is not None
            print(f"  获取 {name}({ts_code}) 日线 从{fetch_start}...")
            try:
                df = _api_call(pro.fund_daily,
                               ts_code=ts_code, start_date=fetch_start)
                df = _validate(df, [
                    "ts_code", "trade_date", "open", "high", "low",
                    "close", "vol", "amount", "pre_close", "pct_chg",
                ])
                n = _upsert_write(df, "index_etf_daily", conn) if is_inc \
                    else _clean_write(df, "index_etf_daily", conn, ts_code)
                print(f"    写入 {n} 条")
            except Exception as e:
                print(f"    [ERR] {e}")
            time.sleep(THROTTLE_SEC)

    # ── 阶段2: 份额数据（全部到齐才写入）──
    _fetch_etf_shares_all_or_nothing(
        conn, pro, default_start, INDEX_ETF, "指数ETF"
    )

    # ── 阶段3: 复权因子（P2.6: 前复权）──
    _fetch_etf_adj_factors(conn, pro, default_start, INDEX_ETF, "指数ETF")

    print("[OK] 指数ETF数据获取完成")


def _get_previous_trading_date(current_date_str):
    """获取前一个交易日（简单日期计算，减一天）"""
    from datetime import datetime, timedelta
    dt = datetime.strptime(current_date_str, "%Y%m%d")
    prev_dt = dt - timedelta(days=1)
    return prev_dt.strftime("%Y%m%d")

def _fetch_etf_shares_all_or_nothing(conn, pro, default_start, etf_dict, label):
    """获取ETF份额：先拉取所有ETF的最新份额数据，
    只有当所有ETF的最新交易日数据都到齐后才统一写入 DB。
    允许份额数据比最新交易日落后1天（Tushare 份额数据天然延迟）。"""
    latest_td = get_latest_trading_date()
    if not latest_td:
        print(f"  [SKIP] 无法确定最新交易日，跳过{label}份额获取")
        return

    # 允许份额数据比最新交易日落后1天
    acceptable_min_td = _get_previous_trading_date(latest_td)

    codes = list(etf_dict.keys())
    pending = {}  # {ts_code: DataFrame}

    for ts_code in codes:
        existing_s = _get_max_date(conn, "etf_share", ts_code)
        if existing_s and _is_fresh(existing_s):
            continue  # 此 ETF 份额已最新

        start_s = existing_s or default_start
        try:
            df_s = _api_call(pro.fund_share, ts_code=ts_code, start_date=start_s)
            if df_s is not None and len(df_s) > 0:
                df_s = _validate(df_s, ["ts_code", "trade_date", "fd_share"])
                if len(df_s) > 0:
                    pending[ts_code] = df_s
        except Exception as e:
            print(f"    [ERR] {etf_dict.get(ts_code, ts_code)} 份额: {e}")
        time.sleep(THROTTLE_SEC)

    if not pending:
        print(f"[SKIP] {label}份额均已是最新，跳过")
        return

    # 检查待写入的每个ETF是否都有不早于 acceptable_min_td 的数据（允许落后1天）
    not_ready = []
    for ts_code, df_s in pending.items():
        name = etf_dict.get(ts_code, ts_code)
        max_date = df_s["trade_date"].max()
        if max_date < acceptable_min_td:
            not_ready.append(f"{name}({ts_code}: {max_date} < {acceptable_min_td})")

    if not_ready:
        print(f"  [HOLD] {label}份额未全部到齐，暂不写入:")
        for info in not_ready:
            print(f"    - {info}")
        print(f"  等待所有ETF份额数据更新到至少 {acceptable_min_td} 后再统一写入")
        return

    # 全部到齐，统一写入
    for ts_code, df_s in pending.items():
        name = etf_dict.get(ts_code, ts_code)
        existing_s = _get_max_date(conn, "etf_share", ts_code)
        is_inc_s = existing_s is not None
        n = _upsert_write(df_s, "etf_share", conn) if is_inc_s \
            else _clean_write(df_s, "etf_share", conn, ts_code)
        print(f"    {name} 份额: {n} 条")

    print(f"  [OK] 全部 {len(pending)} 只{label}份额已写入 (最晚 {latest_td})")


# ══════════════════════════════════════════════════
#  P2.6: ETF 复权因子 (前复权)
# ══════════════════════════════════════════════════
def _fetch_etf_adj_factors(conn, pro, default_start, etf_dict, label):
    """获取ETF复权因子（fund_adj）并写入 etf_adj_factor 表。

    Tushare fund_daily 返回的是未复权价格，fund_adj 提供复权因子。
    前复权公式: adj_price = price × adj_factor / latest_adj_factor
    """
    codes = list(etf_dict.keys())
    total_fetched = 0

    for ts_code in codes:
        name = etf_dict.get(ts_code, ts_code)

        # 检查该ETF的复权因子是否已是最新
        existing_max = _get_max_date(conn, "etf_adj_factor", ts_code)
        if existing_max and _is_fresh(existing_max):
            continue

        start = existing_max or default_start
        try:
            df_adj = _api_call(pro.fund_adj, ts_code=ts_code, start_date=start)
            if df_adj is not None and len(df_adj) > 0:
                df_adj = _validate(df_adj, ["ts_code", "trade_date", "adj_factor"])
                if len(df_adj) > 0:
                    n = _upsert_write(df_adj, "etf_adj_factor", conn)
                    total_fetched += n
                    print(f"    {name} 复权因子: {n} 条 (从 {start})")
        except Exception as e:
            err_msg = str(e)
            # fund_adj 接口可能对部分ETF不可用 —— 记录并继续
            print(f"    [WARN] {name} 复权因子获取失败: {err_msg}")
            # 如果权限不足，记录警告但不阻塞
            if "权限" in err_msg or "积分" in err_msg:
                print(f"    [INFO] {name} 无 fund_adj 权限，K线将使用未复权价格")
        time.sleep(THROTTLE_SEC)

    if total_fetched > 0:
        print(f"  [OK] {label}复权因子写入完成 ({total_fetched} 条)")
    return total_fetched


def _apply_etf_adj(df, ts_code):
    """对ETF日线DataFrame应用前复权因子。

    Args:
        df: ETF日线DataFrame (需包含 open/high/low/close/pre_close/trade_date)
        ts_code: ETF代码，用于查询复权因子

    Returns:
        应用复权后的DataFrame副本。如果无复权因子，返回原始数据。

    前复权公式: adj_price = price × adj_factor / latest_adj_factor
    其中 latest_adj_factor 为最新交易日对应的复权因子。
    """
    import math

    if df is None or len(df) == 0:
        return df

    try:
        db = get_db_manager()
        with db.get_connection() as conn:
            adj_df = db.query(
                "SELECT trade_date, adj_factor FROM etf_adj_factor "
                "WHERE ts_code=:p0 ORDER BY trade_date",
                {"p0": ts_code}
            )
    except Exception:
        return df  # DB不可用时返回原始数据

    if adj_df is None or len(adj_df) == 0:
        return df  # 无复权因子，返回原始数据

    # 获取最新复权因子，并确保有效
    latest_adj_raw = adj_df["adj_factor"].iloc[-1]
    try:
        if pd.isna(latest_adj_raw):
            return df
        latest_adj = float(latest_adj_raw)
    except (ValueError, TypeError):
        return df
    if latest_adj <= 0:
        return df  # 无效复权因子

    # 构建 trade_date → adj_factor 映射，过滤 NaN
    adj_map = {}
    for _, r in adj_df.iterrows():
        td = str(r.get("trade_date", ""))
        adj_val = r.get("adj_factor")
        if adj_val is None or (isinstance(adj_val, float) and (pd.isna(adj_val) or math.isnan(adj_val))):
            continue
        adj_map[td] = float(adj_val)

    df = df.copy()
    price_cols = ["open", "high", "low", "close", "pre_close"]

    for idx, row in df.iterrows():
        td = str(row.get("trade_date", ""))
        adj = adj_map.get(td)
        if adj is None or adj <= 0:
            continue  # 无该日复权因子或无效，保留原值
        ratio = adj / latest_adj
        for col in price_cols:
            if col in df.columns and pd.notna(row[col]):
                df.at[idx, col] = float(row[col]) * ratio

    return df


# ══════════════════════════════════════════════════
#  行业ETF
# ══════════════════════════════════════════════════
def fetch_sector_etf():
    pro = get_pro()
    db = get_db_manager()
    conn = db.get_connection()
    default_start = _start_date()
    total = len(SECTOR_ETF)

    all_fresh_daily = _all_codes_fresh(conn, "sector_etf_daily", list(SECTOR_ETF.keys()))
    all_fresh_share = _all_codes_fresh(conn, "etf_share", list(SECTOR_ETF.keys()))

    if all_fresh_daily and all_fresh_share:
        print("[SKIP] 行业ETF日线+份额均为最新，跳过")
        return

    # ── 阶段1: 日线数据（逐个获取，互不影响）──
    for i, (ts_code, name) in enumerate(SECTOR_ETF.items(), 1):
        print(f"  [{i}/{total}] {name}({ts_code})")

        existing = _get_max_date(conn, "sector_etf_daily", ts_code)
        if existing and _is_fresh(existing):
            print(f"    日线已是最新 ({existing})，跳过")
        else:
            start = existing or default_start
            is_inc = existing is not None
            try:
                df = _api_call(pro.fund_daily, ts_code=ts_code, start_date=start)
                df = _validate(df, [
                    "ts_code", "trade_date", "open", "high", "low",
                    "close", "vol", "amount", "pre_close", "pct_chg",
                ])
                n = _upsert_write(df, "sector_etf_daily", conn) if is_inc \
                    else _clean_write(df, "sector_etf_daily", conn, ts_code)
                print(f"    日线: {n} 条 (从{start})")
            except Exception as e:
                print(f"    [ERR] 日线: {e}")
            time.sleep(THROTTLE_SEC)

    # ── 阶段2: 份额数据（全部到齐才写入）──
    _fetch_etf_shares_all_or_nothing(
        conn, pro, default_start, SECTOR_ETF, "行业ETF"
    )

    # ── 阶段3: 复权因子（P2.6: 前复权）──
    _fetch_etf_adj_factors(conn, pro, default_start, SECTOR_ETF, "行业ETF")

    print("[OK] 行业ETF数据获取完成")


# ══════════════════════════════════════════════════
#  个股数据
# ══════════════════════════════════════════════════
def fetch_stock_list():
    pro = get_pro()
    db = get_db_manager()
    conn = db.get_connection()

    print("  获取股票列表...")
    df = _api_call(pro.stock_basic,
                   exchange="", list_status="L",
                   fields="ts_code,name,industry,area,market,list_date")
    df = df[~df["name"].str.contains("ST", na=False)]
    df = df[~df["ts_code"].str.endswith(".BJ")]
    # Use the same connection for DELETE + INSERT to maintain atomicity.
    # If the INSERT fails, the transaction rolls back and the old data is preserved.
    try:
        with conn.begin():
            conn.execute(text("DELETE FROM stock_basic"))
            df.to_sql("stock_basic", conn, if_exists='append', index=False, method='multi')
    except Exception:
        import traceback
        print(f"[ERROR] stock_basic 更新失败，数据已回滚: {traceback.format_exc()}")
        raise
    print(f"  共 {len(df)} 只非ST股票")
    return df["ts_code"].tolist()


def fetch_stock_daily():
    pro = get_pro()
    db = get_db_manager()
    conn = db.get_connection()

    existing_max = _get_max_date(conn, "stock_daily")
    if existing_max and _is_fresh(existing_max):
        print("[SKIP] 个股日线已是最新，跳过")
        return

    default_start = _start_date()
    start_date = existing_max or default_start

    if existing_max:
        print(f"  个股日线已有数据至 {existing_max}，增量拉取")
    else:
        print(f"  个股日线无数据，从 {start_date} 开始拉取")

    trade_dates = get_dates_to_fetch("stock_daily", start_date=start_date)

    if not trade_dates:
        print("[SKIP] 个股日线已是最新，无需拉取")
        return

    total = len(trade_dates)
    print(f"  需拉取 {total} 个交易日 ({trade_dates[0]} ~ {trade_dates[-1]})")

    required = [
        "ts_code", "trade_date", "open", "high", "low",
        "close", "vol", "amount", "pre_close", "pct_chg",
    ]
    batch_dfs = []
    done = 0
    errors = []

    for i, td in enumerate(trade_dates):
        try:
            df = _api_call(pro.daily, trade_date=td)
            if df is not None and len(df) > 0:
                batch_dfs.append(_validate(df, required))
            done += 1
        except Exception as e:
            err_msg = str(e)
            print(f"    [FAIL] {td}: {err_msg}")
            errors.append(td)
            if any(kw in err_msg for kw in ["权限", "积分不足", "没有访问"]):
                print("    [ABORT] 权限不足，停止")
                break

        is_last = (i + 1 == total)
        if (len(batch_dfs) >= WRITE_BATCH) or (is_last and batch_dfs):
            big_df = pd.concat(batch_dfs, ignore_index=True)
            n = _upsert_trade_dates(big_df, "stock_daily", conn)
            print(f"    进度: {done}/{total} 天, 写入 {n} 条")
            batch_dfs = []

        time.sleep(THROTTLE_SEC)

    total_rows = conn.execute(text("SELECT COUNT(*) FROM stock_daily")).fetchone()[0]
    date_range = conn.execute(
        text("SELECT MIN(trade_date), MAX(trade_date) FROM stock_daily")
    ).fetchone()
    print(f"  个股日线表共 {total_rows} 条 ({date_range[0]} ~ {date_range[1]})")
    if errors:
        print(f"  [WARN] 以下日期获取失败: {errors}")
    print("[OK] 个股日线获取完成")


# ══════════════════════════════════════════════════
#  每日估值（PE/PB/市值等）
# ══════════════════════════════════════════════════
def fetch_daily_basic():
    pro = get_pro()
    db = get_db_manager()
    conn = db.get_connection()

    existing_max = _get_max_date(conn, "stock_daily_basic")
    if existing_max and _is_fresh(existing_max):
        print("[SKIP] 每日估值已是最新，跳过")
        return

    default_start = _start_date()
    start_date = existing_max or default_start

    if existing_max:
        print(f"  每日估值已有数据至 {existing_max}，增量拉取")
    else:
        print(f"  每日估值无数据，从 {start_date} 开始拉取")

    trade_dates = get_dates_to_fetch("stock_daily_basic", start_date=start_date)

    if not trade_dates:
        print("[SKIP] 每日估值已是最新，无需拉取")
        return

    total = len(trade_dates)
    print(f"  需拉取 {total} 个交易日 ({trade_dates[0]} ~ {trade_dates[-1]})")

    required = [
        "ts_code", "trade_date", "pe", "pe_ttm", "pb",
        "ps", "ps_ttm", "total_mv", "circ_mv", "turnover_rate",
    ]
    batch_dfs = []
    done = 0
    errors = []

    for i, td in enumerate(trade_dates):
        try:
            df = _api_call(pro.daily_basic,
                           trade_date=td,
                           fields=",".join(required))
            if df is not None and len(df) > 0:
                # 过滤掉 BJ 股票
                df = df[~df["ts_code"].str.endswith(".BJ")]
                cols = [c for c in required if c in df.columns]
                df = df[cols]
                df = df.drop_duplicates(subset=["ts_code", "trade_date"], keep="last")
                batch_dfs.append(df)
            done += 1
        except Exception as e:
            err_msg = str(e)
            print(f"    [FAIL] {td}: {err_msg}")
            errors.append(td)
            if any(kw in err_msg for kw in ["权限", "积分不足", "没有访问"]):
                print("    [ABORT] 权限不足，停止")
                break

        is_last = (i + 1 == total)
        if (len(batch_dfs) >= WRITE_BATCH) or (is_last and batch_dfs):
            big_df = pd.concat(batch_dfs, ignore_index=True)
            n = _upsert_trade_dates(big_df, "stock_daily_basic", conn)
            print(f"    进度: {done}/{total} 天, 写入 {n} 条")
            batch_dfs = []

        time.sleep(THROTTLE_SEC)

    total_rows = conn.execute(text("SELECT COUNT(*) FROM stock_daily_basic")).fetchone()[0]
    print(f"  每日估值表共 {total_rows} 条")
    if errors:
        print(f"  [WARN] 以下日期获取失败: {errors}")
    print("[OK] 每日估值获取完成")


# ══════════════════════════════════════════════════
#  财务指标（季度）
# ══════════════════════════════════════════════════
def _recent_quarters(n=4):
    """返回最近 n 个报告期的 end_date 列表，如 ['20250930','20250630',...]"""
    now = now_beijing()
    quarters = []
    for offset in range(n):
        total_q = now.year * 4 + (now.month - 1) // 3 - offset
        qy = total_q // 4
        qm = (total_q % 4) * 3 + 3  # 季度末月份
        quarters.append(f"{qy}{qm:02d}30")
    return quarters


def fetch_fina_indicator():
    """多线程拉取最近 4 个季度财务指标。"""
    CONCURRENCY = 4
    THROTTLE_PER_THREAD = 0.40  # 每线程间隔

    required = [
        "ts_code", "ann_date", "end_date", "roe", "netprofit_yoy",
        "tr_yoy", "grossprofit_margin", "netprofit_margin",
        "eps", "debt_to_assets", "current_ratio",
    ]

    db = get_db_manager()
    conn = db.get_connection()
    stocks = conn.execute(text("SELECT ts_code FROM stock_basic")).fetchall()
    codes = [s[0] for s in stocks]

    existing = set()
    try:
        rows = conn.execute(
            text("SELECT DISTINCT ts_code FROM stock_fina_indicator")
        ).fetchall()
        existing = {r[0] for r in rows}
    except Exception:
        pass

    codes_to_fetch = [c for c in codes if c not in existing]
    total = len(codes_to_fetch)

    if total == 0:
        print("[SKIP] 财务指标已是最新，跳过")
        return

    print(f"  需获取 {total}/{len(codes)} 只股票的财务指标 ({CONCURRENCY}线程)")

    # ─── 线程安全的状态 ───
    lock = threading.Lock()
    progress = {"done": 0, "errors": 0, "abort": False}
    result_queue = Queue()  # 线程间传递 DataFrame

    def _worker(code_list, thread_id):
        """工作线程：每人一个 pro 实例，按节流抓取"""
        pro = get_pro()
        for code in code_list:
            if progress["abort"]:
                return
            try:
                df = _api_call(pro.fina_indicator, ts_code=code)
                if df is not None and len(df) > 0:
                    cols = [c for c in required if c in df.columns]
                    df = df[cols]
                    df = df.drop_duplicates(
                        subset=["ts_code", "end_date"], keep="last"
                    )
                    df = df.sort_values("end_date", ascending=False).head(4)
                    result_queue.put(df)
                with lock:
                    progress["done"] += 1
            except Exception as e:
                with lock:
                    progress["errors"] += 1
                    progress["done"] += 1
                if any(kw in str(e) for kw in ["权限", "积分不足", "没有访问"]):
                    progress["abort"] = True
                    return
            time.sleep(THROTTLE_PER_THREAD)

    # ─── 分片 & 启动线程 ───
    chunks = [[] for _ in range(CONCURRENCY)]
    for i, code in enumerate(codes_to_fetch):
        chunks[i % CONCURRENCY].append(code)

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = []
        for tid in range(CONCURRENCY):
            if chunks[tid]:
                futures.append(executor.submit(_worker, chunks[tid], tid))

        # ─── 主线程：从队列消费并批量写入 PostgreSQL ───
        batch_dfs = []
        last_report = time.time()

        while any(f.running() for f in futures) or not result_queue.empty():
            try:
                df = result_queue.get(timeout=0.5)
                batch_dfs.append(df)
            except Exception:
                continue

            if len(batch_dfs) >= WRITE_BATCH:
                _write_fina_batch(conn, batch_dfs, required)
                batch_dfs = []

            # 每 5 秒打印进度
            now = time.time()
            if now - last_report >= 5:
                d = progress["done"]
                e = progress["errors"]
                print(f"    进度: {d}/{total} 只 (失败 {e})")
                last_report = now

        # 写入剩余
        if batch_dfs:
            _write_fina_batch(conn, batch_dfs, required)

        total_rows = conn.execute(
            text("SELECT COUNT(*) FROM stock_fina_indicator")
        ).fetchone()[0]

    d = progress["done"]
    e = progress["errors"]
    print(f"  财务指标表共 {total_rows} 条 (获取 {d} 只, 失败 {e})")
    print("[OK] 财务指标获取完成")


def _write_fina_batch(conn, batch_dfs, required):
    """批量 upert 一批 DataFrame 到 stock_fina_indicator（向量化操作）"""
    batch_dfs = [df for df in batch_dfs if df is not None and len(df) > 0]
    if not batch_dfs:
        return
    big_df = pd.concat(batch_dfs, ignore_index=True)
    cols_in_df = [c for c in required if c in big_df.columns]
    big_df = big_df[cols_in_df]
    
    db = get_db_manager()
    db.upsert_dataframe(big_df, "stock_fina_indicator", ["ts_code", "end_date"])


# ══════════════════════════════════════════════════
#  缓存清除（在数据更新后通知 Web 服务刷新）
# ══════════════════════════════════════════════════
def _invalidate_web_cache():
    """清除 Web 服务的两级缓存（Redis + 内存），使新数据立即生效"""
    # 方式1：直接清除 Redis（进程间共享）
    try:
        from src.web.services.cache import _cache_invalidate
        _cache_invalidate("etf", "overview", "analysis")
        print("[OK] Redis 缓存已清除")
    except ImportError:
        print("[SKIP] 无法导入缓存模块，跳过 Redis 清除")
    except Exception as e:
        print(f"[SKIP] Redis 缓存清除异常: {e}")

    # 方式2：通过 HTTP 通知 Web 服务清除自身的内存缓存
    try:
        import urllib.request
        req = urllib.request.Request(
            "http://localhost:8000/api/cache/invalidate",
            method="POST", data=b"{}",
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=3)
        print("[OK] Web 服务缓存已刷新")
    except Exception:
        print("[INFO] Web 服务未运行或无法连接，下次启动后自动加载新数据")


# ══════════════════════════════════════════════════
#  主入口
# ══════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="ATMstockMarket 数据获取 v4")
    parser.add_argument("--etf", action="store_true", help="仅 ETF")
    parser.add_argument("--stocks", action="store_true", help="仅个股")
    parser.add_argument("--funda", action="store_true", help="仅基本面数据")
    parser.add_argument("--init", action="store_true", help="仅初始化")
    parser.add_argument("--verify", action="store_true", help="仅检查数据库状态")
    args = parser.parse_args()

    print("=" * 50)
    print("  ATMstockMarket 数据获取工具 v4")
    print(f"  {now_beijing().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    if args.verify:
        verify_database()
        return

    try:
        init_db()

        if args.init:
            return
        if args.etf:
            fetch_index_etf()
            fetch_sector_etf()
            # After sector ETF data is fetched, compute analysis
            try:
                from src.analysis import factor_engine, ic_analyzer
                print("Computing factor analysis...")
                factor_engine.compute_all_factors()
                ic_analyzer.compute_all_ic()
                print("[OK] Analysis computation complete")
            except Exception as e:
                print(f"[SKIP] Analysis computation failed: {e}")
            _invalidate_web_cache()
            return
        if args.stocks:
            fetch_stock_list()
            fetch_stock_daily()
            fetch_daily_basic()
            return
        if args.funda:
            fetch_daily_basic()
            fetch_fina_indicator()
            return

        # 默认：全部获取（自动跳过已是最新）
        fetch_index_etf()
        fetch_sector_etf()
        # After sector ETF data is fetched, compute analysis
        try:
            from src.analysis import factor_engine, ic_analyzer
            print("Computing factor analysis...")
            factor_engine.compute_all_factors()
            ic_analyzer.compute_all_ic()
            print("[OK] Analysis computation complete")
        except Exception as e:
            print(f"[SKIP] Analysis computation failed: {e}")
        _invalidate_web_cache()
        fetch_stock_list()
        fetch_stock_daily()
        fetch_daily_basic()
        fetch_fina_indicator()
        print(f"\n[ALL DONE] 全部数据获取完成！({now_beijing().strftime('%H:%M:%S')})")
    finally:
        close_db_manager()


if __name__ == "__main__":
    main()
