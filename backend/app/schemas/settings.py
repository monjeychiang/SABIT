from pydantic import BaseModel, Field, validator, model_validator
from typing import Optional, List
from datetime import datetime
from ..schemas.trading import ExchangeEnum

class ExchangeAPIBase(BaseModel):
    """交易所API基礎模型"""
    exchange: ExchangeEnum
    # HMAC-SHA256
    api_key: Optional[str] = Field(None, description="HMAC API Key")
    api_secret: Optional[str] = Field(None, description="HMAC API Secret")
    # Ed25519
    ed25519_key: Optional[str] = Field(None, description="Ed25519 公鑰")
    ed25519_secret: Optional[str] = Field(None, description="Ed25519 私鑰")
    description: Optional[str] = Field(None, description="API密鑰描述")

    @model_validator(mode='after')
    def validate_key_pairs(self):
        """
        驗證至少提供一種完整的密鑰對，並確保每種類型的密鑰對是成對提供的
        """
        # 檢查HMAC密鑰是否成對
        hmac_key = self.api_key
        hmac_secret = self.api_secret
        has_hmac = bool(hmac_key and hmac_secret)
        
        # 檢查Ed25519密鑰是否成對
        ed25519_key = self.ed25519_key
        ed25519_secret = self.ed25519_secret
        has_ed25519 = bool(ed25519_key and ed25519_secret)
        
        # 檢查是否至少有一種完整的密鑰對
        if not has_hmac and not has_ed25519:
            raise ValueError("至少需要提供一種完整的密鑰對 (HMAC-SHA256 或 Ed25519)")
        
        # 檢查HMAC密鑰是否完整
        if (hmac_key and not hmac_secret) or (not hmac_key and hmac_secret):
            raise ValueError("HMAC-SHA256 密鑰必須同時提供 api_key 和 api_secret")
        
        # 檢查Ed25519密鑰是否完整
        if (ed25519_key and not ed25519_secret) or (not ed25519_key and ed25519_secret):
            raise ValueError("Ed25519 密鑰必須同時提供 ed25519_key 和 ed25519_secret")
        
        return self

class ExchangeAPICreate(ExchangeAPIBase):
    """創建交易所API模型"""
    pass

class ExchangeAPIUpdate(BaseModel):
    """更新交易所API模型"""
    api_key: Optional[str] = Field(None, description="HMAC API Key")
    api_secret: Optional[str] = Field(None, description="HMAC API Secret")
    ed25519_key: Optional[str] = Field(None, description="Ed25519 公鑰")
    ed25519_secret: Optional[str] = Field(None, description="Ed25519 私鑰")
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
    has_hmac: bool  # 是否有 HMAC-SHA256 密鑰
    has_ed25519: bool  # 是否有 Ed25519 密鑰
    api_key: Optional[str] = None  # 只返回最後4位
    ed25519_key: Optional[str] = None  # 只返回最後4位
    created_at: datetime
    updated_at: Optional[datetime] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True 