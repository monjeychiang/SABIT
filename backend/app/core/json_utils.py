"""
高性能 JSON 處理工具

此模組提供基於 orjson 的優化 JSON 處理功能，專為高頻交易 API 設計。
orjson 是一個用 Rust 編寫的高性能 JSON 庫，比 Python 內建的 json 模組快 2-3 倍。
"""

import orjson
from typing import Any, Dict, Optional, Union
from fastapi.responses import ORJSONResponse as BaseORJSONResponse


class OptimizedORJSONResponse(BaseORJSONResponse):
    """
    優化的 ORJSONResponse 類，專為高頻交易 API 設計。
    
    此類使用 orjson 的特定選項來優化 JSON 序列化：
    - ORJSON_OPTS.NON_STR_KEYS: 允許非字符串鍵（例如整數、元組）
    - ORJSON_OPTS.STRICT_INTEGER: 嚴格檢查整數範圍，避免精度損失
    - ORJSON_OPTS.NAIVE_UTC: 將 naive datetime 視為 UTC
    - ORJSON_OPTS.OMIT_MICROSECONDS: 省略微秒，減少數據大小
    """
    
    def render(self, content: Any) -> bytes:
        """
        使用優化的 orjson 選項渲染 JSON 響應。
        
        Args:
            content: 要序列化為 JSON 的內容
            
        Returns:
            bytes: 序列化後的 JSON 字節數據
        """
        return orjson.dumps(
            content,
            option=orjson.OPT_NON_STR_KEYS | 
                  orjson.OPT_STRICT_INTEGER | 
                  orjson.OPT_NAIVE_UTC | 
                  orjson.OPT_OMIT_MICROSECONDS
        )


def parse_json(data: Union[str, bytes]) -> Dict[str, Any]:
    """
    使用 orjson 高效解析 JSON 字符串。
    
    Args:
        data: JSON 字符串或字節數據
        
    Returns:
        Dict[str, Any]: 解析後的 JSON 對象
        
    Raises:
        ValueError: 如果 JSON 解析失敗
    """
    try:
        if isinstance(data, str):
            data = data.encode('utf-8')
        return orjson.loads(data)
    except (orjson.JSONDecodeError, TypeError) as e:
        raise ValueError(f"JSON 解析錯誤: {str(e)}")


def dump_json(obj: Any) -> bytes:
    """
    使用 orjson 高效序列化對象為 JSON 字節數據。
    
    Args:
        obj: 要序列化的對象
        
    Returns:
        bytes: 序列化後的 JSON 字節數據
    """
    return orjson.dumps(
        obj,
        option=orjson.OPT_NON_STR_KEYS | 
              orjson.OPT_STRICT_INTEGER | 
              orjson.OPT_NAIVE_UTC | 
              orjson.OPT_OMIT_MICROSECONDS
    )


def dump_json_str(obj: Any) -> str:
    """
    使用 orjson 高效序列化對象為 JSON 字符串。
    
    Args:
        obj: 要序列化的對象
        
    Returns:
        str: 序列化後的 JSON 字符串
    """
    return dump_json(obj).decode('utf-8') 