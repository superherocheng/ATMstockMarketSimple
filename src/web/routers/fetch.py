import os
import sys
import logging
import subprocess
import threading
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.core.db_manager_postgresql import get_conn, reset_db_initialized
from src.web.services.cache import _cache_invalidate
from src.core.trading_calendar import now_beijing
from src.core.db_manager_postgresql import close_db_manager
from config.config import DATA_DIR

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


def _check_stock_info_exists():
    """检查 stock_info 表是否已有数据"""
    conn = None
    try:
        conn = get_conn()
        result = conn.execute(text("SELECT COUNT(*) FROM stock_info")).fetchone()
        count = result[0] if result else 0
        return count > 0
    except Exception:
        return False
    finally:
        if conn:
            conn.close()


def _load_allsymbol_data():
    """加载 ALLSYMBOL.csv 数据到数据库"""
    allsymbol_csv = DATA_DIR / "external" / "ALLSYMBOL.csv"

    if not allsymbol_csv.exists():
        _add_log("[SKIP] ALLSYMBOL.csv 文件不存在，跳过股票分类数据加载")
        return False

    if _check_stock_info_exists():
        _add_log("[SKIP] stock_info 表已有数据，跳过 ALLSYMBOL.csv 加载")
        return True

    _add_log("--- 开始加载股票分类数据 (ALLSYMBOL.csv) ---")

    load_script = str(BASE_DIR.parent / "scripts" / "load_allsymbol.py")
    work_dir = str(BASE_DIR.parent.parent)

    cmd = [sys.executable, "-u", load_script]
    success = _run_subprocess(load_script, cmd, work_dir, "股票分类数据", 0, 100)

    if success:
        _add_log("[OK] 股票分类数据加载完成")
    else:
        _add_log("[ERROR] 股票分类数据加载失败")

    return success


def _run_fetch(task_type):
    """在子线程中运行数据获取"""
    with _fetch_lock:
        _fetch_status["running"] = True
        _fetch_status["log"] = []
        _fetch_status["started_at"] = now_beijing().strftime("%Y-%m-%d %H:%M:%S")
        _fetch_status["finished_at"] = None
        _fetch_status["progress"] = 0
        _fetch_status["current_step"] = "初始化..."

    reset_db_initialized()
    close_db_manager()

    tushare_script = str(BASE_DIR.parent / "data_fetchers" / "tushare_fetcher.py")
    work_dir = str(BASE_DIR.parent.parent)

    try:
        if task_type == "all":
            _load_allsymbol_data()

            cmd = [sys.executable, "-u", tushare_script]
            _run_subprocess(tushare_script, cmd, work_dir, "Tushare", 10, 60)

        elif task_type == "tushare":
            cmd = [sys.executable, "-u", tushare_script]
            _run_subprocess(tushare_script, cmd, work_dir, "Tushare", 0, 100)

        elif task_type in ("etf", "stocks"):
            cmd = [sys.executable, "-u", tushare_script]
            if task_type == "etf":
                cmd.append("--etf")
            elif task_type == "stocks":
                cmd.append("--stocks")
            _run_subprocess(tushare_script, cmd, work_dir, "Tushare", 0, 100)

        _add_log("[DONE] 数据获取完成！")

        if task_type == "etf":
            _cache_invalidate("etf", "overview")
        elif task_type == "stocks":
            _cache_invalidate("overview")
        else:
            _cache_invalidate()
        with _fetch_lock:
            _fetch_status["progress"] = 100
    except Exception as e:
        _add_log(f"[ERROR] {e}")
    finally:
        with _fetch_lock:
            _fetch_status["running"] = False
            _fetch_status["finished_at"] = now_beijing().strftime("%Y-%m-%d %H:%M:%S")
            _fetch_status["current_step"] = "完成"


@router.post("/api/fetch/{task_type}")
async def api_fetch_data(task_type: str):
    if task_type not in ("all", "tushare", "etf", "stocks"):
        return JSONResponse({"error": "无效的任务类型"}, status_code=400)

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
        }
