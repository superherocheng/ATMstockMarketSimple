# ATMstockMarket VPS 部署修复记录

> 部署环境：Ubuntu Linux (VPS)，Python 3.12，PostgreSQL
> 部署日期：2026-05-05

项目从 GitHub 克隆后无法直接运行，经过排查共发现 **4 个问题**，分为代码缺陷、安全疏漏和依赖兼容三类。以下逐一说明。

---

## 问题 1：`config.py.example` 模板不完整

**现象**：按照 README 指引执行 `cp config/config.py.example src/core/config.py` 后，启动应用报错：

```
ImportError: cannot import name 'DATA_DIR' from 'src.core.config'
```

**原因**：`src/core/__init__.py` 从 `config.py` 导出了以下 5 个变量：

| 变量 | 用途 |
|------|------|
| `DATA_DIR` | 数据目录路径 |
| `EXTERNAL_DATA_DIR` | 外部数据目录路径 |
| `CYCLICAL_INDUSTRIES` | 周期性行业集合 |
| `CACHE_MAX_SIZE` | 缓存最大条目数 |
| `CACHE_DEFAULT_TTL` | 缓存默认过期时间 |

但 `config/config.py.example` 中 **全部缺失**。用户按文档操作后，这些导出找不到定义，导致整个 `src.core` 模块无法加载。

仓库中实际的 `src/core/config.py` 包含这些定义，但它是作者本地的工作文件（还包含硬编码 Token），不会随 `git clone` 到达用户手中。`config.py.example` 作为唯一的模板，却没有与代码保持同步。

**修复**：在 `src/core/config.py` 中补全缺失定义。

---

## 问题 2：作者 Tushare API Token 泄露在仓库中

**现象**：仓库中 `src/core/config.py` 硬编码了一个真实 Token：

```python
TUSHARE_TOKEN = "<REDACTED-2026-07-19-请到 tushare.pro 轮换并清洗 git 历史>"
```

**原因**：作者将含有个人 Token 的 `config.py` 提交到了 Git 仓库。

**风险**：
- 任何人 clone 后可直接使用该 Token 调用 Tushare API
- Token 可能被滥用导致积分消耗或接口被封
- 属于典型的敏感信息泄露

**修复**：将 Token 替换为占位符 `"你的Token"`，并建议作者：
1. 立即到 Tushare 后台重置 Token
2. 用 `.gitignore` 排除 `src/core/config.py`
3. 只保留 `config/config.py.example` 作为模板

---

## 问题 3：`init_database.py` 引用不存在的脚本

**现象**：运行 `python scripts/init_database.py` 时报错：

```
[ERROR] 脚本不存在: /path/to/scripts/fetch_data.py
```

**原因**：`scripts/init_database.py` 中的 `init_schema()` 函数调用了 `scripts/fetch_data.py`：

```python
def init_schema() -> bool:
    return run_script("fetch_data.py", "--init")
```

但 `scripts/fetch_data.py` 在仓库中 **不存在**。实际的建表逻辑位于 `src/data_fetchers/tushare_fetcher.py` 的 `init_db()` 函数中。

这说明项目重构（v13.0 从 DuckDB 迁移到 PostgreSQL）时，`init_database.py` 没有同步更新引用路径，遗留了对旧脚本的调用。

**修复**：绕过 `init_database.py`，直接调用 `tushare_fetcher.init_db()` 完成建表。

---

## 问题 4：Starlette 1.0 与 Jinja2 不兼容

**现象**：服务启动成功，但访问页面返回 HTTP 500，错误信息：

```
TypeError: unhashable type: 'dict'
  File "jinja2/utils.py", line 515, in __getitem__
    rv = self._mapping[key]
```

**原因**：`requirements.txt` 中未锁定 starlette 版本：

```
fastapi>=0.104.0
```

`pip install` 会拉取最新版依赖。当前最新版 `starlette==1.0.0`，其 `Jinja2Templates` 内部传递模板缓存 key 的方式发生了 breaking change，导致与 `Jinja2 3.1.x` 不兼容。

FastAPI 的 `Jinja2Templates` 直接加载模板没有问题，但通过 FastAPI 路由渲染时，starlette 1.0 传入了一个 dict 作为缓存 key，而 Jinja2 的 `LRUCache` 要求 key 必须可哈希。

**修复**：降级到兼容版本：

```bash
pip install "starlette<1.0" "fastapi>=0.104,<0.116"
```

降级后 `starlette==0.46.2` + `fastapi==0.115.14`，模板渲染恢复正常。

---

## 修复汇总

| # | 问题 | 类型 | 严重程度 | 根因 |
|---|------|------|----------|------|
| 1 | config.py.example 缺失变量 | 代码缺陷 | 高 — 无法启动 | 模板与代码不同步 |
| 2 | API Token 硬编码泄露 | 安全疏漏 | 高 — 凭据泄露 | 敏感文件入库 |
| 3 | init_database.py 引用幽灵脚本 | 代码缺陷 | 中 — 初始化失败 | 重构后未更新引用 |
| 4 | starlette 1.0 兼容性 | 依赖兼容 | 高 — 页面白屏 | 未锁定依赖版本 |
| 7 | 数据库单例无法重新初始化 | 代码缺陷 | 高 — fetch 后全局 500 | 单例 close 不重置 _instance/_initialized |

---


## 问题 5：NPM (Nginx Proxy Manager) 子域名部署

**日期**：2026-05-05

**现象**：需要将 NPM 管理后台和多个项目通过不同子域名对外暴露，全部启用 HTTPS。

**背景**：VPS 使用 Docker 运行 Nginx Proxy Manager (NPM) 作为统一反向代理，所有 HTTP/HTTPS 流量由 NPM 处理。系统自带 nginx 因端口冲突处于 failed 状态，无需修复。

**操作记录**：

| 域名 | 指向 | 端口 | SSL |
|------|------|------|-----|
| `docker.gaodeqingchuda.icu` | Portainer | 9000 | Let's Encrypt |
| `auth.gaodeqingchuda.icu` | 2FAuth | 8000 | Let's Encrypt |
| `music.gaodeqingchuda.icu` | Solara Music | 3001 | Let's Encrypt |
| `stock.gaodeqingchuda.icu` | ATMstockMarket | 8000 | Let's Encrypt |
| `orc.gaodeqingchuda.icu` | NPM 管理后台 | 81 | Let's Encrypt |
| `etf.gaodeqingchuda.icu` | ETFRound (ETF轮动策略) | 8848 | Let's Encrypt |

**关键步骤**：

1. **NPM 密码重置**：通过 Docker 复制 SQLite 数据库，用 bcrypt 生成新密码哈希覆盖 `auth` 表，重启容器生效
2. **防火墙规则**：Docker 容器默认无法访问宿主机端口，需手动添加 iptables 规则：
   ```bash
   sudo iptables -I INPUT -p tcp --dport 8848 -s 172.18.0.0/16 -j ACCEPT
   sudo iptables -I INPUT -p tcp --dport 8848 -s 172.17.0.0/16 -j ACCEPT
   ```
3. **NPM API 自动化配置**：通过 JWT Token 调用 NPM REST API 完成代理主机创建、SSL 证书申请、强制 HTTPS 等操作
4. **ORC 域名**：最初指向 ETFRound，后改为指向 NPM 管理后台自身（`127.0.0.1:81`）
5. **ETF 域名**：新建代理主机指向宿主机 ETFRound 服务（`172.18.0.1:8848`）

**注意事项**：
- NPM 容器访问宿主机服务需使用 Docker 网桥网关 IP（`172.18.0.1`），非 `localhost`
- iptables 规则需持久化（`netfilter-persistent save`），否则重启丢失
- NPM 管理后台邮箱：`superherocheng@163.com`

---

## 问题 6：Tushare Token 配置与 ALLSYMBOL.csv 加载

**日期**：2026-05-05

**现象**：运行 `tushare_fetcher.py` 报错 `请先配置 Tushare Token`；`ALLSYMBOL.csv` 加载提示文件不存在。

**原因**：

1. `src/core/config.py` 中 `TUSHARE_TOKEN` 为硬编码占位符 `"你的Token"`，未读取 `.env` 文件中的变量
2. `ALLSYMBOL.csv` 被放在项目根目录，但代码中查找路径为 `data/external/ALLSYMBOL.csv`

**修复**：

1. 修改 `src/core/config.py`，使 Token 优先读取环境变量，回退到硬编码值：
   ```python
   TUSHARE_TOKEN = os.environ.get("TUSHARE_TOKEN", "") or "<REDACTED-2026-07-19-请到 tushare.pro 轮换并清洗 git 历史>"
   ```

2. 将 `ALLSYMBOL.csv` 从项目根目录移至 `data/external/` 目录

3. 手动执行加载脚本写入数据库：
   ```bash
   .venv/bin/python scripts/load_allsymbol.py
   ```
   加载结果：1095 只股票，458 个概念，13458 条关联

4. 重启 ATMstockMarket 服务使配置生效

---


## 问题 7：数据加载后全局 500 — 数据库单例无法重新初始化

**日期**：2026-05-05

**现象**：首页正常访问，但点击「更新数据」（`POST /api/fetch/all` 或任意 fetch 类型）后，所有 API 端点返回 `{"error": "Database engine not initialized"}`，页面数据加载失败 HTTP 500。必须重启整个服务才能恢复。

**原因**：`PostgreSQLConnectionManager` 使用了 `__new__` 单例模式：

```python
class PostgreSQLConnectionManager:
    _instance = None

    def __new__(cls, db_url=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_url=None):
        if self._initialized:
            return                     # ← 提前退出，不创建新引擎
        self._engine = create_engine(db_url, ...)
        self._initialized = True
```

数据获取流程 `_run_fetch()` 在启动子进程前会调用 `close_db_manager()`：

```python
def _run_fetch(task_type):
    close_db_manager()   # ① _engine.dispose(), _engine=None, _db_manager=None
    ...
```

`close_db_manager()` 执行三步：
1. `_db_manager.close()` → `_engine = None`
2. `_db_manager = None`

但 **`cls._instance` 和 `_initialized` 从未被重置**。

fetch 完成后，下一个 API 请求触发 `_ensure_db()` → `init_db_manager()`：
1. `_db_manager` 为 `None`，进入创建分支
2. `PostgreSQLConnectionManager(db_url)` → `__new__` 返回 **旧的单例实例**（`cls._instance` 仍指向它）
3. `__init__` 看到 `_initialized = True`，直接 `return`
4. `_engine` 仍为 `None` → `get_connection()` 抛出 `RuntimeError: Database engine not initialized`

**调用链**：

```
POST /api/fetch/all
  → _run_fetch()
    → close_db_manager()          # 销毁引擎，但单例未重置
    → subprocess: tushare_fetcher  # 子进程跑完
    → _cache_invalidate()          # 清缓存

GET /api/overview（fetch 之后）
  → _cached_persistent()
    → _compute_overview()
      → get_conn()
        → get_db_manager().get_connection()
          → RuntimeError: Database engine not initialized  ← 500
```

**修复**：在 `PostgreSQLConnectionManager.close()` 中重置单例状态：

```python
# src/core/db_manager_postgresql.py
def close(self):
    """关闭连接池并重置单例状态"""
    if self._engine:
        self._engine.dispose()
        self._engine = None
    self._initialized = False
    PostgreSQLConnectionManager._instance = None
```

这样 `close_db_manager()` 调用后，下次 `init_db_manager()` 能正确创建全新的实例和引擎。

**验证**：重启服务 → 调用 `POST /api/fetch/etf` → 再请求 `/api/overview`，数据正常返回。

---

## 建议改进

1. **锁定依赖版本**：在 `requirements.txt` 中使用 `==` 或 `~=` 指定精确版本，避免上游 breaking change
2. **将 `src/core/config.py` 加入 `.gitignore`**：只保留 `config/config.py.example`，防止凭据泄露
3. **同步模板文件**：每次修改 `config.py` 后，同步更新 `config.py.example`，确保导出变量一致
4. **清理死引用**：删除 `init_database.py` 中对 `fetch_data.py` 的调用，改为引用 `tushare_fetcher.init_db()`
5. **添加 CI 验证**：在 GitHub Actions 中增加一条最小启动测试，确保 clone 后能正常运行
6. **Token 配置统一**：`config.py` 应统一从 `.env` 读取 Token，避免硬编码敏感信息
7. **数据文件路径文档化**：`ALLSYMBOL.csv` 的期望路径 `data/external/` 应在 README 中明确说明
