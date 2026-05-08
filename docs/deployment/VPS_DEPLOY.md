# VPS 部署指南

## 目录结构

在 VPS 上的推荐目录：

```
/opt/atmstockmarket/      # 项目根目录
├── .env                  # 环境变量（数据库连接、Token）
├── docker-compose.yml    # 服务编排
├── src/web/static/react/ # React 前端构建产物（Git忽略，Docker构建生成）
└── data/                 # 持久化数据（映射到容器内）
```

## 快速部署

```bash
# 1. 克隆项目
cd /opt
git clone https://github.com/superherocheng/ATMstockMarket.git atmstockmarket
cd atmstockmarket

# 2. 配置环境变量
cp .env.example .env
nano .env  # 填入 DATABASE_URL 和 TUSHARE_TOKEN

# 3. 启动服务（首次会构建镜像）
docker compose up -d

# 4. 初始化数据库
docker exec -it atmstockmarket python scripts/init_database.py

# 5. 获取数据
docker exec atmstockmarket python src/data_fetchers/tushare_fetcher.py
docker exec atmstockmarket python src/data_fetchers/akshare_fetcher.py
```

## 环境变量说明

| 变量 | 说明 | 示例 |
|------|------|------|
| `DATABASE_URL` | PostgreSQL 连接串 | `postgresql://user:pass@host:5432/dbname` |
| `TUSHARE_TOKEN` | Tushare API Token | 从 tushare.pro 获取 |
| `POSTGRES_USER` | 数据库用户 | `postgres` |
| `POSTGRES_PASSWORD` | 数据库密码 | 强密码 |
| `POSTGRES_DB` | 数据库名 | `atm_stock_market` |

## 数据库地址

- 使用 Docker Compose 部署时：`DATABASE_URL=postgresql://postgres:password@db:5432/atm_stock_market`
  （`db` 是 docker-compose 中的服务名，容器内 DNS 自动解析）
- 使用外部 PostgreSQL 时：将 `DATABASE_URL` 改为实际地址
- 本地开发时：在 `.env` 中设置本地 PostgreSQL 地址

## 访问地址

- 原 Jinja2 页面：`http://your-server:8000/`
- 新版 React SPA：`http://your-server:8000/react/`

## 更新部署

```bash
cd /opt/atmstockmarket
git pull
docker compose up -d --build
```

## 日志查看

```bash
docker compose logs -f app
docker compose logs -f db
```
