"""Alembic 迁移环境配置。

从 .env 的 DATABASE_URL 读取数据库连接，支持离线模式。
"""
import os
import re
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# 加载 .env
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

# Alembic Config 对象
config = context.config

# 从环境变量获取数据库 URL，注入到 alembic 配置
db_url = os.getenv("DATABASE_URL", "")
if db_url:
    # 如果 URL 中包含 %，说明已经编码，直接使用
    config.set_main_option("sqlalchemy.url", db_url)
else:
    # 尝试从 config 文件读取（用于离线模式）
    pass

# 配置日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 目标元数据（可选 —— 此处使用原始 SQL，不需要 ORM metadata）
target_metadata = None


def run_migrations_offline() -> None:
    """离线模式：生成 SQL 而不连接数据库。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接数据库并执行迁移。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
