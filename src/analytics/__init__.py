"""
ATMstockMarket 分析模块
======================
提供 BARRA 多因子分析、个股分析、ETF 分析等功能
"""
from src.analytics.barra import (
    calc_industry_factors,
    calc_momentum_factors,
    calc_size_factors,
    calc_style_factors,
    calc_barra_summary,
)

__all__ = [
    "calc_industry_factors",
    "calc_momentum_factors",
    "calc_size_factors",
    "calc_style_factors",
    "calc_barra_summary",
]
