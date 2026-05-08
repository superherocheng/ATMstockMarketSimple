# PostgreSQL 迁移部署指南

## 📋 概述

本文档说明如何从 DuckDB 迁移到 PostgreSQL，以解决并发访问问题。

## 🎯 迁移优势

- ✅ **完美支持并发读写** - 可以同时更新数据和查看网站
- ✅ **企业级稳定性** - 适合生产环境
- ✅ **连接池管理** - 自动管理数据库连接
- ✅ **ACID事务** - 数据一致性保障

## 📦 前置要求

### 1. 安装 PostgreSQL

#### macOS
```bash
brew install postgresql@15
brew services start postgresql@15
```

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### CentOS/RHEL
```bash
sudo yum install postgresql-server postgresql-contrib
sudo postgresql-setup initdb
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### 2. 创建数据库和用户

```bash
# 切换到 postgres 用户
sudo -u postgres psql

# 在 PostgreSQL 命令行中执行
CREATE DATABASE atm_stock_market;
CREATE USER atm_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE atm_stock_market TO atm_user;
\q
```

### 3. 安装 Python 依赖

```bash
cd /path/to/ATMstockMarket
pip install -r requirements.txt
```

## 🚀 迁移步骤

### 步骤 1: 配置环境变量

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env 文件，填写您的数据库信息
nano .env
```

`.env` 文件内容示例：
```bash
DATABASE_URL=postgresql://atm_user:your_secure_password@localhost:5432/atm_stock_market
TUSHARE_TOKEN=your_tushare_token
```

### 步骤 2: 导出环境变量

```bash
# 对于 bash
export DATABASE_URL="postgresql://atm_user:your_secure_password@localhost:5432/atm_stock_market"

# 对于 zsh (macOS 默认)
echo 'export DATABASE_URL="postgresql://atm_user:your_secure_password@localhost:5432/atm_stock_market"' >> ~/.zshrc
source ~/.zshrc
```

### 步骤 3: 执行数据迁移

```bash
# 运行迁移脚本
python scripts/migrate_to_postgresql.py "$DATABASE_URL"
```

迁移脚本会：
1. 创建所有必要的表结构
2. 从 DuckDB 导出所有数据
3. 导入数据到 PostgreSQL
4. 验证数据完整性

### 步骤 4: 验证迁移

```bash
# 启动 Web 服务器测试
python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000 检查网站是否正常工作。

### 步骤 5: 测试数据获取

```bash
# 测试数据更新功能
python src/data_fetchers/tushare_fetcher.py --verify
```

## 🔧 配置优化

### PostgreSQL 性能调优

编辑 `postgresql.conf` (通常在 `/etc/postgresql/15/main/postgresql.conf`):

```ini
# 连接设置
max_connections = 100

# 内存设置
shared_buffers = 256MB
effective_cache_size = 768MB
maintenance_work_mem = 64MB
work_mem = 4MB

# 查询优化
random_page_cost = 1.1
effective_io_concurrency = 200

# 日志设置
logging_collector = on
log_directory = 'pg_log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_statement = 'ddl'
log_duration = on
```

重启 PostgreSQL：
```bash
sudo systemctl restart postgresql
```

### 连接池配置

在 `src/core/db_manager_postgresql.py` 中已配置连接池：
- `pool_size=10` - 常规连接数
- `max_overflow=20` - 最大溢出连接数
- `pool_pre_ping=True` - 连接健康检查
- `pool_recycle=3600` - 连接回收时间（1小时）

## 🌐 VPS 部署

### 1. 设置系统服务

创建 systemd 服务文件：
```bash
sudo nano /etc/systemd/system/atmstockmarket.service
```

内容：
```ini
[Unit]
Description=ATMstockMarket Web Application
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/path/to/ATMstockMarket
Environment="DATABASE_URL=postgresql://atm_user:your_secure_password@localhost:5432/atm_stock_market"
Environment="TUSHARE_TOKEN=your_tushare_token"
ExecStart=/usr/bin/python3 -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl daemon-reload
sudo systemctl start atmstockmarket
sudo systemctl enable atmstockmarket
```

### 2. Nginx 反向代理

安装 Nginx：
```bash
sudo apt install nginx
```

配置文件 `/etc/nginx/sites-available/atmstockmarket`:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /path/to/ATMstockMarket/src/web/static;
        expires 30d;
    }
}
```

启用配置：
```bash
sudo ln -s /etc/nginx/sites-available/atmstockmarket /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 3. 定时数据更新

创建 cron 任务：
```bash
crontab -e
```

添加以下行（每天收盘后 16:30 更新）：
```cron
30 16 * * 1-5 cd /path/to/ATMstockMarket && /usr/bin/python3 src/data_fetchers/tushare_fetcher.py >> /var/log/atmstockmarket/update.log 2>&1
```

## 🔒 安全建议

### 1. 数据库安全

```sql
-- 限制用户权限
REVOKE ALL ON DATABASE atm_stock_market FROM PUBLIC;
GRANT CONNECT ON DATABASE atm_stock_market TO atm_user;

-- 设置密码加密
ALTER USER atm_user WITH ENCRYPTED PASSWORD 'your_secure_password';
```

### 2. 防火墙配置

```bash
# 仅允许本地访问 PostgreSQL
sudo ufw allow 8000/tcp
sudo ufw enable
```

### 3. SSL 连接（生产环境推荐）

编辑 `postgresql.conf`:
```ini
ssl = on
ssl_cert_file = '/etc/ssl/certs/ssl-cert-snakeoil.pem'
ssl_key_file = '/etc/ssl/private/ssl-cert-snakeoil.key'
```

## 📊 监控和维护

### 查看连接状态

```sql
SELECT * FROM pg_stat_activity WHERE datname = 'atm_stock_market';
```

### 数据库备份

```bash
# 备份
pg_dump -U atm_user atm_stock_market > backup_$(date +%Y%m%d).sql

# 恢复
psql -U atm_user atm_stock_market < backup_20260504.sql
```

### 性能监控

```sql
-- 查看慢查询
SELECT query, calls, total_time, mean_time 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;

-- 查看表大小
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## ❓ 常见问题

### Q1: 迁移后网站无法访问？

**A:** 检查以下几点：
1. 环境变量 `DATABASE_URL` 是否正确设置
2. PostgreSQL 服务是否运行
3. 数据库用户权限是否正确
4. 防火墙是否阻止连接

### Q2: 数据迁移失败？

**A:** 
1. 检查 DuckDB 文件是否存在
2. 确保有足够的磁盘空间
3. 查看 PostgreSQL 日志：`tail -f /var/log/postgresql/postgresql-15-main.log`

### Q3: 并发访问仍然有问题？

**A:** 
1. 检查连接池配置
2. 调整 `max_connections` 参数
3. 使用 `pg_stat_activity` 查看连接状态

## 🎉 迁移完成

恭喜！您已成功从 DuckDB 迁移到 PostgreSQL。现在您可以：

- ✅ 同时更新数据和查看网站
- ✅ 支持多用户并发访问
- ✅ 享受企业级数据库的稳定性

如有任何问题，请查看日志文件或联系技术支持。
