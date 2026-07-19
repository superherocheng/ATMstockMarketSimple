"""Response schemas for the ATMstockMarket API (Web-layer contract).

Single source of truth that Agent 4 (frontend TS interfaces) mirrors and
Agent 5 (Pydantic <-> TS field-parity) validates against.

Serialization rules — every cached payload passes through
src.core.db_manager_postgresql.safe_dict, so:
  * NaN / ±inf           -> null
  * numpy scalars        -> python float / int
  * date / datetime / pd.Timestamp -> ISO 8601 string ("YYYY-MM-DD")

Envelope rules:
  * Successful GETs return the modelled shape DIRECTLY (no {success,data} wrapper).
  * The {success,error,timestamp} envelope appears ONLY on errors (global handlers
    in app.py) and on the bare-dict {error: ...} returned by _cached_persistent
    when a compute fails.

response_model is intentionally NOT wired on the cached data endpoints: because
_cached_persistent can return {error: ...}, strict output validation would 500
on a compute failure instead of surfacing the error envelope. The models below
document the success-path shapes for OpenAPI / the frontend. (Agent 5 may add
Union[Model, ErrorEnvelope] response_models later if runtime typing is desired.)

Endpoints returning ECharts `option` objects (/api/analysis/factor-distribution,
ic-series, quadrant-heatmap, group-returns, rolling-icir) and the list/metadata
variants of /api/sector-etf, plus /api/investment-recommendation and
/api/market-timing, are raw dict — ECharts-driven, not modelled here. The
single-ETF detail endpoints (/api/index-etf/{code}, /api/sector-etf/{code}) ARE
modelled below via EtfDetail.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict

# Permissive base: keeps extra keys (no field-dropping) while declaring the contract.
class _Allow(BaseModel):
    model_config = ConfigDict(extra="allow")


# ── Overview  (GET /api/overview) ──────────────────────────────────
class OverviewBar(_Allow):
    ts_code: str
    name: str
    trade_date: Optional[str] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    pre_close: Optional[float] = None
    vol: Optional[float] = None
    amount: Optional[float] = None
    pct_chg: Optional[float] = None
    # Share-flow fields injected at runtime (overview.py) — declared here so the
    # contract is explicit and TS<->Pydantic drift is caught, not silently allowed.
    share_change_qty: Optional[float] = None
    share_change_pct: Optional[float] = None
    share_change_10d_qty: Optional[float] = None
    share_change_10d_pct: Optional[float] = None
    latest_share: Optional[float] = None
    share_date: Optional[str] = None


class OverviewResponse(_Allow):
    index_etf: list[OverviewBar]
    sector_summary: list[OverviewBar]


# ── ETF detail  (GET /api/index-etf/{code}, /api/sector-etf/{code}) ──
class KlineBar(_Allow):
    ts_code: Optional[str] = None
    trade_date: Optional[str] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    vol: Optional[float] = None
    amount: Optional[float] = None
    pre_close: Optional[float] = None
    pct_chg: Optional[float] = None


class SharePoint(_Allow):
    trade_date: Optional[str] = None
    fd_share: Optional[float] = None


class EtfDetail(_Allow):
    kline: list[KlineBar] = []
    shares: list[SharePoint] = []
    anomalies: dict = {}
    name: str = ""


# ── Heatmap  (GET /api/heatmap) ────────────────────────────────────
class HeatmapPoint(BaseModel):
    name: str
    ts_code: str
    pct_chg: float


# ── Sector cards  (GET /api/sector-cards) ──────────────────────────
class SectorCard(_Allow):
    ts_code: str
    name: str
    trade_date: Optional[str] = None
    pct_chg: float
    close: float
    amplitude: float
    sparkline: list[float]


# ── Analysis summary  (GET /api/analysis/summary) ──────────────────
class SummaryFactor(_Allow):
    code: str
    name: str
    factor: float
    quadrant: int
    weight: float = 0.0


class AnalysisSummaryResponse(_Allow):
    date: Optional[str] = None
    ic_mean: Optional[float] = None
    icir: Optional[float] = None
    ic_win_rate: Optional[float] = None
    sample_count: int = 0
    factor_validity: str = ""
    strong_buy: str = ""
    contrarian: str = ""
    q1_count: int = 0
    q2_count: int = 0
    latest_factors: list[SummaryFactor] = []


# ── Presets  (GET /api/analysis/presets, /api/analysis/ic-summary-all) ──
class PresetsResponse(BaseModel):
    presets: list[dict]
    default: str = "optimized"


class IcSummaryRow(_Allow):
    preset_id: str
    label: str
    forward_days: int
    ic_mean: Optional[float] = None
    ic_std: Optional[float] = None
    icir: Optional[float] = None
    ic_win_rate: Optional[float] = None
    sample_count: int = 0


class IcSummaryAllResponse(BaseModel):
    presets: list[IcSummaryRow]
    count: int


# ── Fetch status  (GET /api/fetch/status) ──────────────────────────
class FetchStatusResponse(BaseModel):
    running: bool
    log: list[str] = []
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    current_step: str = ""
    progress: int = 0
    backtest_done: bool = False


# ── Health  (GET /health) ──────────────────────────────────────────
class HealthResponse(_Allow):
    status: str
    timestamp: Optional[str] = None
    version: str = ""
    checks: dict = {}


# ── Data range  (GET /api/data-range) ──────────────────────────────
class DataRangeTable(_Allow):
    display_name: str
    exists: bool
    count: int
    min_date: Optional[str] = None
    max_date: Optional[str] = None
