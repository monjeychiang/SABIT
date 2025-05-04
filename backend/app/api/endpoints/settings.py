from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Any, Dict, Optional, List
from pydantic import BaseModel
import logging

from ...db.database import get_db
from ...db.models import User, NotificationSetting, ExchangeAPI
from ...schemas.notification import NotificationSettingsUpdate, NotificationSettingsResponse
from ...core.security import oauth2_scheme, verify_token, encrypt_api_key, decrypt_api_key, get_current_user
from jose import JWTError
from ...schemas.settings import (
    ExchangeAPICreate, ExchangeAPIUpdate, ExchangeAPIResponse,
    ExchangeAPIListResponse, ApiKeyResponse
)

router = APIRouter()
logger = logging.getLogger(__name__)

# API密鑰更新模型
class ApiKeyUpdate(BaseModel):
    api_key: str
    api_secret: str

# 獲取用戶API密鑰（解密後）
def get_user_api_keys(user: User, db: Session) -> dict:
    """
    獲取用戶的所有交易所API密鑰
    
    將資料庫中的加密API密鑰解密後返回，供內部使用。
    此函數僅用於系統內部操作，不直接暴露給API。
    """
    api_keys = {}
    db_api_keys = db.query(ExchangeAPI).filter(ExchangeAPI.user_id == user.id).all()
    
    for api_key in db_api_keys:
        api_keys[api_key.exchange] = {
            "api_key": decrypt_api_key(api_key.api_key),
            "api_secret": decrypt_api_key(api_key.api_secret)
        }
    
    return api_keys

# 獲取用戶設置
@router.get("/api-keys", response_model=List[ApiKeyResponse])
async def get_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[ApiKeyResponse]:
    """
    獲取用戶所有交易所的API密鑰
    
    返回當前登入用戶在各交易所設置的API密鑰列表。
    出於安全考慮，API密鑰只返回末尾4位字符，不會返回完整密鑰。
    
    返回:
        包含每個交易所API密鑰部分資訊的列表
    """
    try:
        api_keys = []
        for exchange_api in current_user.exchange_apis:
            api_keys.append(
                ApiKeyResponse(
                    exchange=exchange_api.exchange,
                    api_key=exchange_api.api_key[-4:],  # 只返回最後4位
                    created_at=exchange_api.created_at,
                    updated_at=exchange_api.updated_at
                )
            )
        return api_keys
    except Exception as e:
        logger.error(f"獲取API密鑰失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"獲取API密鑰失敗: {str(e)}"
        )

# 更新API密鑰
@router.post("/api-keys", response_model=ExchangeAPIResponse)
async def create_api_key(
    api_key_data: ExchangeAPICreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ExchangeAPIResponse:
    """
    創建新的交易所API密鑰
    
    為當前用戶添加新的交易所API密鑰。每個用戶在每個交易所只能設置一組API密鑰，
    若需更改需使用更新端點。API密鑰和密鑰將使用加密算法存儲。
    
    參數:
        api_key_data: 包含交易所名稱、API密鑰和密鑰的資料
        
    返回:
        包含操作狀態和新建API密鑰資訊的響應
        
    錯誤:
        400: 相同交易所的API密鑰已存在
        500: 創建過程中出現伺服器錯誤
    """
    # 檢查是否已存在相同交易所的API密鑰
    existing_api = db.query(ExchangeAPI).filter(
        ExchangeAPI.user_id == current_user.id,
        ExchangeAPI.exchange == api_key_data.exchange
    ).first()
    
    if existing_api:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"已存在{api_key_data.exchange}的API密鑰"
        )
    
    # 加密API密鑰
    encrypted_key = encrypt_api_key(api_key_data.api_key)
    encrypted_secret = encrypt_api_key(api_key_data.api_secret)
    
    # 創建新的API密鑰記錄
    db_api_key = ExchangeAPI(
        user_id=current_user.id,
        exchange=api_key_data.exchange,
        api_key=encrypted_key,
        api_secret=encrypted_secret,
        description=api_key_data.description
    )
    
    try:
        db.add(db_api_key)
        db.commit()
        db.refresh(db_api_key)
        return {
            "success": True,
            "message": f"成功添加{api_key_data.exchange}的API密鑰",
            "data": db_api_key
        }
    except Exception as e:
        db.rollback()
        logger.error(f"創建API密鑰失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="創建API密鑰失敗"
        )

@router.put("/api-keys/{exchange}", response_model=ExchangeAPIResponse)
async def update_api_key(
    exchange: str,
    api_key_data: ExchangeAPIUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ExchangeAPIResponse:
    """
    更新交易所API密鑰
    
    更新用戶在指定交易所的API密鑰。支援部分更新，可以只更新密鑰或描述。
    更新的API密鑰將使用加密算法重新加密存儲。
    
    參數:
        exchange: 要更新的交易所名稱
        api_key_data: 包含要更新的欄位（可選）
        
    返回:
        包含操作狀態和更新後API密鑰資訊的響應
        
    錯誤:
        404: 指定交易所的API密鑰不存在
        500: 更新過程中出現伺服器錯誤
    """
    db_api_key = db.query(ExchangeAPI).filter(
        ExchangeAPI.user_id == current_user.id,
        ExchangeAPI.exchange == exchange
    ).first()
    
    if not db_api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到{exchange}的API密鑰"
        )
    
    try:
        if api_key_data.api_key:
            db_api_key.api_key = encrypt_api_key(api_key_data.api_key)
        if api_key_data.api_secret:
            db_api_key.api_secret = encrypt_api_key(api_key_data.api_secret)
        if api_key_data.description is not None:
            db_api_key.description = api_key_data.description
            
        db.commit()
        db.refresh(db_api_key)
        return {
            "success": True,
            "message": f"成功更新{exchange}的API密鑰",
            "data": db_api_key
        }
    except Exception as e:
        db.rollback()
        logger.error(f"更新API密鑰失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新API密鑰失敗"
        )

@router.delete("/api-keys/{exchange}", response_model=ExchangeAPIResponse)
async def delete_api_key(
    exchange: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ExchangeAPIResponse:
    """
    刪除交易所API密鑰
    
    永久刪除用戶在指定交易所設置的API密鑰。
    此操作不可逆，刪除後需要重新創建新的API密鑰。
    
    參數:
        exchange: 要刪除API密鑰的交易所名稱
        
    返回:
        包含操作狀態的響應
        
    錯誤:
        404: 指定交易所的API密鑰不存在
        500: 刪除過程中出現伺服器錯誤
    """
    db_api_key = db.query(ExchangeAPI).filter(
        ExchangeAPI.user_id == current_user.id,
        ExchangeAPI.exchange == exchange
    ).first()
    
    if not db_api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到{exchange}的API密鑰"
        )
    
    try:
        db.delete(db_api_key)
        db.commit()
        return {
            "success": True,
            "message": f"成功刪除{exchange}的API密鑰"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"刪除API密鑰失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="刪除API密鑰失敗"
        )

# 獲取通知設置
@router.get("/notifications", response_model=NotificationSettingsResponse)
def get_notification_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    獲取當前用戶的通知設置
    
    返回用戶的通知偏好設置，包括電子郵件通知、系統通知等各種通知類型的啟用狀態。
    若用戶尚未設置通知偏好，將返回系統默認設置。
    
    返回:
        用戶的通知設置詳情
    """
    # 檢查用戶是否已有通知設置
    if not current_user.notification_settings:
        # 如果沒有，創建默認設置
        notification_settings = NotificationSetting(user_id=current_user.id)
        db.add(notification_settings)
        db.commit()
        db.refresh(notification_settings)
    else:
        notification_settings = current_user.notification_settings
    
    return notification_settings

# 更新通知設置
@router.post("/notifications", response_model=NotificationSettingsResponse)
def update_notification_settings(
    settings: NotificationSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    更新用戶的通知設置
    
    允許用戶自定義各種通知偏好，包括是否接收特定類型的通知，
    以及通知的接收方式（電子郵件、系統通知、桌面推送等）。
    
    參數:
        settings: 包含用戶更新後通知偏好的對象
        
    返回:
        更新後的通知設置詳情
        
    錯誤:
        500: 更新過程中出現伺服器錯誤
    """
    try:
        # 檢查用戶是否已有通知設置
        if not current_user.notification_settings:
            # 如果沒有，創建新設置
            notification_settings = NotificationSetting(
                user_id=current_user.id,
                email_notifications=settings.email_notifications,
                trade_notifications=settings.trade_notifications,
                system_notifications=settings.system_notifications,
                desktop_notifications=settings.desktop_notifications,
                sound_notifications=settings.sound_notifications,
                notification_preferences=settings.notification_preferences
            )
            db.add(notification_settings)
        else:
            # 更新現有設置
            notification_settings = current_user.notification_settings
            notification_settings.email_notifications = settings.email_notifications
            notification_settings.trade_notifications = settings.trade_notifications
            notification_settings.system_notifications = settings.system_notifications
            notification_settings.desktop_notifications = settings.desktop_notifications
            notification_settings.sound_notifications = settings.sound_notifications
            notification_settings.notification_preferences = settings.notification_preferences
        
        db.commit()
        db.refresh(notification_settings)
        
        logger.info(f"用戶 {current_user.username} 已更新通知設置")
        return notification_settings
        
    except Exception as e:
        db.rollback()
        logger.error(f"更新通知設置時出錯: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新通知設置失敗"
        ) 