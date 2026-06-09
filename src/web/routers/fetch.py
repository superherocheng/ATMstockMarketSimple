import os
import sys
import logging
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.core.db_manager_postgresql import get_conn, get_db_manager
from src.web.services.cache import _cache_invalidate
from src.core.trading_calendar import now_beijing, get_latest_trading_date, get_open_trade_dates
from src.core.db_manager_postgresql import close_db_manager, _ensure_db
from src.analysis import factor_engine, ic_analyzer
from config.config import DATA_DIR, INDEX_ETF, SECTOR_ETF, get_pro

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

router = APIRouter()

_fetch_lock = threading.Lock()
_fetch_status = {
    "running": False,
    "log": [],
    "started_at": None,
    "finished_at": None,
    "current_step": "",
    "progress": 0,
}


def _parse_progress(line):
    if "获取" in line and ("日线" in line or "份额" in line):
        return line.strip()
    if "进度:" in line:
        return line.strip()
    if line.startswith("[OK]") or line.startswith("[DONE]") or line.startswith("[SKIP]"):
        return line.strip()
    return ""


def _add_log(msg):
    """线程安全地添加日志"""
    with _fetch_lock:
        _fetch_status["log"].append(msg)
        if len(_fetch_status["log"]) > 500:
            _fetch_status["log"] = _fetch_status["log"][-300:]


def _run_subprocess(fetch_script, cmd, cwd, phase_label, progress_base, progress_total):
    """运行子进程并更新进度，返回是否成功"""
    _add_log(f"$ {' '.join(cmd)}")
    with _fetch_lock:
        _fetch_status["current_step"] = f"启动{phase_label}..."

    env = os.environ.copy()
    env["PYTHONPATH"] = cwd

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            text=True,
            bufsize=1,
            env=env,
        )
        for line in proc.stdout:
            stripped = line.rstrip()
            if not stripped:
                continue
            _add_log(stripped)
            step = _parse_progress(stripped)
            with _fetch_lock:
                if step:
                    _fetch_status["current_step"] = step
                done_count = sum(1 for l in _fetch_status["log"]
                                 if l.startswith("[OK]") or l.startswith("[SKIP]"))
                _fetch_status["progress"] = min(int(progress_base + done_count * progress_total), 99)

        proc.wait()
        return proc.returncode == 0
    except FileNotFoundError:
        _add_log(f"[ERROR] 找不到脚本: {fetch_script}")
        return False
    except Exception as e:
        _add_log(f"[ERROR] {e}")
        return False


def _run_fetch(task_type):
    """在子线程中运行数据获取"""
    with _fetch_lock:
        _fetch_status["running"] = True
        _fetch_status["log"] = []
        _fetch_status["started_at"] = now_beijing().strftime("%Y-%m-%d %H:%M:%S")
        _fetch_status["finished_at"] = None
        _fetch_status["progress"] = 0
        _fetch_status["current_step"] = "初始化..."
        _fetch_status["backtest_done"] = False

    close_db_manager()

    tushare_script = str(BASE_DIR.parent / "data_fetchers" / "tushare_fetcher.py")
    work_dir = str(BASE_DIR.parent.parent)

    try:
        if task_type == "all" or task_type == "tushare":
            cmd = [sys.executable, "-u", tushare_script, "--etf"]
            _run_subprocess(tushare_script, cmd, work_dir, "ETF数据", 0, 90)

            # ── 子进程跑完后，先重连数据库，再跑ETF份额更新（独立容错）──
            _ensure_db()
            _add_log("正在更新ETF份额数据...")
            with _fetch_lock:
                _fetch_status["current_step"] = "更新ETF份额..."
            try:
                share_result = api_etf_share_update()
                if isinstance(share_result, dict):
                    if share_result.get("status") == "updated":
                        _add_log(f"[OK] ETF份额更新成功: {share_result.get('message', '')}")
                    elif share_result.get("status") == "already_fresh":
                        _add_log(f"[SKIP] ETF份额已是最新")
                    elif share_result.get("status") == "data_not_ready":
                        _add_log(f"[HOLD] 部分ETF份额数据尚未就绪")
            except Exception as e:
                _add_log(f"[ERROR] ETF份额更新异常: {e}")

        elif task_type == "etf":
            cmd = [sys.executable, "-u", tushare_script, "--etf"]
            _run_subprocess(tushare_script, cmd, work_dir, "ETF数据", 0, 100)

        _add_log("[DONE] 数据获取完成！")

        # ── 检查份额数据截面完整性 ──
        # 因子计算依赖完整的截面数据。份额数据通常T+1才公布，
        # 如果最新交易日只有部分ETF有份额数据，说明截面不完整，
        # 此时计算因子会引入偏差（缺失ETF的flow因子=NaN），应跳过。
        try:
            _ensure_db()
            from config.config import SECTOR_ETF
            from sqlalchemy import text
            from src.core.db_manager_postgresql import get_conn
            with get_conn() as conn:

                # 找到最新的份额日期和日线日期
                share_max = conn.execute(text(
                    "SELECT MAX(trade_date) FROM etf_share"
                )).fetchone()[0]
                kline_max = conn.execute(text(
                    "SELECT MAX(trade_date) FROM sector_etf_daily"
                )).fetchone()[0]

                share_max_str = str(share_max).replace("-", "")
                kline_max_str = str(kline_max).replace("-", "")

                # 统计最新份额日期有多少个ETF
                share_count = conn.execute(text(
                    "SELECT COUNT(DISTINCT ts_code) FROM etf_share WHERE trade_date = :d"
                ), {"d": share_max}).fetchone()[0]

                total_sector = len(SECTOR_ETF)

                _add_log(f"[INFO] 最新日线日期: {kline_max_str}, 最新份额日期: {share_max_str}")
                _add_log(f"[INFO] 份额截面: {share_count}/{total_sector} 只ETF有数据")

                if share_count < total_sector:
                    _add_log(f"[INFO] 份额数据不完整（{share_count}/{total_sector}），因子子进程已运行，继续执行回测")
                    _add_log("[INFO] 份额数据通常T+1公布，此提示不影响因子计算结果")
        except Exception as e:
            _add_log(f"[WARN] 份额完整性检查失败: {e}，继续执行回测")

        # ── 回测阶段：因子计算+IC分析 ──
        try:
            _ensure_db()
        except Exception:
            pass

        backtest_start = time.time()
        _add_log("")
        _add_log("=" * 40)
        _add_log("开始运行回测：因子计算 + IC 分析")
        _add_log("=" * 40)

        with _fetch_lock:
            _fetch_status["current_step"] = "因子计算中..."
            _fetch_status["progress"] = 80

        try:
            factor_rows = factor_engine.compute_all_factors()
            _add_log(f"[OK] 因子计算完成: {factor_rows} 行")
        except Exception as e:
            _add_log(f"[ERROR] 因子计算失败: {e}")
            logger.error(f"因子计算失败: {e}", exc_info=True)

        with _fetch_lock:
            _fetch_status["current_step"] = "IC分析中..."
            _fetch_status["progress"] = 90

        try:
            ic_rows = ic_analyzer.compute_all_ic(log_func=_add_log)
            _add_log(f"[OK] IC分析完成: {ic_rows} 行")
        except Exception as e:
            _add_log(f"[ERROR] IC分析失败: {e}")
            logger.error(f"IC分析失败: {e}", exc_info=True)

        total_elapsed = time.time() - backtest_start
        _add_log(f"[DONE] 回测完成！总耗时约 {total_elapsed:.0f}s")

        # 投资建议预生成（缓存预热）
        try:
            from src.analysis.recommendation_engine import build_investment_recommendation
            for pid in ["short", "medium", "long"]:
                build_investment_recommendation(pid)
            _add_log("[OK] 投资建议已预生成（3个预设）")
        except Exception as e:
            _add_log(f"[WARN] 投资建议预生成失败: {e}")

        _cache_invalidate("etf", "overview", "analysis")
        with _fetch_lock:
            _fetch_status["backtest_done"] = True
            _fetch_status["progress"] = 100
            _fetch_status["current_step"] = "全部完成"
    except Exception as e:
        _add_log(f"[ERROR] {e}")
        logger.error(f"数据获取异常: {e}", exc_info=True)
    finally:
        with _fetch_lock:
            _fetch_status["running"] = False
            _fetch_status["finished_at"] = now_beijing().strftime("%Y-%m-%d %H:%M:%S")
            if not _fetch_status.get("backtest_done"):
                _fetch_status["current_step"] = "完成（回测跳过）"
        try:
            _ensure_db()
            _add_log("[OK] 数据库连接已恢复")
        except Exception as e:
            logger.error("数据库连接恢复失败: %s", e)


@router.post("/api/fetch/{task_type}")
async def api_fetch_data(task_type: str):
    if task_type not in ("all", "tushare", "etf"):
        return JSONResponse({"error": "无效的任务类型，只支持 ETF 数据更新"}, status_code=400)

    with _fetch_lock:
        if _fetch_status["running"]:
            return JSONResponse({
                "error": "已有任务正在运行",
                "current_step": _fetch_status["current_step"],
                "progress": _fetch_status["progress"],
            }, status_code=409)

    thread = threading.Thread(target=_run_fetch, args=(task_type,), daemon=True)
    thread.start()

    return {"message": f"数据获取任务已启动: {task_type}"}


@router.get("/api/fetch/status")
async def api_fetch_status():
    with _fetch_lock:
        return {
            "running": _fetch_status["running"],
            "log": list(_fetch_status["log"]),
            "started_at": _fetch_status["started_at"],
            "finished_at": _fetch_status["finished_at"],
            "current_step": _fetch_status["current_step"],
            "progress": _fetch_status["progress"],
            "backtest_done": _fetch_status.get("backtest_done", False),
        }


@router.get("/api/etf-share/status")
async def api_etf_share_status():
    """
    检查ETF份额数据状态
    
    返回：
    - latest_trading_date: 最新交易日
    - is_up_to_date: 是否已更新到最新
    - index_etf: 宽基ETF份额状态列表
    - sector_etf: 行业ETF份额状态列表
    - summary: 汇总信息
    """
    try:
        latest_td = get_latest_trading_date()
        if not latest_td:
            return JSONResponse({"error": "无法确定最新交易日"}, status_code=500)
        
        conn = get_conn()
        
        all_etf_codes = list(INDEX_ETF.keys()) + list(SECTOR_ETF.keys())
        placeholders = ",".join([f":p{i}" for i in range(len(all_etf_codes))])
        params = {f"p{i}": c for i, c in enumerate(all_etf_codes)}
        
        sql = f"""
            SELECT ts_code, MAX(trade_date) as max_date, COUNT(*) as cnt
            FROM etf_share
            WHERE ts_code IN ({placeholders})
            GROUP BY ts_code
        """
        results = conn.execute(text(sql), params).fetchall()
        db_dates = {row[0]: {"max_date": row[1], "count": row[2]} for row in results}
        conn.close()
        
        index_etf_status = []
        sector_etf_status = []
        
        for code, name in INDEX_ETF.items():
            info = db_dates.get(code, {"max_date": None, "count": 0})
            is_fresh = info["max_date"] and info["max_date"] >= latest_td
            index_etf_status.append({
                "code": code,
                "name": name,
                "max_date": info["max_date"],
                "count": info["count"],
                "is_fresh": is_fresh,
                "type": "宽基"
            })
        
        for code, name in SECTOR_ETF.items():
            info = db_dates.get(code, {"max_date": None, "count": 0})
            is_fresh = info["max_date"] and info["max_date"] >= latest_td
            sector_etf_status.append({
                "code": code,
                "name": name,
                "max_date": info["max_date"],
                "count": info["count"],
                "is_fresh": is_fresh,
                "type": "行业"
            })
        
        all_status = index_etf_status + sector_etf_status
        fresh_count = sum(1 for s in all_status if s["is_fresh"])
        total_count = len(all_status)
        not_fresh_list = [s for s in all_status if not s["is_fresh"]]
        
        return {
            "latest_trading_date": latest_td,
            "is_up_to_date": fresh_count == total_count,
            "index_etf": index_etf_status,
            "sector_etf": sector_etf_status,
            "summary": {
                "total": total_count,
                "fresh": fresh_count,
                "not_fresh": total_count - fresh_count,
                "not_fresh_codes": [{"code": s["code"], "name": s["name"], "max_date": s["max_date"]} for s in not_fresh_list]
            }
        }
    except Exception as e:
        logger.error(f"检查ETF份额状态失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


def _get_previous_trading_date(current_date_str):
    """获取前一个实际交易日（基于交易日历，正确处理周末/节假日）"""
    from src.core.trading_calendar import get_open_trade_dates
    dt = datetime.strptime(current_date_str, "%Y%m%d")
    start = (dt - timedelta(days=10)).strftime("%Y%m%d")
    dates = get_open_trade_dates(start, current_date_str)
    if len(dates) >= 2:
        return dates[-2]  # 倒数第二个是上一个交易日
    # fallback: 简单减1天
    return (dt - timedelta(days=1)).strftime("%Y%m%d")


def _fetch_etf_share_for_code(pro, ts_code, start_date):
    """获取单个ETF的份额数据"""
    try:
        df = pro.fund_share(ts_code=ts_code, start_date=start_date)
        if df is not None and len(df) > 0:
            df = df[["ts_code", "trade_date", "fd_share"]].copy()
            df = df.drop_duplicates(subset=["ts_code", "trade_date"], keep="last")
            df = df.sort_values(["ts_code", "trade_date"]).reset_index(drop=True)
            return df
    except Exception as e:
        logger.error(f"获取 {ts_code} 份额失败: {e}")
    return None


@router.post("/api/etf-share/update")
async def api_etf_share_update():
    """
    更新ETF份额数据
    
    逻辑：
    1. 检查所有ETF份额是否已是最新
    2. 如果已是最新，返回状态
    3. 如果不是，尝试从Tushare获取新数据
    4. 如果数据不足，返回哪些ETF数据还没更新
    5. 如果数据足够，更新数据库并返回完成
    """
    try:
        latest_td = get_latest_trading_date()
        if not latest_td:
            return JSONResponse({"error": "无法确定最新交易日"}, status_code=500)
        
        acceptable_min_td = _get_previous_trading_date(latest_td)
        
        conn = get_conn()
        
        all_etf = {**INDEX_ETF, **SECTOR_ETF}
        all_codes = list(all_etf.keys())
        
        placeholders = ",".join([f":p{i}" for i in range(len(all_codes))])
        params = {f"p{i}": c for i, c in enumerate(all_codes)}
        
        sql = f"""
            SELECT ts_code, MAX(trade_date) as max_date
            FROM etf_share
            WHERE ts_code IN ({placeholders})
            GROUP BY ts_code
        """
        results = conn.execute(text(sql), params).fetchall()
        db_dates = {row[0]: row[1] for row in results}
        
        need_update = []
        for code in all_codes:
            max_date = db_dates.get(code)
            if not max_date or max_date < latest_td:
                need_update.append(code)
        
        if not need_update:
            conn.close()
            return {
                "status": "already_fresh",
                "message": f"所有ETF份额数据已是最新 ({latest_td})",
                "latest_trading_date": latest_td,
                "total_etf": len(all_codes),
                "index_etf_count": len(INDEX_ETF),
                "sector_etf_count": len(SECTOR_ETF)
            }
        
        pro = get_pro()
        default_start = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=365)).strftime("%Y%m%d")
        
        fetched_data = {}
        not_ready = []
        
        for code in need_update:
            name = all_etf.get(code, code)
            existing_max = db_dates.get(code)
            start_date = existing_max or default_start
            
            df = _fetch_etf_share_for_code(pro, code, start_date)
            time.sleep(0.35)
            
            if df is not None and len(df) > 0:
                max_date = df["trade_date"].max()
                if max_date >= acceptable_min_td:
                    fetched_data[code] = df
                else:
                    not_ready.append({
                        "code": code,
                        "name": name,
                        "max_date": max_date,
                        "required_min": acceptable_min_td
                    })
            else:
                not_ready.append({
                    "code": code,
                    "name": name,
                    "max_date": existing_max,
                    "required_min": acceptable_min_td
                })
        
        if not_ready:
            conn.close()
            return {
                "status": "data_not_ready",
                "message": f"Tushare数据尚未更新到 {acceptable_min_td}，以下ETF份额数据不完整：",
                "latest_trading_date": latest_td,
                "acceptable_min_date": acceptable_min_td,
                "not_ready": not_ready,
                "ready_count": len(fetched_data),
                "total_need_update": len(need_update)
            }
        
        db = get_db_manager()
        updated_count = 0
        update_details = []
        
        for code, df in fetched_data.items():
            name = all_etf.get(code, code)
            existing_max = db_dates.get(code)
            
            if existing_max:
                n = db.upsert_dataframe(df, "etf_share", ["ts_code", "trade_date"])
            else:
                conn.execute(text("DELETE FROM etf_share WHERE ts_code=:p0"), {"p0": code})
                conn.commit()
                n = db.insert_dataframe(df, "etf_share", if_exists='append')
            
            updated_count += 1
            update_details.append({
                "code": code,
                "name": name,
                "rows": n,
                "new_max_date": df["trade_date"].max()
            })
        
        conn.close()
        _cache_invalidate("etf", "overview")
        
        return {
            "status": "updated",
            "message": f"成功更新 {updated_count} 只ETF份额数据",
            "latest_trading_date": latest_td,
            "updated_count": updated_count,
            "update_details": update_details
        }
        
    except Exception as e:
        logger.error(f"更新ETF份额失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/cache/invalidate")
async def api_cache_invalidate(category: str = None):
    """
    清除服务端全部缓存（两级缓存：Redis + 内存）

    可选参数 category：仅清除某一类缓存，如 'etf' / 'overview' / 'analysis'
    不带参数则清除所有缓存。
    """
    from src.web.services.cache import _cache_invalidate
    if category:
        _cache_invalidate(category)
        logger.info("缓存已清除 (category=%s)", category)
    else:
        _cache_invalidate("etf", "overview", "analysis")
        logger.info("所有缓存已清除")
    return {"status": "ok", "category": category or "all"}
