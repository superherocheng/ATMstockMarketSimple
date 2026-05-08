import logging
import os

import numpy as np
import pandas as pd

from src.core.db_manager_postgresql import init_db_manager, get_db_manager

logger = logging.getLogger(__name__)

_db_initialized = False


def _ensure_db():
    """初始化PostgreSQL数据库连接"""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError(
            "DATABASE_URL environment variable not set. "
            "Please set it to your PostgreSQL connection string. "
            "Example: postgresql://user:password@host:port/database"
        )
    init_db_manager(db_url)
    logger.info("PostgreSQL数据库连接已建立")


def get_conn():
    """获取PostgreSQL连接"""
    global _db_initialized
    if not _db_initialized:
        _ensure_db()
        _db_initialized = True
    return get_db_manager().get_connection()


def query(sql, params=None):
    """执行查询并返回DataFrame（向量化执行）"""
    try:
        return get_db_manager().query(sql, params)
    except Exception as e:
        logger.error(f"Query failed: {sql[:100]}..., params: {params}, error: {e}", exc_info=True)
        return pd.DataFrame()


def reset_db_initialized():
    """重置数据库初始化状态（供 fetch 模块在 close_db_manager 后调用）"""
    global _db_initialized
    _db_initialized = False


def safe_json(df):
    """安全地将 DataFrame 转换为 JSON 可序列化的字典列表"""
    if df is None or len(df) == 0:
        return []

    df = df.copy()
    df = df.replace([float('inf'), float('-inf')], float('nan'))
    records = df.to_dict(orient="records")

    for record in records:
        for key, value in record.items():
            if pd.isna(value):
                record[key] = None

    return records


def safe_value(value):
    """将单个值转换为 JSON 安全的值"""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, (int, float, np.floating, np.integer)):
        try:
            if not np.isfinite(value):
                return None
        except Exception:
            pass
    return value


def safe_dict(d):
    """将字典中的所有值转换为 JSON 安全的值"""
    if not isinstance(d, dict):
        if isinstance(d, list):
            return [safe_dict(item) for item in d]
        return safe_value(d)
    return {k: safe_dict(v) for k, v in d.items()}
