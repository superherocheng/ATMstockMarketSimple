import logging
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from src.web.services.cache import _cached_persistent
from src.core.db_manager_postgresql import get_conn, query
from config.config import SECTOR_ETF

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()


@router.get("/heatmap", response_class=HTMLResponse)
async def page_heatmap(request: Request):
    return templates.TemplateResponse("heatmap.html", {"request": request})


def _compute_share_std_correlation():
    sector_codes = list(SECTOR_ETF.keys())
    sector_names = [SECTOR_ETF[c] for c in sector_codes]

    conn = get_conn()
    try:
        series_map = {}
        for code in sector_codes:
            rows = conn.execute(
                text(
                    "SELECT trade_date, fd_share FROM etf_share "
                    "WHERE ts_code=:code ORDER BY trade_date DESC LIMIT 30"
                ),
                {"code": code},
            ).fetchall()

            if len(rows) < 22:
                continue

            shares = [float(r[1]) for r in reversed(rows)]
            dates = [str(r[0]) for r in reversed(rows)]

            pct_changes = []
            for i in range(1, len(shares)):
                if shares[i - 1] > 0:
                    pct_changes.append(
                        (shares[i] - shares[i - 1]) / shares[i - 1] * 100
                    )
                else:
                    pct_changes.append(0.0)

            if len(pct_changes) < 20:
                continue

            rolling_std = []
            window = 10
            for i in range(window, len(pct_changes) + 1):
                chunk = pct_changes[i - window : i]
                mean_val = sum(chunk) / len(chunk)
                variance = sum((x - mean_val) ** 2 for x in chunk) / len(chunk)
                rolling_std.append(variance ** 0.5)

            last_20 = rolling_std[-20:]
            series_map[code] = last_20

        if len(series_map) < 2:
            return {"labels": [], "matrix": [], "error": "数据不足"}

        ordered_codes = [c for c in sector_codes if c in series_map]
        ordered_names = [SECTOR_ETF[c] for c in ordered_codes]
        data_matrix = np.array([series_map[c] for c in ordered_codes])

        n = len(ordered_codes)
        corr_matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                if i == j:
                    corr_matrix[i][j] = 1.0
                else:
                    s1 = data_matrix[i]
                    s2 = data_matrix[j]
                    if np.std(s1) == 0 or np.std(s2) == 0:
                        corr_matrix[i][j] = 0.0
                    else:
                        corr_matrix[i][j] = round(
                            float(np.corrcoef(s1, s2)[0, 1]), 4
                        )

        return {
            "labels": ordered_names,
            "codes": ordered_codes,
            "matrix": corr_matrix.tolist(),
        }
    finally:
        conn.close()


@router.get("/api/heatmap/share-std-correlation")
async def api_share_std_correlation():
    return _cached_persistent(
        "heatmap_share_std_corr", _compute_share_std_correlation, max_age_hours=4
    )


def _compute_kline_pivot_correlation():
    all_codes = ["510500.SH"] + list(SECTOR_ETF.keys())
    all_names = ["中证500ETF"] + [SECTOR_ETF[c] for c in SECTOR_ETF]

    conn = get_conn()
    try:
        series_map = {}
        for code in all_codes:
            table = "index_etf_daily" if code.startswith("510") else "sector_etf_daily"
            if code in SECTOR_ETF:
                table = "sector_etf_daily"

            rows = conn.execute(
                text(
                    f"SELECT trade_date, open, close, high, low FROM {table} "
                    f"WHERE ts_code=:code ORDER BY trade_date DESC LIMIT 25"
                ),
                {"code": code},
            ).fetchall()

            if len(rows) < 20:
                continue

            rows_list = list(reversed(rows))
            pivots = []
            for r in rows_list[-20:]:
                o = float(r[1] or 0)
                c = float(r[2] or 0)
                h = float(r[3] or 0)
                l = float(r[4] or 0)
                pivots.append((o + c + h + l) / 4.0)

            series_map[code] = pivots

        if len(series_map) < 2:
            return {"labels": [], "matrix": [], "error": "数据不足"}

        ordered_codes = [c for c in all_codes if c in series_map]
        ordered_names = []
        for c in ordered_codes:
            if c == "510500.SH":
                ordered_names.append("中证500ETF")
            else:
                ordered_names.append(SECTOR_ETF.get(c, c))

        data_matrix = np.array([series_map[c] for c in ordered_codes])

        n = len(ordered_codes)
        corr_matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                if i == j:
                    corr_matrix[i][j] = 1.0
                else:
                    s1 = data_matrix[i]
                    s2 = data_matrix[j]
                    if np.std(s1) == 0 or np.std(s2) == 0:
                        corr_matrix[i][j] = 0.0
                    else:
                        corr_matrix[i][j] = round(
                            float(np.corrcoef(s1, s2)[0, 1]), 4
                        )

        return {
            "labels": ordered_names,
            "codes": ordered_codes,
            "matrix": corr_matrix.tolist(),
        }
    finally:
        conn.close()


@router.get("/api/heatmap/kline-pivot-correlation")
async def api_kline_pivot_correlation():
    return _cached_persistent(
        "heatmap_kline_pivot_corr", _compute_kline_pivot_correlation, max_age_hours=4
    )
