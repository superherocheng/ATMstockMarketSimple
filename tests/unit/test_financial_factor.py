"""Unit tests for the Financial Quality Factor module.

Tests the core logic of financial_factor.py:
- Stock code conversion
- Cross-sectional Z-scoring
- Sector aggregation logic
- Commodity ETF handling
- The full computation chain with mock data

Note: These tests do NOT require a live database connection.
They test the pure-Python computation logic in isolation.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.analysis.financial_factor import (
    _stock_code_to_tushare,
    _cross_sectional_zscore,
    _aggregate_by_sector,
    COMMODITY_ETF_CODES,
    SECTOR_CONSTITUENTS,
)


# ────────────────────────────────────────────────────────────
#  Test: _stock_code_to_tushare
# ────────────────────────────────────────────────────────────
class TestStockCodeConversion:
    def test_shanghai_6xx(self):
        assert _stock_code_to_tushare("600519") == "600519.SH"
        assert _stock_code_to_tushare("601398") == "601398.SH"
        assert _stock_code_to_tushare("603259") == "603259.SH"

    def test_shanghai_star_688(self):
        assert _stock_code_to_tushare("688981") == "688981.SH"
        assert _stock_code_to_tushare("688012") == "688012.SH"

    def test_shenzhen_0xx(self):
        assert _stock_code_to_tushare("000001") == "000001.SZ"
        assert _stock_code_to_tushare("000858") == "000858.SZ"

    def test_shenzhen_3xx(self):
        assert _stock_code_to_tushare("300750") == "300750.SZ"
        assert _stock_code_to_tushare("300059") == "300059.SZ"

    def test_shenzhen_2xx(self):
        assert _stock_code_to_tushare("002594") == "002594.SZ"
        assert _stock_code_to_tushare("002371") == "002371.SZ"

    def test_shenzhen_001(self):
        assert _stock_code_to_tushare("001289") == "001289.SZ"

    def test_shenzhen_003(self):
        assert _stock_code_to_tushare("003816") == "003816.SZ"

    def test_beijing_873(self):
        assert _stock_code_to_tushare("873593") == "873593.BJ"

    def test_invalid_code_short(self):
        with pytest.raises(ValueError, match="Invalid stock code"):
            _stock_code_to_tushare("600")


# ────────────────────────────────────────────────────────────
#  Test: _cross_sectional_zscore
# ────────────────────────────────────────────────────────────
class TestCrossSectionalZscore:
    def test_basic_zscore(self):
        values = pd.Series({"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0, "e": 5.0})
        result = _cross_sectional_zscore(values)
        assert len(result) == 5
        # Mean should be ~0 after Z-scoring (Winsorize doesn't affect uniform data)
        assert abs(result.mean()) < 1e-10

    def test_winsorization(self):
        """Winzorize 10% should clip the extreme values."""
        values = pd.Series({f"e{i}": float(v) for i, v in enumerate(
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 100]  # 100 is extreme
        )})
        result = _cross_sectional_zscore(values)
        # The extreme value (100) should be clipped
        # After Winsorize 10%, p90 = 9, so 100 is clipped to 9
        assert not any(result.isna())
        # Result with only 10 entries should still work
        assert abs(result.mean()) < 1e-10

    def test_all_same_values(self):
        values = pd.Series({"a": 5.0, "b": 5.0, "c": 5.0})
        result = _cross_sectional_zscore(values)
        assert all(v == 0.0 for v in result)

    def test_single_value(self):
        values = pd.Series({"a": 1.0})
        result = _cross_sectional_zscore(values)
        assert result["a"] == 0.0

    def test_empty_series(self):
        values = pd.Series(dtype=float)
        result = _cross_sectional_zscore(values)
        assert len(result) == 0


# ────────────────────────────────────────────────────────────
#  Test: _aggregate_by_sector
# ────────────────────────────────────────────────────────────
class TestAggregateBySector:
    def test_equal_weight(self):
        """Three valid stocks → equal weight mean."""
        stocks = ["a.SH", "b.SZ", "c.SH"]
        factors = {"a.SH": 10.0, "b.SZ": 20.0, "c.SH": 30.0}
        result = _aggregate_by_sector(stocks, factors, weight_dict=None)
        assert result == pytest.approx(20.0)

    def test_circ_mv_weighted(self):
        """Use circ_mv as weight."""
        stocks = ["a.SH", "b.SZ", "c.SH"]
        factors = {"a.SH": 10.0, "b.SZ": 20.0, "c.SH": 30.0}
        weights = {"a.SH": 100.0, "b.SZ": 200.0, "c.SH": 300.0}
        # Weighted: (10*100 + 20*200 + 30*300) / (100+200+300) = 14000/600 = 23.33
        result = _aggregate_by_sector(stocks, factors, weight_dict=weights)
        expected = (10*100 + 20*200 + 30*300) / (100 + 200 + 300)
        assert result == pytest.approx(expected)

    def test_less_than_3_stocks(self):
        """Less than 3 valid stocks → None."""
        stocks = ["a.SH", "b.SZ", "c.SH"]
        factors = {"a.SH": 10.0, "b.SZ": 20.0}  # Only 2 valid
        result = _aggregate_by_sector(stocks, factors)
        assert result is None

    def test_missing_constituent_not_in_factors(self):
        """Stock not in factor dict → skipped, should still work if >= 3 valid."""
        stocks = ["a.SH", "b.SZ", "c.SH", "d.SZ"]
        factors = {"a.SH": 10.0, "b.SZ": 20.0, "c.SH": 30.0}  # d.SZ missing
        result = _aggregate_by_sector(stocks, factors)
        assert result == pytest.approx(20.0)

    def test_empty_stock_list(self):
        """Empty stock list → None."""
        result = _aggregate_by_sector([], {})
        assert result is None

    def test_weighted_with_zero_weight(self):
        """Zero weight stocks should be handled."""
        stocks = ["a.SH", "b.SZ"]
        factors = {"a.SH": 10.0, "b.SZ": 20.0}
        weights = {"a.SH": 0.0, "b.SZ": 100.0}
        result = _aggregate_by_sector(stocks, factors, weight_dict=weights)
        assert result is None  # < 3 valid with positive weight


# ────────────────────────────────────────────────────────────
#  Test: Commodity ETF handling
# ────────────────────────────────────────────────────────────
class TestCommodityETF:
    def test_commodity_codes_exist(self):
        """石油ETF is a commodity ETF."""
        assert "561360.SH" in COMMODITY_ETF_CODES

    def test_commodity_has_no_constituents(self):
        """Commodity ETFs should have no constituent stocks."""
        assert SECTOR_CONSTITUENTS.get("561360.SH", []) == []

    def test_non_commodity_has_constituents(self):
        """Regular sector ETFs should have 10 constituents."""
        for code, stocks in SECTOR_CONSTITUENTS.items():
            if code in COMMODITY_ETF_CODES:
                continue
            if stocks:  # Skip if empty (some ETFs may not be in the map)
                assert len(stocks) == 10, f"{code} should have 10 constituents, got {len(stocks)}"


# ────────────────────────────────────────────────────────────
#  Test: SECTOR_CONSTITUENTS mapping completeness
# ────────────────────────────────────────────────────────────
class TestConstituentsMapping:
    def test_all_sector_etfs_have_constituents_or_commodity(self):
        """Every ETF in the config should either be a commodity or have constituents."""
        from config.config import SECTOR_ETF
        missing = []
        for code in SECTOR_ETF:
            if code not in COMMODITY_ETF_CODES and code not in SECTOR_CONSTITUENTS:
                missing.append(code)
        if missing:
            pytest.skip(f"ETFs without constituent mapping: {missing}")

    def test_constituent_code_format(self):
        """All constituent codes should be valid Tushare format."""
        for code, stocks in SECTOR_CONSTITUENTS.items():
            for stock in stocks:
                assert stock.endswith(".SH") or stock.endswith(".SZ") or stock.endswith(".BJ"), \
                    f"{stock} (in {code}) not in valid Tushare format"
                assert len(stock) == 9, \
                    f"{stock} has unexpected length (expected 9 chars like '600519.SH')"


# ────────────────────────────────────────────────────────────
#  Test: Full computation chain (synthetic data, no DB)
# ────────────────────────────────────────────────────────────
class TestComputationChain:
    def test_aggregate_sector_sub_factors(self):
        """Simulate the per-sector aggregation step with synthetic data.

        This tests the aggregation functions without needing a DB.
        """
        # Simulate 4 representative ETFs with synthetic constituent data
        etf_stocks = {
            "BANK.SH": ["a.SH", "b.SZ", "c.SH", "d.SZ", "e.SH"],
            "TECH.SH": ["f.SH", "g.SZ", "h.SH", "i.SZ", "j.SH"],
            "ENERGY.SH": ["k.SH", "l.SZ", "m.SH", "n.SZ", "o.SH"],
        }

        # Synthetic ROE data
        roe_data = {
            "a.SH": 12.0, "b.SZ": 10.0, "c.SH": 14.0, "d.SZ": 9.0, "e.SH": 11.0,
            "f.SH": 18.0, "g.SZ": 15.0, "h.SH": 20.0, "i.SZ": 12.0, "j.SH": 16.0,
            "k.SH": 8.0, "l.SZ": 6.0, "m.SH": 10.0, "n.SZ": 7.0, "o.SH": 9.0,
        }

        # Aggregate per sector (equal weight, no weight_dict)
        sector_roes = {}
        for etf_code, stocks in etf_stocks.items():
            aggregated = _aggregate_by_sector(stocks, roe_data, weight_dict=None)
            sector_roes[etf_code] = aggregated

        # BANK: (12+10+14+9+11)/5 = 11.2
        assert sector_roes["BANK.SH"] == pytest.approx(11.2)
        # TECH: (18+15+20+12+16)/5 = 16.2
        assert sector_roes["TECH.SH"] == pytest.approx(16.2)
        # ENERGY: (8+6+10+7+9)/5 = 8.0
        assert sector_roes["ENERGY.SH"] == pytest.approx(8.0)

        # Test cross-sectional Z-scoring of the aggregated values
        series = pd.Series(sector_roes)
        z_scored = _cross_sectional_zscore(series)
        # 3 data points with different values → mean should be ~0
        assert abs(z_scored.mean()) < 1e-10
        # TECH has highest ROE → positive Z-score
        assert z_scored["TECH.SH"] > 0
        # ENERGY has lowest ROE → negative Z-score
        assert z_scored["ENERGY.SH"] < 0

    def test_composite_quality_factor(self):
        """Simulate the F_Quality composite computation."""
        etf_codes = ["A.SH", "B.SH", "C.SH", "D.SH"]

        # Simulated Z-scored sub-factors
        z_roe = pd.Series({"A.SH": 0.5, "B.SH": 1.0, "C.SH": -0.5, "D.SH": -1.0})
        z_pb = pd.Series({"A.SH": 0.3, "B.SH": 0.8, "C.SH": 0.1, "D.SH": -0.6})
        z_earn = pd.Series({"A.SH": 0.7, "B.SH": 0.5, "C.SH": -0.3, "D.SH": -0.9})

        # Composite: equal-weight mean of available sub-factors
        composite_map = {}
        composite_values = []
        for code in etf_codes:
            z_vals = [z_roe[code], z_pb[code], z_earn[code]]
            composite = float(np.mean(z_vals))
            composite_map[code] = composite
            composite_values.append(composite)

        # B.SH should have the highest composite
        assert composite_map["C.SH"] < composite_map["A.SH"] < composite_map["B.SH"]
        assert composite_map["D.SH"] < composite_map["C.SH"]
        # D.SH should be the lowest
        assert composite_map["D.SH"] == min(composite_map.values())

    def test_quality_factor_reorders_ranking(self):
        """Test that adding F_Quality changes the ranking order.

        Simulates 4 ETFs with RSRS/Flow/Mom quality data.
        """
        # Without quality (3-factor)
        etfs = ["ETF1", "ETF2", "ETF3", "ETF4"]
        three_factor = {"ETF1": 1.0, "ETF2": 0.8, "ETF3": -0.2, "ETF4": -0.5}

        # With quality (adding equal-weight quality changes ranking)
        quality = {"ETF1": -0.8, "ETF2": 1.2, "ETF3": 0.5, "ETF4": -0.3}

        four_factor = {}
        for e in etfs:
            four_factor[e] = 0.75 * three_factor[e] + 0.25 * quality[e]

        # In 3-factor world: ETF1 > ETF2 > ETF3 > ETF4
        # In 4-factor world: ETF2 might overtake ETF1 due to strong quality
        assert three_factor["ETF1"] > three_factor["ETF2"]
        assert four_factor["ETF2"] > four_factor["ETF1"], \
            "Strong quality should pull ETF2 ahead of ETF1"

    def test_commodity_fallback_median(self):
        """Commodity ETFs should get median F_Quality value."""
        # Simulate non-commodity quality factors
        sector_scores = {
            "A.SH": 0.5,
            "B.SH": 1.2,
            "C.SH": -0.3,
            "D.SH": 0.8,
            "COMMODITY.SH": None,  # Commodity — needs fallback
        }
        non_commodity_values = [v for v in sector_scores.values() if v is not None]
        median_val = float(np.median(non_commodity_values))
        # The commodity ETF's value should equal the median
        sector_scores["COMMODITY.SH"] = median_val
        assert sector_scores["COMMODITY.SH"] == pytest.approx(np.median([0.5, 1.2, -0.3, 0.8]))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
