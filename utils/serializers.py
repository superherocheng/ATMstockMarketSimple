"""
序列化工具
==========
提供安全的数据序列化函数，处理 NaN、inf 等特殊值
"""
import json
import math
from typing import Any
import pandas as pd
import numpy as np


def safe_json(obj: Any) -> Any:
    """
    安全的JSON序列化，处理 NaN、inf 等特殊值
    
    Args:
        obj: 需要序列化的对象
    
    Returns:
        可JSON序列化的对象
    """
    if obj is None:
        return None
    
    if isinstance(obj, (pd.DataFrame, pd.Series)):
        obj = obj.where(pd.notnull(obj), None)
        obj = obj.replace([np.inf, -np.inf], None)
        if isinstance(obj, pd.DataFrame):
            return obj.to_dict(orient="records")
        else:
            return obj.tolist()
    
    if isinstance(obj, (list, tuple)):
        return [safe_json(item) for item in obj]
    
    if isinstance(obj, dict):
        return {key: safe_json(value) for key, value in obj.items()}
    
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    
    if isinstance(obj, np.floating):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)
    
    if isinstance(obj, np.integer):
        return int(obj)
    
    if isinstance(obj, np.ndarray):
        return safe_json(obj.tolist())
    
    return obj


def safe_json_dumps(obj: Any, **kwargs) -> str:
    """
    安全的JSON序列化为字符串
    
    Args:
        obj: 需要序列化的对象
        **kwargs: json.dumps 的其他参数
    
    Returns:
        JSON字符串
    """
    return json.dumps(safe_json(obj), **kwargs, ensure_ascii=False)
