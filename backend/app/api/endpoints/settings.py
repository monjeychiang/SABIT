from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Response, Cookie
from sqlalchemy.orm import Session
from typing import Any, Dict, Optional, List
from pydantic import BaseModel
import logging
import os
import uuid
import shutil
from pathlib import Path
from PIL import Image
import io
import json

from ...db.database import get_db
from ...db.models import User, ExchangeAPI
from ...schemas.notification import NotificationSettingsUpdate, NotificationSettingsResponse
from ...core.security import oauth2_scheme, verify_token, encrypt_api_key, decrypt_api_key, get_current_user
from jose import JWTError
from ...schemas.settings import (
    ExchangeAPICreate, ExchangeAPIUpdate, ExchangeAPIResponse,
    ExchangeAPIListResponse, ApiKeyResponse
)

# 获取当前代码文件的绝对路径
current_file_path = Path(__file__).resolve()
# 获取后端目录路径
backend_dir = current_file_path.parent.parent.parent.parent
# 构建静态文件中的头像目录路径
avatar_dir = backend_dir / "static" / "avatars"
# 确保头像目录存在
avatar_dir.mkdir(parents=True, exist_ok=True)

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
        api_keys[api_key.exchange] = {}
        
        # 添加 HMAC-SHA256 密鑰（如果存在）
        if api_key.api_key:
            api_keys[api_key.exchange]["hmac"] = {
                "api_key": decrypt_api_key(api_key.api_key),
                "api_secret": decrypt_api_key(api_key.api_secret)
            }
        
        # 添加 Ed25519 密鑰（如果存在）
        if api_key.ed25519_key:
            api_keys[api_key.exchange]["ed25519"] = {
                "public_key": decrypt_api_key(api_key.ed25519_key),
                "private_key": decrypt_api_key(api_key.ed25519_secret)
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
    返回結果包括兩種密鑰類型（HMAC-SHA256 和 Ed25519）的存在狀態。
    
    返回:
        包含每個交易所API密鑰部分資訊的列表
    """
    try:
        api_keys = []
        for exchange_api in current_user.exchange_apis:
            # 初始化返回項目，確保所有必填字段都有值
            response_item = ApiKeyResponse(
                exchange=exchange_api.exchange,
                has_hmac=bool(exchange_api.api_key),
                has_ed25519=bool(exchange_api.ed25519_key),
                created_at=exchange_api.created_at,
                updated_at=exchange_api.updated_at,
                description=exchange_api.description or "",
                api_key=None,
                ed25519_key=None
            )
            
            # 只在密鑰存在時添加最後4位
            if exchange_api.api_key:
                try:
                    decrypted_key = decrypt_api_key(exchange_api.api_key)
                    response_item.api_key = "•••••••" + decrypted_key[-4:] if len(decrypted_key) >= 4 else "•••••••"
                except Exception as e:
                    logger.warning(f"解密 API 密鑰失敗: {str(e)}")
                    response_item.api_key = "•••••••" + exchange_api.api_key[-4:] if len(exchange_api.api_key) >= 4 else "•••••••"
                    
            if exchange_api.ed25519_key:
                try:
                    decrypted_key = decrypt_api_key(exchange_api.ed25519_key)
                    response_item.ed25519_key = "•••••••" + decrypted_key[-4:] if len(decrypted_key) >= 4 else "•••••••"
                except Exception as e:
                    logger.warning(f"解密 Ed25519 密鑰失敗: {str(e)}")
                    response_item.ed25519_key = "•••••••" + exchange_api.ed25519_key[-4:] if len(exchange_api.ed25519_key) >= 4 else "•••••••"
                
            api_keys.append(response_item)
            
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
    若已存在則會更新現有密鑰。API密鑰和密鑰將使用加密算法存儲。
    
    支持同時設置 HMAC-SHA256 和 Ed25519 兩種類型的密鑰，可以只提供一種類型。
    
    參數:
        api_key_data: 包含交易所名稱、API密鑰和密鑰的資料
        
    返回:
        包含操作狀態和新建/更新API密鑰資訊的響應
        
    錯誤:
        500: 創建過程中出現伺服器錯誤
    """
    # 檢查是否已存在相同交易所的API密鑰
    existing_api = db.query(ExchangeAPI).filter(
        ExchangeAPI.user_id == current_user.id,
        ExchangeAPI.exchange == api_key_data.exchange
    ).first()
    
    # 如果已存在，則調用更新接口而不是創建新記錄
    if existing_api:
        # 創建更新用的數據模型
        update_data = ExchangeAPIUpdate(
            api_key=api_key_data.api_key,
            api_secret=api_key_data.api_secret,
            ed25519_key=api_key_data.ed25519_key,
            ed25519_secret=api_key_data.ed25519_secret,
            description=api_key_data.description
        )
        
        # 轉到更新函數處理
        return await update_api_key(
            exchange=api_key_data.exchange,
            api_key_data=update_data,
            db=db,
            current_user=current_user
        )
    
    # 創建新的API密鑰記錄
    db_api_key = ExchangeAPI(
        user_id=current_user.id,
        exchange=api_key_data.exchange,
        description=api_key_data.description
    )
    
    # 添加 HMAC-SHA256 密鑰（如果提供）
    if api_key_data.api_key:
        db_api_key.api_key = encrypt_api_key(api_key_data.api_key)
    if api_key_data.api_secret:
        db_api_key.api_secret = encrypt_api_key(api_key_data.api_secret)
    
    # 添加 Ed25519 密鑰（如果提供）
    if api_key_data.ed25519_key:
        db_api_key.ed25519_key = encrypt_api_key(api_key_data.ed25519_key)
    if api_key_data.ed25519_secret:
        db_api_key.ed25519_secret = encrypt_api_key(api_key_data.ed25519_secret)
    
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
    
    更新用戶在指定交易所的API密鑰。支援部分更新，可以只更新某種類型的密鑰或描述。
    更新的API密鑰將使用加密算法重新加密存儲。可以同時存在兩種類型的密鑰。
    
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
        # 更新描述（如果提供）
        if api_key_data.description is not None:
            db_api_key.description = api_key_data.description
            
        # 更新 HMAC-SHA256 密鑰（如果提供）
        if api_key_data.api_key is not None:
            db_api_key.api_key = encrypt_api_key(api_key_data.api_key)
        if api_key_data.api_secret is not None:
            db_api_key.api_secret = encrypt_api_key(api_key_data.api_secret)
            
        # 更新 Ed25519 密鑰（如果提供）
        if api_key_data.ed25519_key is not None:
            db_api_key.ed25519_key = encrypt_api_key(api_key_data.ed25519_key)
        if api_key_data.ed25519_secret is not None:
            db_api_key.ed25519_secret = encrypt_api_key(api_key_data.ed25519_secret)
            
        db.commit()
        db.refresh(db_api_key)
        
        # 構建響應消息
        message = f"成功更新{exchange}的API密鑰"
        if api_key_data.api_key is not None or api_key_data.api_secret is not None:
            message += "（HMAC-SHA256）"
        if api_key_data.ed25519_key is not None or api_key_data.ed25519_secret is not None:
            message += "（Ed25519）"
            
        return {
            "success": True,
            "message": message,
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

# 获取通知设置 - 改为使用cookie
@router.get("/notifications", response_model=NotificationSettingsResponse)
def get_notification_settings(
    response: Response,
    notification_settings: Optional[str] = Cookie(None),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    获取当前用户的通知设置
    
    返回用户的通知首选项设置，包括电子邮件通知、系统通知等各种通知类型的启用状态。
    通知设置存储在cookie中，而不是数据库。
    
    返回:
        用户的通知设置详情
    """
    try:
        # 如果有cookie，解析通知设置
        if notification_settings:
            try:
                settings = json.loads(notification_settings)
                return NotificationSettingsResponse(
                    email_notifications=settings.get("email_notifications", True),
                    trade_notifications=settings.get("trade_notifications", True),
                    system_notifications=settings.get("system_notifications", True),
                    desktop_notifications=settings.get("desktop_notifications", False),
                    sound_notifications=settings.get("sound_notifications", False),
                    notification_preferences=settings.get("notification_preferences", {})
                )
            except json.JSONDecodeError:
                logger.warning(f"用户 {current_user.username} 的通知设置cookie无效，使用默认设置")
        
        # 如果没有cookie或解析失败，返回默认设置
        default_settings = NotificationSettingsResponse(
            email_notifications=True,
            trade_notifications=True,
            system_notifications=True,
            desktop_notifications=False,
            sound_notifications=False,
            notification_preferences={}
        )
        
        # 设置默认cookie
        response.set_cookie(
            key="notification_settings",
            value=json.dumps(default_settings.dict()),
            max_age=60 * 60 * 24 * 365,  # 一年有效期
            httponly=True,
            samesite="lax",
            secure=False  # 在生产环境中应设为True
        )
        
        return default_settings
    except Exception as e:
        logger.error(f"获取通知设置时出错: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取通知设置失败"
        )

# 更新通知设置 - 改为使用cookie
@router.post("/notifications", response_model=NotificationSettingsResponse)
def update_notification_settings(
    settings: NotificationSettingsUpdate,
    response: Response,
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    更新用户的通知设置
    
    允许用户自定义各种通知首选项，包括是否接收特定类型的通知，
    以及通知的接收方式（电子邮件、系统通知、桌面推送等）。
    更新后的设置会保存在cookie中，不保存到数据库。
    
    参数:
        settings: 包含用户更新后通知首选项的对象
        
    返回:
        更新后的通知设置详情
        
    错误:
        500: 更新过程中出现服务器错误
    """
    try:
        # 创建更新后的设置
        updated_settings = {
            "email_notifications": settings.email_notifications,
            "trade_notifications": settings.trade_notifications,
            "system_notifications": settings.system_notifications,
            "desktop_notifications": settings.desktop_notifications,
            "sound_notifications": settings.sound_notifications,
            "notification_preferences": settings.notification_preferences
        }
        
        # 设置cookie
        response.set_cookie(
            key="notification_settings",
            value=json.dumps(updated_settings),
            max_age=60 * 60 * 24 * 365,  # 一年有效期
            httponly=True,
            samesite="lax",
            secure=False  # 在生产环境中应设为True
        )
        
        logger.info(f"用户 {current_user.username} 已更新通知设置（使用cookie）")
        return NotificationSettingsResponse(**updated_settings)
        
    except Exception as e:
        logger.error(f"更新通知设置时出错: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新通知设置失败"
        )

# 圖片壓縮功能
def compress_image(file_content, max_size=(200, 200), quality=85, format='WEBP'):
    """
    壓縮圖片並轉換為WebP格式
    
    參數:
        file_content: 文件內容的字節流
        max_size: 圖片的最大尺寸(寬,高)
        quality: 壓縮質量(1-100)
        format: 輸出格式，默認為WebP
        
    返回:
        bytes: 壓縮後的圖片字節數據
    """
    try:
        # 打開圖片
        img = Image.open(io.BytesIO(file_content))
        
        # 檢查是否為GIF並且有多幀(動畫)
        if img.format == 'GIF' and hasattr(img, 'n_frames') and img.n_frames > 1:
            logger.info(f"檢測到動畫GIF圖片，保留原始格式")
            # 直接返回原始GIF數據以保留動畫
            return file_content
        
        # 縮放圖片，保持比例
        img.thumbnail(max_size)
        
        # 準備輸出
        output = io.BytesIO()
        
        # 如果圖片有透明通道且輸出格式為WebP，需要確保透明度得到保留
        if img.mode in ('RGBA', 'LA') and format == 'WEBP':
            img.save(output, format=format, quality=quality, lossless=False, method=6)
        else:
            # 轉換為RGB模式（WebP支持的模式）
            if format == 'WEBP' and img.mode not in ('RGBA', 'RGB'):
                img = img.convert('RGB')
            img.save(output, format=format, quality=quality)
            
        # 獲取壓縮後的數據
        compressed_data = output.getvalue()
        
        logger.info(f"圖片已壓縮: 原始格式={img.format}, 原始尺寸={img.size}, "
                    f"壓縮後格式={format}, 壓縮後尺寸={img.size}")
        
        return compressed_data
    except Exception as e:
        logger.error(f"圖片壓縮失敗: {str(e)}")
        raise e

@router.post("/user/avatar", response_model=Dict[str, Any])
async def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    上传用户头像
    
    接收用户上传的图片文件，保存到服务器并更新用户的avatar_url字段。
    支持的图片格式: .jpg, .jpeg, .png, .gif
    文件大小限制: 最大5MB
    图片会自动压缩并转换为WebP格式以节省空间
    GIF圖片將保留原始格式以維持動畫效果
    
    参数:
        file: 上传的图片文件
        
    返回:
        包含操作状态和新头像URL的响应
        
    错误:
        400: 文件格式不被支持或文件大小超过限制
        500: 上传过程中服务器错误
    """
    try:
        # 验证文件类型
        allowed_extensions = [".jpg", ".jpeg", ".png", ".gif"]
        file_extension = os.path.splitext(file.filename)[1].lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不支持的文件格式，请上传JPG、JPEG、PNG或GIF图片"
            )
        
        # 限制文件大小（5MB）
        file_size_limit = 5 * 1024 * 1024  # 5MB in bytes
        file.file.seek(0, 2)  # 移动到文件末尾
        file_size = file.file.tell()  # 获取文件大小
        file.file.seek(0)  # 重置文件指针
        
        if file_size > file_size_limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件大小超过限制，请上传小于5MB的图片"
            )
        
        # 读取文件内容
        file_content = await file.read()
        
        # 檢查是否為GIF動畫圖片
        is_animated_gif = False
        try:
            img = Image.open(io.BytesIO(file_content))
            is_animated_gif = img.format == 'GIF' and hasattr(img, 'n_frames') and img.n_frames > 1
        except Exception:
            pass
            
        try:
            if is_animated_gif:
                # 如果是動畫GIF，保留原始格式
                compressed_data = file_content
                unique_filename = f"{uuid.uuid4()}.gif"
                logger.info("處理動畫GIF頭像，保留原始格式")
            else:
                # 压缩图片
                compressed_data = compress_image(
                    file_content, 
                    max_size=(300, 300),  # 设置最大尺寸为300x300像素
                    quality=85,           # 设置压缩质量为85%
                    format='WEBP'         # 转换为WebP格式
                )
                # 生成唯一文件名 (使用WebP扩展名)
                unique_filename = f"{uuid.uuid4()}.webp"
            
            file_path = avatar_dir / unique_filename
            
            # 保存压缩后的文件
            with open(file_path, "wb") as f:
                f.write(compressed_data)
                
        except Exception as e:
            logger.warning(f"图片压缩失败，将使用原始图片: {str(e)}")
            
            # 压缩失败时回退到原始方法
            # 生成唯一文件名
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            file_path = avatar_dir / unique_filename
            
            # 重置文件指针
            file.file.seek(0)
            
            # 保存原始文件
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        
        # 更新用户头像URL
        avatar_url = f"/static/avatars/{unique_filename}"
        
        # 删除旧头像文件（如果存在且不是默认头像）
        if current_user.avatar_url and "default" not in current_user.avatar_url:
            old_avatar_path = backend_dir / current_user.avatar_url.lstrip("/")
            if os.path.exists(old_avatar_path):
                os.remove(old_avatar_path)
        
        # 更新数据库中的头像URL
        current_user.avatar_url = avatar_url
        db.commit()
        
        logger.info(f"用户 {current_user.username} 成功上传新头像: {avatar_url}")
        
        return {
            "success": True,
            "message": "头像上传成功",
            "avatar_url": avatar_url
        }
    
    except HTTPException as e:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"头像上传失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"头像上传失败: {str(e)}"
        )

@router.delete("/user/avatar", response_model=Dict[str, Any])
async def delete_avatar(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    删除用户头像
    
    删除用户当前的自定义头像，并重置为默认头像或清空头像URL。
    
    返回:
        包含操作状态的响应
        
    错误:
        404: 用户没有设置头像
        500: 删除过程中服务器错误
    """
    try:
        # 检查用户是否设置了头像
        if not current_user.avatar_url or "default" in current_user.avatar_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户没有设置自定义头像"
            )
        
        # 删除头像文件
        avatar_path = backend_dir / current_user.avatar_url.lstrip("/")
        if os.path.exists(avatar_path):
            os.remove(avatar_path)
        
        # 清空数据库中的头像URL
        current_user.avatar_url = None
        db.commit()
        
        logger.info(f"用户 {current_user.username} 已删除头像")
        
        return {
            "success": True,
            "message": "头像已成功删除"
        }
    
    except HTTPException as e:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"删除头像失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除头像失败: {str(e)}"
        ) 