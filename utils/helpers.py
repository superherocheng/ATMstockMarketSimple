"""
通用辅助函数
============
提供项目级别的通用工具函数
"""
from pathlib import Path


def get_project_root() -> Path:
    """
    获取项目根目录
    
    Returns:
        项目根目录的 Path 对象
    """
    return Path(__file__).resolve().parent.parent


def ensure_dir(path: Path) -> Path:
    """
    确保目录存在，不存在则创建
    
    Args:
        path: 目录路径
    
    Returns:
        目录路径
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def format_number(num: float, decimal: int = 2) -> str:
    """
    格式化数字，添加千分位分隔符
    
    Args:
        num: 数字
        decimal: 小数位数
    
    Returns:
        格式化后的字符串
    """
    if num is None:
        return "-"
    
    if abs(num) >= 1e8:
        return f"{num / 1e8:.{decimal}f}亿"
    elif abs(num) >= 1e4:
        return f"{num / 1e4:.{decimal}f}万"
    else:
        return f"{num:,.{decimal}f}"


def format_percent(num: float, decimal: int = 2) -> str:
    """
    格式化百分比
    
    Args:
        num: 数字（小数形式）
        decimal: 小数位数
    
    Returns:
        格式化后的字符串
    """
    if num is None:
        return "-"
    
    return f"{num * 100:.{decimal}f}%"
