from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from ..db.models.base import UserTag

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    confirm_password: str
    referrer_id: Optional[int] = None
    referral_code: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "username": "john_doe",
                "email": "john@example.com",
                "password": "strongpassword123",
                "confirm_password": "strongpassword123",
                "referral_code": "ABC123"  # 也可以使用推荐码
            }
        }

class UserUpdate(BaseModel):
    binance_api_key: Optional[str] = None
    binance_api_secret: Optional[str] = None

class UserTagUpdate(BaseModel):
    user_tag: UserTag

class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    is_active: bool
    is_verified: bool
    is_admin: bool
    user_tag: UserTag
    created_at: Optional[datetime] = None
    avatar_url: Optional[str] = None
    full_name: Optional[str] = None
    oauth_provider: Optional[str] = None
    referral_code: Optional[str] = None
    referrer_id: Optional[int] = None
    
    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class UserPublicInfo(BaseModel):
    """用户的公开信息模型
    
    此模型定义了可以公开展示给其他用户的用户信息字段集合，
    不包含敏感信息如电子邮件、验证状态等。
    """
    id: int
    username: str
    created_at: Optional[datetime] = None
    avatar_url: Optional[str] = None
    full_name: Optional[str] = None
    
    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None

class RefreshToken(BaseModel):
    refresh_token: str = Field(..., description="用於刷新訪問令牌的刷新令牌")

class RefreshTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="訪問令牌過期時間（秒）")
    refresh_token: Optional[str] = None
    refresh_token_expires_in: Optional[int] = Field(None, description="刷新令牌過期時間（秒）") 