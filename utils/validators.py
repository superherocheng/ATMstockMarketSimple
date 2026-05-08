"""
输入验证工具
============
提供各种输入数据的验证函数，防止SQL注入和格式错误
"""
import re
from datetime import datetime


def validate_ts_code(ts_code: str) -> str:
    """
    验证股票代码格式
    
    Args:
        ts_code: 股票代码，格式如 "000001.SZ"
    
    Returns:
        验证通过的股票代码
    
    Raises:
        ValueError: 格式不正确
    """
    if not ts_code:
        raise ValueError("股票代码不能为空")
    
    pattern = r'^\d{6}\.(SZ|SH|BJ)$'
    if not re.match(pattern, ts_code):
        raise ValueError(f"股票代码格式不正确: {ts_code}，应为 6位数字.(SZ|SH|BJ)")
    
    return ts_code


def validate_date(date_str: str) -> str:
    """
    验证日期格式
    
    Args:
        date_str: 日期字符串，格式如 "20240101"
    
    Returns:
        验证通过的日期字符串
    
    Raises:
        ValueError: 格式不正确
    """
    if not date_str:
        raise ValueError("日期不能为空")
    
    try:
        datetime.strptime(date_str, "%Y%m%d")
    except ValueError:
        raise ValueError(f"日期格式不正确: {date_str}，应为 YYYYMMDD")
    
    return date_str


def validate_industry_name(industry: str) -> str:
    """
    验证行业名称，防止SQL注入
    
    Args:
        industry: 行业名称
    
    Returns:
        验证通过的行业名称
    
    Raises:
        ValueError: 包含非法字符
    """
    if not industry:
        raise ValueError("行业名称不能为空")
    
    dangerous_chars = ["'", '"', ';', '--', '/*', '*/', 'xp_', 'exec', 'execute']
    for char in dangerous_chars:
        if char in industry.lower():
            raise ValueError(f"行业名称包含非法字符: {char}")
    
    return industry
