from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from ..schemas.trading import ExchangeEnum

class ExchangeAPIBase(BaseModel):
    """交易所API基礎模型"""
    exchange: ExchangeEnum
    api_key: str = Field(..., description="API Key")
    api_secret: str = Field(..., description="API Secret")
    description: Optional[str] = Field(None, description="API密鑰描述")

class ExchangeAPICreate(ExchangeAPIBase):
    """創建交易所API模型"""
    pass

class ExchangeAPIUpdate(BaseModel):
    """更新交易所API模型"""
    api_key: Optional[str] = Field(None, description="API Key")
    api_secret: Optional[str] = Field(None, description="API Secret")
    description: Optional[str] = Field(None, description="API密鑰描述")

class ExchangeAPIInDB(ExchangeAPIBase):
    """數據庫中的交易所API模型"""
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True

class ExchangeAPIResponse(BaseModel):
    """交易所API響應模型"""
    success: bool
    message: Optional[str] = None
    data: Optional[ExchangeAPIInDB] = None

class ExchangeAPIListResponse(BaseModel):
    """交易所API列表響應模型"""
    success: bool
    message: Optional[str] = None
    data: List[ExchangeAPIInDB]

class ApiKeyResponse(BaseModel):
    """API 密鑰響應模型"""
    exchange: ExchangeEnum
    api_key: str  # 只返回最後4位
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True 