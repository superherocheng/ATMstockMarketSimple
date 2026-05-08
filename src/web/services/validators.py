import re
from datetime import datetime


def validate_ts_code(ts_code: str) -> bool:
    """验证股票代码格式"""
    if not ts_code or not isinstance(ts_code, str):
        return False
    pattern = r'^\d{6}\.(SH|SZ|BJ)$'
    return bool(re.match(pattern, ts_code.strip()))


def validate_date(date_str: str) -> bool:
    """验证日期格式 (YYYYMMDD)"""
    if not date_str or not isinstance(date_str, str):
        return False
    pattern = r'^\d{8}$'
    if not re.match(pattern, date_str.strip()):
        return False
    try:
        datetime.strptime(date_str, "%Y%m%d")
        return True
    except ValueError:
        return False


def validate_industry_name(industry_name: str) -> bool:
    """验证行业名称（防止注入）"""
    if not industry_name or not isinstance(industry_name, str):
        return False
    pattern = r'^[一-龥a-zA-Z0-9_\-]+$'
    return bool(re.match(pattern, industry_name.strip())) and len(industry_name) <= 50
