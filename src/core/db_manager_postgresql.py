"""
ATMstockMarket PostgreSQL 数据库连接管理模块
=============================================
提供统一的PostgreSQL连接管理，支持：
- 连接池管理
- 并发读写
- 事务支持
- 自动类型转换
"""
import logging
import os
import re
import threading
import time
import datetime as dt
from functools import wraps
from pathlib import Path
from typing import Optional, Any, Dict, List, Callable
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text, pool
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError, OperationalError, ProgrammingError, DataError
# psycopg2 is used indirectly via SQLAlchemy


logger = logging.getLogger(__name__)


# ── Retry decorator for transient DB failures ──
def _retry_on_disconnect(max_retries: int = 3, base_delay: float = 0.5):
    """Decorator: retry DB operations that fail due to connection issues.

    Catches OperationalError (connection lost, server restart, etc.)
    and retries with exponential backoff.
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except OperationalError as e:
                    last_exc = e
                    if attempt < max_retries:
                        delay = base_delay * (2 ** (attempt - 1))
                        logger.warning(
                            f"DB connection lost (attempt {attempt}/{max_retries}), "
                            f"retrying in {delay:.1f}s: {e}"
                        )
                        time.sleep(delay)
                        # pool_pre_ping=True handles stale connections;
                        # no need to dispose the entire pool on transient errors.
                    else:
                        logger.error(f"DB operation failed after {max_retries} retries: {e}")
                except SQLAlchemyError as e:
                    # Non-transient SQL errors — don't retry
                    last_exc = e
                    raise
            raise last_exc
        return wrapper
    return decorator


class PostgreSQLConnectionManager:
    """PostgreSQL连接管理器，使用SQLAlchemy连接池"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, db_url: Optional[str] = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_url: Optional[str] = None):
        if self._initialized:
            return
        
        self._db_url = db_url
        self._engine: Optional[Engine] = None
        self._initialized = True
        
        self._configure_connection_pool()
    
    def _configure_connection_pool(self):
        """配置PostgreSQL连接池"""
        if not self._db_url:
            return
        
        self._engine = create_engine(
            self._db_url,
            poolclass=pool.QueuePool,
            pool_size=20,
            max_overflow=30,
            pool_pre_ping=True,
            pool_recycle=1800,
            echo=False
        )
    
    def get_connection(self):
        """获取数据库连接"""
        if not self._engine:
            raise RuntimeError("Database engine not initialized")
        return self._engine.connect()
    
    @_retry_on_disconnect()
    def execute(self, sql: str, params: Optional[tuple] = None) -> Any:
        """执行SQL语句
        
        支持两种参数格式：
        1. 命名参数：使用 :param 格式，传递字典
        2. 位置参数：使用 %s 格式，传递元组（自动转换为命名参数）
        """
        try:
            with self.get_connection() as conn:
                if params:
                    if isinstance(params, dict):
                        result = conn.execute(text(sql), params)
                    else:
                        result = self._execute_with_positional_params(conn, sql, params)
                else:
                    result = conn.execute(text(sql))
                conn.commit()
                return result
        except SQLAlchemyError as e:
            logger.error("Execute error on sql=%s params=%s: %s", sql[:80], params, e, exc_info=True)
            raise
    
    def _execute_with_positional_params(self, conn, sql: str, params: tuple):
        """将位置参数转换为命名参数执行"""
        param_names = []
        param_counter = [0]
        
        def replace_placeholder(match):
            param_name = f"p{param_counter[0]}"
            param_names.append(param_name)
            param_counter[0] += 1
            return f":{param_name}"
        
        converted_sql = re.sub(r'%s|\?', replace_placeholder, sql)
        params_dict = dict(zip(param_names, params))
        return conn.execute(text(converted_sql), params_dict)
    
    @_retry_on_disconnect()
    def query(self, sql: str, params: Optional[tuple] = None) -> pd.DataFrame:
        """执行查询并返回DataFrame

        支持两种参数格式：
        1. 命名参数：使用 :param 格式，传递字典
        2. 位置参数：使用 %s 或 ? 格式，传递元组（自动转换为命名参数）
        """
        try:
            with self.get_connection() as conn:
                if params:
                    if isinstance(params, dict):
                        return pd.read_sql_query(text(sql), conn, params=params)
                    else:
                        return self._query_with_positional_params(conn, sql, params)
                else:
                    return pd.read_sql_query(text(sql), conn)
        except (ProgrammingError, DataError) as e:
            logger.error("Query error (re-raising) on sql=%s params=%s: %s", sql[:80], params, e, exc_info=True)
            raise
        except OperationalError as e:
            logger.error("Query operational error on sql=%s params=%s: %s", sql[:80], params, e, exc_info=True)
            return pd.DataFrame()
    
    def _query_with_positional_params(self, conn, sql: str, params: tuple) -> pd.DataFrame:
        """将位置参数转换为命名参数查询"""
        param_names = []
        param_counter = [0]
        
        def replace_placeholder(match):
            param_name = f"p{param_counter[0]}"
            param_names.append(param_name)
            param_counter[0] += 1
            return f":{param_name}"
        
        converted_sql = re.sub(r'%s|\?', replace_placeholder, sql)
        params_dict = dict(zip(param_names, params))
        return pd.read_sql_query(text(converted_sql), conn, params=params_dict)
    
    def insert_dataframe(self, df: pd.DataFrame, table_name: str, 
                        if_exists: str = 'append', 
                        primary_key: Optional[List[str]] = None) -> int:
        """高效插入DataFrame到表中"""
        if df is None or len(df) == 0:
            return 0
        
        try:
            with self.get_connection() as conn:
                df.to_sql(
                    table_name, 
                    conn, 
                    if_exists=if_exists, 
                    index=False,
                    method='multi',
                    chunksize=10000
                )
                return len(df)
        except Exception as e:
            logger.error("Insert error into %s: %s", table_name, e, exc_info=True)
            return 0
    
    def upsert_dataframe(self, df: pd.DataFrame, table_name: str,
                        primary_key: List[str], chunk_size: int = 1000) -> int:
        """使用UPSERT语义插入DataFrame（PostgreSQL ON CONFLICT）"""
        if df is None or len(df) == 0:
            return 0

        try:
            columns = list(df.columns)
            columns_str = ", ".join([f'"{col}"' for col in columns])
            placeholders = ", ".join([f":{col}" for col in columns])
            pk_constraint = ", ".join([f'"{pk}"' for pk in primary_key])

            update_cols = [col for col in columns if col not in primary_key]
            if update_cols:
                update_str = ", ".join([f'"{col}" = EXCLUDED."{col}"' for col in update_cols])
                sql = f"""
                    INSERT INTO {table_name} ({columns_str})
                    VALUES ({placeholders})
                    ON CONFLICT ({pk_constraint})
                    DO UPDATE SET {update_str}
                """
            else:
                sql = f"""
                    INSERT INTO {table_name} ({columns_str})
                    VALUES ({placeholders})
                    ON CONFLICT ({pk_constraint})
                    DO NOTHING
                """

            total = 0
            data = df.to_dict('records')
            for i in range(0, len(data), chunk_size):
                chunk = data[i:i + chunk_size]
                with self.get_connection() as conn:
                    conn.execute(text(sql), chunk)
                    conn.commit()
                total += len(chunk)

            return total
        except Exception as e:
            logger.error("Upsert error into %s: %s", table_name, e, exc_info=True)
            return 0
    
    def execute_batch(self, operations: List[tuple]) -> int:
        """批量执行SQL操作（事务性）"""
        count = 0

        try:
            with self.get_connection() as conn:
                for sql, params in operations:
                    if params:
                        conn.execute(text(sql), params)
                    else:
                        conn.execute(text(sql))
                    count += 1
                conn.commit()
            return count
        except Exception as e:
            logger.error("Batch execution error (%d ops attempted, none committed): %s", count, e, exc_info=True)
            return 0
    
    def close(self):
        """关闭连接池并重置单例状态"""
        if self._engine:
            self._engine.dispose()
            self._engine = None
        self._initialized = False
        PostgreSQLConnectionManager._instance = None
    
    def close_all(self):
        """关闭所有连接"""
        self.close()


_db_manager: Optional[PostgreSQLConnectionManager] = None
_db_lock = threading.Lock()


def init_db_manager(db_url: str):
    """初始化数据库管理器"""
    global _db_manager
    with _db_lock:
        if _db_manager is None:
            _db_manager = PostgreSQLConnectionManager(db_url)
    return _db_manager


def get_db_manager() -> PostgreSQLConnectionManager:
    """获取数据库管理器实例"""
    global _db_manager
    if _db_manager is None:
        raise RuntimeError("Database manager not initialized. Call init_db_manager first.")
    return _db_manager


def get_conn():
    """获取数据库连接（兼容旧代码）"""
    return get_db_manager().get_connection()


def close_db_manager():
    """关闭并重置数据库管理器"""
    global _db_manager
    with _db_lock:
        if _db_manager is not None:
            try:
                _db_manager.close()
            except Exception:
                pass
            _db_manager = None


@_retry_on_disconnect()
def query(sql: str, params: Optional[tuple] = None) -> pd.DataFrame:
    """执行查询（兼容旧代码）"""
    return get_db_manager().query(sql, params)


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





def _json_safe_value(value):
    """Convert a single value to a JSON-safe type.
    Handles date/datetime objects that arise from DATE columns in PostgreSQL."""
    if value is None:
        return None
    # Handle pandas NaT/NaN
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    # Handle infinities
    if isinstance(value, (int, float, np.floating, np.integer)):
        try:
            if not np.isfinite(value):
                return None
        except Exception:
            pass
        return value
    # Handle date/time -> ISO string
    if isinstance(value, (dt.date, dt.datetime, pd.Timestamp)):
        return value.isoformat() if hasattr(value, 'isoformat') else str(value)
    return value


def safe_json(df):
    """Safely convert DataFrame to JSON-serializable list of dicts"""
    if df is None or len(df) == 0:
        return []
    df = df.copy()
    df = df.replace([float('inf'), float('-inf')], float('nan'))
    records = df.to_dict(orient="records")
    for record in records:
        for key, value in record.items():
            try:
                if pd.isna(value):
                    record[key] = None
                    continue
            except Exception:
                pass
            record[key] = _json_safe_value(value)
    return records


def safe_value(value):
    """Convert a single value to JSON-safe value"""
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
    # Handle date/time -> ISO string
    if isinstance(value, (dt.date, dt.datetime, pd.Timestamp)):
        return value.isoformat() if hasattr(value, 'isoformat') else str(value)
    return value


def safe_dict(d):
    """Recursively convert dict/list values to JSON-safe values"""
    if not isinstance(d, dict):
        if isinstance(d, list):
            return [safe_dict(item) for item in d]
        return safe_value(d)
    return {k: safe_dict(v) for k, v in d.items()}
