from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, TypeVar, Generic, List, Union

# 定義通用類型變量
T = TypeVar('T')

class StandardResponse(BaseModel):
    """
    標準 API 響應模型
    
    用於返回統一格式的 API 響應，包含狀態、消息和數據
    """
    status: str = Field(..., description="響應狀態，通常為 'success' 或 'error'")
    message: Optional[str] = Field(None, description="響應消息，通常用於提供額外信息或錯誤詳情")
    data: Optional[Dict[str, Any]] = Field(None, description="響應數據")

class PaginatedResponse(BaseModel, Generic[T]):
    """
    分頁響應模型
    
    用於返回分頁數據的 API 響應
    """
    status: str = Field(..., description="響應狀態")
    message: Optional[str] = Field(None, description="響應消息")
    data: Optional[List[T]] = Field(None, description="分頁數據列表")
    total: int = Field(..., description="總記錄數")
    page: int = Field(..., description="當前頁碼")
    per_page: int = Field(..., description="每頁記錄數")
    total_pages: int = Field(..., description="總頁數")

class ErrorResponse(BaseModel):
    """
    錯誤響應模型
    
    用於返回錯誤信息的 API 響應
    """
    status: str = Field("error", description="錯誤狀態")
    message: str = Field(..., description="錯誤消息")
    error_code: Optional[str] = Field(None, description="錯誤代碼")
    details: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = Field(None, description="錯誤詳情") 