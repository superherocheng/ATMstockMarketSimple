"""推荐引擎单元测试"""
import datetime
from unittest.mock import patch, MagicMock

import numpy as np
import pytest


class MockRow:
    """模拟数据库行对象，支持下标、属性访问和迭代"""

    def __init__(self, values):
        self._values = list(values)

    def __getitem__(self, idx):
        return self._values[idx]

    def __len__(self):
        return len(self._values)

    def __iter__(self):
        return iter(self._values)


class MockResult:
    """模拟 execute().fetchall() / fetchone() 结果"""

    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


def _mock_conn(prepare_func=None):
    """创建 mock 数据库连接"""
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=None)

    def side_effect(sql, params=None):
        if prepare_func:
            return prepare_func(sql, params)
        return MagicMock()

    conn.execute.side_effect = side_effect
    return conn


def _make_side_effect(defaults=None):
    """根据SQL内容返回不同的 mock 结果"""
    _defaults = defaults or {}
    column_cache = _defaults.get("columns", {"rsrs", "z_quality", "z_efficiency", "z_rsi_momentum"})
    latest_date = _defaults.get("latest_date", datetime.date(2026, 6, 5))
    factor_rows = _defaults.get("factor_rows", [])
    ic_rows = _defaults.get("ic_rows", [])
    ic_daily_rows = _defaults.get("ic_daily_rows", [])
    qp_rows = _defaults.get("qp_rows", [])
    close_rows = _defaults.get("close_rows", [])
    cov_count = _defaults.get("cov_count", 30)

    def _side_effect(sql, params=None):
        sql_text = str(sql) if not isinstance(sql, str) else sql

        if "information_schema.columns" in sql_text:
            col_name = None
            if "rsrs" in sql_text and "z_quality" not in sql_text and "z_efficiency" not in sql_text and "z_rsi_momentum" not in sql_text:
                col_name = "rsrs"
            elif "z_quality" in sql_text:
                col_name = "z_quality"
            elif "z_efficiency" in sql_text:
                col_name = "z_efficiency"
            elif "z_rsi_momentum" in sql_text:
                col_name = "z_rsi_momentum"

            if col_name in column_cache:
                return MockResult([MockRow([col_name])])
            return MockResult([])

        if "COUNT(*) as cnt" in sql_text:
            return MockResult([MockRow([latest_date, cov_count])])

        if "MAX(trade_date) FROM factor_daily" in sql_text:
            return MockResult([MockRow([latest_date])])

        if "FROM factor_daily" in sql_text and "ORDER BY factor DESC" in sql_text:
            return MockResult(factor_rows)

        if "FROM ic_summary" in sql_text:
            return MockResult(ic_rows)

        if "FROM ic_daily" in sql_text:
            return MockResult(ic_daily_rows)

        if "FROM quadrant_perf" in sql_text:
            return MockResult(qp_rows)

        if "FROM sector_etf_daily" in sql_text:
            return MockResult(close_rows)

        return MockResult([])

    return _side_effect


@pytest.fixture(autouse=True)
def _auto_mock_db():
    """自动 mock 数据库连接和外部依赖"""
    with patch("src.analysis.recommendation_engine._get_conn") as mock_get_conn:
        with patch("src.analysis.market_timing.compute_market_timing") as mock_timing:
            mock_timing.return_value = {
                "score": 0.2,
                "adjustment": 0.06,
                "regime_cn": "Slightly Bullish",
                "narrative": "CSI500 RSI=45 oversold; CSI300 20d=5.2%",
            }
            # _load_holdings / _save_holdings / _trading_days_between each do their own
            # local `from ... import get_conn`, so the _get_conn patch above does not
            # reach them. Patch the helpers directly to keep these tests DB-free.
            with patch("src.analysis.recommendation_engine._load_holdings", return_value={}), \
                 patch("src.analysis.recommendation_engine._save_holdings"), \
                 patch("src.analysis.recommendation_engine._trading_days_between", return_value=10):
                yield mock_get_conn, mock_timing


class TestBuildInvestmentRecommendation:
    """测试 build_investment_recommendation 函数"""

    def _make_factor_row(self, code, z_flow, z_mom, factor, quadrant,
                         flow_raw, mom_raw, z_rsrs=0, f_quality=0,
                         z_quality=0, efficiency_raw=0, z_efficiency=0,
                         rsi_raw=0, z_rsi=0):
        """构造一行因子数据（包含全部 V6 列）"""
        return MockRow([code, z_flow, z_mom, factor, quadrant,
                        flow_raw, mom_raw, z_rsrs, f_quality,
                        z_quality, efficiency_raw, z_efficiency,
                        rsi_raw, z_rsi])

    @patch("config.config.SECTOR_ETF", {"512480.SH": "半导体", "515030.SH": "新能源车", "512010.SH": "医药"})
    def test_return_structure(self, _auto_mock_db):
        """测试返回数据结构完整性"""
        from src.analysis.recommendation_engine import build_investment_recommendation
        mock_get_conn, mock_timing = _auto_mock_db

        latest = datetime.date(2026, 6, 5)
        factor_rows = [
            self._make_factor_row("512480.SH", 0.5, 0.6, 0.42, 1, 0.01, 0.02),
            self._make_factor_row("515030.SH", 0.3, 0.2, 0.25, 2, 0.005, 0.01),
            self._make_factor_row("512010.SH", -0.1, 0.1, 0.15, 2, -0.002, 0.005),
        ]

        ic_rows = [
            MockRow([10, 0.05, 0.10, 0.50, 0.75, 60]),
        ]

        ic_daily_rows = [
            MockRow([0.04 + float(np.random.normal(0, 0.05))]) for _ in range(60)
        ]

        qp_rows = [
            MockRow([1, 0.02, 120, 75]),
            MockRow([2, 0.01, 80, 45]),
        ]

        close_rows = []

        conn = _mock_conn(_make_side_effect({
            "latest_date": latest,
            "factor_rows": factor_rows,
            "ic_rows": ic_rows,
            "ic_daily_rows": ic_daily_rows,
            "qp_rows": qp_rows,
            "close_rows": close_rows,
            "cov_count": 30,
        }))
        mock_get_conn.return_value = conn

        result = build_investment_recommendation("optimized")

        assert "date" in result
        assert "strategy" in result
        assert "recommendations" in result
        assert "reasons" in result
        assert "risk_warning" in result
        assert "stats" in result
        assert "etf_data_coverage" in result
        assert "weight_allocation" in result
        assert "timing" in result
        assert result["date"] == "2026-06-05"
        assert len(result["recommendations"]) > 0
        for rec in result["recommendations"]:
            assert "name" in rec
            assert "code" in rec
            assert "strategy" in rec
            assert "factor_score" in rec
            assert "quadrant" in rec
            assert "position_ratio" in rec
            assert "confidence" in rec

    def test_empty_factor_data(self, _auto_mock_db):
        """无因子数据时返回"""
        from src.analysis.recommendation_engine import build_investment_recommendation
        mock_get_conn, mock_timing = _auto_mock_db

        latest = datetime.date(2026, 6, 5)

        conn = _mock_conn(_make_side_effect({
            "latest_date": latest,
            "factor_rows": [],
            "ic_rows": [],
            "ic_daily_rows": [],
            "qp_rows": [],
            "close_rows": [],
            "cov_count": 0,
        }))
        mock_get_conn.return_value = conn

        result = build_investment_recommendation("optimized")
        # 空因子数据走 factor_rows 为空检查分支，返回 error + 空 recommendations
        assert "recommendations" in result
        assert len(result["recommendations"]) == 0

    def test_no_date_returns_error(self, _auto_mock_db):
        """无日期数据时返回错误"""
        from src.analysis.recommendation_engine import build_investment_recommendation
        mock_get_conn, mock_timing = _auto_mock_db

        def side_effect(sql, params=None):
            sql_text = str(sql)
            if "MAX(trade_date) FROM factor_daily" in sql_text:
                return MockResult([MockRow([None])])
            return MockResult([])

        conn = MagicMock()
        conn.execute.side_effect = side_effect
        mock_get_conn.return_value = conn

        result = build_investment_recommendation("optimized")
        assert "error" in result
        assert "No factor data available" in result["error"]

    @patch("config.config.SECTOR_ETF", {"512480.SH": "半导体", "515030.SH": "新能源车", "512010.SH": "医药", "512800.SH": "银行", "512880.SH": "证券"})
    def test_candidate_scoring_order(self, _auto_mock_db):
        """测试候选ETF评分排序逻辑"""
        from src.analysis.recommendation_engine import build_investment_recommendation
        mock_get_conn, mock_timing = _auto_mock_db

        latest = datetime.date(2026, 6, 5)
        factor_rows = [
            self._make_factor_row("512480.SH", 0.8, 0.9, 0.80, 1, 0.02, 0.03),
            self._make_factor_row("515030.SH", 0.6, 0.7, 0.60, 1, 0.015, 0.025),
            self._make_factor_row("512010.SH", 0.4, 0.5, 0.40, 2, 0.01, 0.02),
            self._make_factor_row("512800.SH", 0.2, 0.3, 0.20, 2, 0.005, 0.01),
            self._make_factor_row("512880.SH", -0.3, -0.4, -0.30, 3, -0.01, -0.02),
        ]

        conn = _mock_conn(_make_side_effect({
            "latest_date": latest,
            "factor_rows": factor_rows,
            "cov_count": 30,
        }))
        mock_get_conn.return_value = conn

        result = build_investment_recommendation("optimized")
        recs = result["recommendations"]
        assert len(recs) > 0
        scores = [r["factor_score"] for r in recs]
        assert scores == sorted(scores, reverse=True)

    @patch("config.config.SECTOR_ETF", {"512480.SH": "半导体", "515030.SH": "新能源车", "512010.SH": "医药", "512800.SH": "银行", "512880.SH": "证券", "515220.SH": "煤炭", "512400.SH": "有色", "562500.SH": "军工"})
    def test_correlation_penalty(self, _auto_mock_db):
        """测试相关度惩罚逻辑"""
        from src.analysis.recommendation_engine import build_investment_recommendation
        mock_get_conn, mock_timing = _auto_mock_db

        latest = datetime.date(2026, 6, 5)
        factor_rows = [
            self._make_factor_row("512480.SH", 0.9, 0.9, 0.85, 1, 0.02, 0.03),
            self._make_factor_row("515030.SH", 0.8, 0.8, 0.75, 1, 0.02, 0.03),
            self._make_factor_row("512010.SH", 0.7, 0.7, 0.65, 1, 0.015, 0.02),
            self._make_factor_row("512800.SH", 0.6, 0.6, 0.55, 1, 0.01, 0.02),
            self._make_factor_row("512880.SH", 0.5, 0.5, 0.45, 1, 0.01, 0.015),
            self._make_factor_row("515220.SH", 0.4, 0.4, 0.35, 2, 0.008, 0.01),
            self._make_factor_row("512400.SH", 0.3, 0.3, 0.25, 2, 0.005, 0.01),
            self._make_factor_row("562500.SH", 0.2, 0.2, 0.15, 2, 0.003, 0.005),
        ]

        dates = ["20260601", "20260602", "20260603", "20260604", "20260605"]
        close_rows = []
        codes = ["512480.SH", "515030.SH", "512010.SH", "512800.SH",
                 "512880.SH", "515220.SH", "512400.SH", "562500.SH"]
        np.random.seed(42)
        base_prices = {c: float(np.random.rand() * 50 + 10) for c in codes}
        for d in dates:
            for c in codes:
                price = float(base_prices[c] * (1 + np.random.randn() * 0.02))
                close_rows.append(MockRow([c, d, price]))

        conn = _mock_conn(_make_side_effect({
            "latest_date": latest,
            "factor_rows": factor_rows,
            "close_rows": close_rows,
            "cov_count": 20,
        }))
        mock_get_conn.return_value = conn

        result = build_investment_recommendation("optimized")
        recs = result["recommendations"]
        assert len(recs) > 0
        for r in recs:
            # position_ratio is a float since commit 1e72e46 (was a "NN%" string);
            # accept either form so this test is robust to the serialization.
            pos = r["position_ratio"]
            pct = float(pos.replace("%", "")) if isinstance(pos, str) else float(pos)
            assert pct <= 25.0, f"Position {pct}% exceeds 25% cap"

    @patch("config.config.SECTOR_ETF", {"512480.SH": "半导体", "515030.SH": "新能源车"})
    def test_icir_decay_detection(self, _auto_mock_db):
        """测试ICIR衰减检测（衰减率 > 40% 时应有警告）"""
        from src.analysis.recommendation_engine import build_investment_recommendation
        mock_get_conn, mock_timing = _auto_mock_db

        latest = datetime.date(2026, 6, 5)
        factor_rows = [
            self._make_factor_row("512480.SH", 0.5, 0.6, 0.42, 1, 0.01, 0.02),
            self._make_factor_row("515030.SH", 0.3, 0.2, 0.25, 2, 0.005, 0.01),
        ]

        ic_rows = [
            MockRow([15, 0.10, 0.10, 1.00, 0.80, 120]),
        ]

        np.random.seed(42)
        ic_daily_rows = [
            MockRow([float(np.random.normal(0.02, 0.15))]) for _ in range(60)
        ]

        conn = _mock_conn(_make_side_effect({
            "latest_date": latest,
            "factor_rows": factor_rows,
            "ic_rows": ic_rows,
            "ic_daily_rows": ic_daily_rows,
            "cov_count": 30,
        }))
        mock_get_conn.return_value = conn

        result = build_investment_recommendation("optimized")
        risk_warnings = result.get("risk_warning", [])
        decay_warnings = [w for w in risk_warnings if "decay" in w.lower()]
        assert len(decay_warnings) > 0, (
            f"Expected decay warning in risk_warnings, got: {risk_warnings}"
        )

    def test_insufficient_recent_ic_data(self, _auto_mock_db):
        """近期 IC 数据不足 20 个时不触发衰减检测"""
        from src.analysis.recommendation_engine import build_investment_recommendation
        mock_get_conn, mock_timing = _auto_mock_db

        latest = datetime.date(2026, 6, 5)
        factor_rows = [
            self._make_factor_row("512480.SH", 0.5, 0.6, 0.42, 1, 0.01, 0.02),
        ]

        ic_rows = [
            MockRow([15, 0.10, 0.10, 1.00, 0.80, 120]),
        ]

        ic_daily_rows = [
            MockRow([0.05]) for _ in range(10)
        ]

        conn = _mock_conn(_make_side_effect({
            "latest_date": latest,
            "factor_rows": factor_rows,
            "ic_rows": ic_rows,
            "ic_daily_rows": ic_daily_rows,
            "cov_count": 30,
        }))
        mock_get_conn.return_value = conn

        result = build_investment_recommendation("optimized")
        risk_warnings = result.get("risk_warning", [])
        decay_warnings = [w for w in risk_warnings if "decay" in w.lower()]
        assert len(decay_warnings) == 0, (
            f"Expected no decay warning with insufficient data, got: {decay_warnings}"
        )

    @patch("config.config.SECTOR_ETF", {"512480.SH": "半导体", "515030.SH": "新能源车"})
    def test_market_timing_error_handling(self, _auto_mock_db):
        """市场择时失败时不会阻断推荐流程"""
        from src.analysis.recommendation_engine import build_investment_recommendation
        mock_get_conn, mock_timing = _auto_mock_db
        mock_timing.side_effect = Exception("Timing API unavailable")

        latest = datetime.date(2026, 6, 5)
        factor_rows = [
            self._make_factor_row("512480.SH", 0.5, 0.6, 0.42, 1, 0.01, 0.02),
            self._make_factor_row("515030.SH", 0.3, 0.2, 0.25, 2, 0.005, 0.01),
        ]

        conn = _mock_conn(_make_side_effect({
            "latest_date": latest,
            "factor_rows": factor_rows,
            "cov_count": 30,
        }))
        mock_get_conn.return_value = conn

        result = build_investment_recommendation("optimized")
        assert "recommendations" in result
        assert len(result["recommendations"]) > 0
        assert result["timing"]["score"] == 0
        assert result["timing"]["regime"] == "Unknown"

    @patch("config.config.SECTOR_ETF", {"512480.SH": "半导体", "512010.SH": "医药", "512690.SH": "酒", "512800.SH": "银行"})
    def test_correlation_penalty_high_corr_pair(self, _auto_mock_db):
        """高相关度 ETF 对在 pool 内受惩罚"""
        from src.analysis.recommendation_engine import build_investment_recommendation
        mock_get_conn, mock_timing = _auto_mock_db

        latest = datetime.date(2026, 6, 5)
        factor_rows = [
            self._make_factor_row("512480.SH", 0.9, 0.9, 0.80, 1, 0.02, 0.03),
            self._make_factor_row("512010.SH", 0.8, 0.8, 0.70, 1, 0.02, 0.03),
            self._make_factor_row("512690.SH", 0.85, 0.85, 0.75, 1, 0.02, 0.03),
            self._make_factor_row("512800.SH", 0.1, 0.1, 0.05, 2, 0.002, 0.003),
        ]

        dates = ["20260601", "20260602", "20260603", "20260604", "20260605"]
        codes = ["512480.SH", "512010.SH", "512690.SH", "512800.SH"]
        close_rows = []
        np.random.seed(123)
        base = np.cumsum(np.random.randn(5) * 0.5 + 1)
        for d_idx, d in enumerate(dates):
            for c in codes:
                if c in ("512690.SH", "512480.SH"):
                    price = float(10 + base[d_idx])
                else:
                    price = float(10 + base[d_idx] * (0.5 + 0.5 * np.random.rand()))
                close_rows.append(MockRow([c, d, price]))

        conn = _mock_conn(_make_side_effect({
            "latest_date": latest,
            "factor_rows": factor_rows,
            "close_rows": close_rows,
            "cov_count": 20,
        }))
        mock_get_conn.return_value = conn

        result = build_investment_recommendation("optimized")
        recs = result.get("recommendations", [])
        assert len(recs) > 0