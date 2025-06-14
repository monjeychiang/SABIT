from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, Body, Response, Cookie
from sqlalchemy.orm import Session
from typing import Any, List, Dict, Optional
from datetime import timedelta, datetime
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
import logging
import json
from fastapi.responses import RedirectResponse
import base64
from urllib.parse import quote, urlencode
import secrets
import os
import httpx
import re
import asyncio
import time
import uuid
import threading
import random
import hashlib

from ...db.database import get_db
from ...db.models import User, get_china_time
from ...schemas.user import UserCreate, UserResponse, Token, RefreshToken, RefreshTokenResponse
from ...core.security import (
    get_password_hash,
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
    revoke_refresh_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    verify_password,
    oauth2_scheme,
    verify_token,
    create_google_oauth_flow,
    verify_google_token,
    get_stored_code_verifier,
    GOOGLE_CLIENT_ID,
    GOOGLE_REDIRECT_URI,
    pwd_context,
    generate_referral_code,
    get_current_active_user
)
from ...core.config import settings
from ...schemas.event import UserActionEvent, EventType

# 從事件管理器導入
from ...core.event_manager import event_manager

router = APIRouter()
logger = logging.getLogger(__name__)

# 定義過期時間（分鐘）
EXTENDED_TOKEN_EXPIRE_MINUTES = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")) * 24 * 60

# 設定登入事件延遲處理時間(秒)，使用配置值
LOGIN_EVENT_DELAY_SECONDS = settings.LOGIN_EVENT_DELAY_SECONDS

# 安全的 Cookie 設置
COOKIE_SECURE = os.getenv("USE_SECURE_COOKIES", "True").lower() == "true"
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN", None)
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax").lower()
COOKIE_PATH = "/api/v1/auth"  # 限制 Cookie 僅用於認證 API

def set_refresh_token_cookie(response: Response, token: str, expires_delta: Optional[timedelta] = None):
    """
    設置包含刷新令牌的 HTTP-only cookie
    
    參數:
        response: FastAPI 響應對象
        token: 刷新令牌
        expires_delta: 可選的過期時間增量
    """
    # 如果未提供過期時間，默認使用90天
    if expires_delta is None:
        expires_delta = timedelta(days=int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "90")))
    
    max_age = int(expires_delta.total_seconds())
    
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        domain=COOKIE_DOMAIN,
        path=COOKIE_PATH,
        max_age=max_age
    )
    
    # 計算過期日期用於日誌顯示
    expire_date = get_china_time() + expires_delta
    logger.info(f"已設置 HTTP-only refresh token cookie，有效期: {max_age/86400:.1f} 天 (到期時間: {expire_date.strftime('%Y-%m-%d %H:%M:%S')})")
    
def clear_refresh_token_cookie(response: Response):
    """清除刷新令牌 cookie"""
    response.delete_cookie(
        key="refresh_token",
        path=COOKIE_PATH,
        domain=COOKIE_DOMAIN,
        secure=COOKIE_SECURE,
        httponly=True
    )

# 定期清理緩存結果的函數
def _clean_refresh_token_cache(request_id=None):
    """清理過期的刷新令牌緩存結果"""
    if not hasattr(refresh_access_token, "result_cache"):
        return
        
    try:
        current_time = time.time()
        
        # 優化 1: 減少鎖的粒度
        # 先無鎖方式獲取要清理的鍵
        # 預先分配足夠的字典空間，減少重新分配
        to_check = {}
        
        try:
            # 快速獲取鍵的副本，最小化鎖定時間
            with refresh_access_token.lock_dict_lock:
                # 估計所需大小，只複製鍵而不是值，大幅減少內存使用
                to_check = dict.fromkeys(refresh_access_token.result_cache.keys())
        except Exception as copy_error:
            logger.debug(f"獲取緩存鍵時出錯: {str(copy_error)}")
            return
            
        # 如果沒有鍵需要檢查，提前返回
        if not to_check:
            return
            
        # 優化 2: 分批處理，減少一次性工作量
        # 計算每個項目的過期時間，分類為過期和仍然有效
        expired_keys = []
        for k in to_check:
            try:
                # 使用無鎖讀取，在多線程環境中可能不精確但足夠高效
                if k in refresh_access_token.result_cache:
                    item = refresh_access_token.result_cache.get(k)
                    if item and current_time - item.get("timestamp", 0) > 180:  # 3分鐘超時
                        expired_keys.append(k)
            except Exception:
                # 忽略單個項目的讀取錯誤，繼續處理其他項目
                continue
                
        # 優化 3: 批量刪除，減少加鎖次數
        if expired_keys:
            # 獲取鎖並批量刪除
            deleted_count = 0
            try:
                with refresh_access_token.lock_dict_lock:
                    for k in expired_keys:
                        if k in refresh_access_token.result_cache:
                            del refresh_access_token.result_cache[k]
                            deleted_count += 1
            except Exception as del_error:
                logger.debug(f"刪除過期緩存時出錯: {str(del_error)}")
                
            # 只記錄實際有刪除時的日誌，減少日誌噪音
            if deleted_count > 0 and (settings.DEBUG or deleted_count > 10):
                logger.debug(f"清理了 {deleted_count} 個過期的令牌緩存 [請求ID: {request_id or 'system'}]")
                
        # 優化 4: 智能緩存大小控制
        # 當緩存大小超過閾值，清理更積極
        try:
            cache_size = len(refresh_access_token.result_cache)
            if cache_size > 1000:
                # 大緩存時採用更積極的策略
                # 創建一個排序函數來找出最舊的項目
                def get_oldest_keys(cache, max_keys=500):
                    """獲取緩存中最舊的一批鍵"""
                    items = []
                    try:
                        with refresh_access_token.lock_dict_lock:
                            # 獲取(鍵,時間戳)對，最小化鎖定時間
                            items = [(k, cache[k].get("timestamp", 0)) for k in cache if k in cache]
                    except:
                        return []
                        
                    # 在無鎖狀態下排序，找出最舊的項目
                    items.sort(key=lambda x: x[1])
                    return [k for k, _ in items[:max_keys]]
                
                # 找出最舊的項目並刪除
                oldest_keys = get_oldest_keys(refresh_access_token.result_cache, 500)
                if oldest_keys:
                    deleted = 0
                    with refresh_access_token.lock_dict_lock:
                        for k in oldest_keys:
                            if k in refresh_access_token.result_cache:
                                del refresh_access_token.result_cache[k]
                                deleted += 1
                                
                    if deleted > 0:
                        logger.info(f"緩存大小超過閾值，已清理 {deleted} 個最舊項目，當前大小約: {len(refresh_access_token.result_cache)} [請求ID: {request_id or 'system'}]")
        except Exception as size_error:
            logger.debug(f"緩存大小控制時出錯: {str(size_error)}")
    except Exception as cache_error:
        logger.error(f"清理過期緩存失敗: {str(cache_error)} [請求ID: {request_id or 'system'}]")

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(*, db: Session = Depends(get_db), user_in: UserCreate) -> Any:
    """
    註冊新用戶
    
    接收用戶提交的註冊資料，進行必要的驗證後創建新用戶。
    會驗證密碼確認、檢查用戶名和電子郵件是否已被使用。
    每個用戶會自動獲得一個唯一的6位推薦碼。
    
    如果提供了推薦碼(referral_code)，會查找對應的用戶並將其ID設為推薦人ID。
    也可以直接提供推薦人ID(referrer_id)。
    """
    # 驗證密碼確認
    if user_in.password != user_in.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密碼和確認密碼不匹配",
        )
    
    # 檢查用戶名是否已存在
    if db.query(User).filter(User.username == user_in.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用戶名已被使用",
        )
    
    # 檢查郵箱是否已存在
    if db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="郵箱已被註冊",
        )
    
    # 處理推薦碼邏輯
    referrer_id = None
    if hasattr(user_in, 'referral_code') and user_in.referral_code:
        # 透過推薦碼查找推薦人
        referrer = db.query(User).filter(User.referral_code == user_in.referral_code).first()
        if referrer:
            referrer_id = referrer.id
            logger.info(f"Found referrer (ID: {referrer_id}) by referral code: {user_in.referral_code}")
        else:
            logger.warning(f"Invalid referral code provided: {user_in.referral_code}")
    elif hasattr(user_in, 'referrer_id') and user_in.referrer_id:
        # 直接使用提供的推薦人ID
        referrer_id = user_in.referrer_id
    
    # 生成唯一推薦碼
    referral_code = generate_referral_code(db)
    
    # 創建新用戶
    db_user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        referral_code=referral_code,
        referrer_id=referrer_id
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    logger.info(f"New user registered: {user_in.username}, referral code: {referral_code}")
    if referrer_id:
        logger.info(f"User {user_in.username} was referred by user ID: {referrer_id}")
    
    return db_user

@router.post("/login", response_model=Token)
async def login(
    request: Request,
    response: Response,  # 新增 Response 參數
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
    keep_logged_in: bool = Form(False)
) -> Any:
    """
    用戶登入 - OAuth2 認證流程
    
    處理用戶的登入請求，驗證憑據並返回訪問令牌和刷新令牌。
    支援七天保持登入功能，若啟用則延長令牌有效期。
    刷新令牌通過 HTTP-only cookie 傳輸，提高安全性。
    
    參數:
    - form_data: OAuth2表單數據，包含用戶名和密碼
    - keep_logged_in: 是否保持登入狀態（延長令牌有效期）
    
    返回:
    - access_token: 訪問令牌
    - token_type: 令牌類型（bearer）
    - expires_in: 令牌過期時間（秒）
    """
    try:
        logger.info(f"OAuth2 login attempt: {form_data.username}")
        
        # 查詢用戶
        user = db.query(User).filter(User.username == form_data.username).first()
        
        if not user:
            logger.warning(f"Username not found: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用戶名或密碼錯誤",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 驗證密碼
        try:
            if not verify_password(form_data.password, user.hashed_password):
                logger.warning(f"Password verification failed: {form_data.username}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="用戶名或密碼錯誤",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        except Exception as pwd_error:
            logger.error(f"Password verification error: {str(pwd_error)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用戶名或密碼錯誤",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 根據是否選擇保持登入來設置token過期時間
        access_token_expires = timedelta(
            minutes=EXTENDED_TOKEN_EXPIRE_MINUTES if keep_logged_in else ACCESS_TOKEN_EXPIRE_MINUTES
        )
        
        # 創建訪問令牌
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        
        # 獲取用戶代理和裝置資訊
        user_agent = request.headers.get("user-agent", "")
        client_ip = request.client.host
        device_info = parse_user_agent(user_agent)
        
        # 創建刷新令牌
        refresh_token, _ = create_refresh_token(
            db, 
            user.id,
            expires_delta=access_token_expires if keep_logged_in else None,
            device_info=str(device_info)  # 儲存裝置資訊
        )
        
        # 設置 HTTP-only cookie 存儲 refresh_token
        set_refresh_token_cookie(response, refresh_token, expires_delta=access_token_expires if keep_logged_in else None)
        
        # 記錄用戶登入IP和時間
        user.last_login_ip = client_ip
        user.last_login_at = get_china_time()
        db.commit()
        
        logger.info(f"Login successful: {form_data.username}, IP: {client_ip}, Extended session: {keep_logged_in}")
        
        # 創建登入成功事件
        try:
            # 提取設備信息
            device_info = parse_user_agent(user_agent)
            
            # 創建登入成功事件
            login_event = UserActionEvent(
                event_type=EventType.LOGIN_SUCCESS,
                source="auth_service",
                user_ids=[user.id],
                action_type="login",
                device_info=device_info,
                ip_address=client_ip,
                location="未知位置",  # 可以在這裡添加地理位置查詢服務
                data={
                    "username": user.username,
                    "login_time": datetime.now().isoformat(),
                    "keep_logged_in": keep_logged_in,
                    "user_agent": user_agent
                }
            )
            
            # 實現延遲處理登入事件
            async def delayed_event_processing():
                logger.info(f"延遲 {LOGIN_EVENT_DELAY_SECONDS} 秒後處理登入成功事件，用戶: {user.username}")
                await asyncio.sleep(LOGIN_EVENT_DELAY_SECONDS)
                try:
                    # 創建新的數據庫會話，因為原會話可能已關閉
                    from ...db.database import SessionLocal
                    async_db = SessionLocal()
                    try:
                        await event_manager.process_event(login_event, async_db)
                        logger.info(f"成功處理延遲的登入事件: {user.username}")
                    finally:
                        async_db.close()
                except Exception as delayed_err:
                    logger.error(f"延遲處理登入事件時發生錯誤: {str(delayed_err)}")
            
            # 創建延遲任務但不等待完成
            asyncio.create_task(delayed_event_processing())
            logger.info(f"已安排延遲處理登入事件: {user.username}")
        except Exception as event_error:
            # 記錄錯誤但不中斷登入流程
            logger.error(f"設置延遲登入事件失敗: {str(event_error)}")
        
        # 返回訪問令牌（不再包含刷新令牌，因為它已經在 cookie 中）
        return {
            "access_token": access_token, 
            "token_type": "bearer",
            "expires_in": access_token_expires.total_seconds()
        }
    except HTTPException:
        # 直接重新拋出HTTP異常
        raise
    except Exception as e:
        logger.error(f"Error during login: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登入失敗，請檢查用戶名和密碼",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/login/simple", response_model=Token)
def login_simple(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    keep_logged_in: bool = Form(False),
    db: Session = Depends(get_db)
) -> Any:
    """
    簡化版用戶登入 - 直接接收表單參數
    
    提供比標準OAuth2流程更簡單的登入方式，直接接收用戶名和密碼參數。
    適用於不方便使用完整OAuth2流程的客戶端。
    
    參數:
    - username: 用戶名
    - password: 密碼
    - keep_logged_in: 是否保持登入狀態（延長令牌有效期）
    
    返回:
    - access_token: 訪問令牌
    - token_type: 令牌類型（bearer）
    - refresh_token: 刷新令牌
    - expires_in: 令牌過期時間（秒）
    """
    try:
        logger.info(f"Simple login attempt: {username}")
        
        # 查詢用戶
        user = db.query(User).filter(User.username == username).first()
        
        if not user:
            logger.warning(f"Username not found: {username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用戶名或密碼錯誤",
            )
        
        # 驗證密碼
        try:
            if not verify_password(password, user.hashed_password):
                logger.warning(f"Password verification failed: {username}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="用戶名或密碼錯誤",
                )
        except Exception as pwd_error:
            logger.error(f"Password verification error: {str(pwd_error)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用戶名或密碼錯誤",
            )
        
        # 根據是否選擇保持登入來設置token過期時間
        access_token_expires = timedelta(
            minutes=EXTENDED_TOKEN_EXPIRE_MINUTES if keep_logged_in else ACCESS_TOKEN_EXPIRE_MINUTES
        )
        
        # 創建訪問令牌
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        
        # 創建刷新令牌（如果選擇了保持登入，刷新令牌也使用延長的過期時間）
        refresh_token, _ = create_refresh_token(
            db, 
            user.id,
            expires_delta=access_token_expires if keep_logged_in else None
        )
        
        # 記錄用戶登入IP和時間
        client_ip = request.client.host
        user.last_login_ip = client_ip
        user.last_login_at = get_china_time()
        db.commit()
        
        logger.info(f"Login successful: {username}, IP: {client_ip}, Extended session: {keep_logged_in}")
        
        # 獲取用戶代理信息
        user_agent = request.headers.get("user-agent", "")
        
        # 創建並處理登入成功事件
        try:
            # 提取設備信息
            device_info = parse_user_agent(user_agent)
            
            # 創建登入成功事件
            login_event = UserActionEvent(
                event_type=EventType.LOGIN_SUCCESS,
                source="auth_service",
                user_ids=[user.id],
                action_type="login",
                device_info=device_info,
                ip_address=client_ip,
                location="未知位置",
                data={
                    "username": user.username,
                    "login_time": datetime.now().isoformat(),
                    "keep_logged_in": keep_logged_in,
                    "user_agent": user_agent
                }
            )
            
            # 實現延遲處理登入事件
            async def delayed_event_processing():
                await asyncio.sleep(LOGIN_EVENT_DELAY_SECONDS)
                try:
                    # 創建新的數據庫會話
                    from ...db.database import SessionLocal
                    async_db = SessionLocal()
                    try:
                        await event_manager.process_event(login_event, async_db)
                        logger.info(f"成功處理延遲的登入事件: {username}")
                    finally:
                        async_db.close()
                except Exception as delayed_err:
                    logger.error(f"延遲處理登入事件時發生錯誤: {str(delayed_err)}")
            
            # 創建任務但不等待完成
            asyncio.create_task(delayed_event_processing())
            logger.info(f"已安排延遲處理登入事件: {username}")
        except Exception as event_error:
            # 記錄錯誤但不中斷登入流程
            logger.error(f"設置延遲登入事件失敗: {str(event_error)}")
        
        # 返回token
        return {
            "access_token": access_token, 
            "token_type": "bearer",
            "refresh_token": refresh_token,
            "expires_in": access_token_expires.total_seconds()
        }
    except HTTPException:
        # 直接重新拋出HTTP異常
        raise
    except Exception as e:
        logger.error(f"Error during simple login: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登入失敗，請檢查用戶名和密碼",
        )

@router.get("/me", response_model=UserResponse)
def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> Any:
    """
    獲取當前用戶資訊
    
    根據請求中的認證令牌，返回當前登入用戶的詳細資訊。
    這是驗證用戶身份和獲取個人資料的標準端點。
    
    返回:
    - 完整的用戶資訊模型（UserResponse）
    """
    try:
        payload = verify_token(token)
        username = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="無效的認證憑據",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無效的認證憑據",
        )
    
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在",
        )
    
    return user

@router.get("/me/referrals", response_model=List[Dict[str, Any]])
def get_user_referrals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    獲取當前用戶的推薦列表
    
    返回當前用戶推薦的所有用戶列表，包含基本資訊和註冊時間。
    如果用戶沒有推薦任何人，則返回空列表。
    
    返回:
    - 被推薦用戶的列表，每個用戶包含ID、用戶名、電子郵件、註冊時間等資訊
    """
    # 獲取當前用戶的推薦列表
    referrals = current_user.referrals
    
    # 將推薦列表轉換為可序列化的格式
    result = []
    for user in referrals:
        result.append({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
        })
    
    return result

@router.post("/refresh", response_model=RefreshTokenResponse)
def refresh_access_token(
    request: Request,
    response: Response,
    refresh_token: str = Cookie(None, alias="refresh_token"),  # 從 cookie 獲取刷新令牌
    keep_logged_in: bool = Form(False),
    db: Session = Depends(get_db)
) -> Any:
    """
    使用刷新令牌獲取新的訪問令牌
    
    當訪問令牌過期時，客戶端可以使用此端點通過刷新令牌獲取新的訪問令牌，
    避免用戶需要重新登入。支援延長登入期間的選項。
    
    刷新令牌從 HTTP-only cookie 中獲取，並在每次刷新時更新有效期，
    提高了安全性，降低令牌被盜用的風險。
    
    參數:
    - keep_logged_in: 是否保持登入狀態（若為true，則延長令牌有效期）
    
    返回:
    - access_token: 新的訪問令牌
    - token_type: 令牌類型（bearer）
    - expires_in: 令牌有效期（秒）
    """
    # 生成一個唯一的請求 ID 用於日誌追蹤，使用更高效的UUID生成方式
    request_id = str(uuid.uuid4())[:8]
    
    try:
        # 減少日誌開銷 - 只在調試模式下記錄詳細資訊
        if settings.DEBUG:
            logger.debug(f"處理刷新令牌請求 [請求ID: {request_id}]")
        
        # 檢查是否提供了 refresh_token - 快速失敗機制
        if not refresh_token:
            if settings.DEBUG:
                logger.debug(f"刷新令牌不存在於 cookie 中 [請求ID: {request_id}]")
            clear_refresh_token_cookie(response)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="缺少刷新令牌",
            )
        
        # 檢查客戶端請求模式 (JSON或重定向) - 延遲至需要時評估
        accept_header = request.headers.get("accept", "")
        is_ajax = "application/json" in accept_header or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        
        # 獲取用戶專用的鎖定鍵和緩存鍵 - 先進行高效的緩存檢查
        
        # 初始化鎖機制和結果緩存（如果尚未初始化）
        if not hasattr(refresh_access_token, "locks"):
            refresh_access_token.locks = {}
            refresh_access_token.lock_dict_lock = threading.RLock()
            refresh_access_token.result_cache = {}
            if settings.DEBUG:
                logger.debug("初始化令牌刷新鎖和緩存機制")
        
        # 使用令牌的安全指紋作為緩存鍵，避免在驗證前暴露完整用戶信息
        token_fingerprint = hashlib.md5(refresh_token.encode()).hexdigest()[:10]
        cache_key = f"refresh_result_{token_fingerprint}"
        
        # 先檢查緩存是否有有效結果 - 無需獲取鎖
        cached_result = None
        current_time = time.time()
        
        # 高效率緩存檢查 - 直接使用字典訪問
        if cache_key in refresh_access_token.result_cache:
            cached_item = refresh_access_token.result_cache[cache_key]
            # 檢查緩存是否過期 - 擴展到45秒有效期提高命中率
            if current_time - cached_item["timestamp"] < 45:  # 45秒內有效
                cached_result = cached_item
                if settings.DEBUG:
                    logger.debug(f"直接使用緩存的刷新結果 [請求ID: {request_id}]")
        
        if cached_result:
            # 添加緩存標記到響應頭
            response.headers["X-Used-Cache"] = "true"
            
            # 設置 HTTP-only cookie 存儲 refresh_token
            set_refresh_token_cookie(
                response, 
                cached_result["refresh_token"], 
                expires_delta=timedelta(seconds=cached_result["refresh_token_expires_in"])
            )
            
            # 構建返回結果，不包含refresh_token
            result = {
                "access_token": cached_result["access_token"],
                "token_type": "bearer",
                "expires_in": cached_result["expires_in"],
                "refresh_token_expires_in": cached_result["refresh_token_expires_in"]
            }
            
            # 觸發非同步緩存清理（更低頻率，減少系統負擔）
            if random.random() < 0.05:  # 降低到5%的請求觸發清理
                threading.Thread(
                    target=_clean_refresh_token_cache,
                    args=(request_id,),
                    daemon=True
                ).start()
            
            # 根據請求類型返回結果
            if is_ajax:
                return result
            else:
                # 構建重定向 URL
                redirect_params = {
                    "access_token": result["access_token"],
                    "token_type": "bearer",
                    "expires_in": result["expires_in"],
                    "refresh_token_expires_in": result["refresh_token_expires_in"],
                    "keep_logged_in": str(keep_logged_in).lower()
                }
                redirect_url = f"{os.getenv('FRONTEND_CALLBACK_URL', 'http://localhost:5175/auth/callback')}?{urlencode(redirect_params)}"
                
                # 重定向到前端
                redir_response = RedirectResponse(url=redirect_url)
                redir_response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                redir_response.headers["Pragma"] = "no-cache"
                redir_response.headers["Expires"] = "0"
                return redir_response
        
        # 驗證刷新令牌並獲取相關用戶 - 移至此處，減少不必要的驗證
        start_time = time.time()
        user = verify_refresh_token(db, refresh_token)
        verify_time = time.time() - start_time
        
        # 如果驗證時間超過閾值，記錄警告 - 使用更高的閾值減少日誌噪音
        if verify_time > 1.5 and settings.DEBUG:
            logger.warning(f"令牌驗證耗時過長: {verify_time:.2f}秒 [請求ID: {request_id}]")
        
        if not user:
            if settings.DEBUG:
                logger.debug(f"刷新令牌驗證失敗 [請求ID: {request_id}]")
            # 清除無效的刷新令牌 cookie
            clear_refresh_token_cookie(response)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="無效的刷新令牌",
            )
        
        # 獲取用戶鎖定鍵 - 使用用戶ID作為鍵更準確
        lock_key = f"refresh_token_lock_{user.id}"
        cache_key = f"refresh_result_{user.id}"  # 更新為使用用戶ID的緩存鍵
        
        # 記錄是否是通過寬限期機制驗證的令牌
        if hasattr(user, "_from_grace_period") and user._from_grace_period:
            if settings.DEBUG:
                logger.debug(f"使用寬限期內的令牌成功驗證用戶 {user.username} [請求ID: {request_id}]")
            response.headers["X-Token-Grace-Period"] = "true"
        
        # 獲取用戶的鎖 - 使用高效率的鎖管理
        with refresh_access_token.lock_dict_lock:
            if lock_key not in refresh_access_token.locks:
                refresh_access_token.locks[lock_key] = threading.RLock()
        
        # 嘗試獲取鎖，使用非阻塞模式立即檢查
        user_lock = refresh_access_token.locks[lock_key]
        lock_acquired = user_lock.acquire(blocking=False)
        
        if not lock_acquired:
            # 已有另一個請求正在處理，等待結果
            if settings.DEBUG:
                logger.debug(f"用戶 {user.username} 的令牌刷新請求正在處理中 [請求ID: {request_id}]，等待結果")
            
            # 等待結果可用，使用更短的等待間隔提高響應性
            wait_start = time.time()
            max_wait_time = 5  # 最多等待5秒
            check_interval = 0.05  # 每0.05秒檢查一次，提高響應速度
            
            # 在等待過程中檢查緩存
            while time.time() - wait_start < max_wait_time:
                # 檢查是否有緩存結果
                if cache_key in refresh_access_token.result_cache:
                    # 獲取緩存結果
                    cached_result = refresh_access_token.result_cache[cache_key]
                    current_time = time.time()
                    
                    # 檢查緩存是否過期
                    if current_time - cached_result["timestamp"] < 45:  # 45秒內有效
                        if settings.DEBUG:
                            logger.debug(f"用戶 {user.username} 等待後使用緩存的刷新結果 [請求ID: {request_id}]")
                        
                        # 添加緩存標記到響應頭
                        response.headers["X-Used-Cache"] = "true"
                        
                        # 設置 HTTP-only cookie 存儲 refresh_token
                        set_refresh_token_cookie(
                            response, 
                            cached_result["refresh_token"], 
                            expires_delta=timedelta(seconds=cached_result["refresh_token_expires_in"])
                        )
                        
                        # 構建返回結果，不包含refresh_token
                        result = {
                            "access_token": cached_result["access_token"],
                            "token_type": "bearer",
                            "expires_in": cached_result["expires_in"],
                            "refresh_token_expires_in": cached_result["refresh_token_expires_in"]
                        }
                        
                        # 根據請求類型返回結果
                        if is_ajax:
                            return result
                        else:
                            # 構建重定向 URL
                            redirect_params = {
                                "access_token": result["access_token"],
                                "token_type": "bearer",
                                "expires_in": result["expires_in"],
                                "refresh_token_expires_in": result["refresh_token_expires_in"],
                                "keep_logged_in": str(keep_logged_in).lower()
                            }
                            redirect_url = f"{os.getenv('FRONTEND_CALLBACK_URL', 'http://localhost:5175/auth/callback')}?{urlencode(redirect_params)}"
                            
                            # 重定向到前端
                            redir_response = RedirectResponse(url=redirect_url)
                            redir_response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                            redir_response.headers["Pragma"] = "no-cache"
                            redir_response.headers["Expires"] = "0"
                            return redir_response
                
                # 等待一段時間後再次檢查
                time.sleep(check_interval)
            
            # 等待超時，嘗試獲取鎖並處理請求
            if settings.DEBUG:
                logger.debug(f"用戶 {user.username} 的令牌刷新請求等待超時 [請求ID: {request_id}]，嘗試自行處理")
            lock_acquired = refresh_access_token.locks[lock_key].acquire(blocking=True, timeout=0.5)
            if not lock_acquired:
                logger.warning(f"用戶 {user.username} 獲取鎖失敗 [請求ID: {request_id}]，返回429錯誤")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="刷新請求過於頻繁，請稍後再試"
                )
        
        # 成功獲取鎖，開始處理請求
        try:
            # 記錄處理開始時間
            process_start = time.time()
            
            # 再次檢查緩存，以防在獲取鎖的過程中其他請求已完成處理
            if cache_key in refresh_access_token.result_cache:
                cached_result = refresh_access_token.result_cache[cache_key]
                current_time = time.time()
                
                if current_time - cached_result["timestamp"] < 45:  # 45秒內有效
                    if settings.DEBUG:
                        logger.debug(f"用戶 {user.username} 獲取鎖後發現已有緩存結果 [請求ID: {request_id}]")
                    
                    # 添加緩存標記到響應頭
                    response.headers["X-Used-Cache"] = "true"
                    
                    # 設置 HTTP-only cookie 存儲 refresh_token
                    set_refresh_token_cookie(
                        response, 
                        cached_result["refresh_token"], 
                        expires_delta=timedelta(seconds=cached_result["refresh_token_expires_in"])
                    )
                    
                    # 構建返回結果，不包含refresh_token
                    result = {
                        "access_token": cached_result["access_token"],
                        "token_type": "bearer",
                        "expires_in": cached_result["expires_in"],
                        "refresh_token_expires_in": cached_result["refresh_token_expires_in"]
                    }
                    
                    # 根據請求類型返回結果
                    if is_ajax:
                        return result
                    else:
                        # 構建重定向 URL
                        redirect_params = {
                            "access_token": result["access_token"],
                            "token_type": "bearer",
                            "expires_in": result["expires_in"],
                            "refresh_token_expires_in": result["refresh_token_expires_in"],
                            "keep_logged_in": str(keep_logged_in).lower()
                        }
                        redirect_url = f"{os.getenv('FRONTEND_CALLBACK_URL', 'http://localhost:5175/auth/callback')}?{urlencode(redirect_params)}"
                        
                        # 重定向到前端
                        redir_response = RedirectResponse(url=redirect_url)
                        redir_response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                        redir_response.headers["Pragma"] = "no-cache"
                        redir_response.headers["Expires"] = "0"
                        return redir_response
        
            # 創建訪問令牌 - 直接使用標準過期時間（15分鐘）
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            
            # 創建訪問令牌 - 使用高效的令牌生成
            token_start = time.time()
            access_token = create_access_token(
                data={"sub": user.username},
                expires_delta=access_token_expires
            )
            token_create_time = time.time() - token_start
            
            if token_create_time > 0.1 and settings.DEBUG:
                logger.debug(f"創建訪問令牌耗時較長: {token_create_time:.2f}秒 [請求ID: {request_id}]")
            
            # 設置refresh token過期時間
            refresh_token_expires = None  # 默認標準過期時間
            if keep_logged_in:
                # 如果保持登入，刷新令牌使用更長的過期時間(REFRESH_TOKEN_EXPIRE_DAYS天)
                refresh_token_expires = timedelta(days=int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "90")))
            
            # 獲取裝置資訊 - 使用緩存提高效率
            device_info = None
            user_agent = request.headers.get("user-agent", "")
            if user_agent:
                # 使用緩存的設備信息或解析新的設備信息
                if not hasattr(refresh_access_token, "device_cache"):
                    refresh_access_token.device_cache = {}
                
                ua_hash = hash(user_agent)
                if ua_hash in refresh_access_token.device_cache:
                    device_info = refresh_access_token.device_cache[ua_hash]
                else:
                    device_info = parse_user_agent(user_agent)
                    refresh_access_token.device_cache[ua_hash] = device_info
            
            # 創建或更新刷新令牌
            refresh_token_start = time.time()
            try:
                # create_refresh_token 會自動檢測並更新現有令牌
                new_refresh_token, _ = create_refresh_token(
                    user_id=user.id, 
                    db=db,
                    expires_delta=refresh_token_expires,
                    device_info=str(device_info) if device_info else None
                )
                
                refresh_token_create_time = time.time() - refresh_token_start
                if refresh_token_create_time > 0.5 and settings.DEBUG:
                    logger.debug(f"創建/更新刷新令牌耗時較長: {refresh_token_create_time:.2f}秒 [請求ID: {request_id}]")
            except Exception as token_error:
                logger.error(f"更新刷新令牌失敗: {str(token_error)} [請求ID: {request_id}]")
                # 如果無法創建或更新令牌，無法繼續處理
                raise token_error
            
            # 計算令牌過期時間（秒）
            access_token_expires_in = int(access_token_expires.total_seconds())
            
            # 刷新令牌過期時間
            refresh_token_expires_in = access_token_expires_in  # 默認與access token相同
            if keep_logged_in:
                # 如果保持登入，使用配置的天數
                refresh_token_expires_in = int(timedelta(days=int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "90"))).total_seconds())
            
            # 準備返回數據和緩存數據
            result = {
                "access_token": access_token,
                "token_type": "bearer", 
                "expires_in": access_token_expires_in,
                "refresh_token_expires_in": refresh_token_expires_in
            }
            
            # 緩存結果，包含refresh_token以供後續請求使用
            cache_result = result.copy()
            cache_result["refresh_token"] = new_refresh_token
            cache_result["timestamp"] = time.time()
            
            # 存儲到緩存 - 使用寫時拷貝策略，更新緩存的同時也使用token_fingerprint作為鍵
            refresh_access_token.result_cache[cache_key] = cache_result
            # 同時用token指紋存儲一份，提高緩存命中率
            refresh_access_token.result_cache[f"refresh_result_{token_fingerprint}"] = cache_result
            
            # 記錄總處理時間 - 只在需要時記錄
            total_process_time = time.time() - process_start
            if total_process_time > 1.0 and settings.DEBUG:
                logger.debug(f"用戶 {user.username} 的令牌刷新處理總耗時較長: {total_process_time:.2f}秒 [請求ID: {request_id}]")
            
            # 設置 HTTP-only cookie 存儲 refresh_token
            set_refresh_token_cookie(response, new_refresh_token, expires_delta=refresh_token_expires)
            
            # 根據請求類型返回結果
            if is_ajax:
                # 返回JSON響應
                return result
            else:
                # 構建重定向 URL
                redirect_params = {
                    "access_token": access_token,
                    "token_type": "bearer",
                    "expires_in": access_token_expires_in,
                    "refresh_token_expires_in": refresh_token_expires_in,
                    "keep_logged_in": str(keep_logged_in).lower()
                }

                redirect_url = f"{os.getenv('FRONTEND_CALLBACK_URL', 'http://localhost:5175/auth/callback')}?{urlencode(redirect_params)}"

                # 重定向到前端
                redirect_response = RedirectResponse(url=redirect_url)
                redirect_response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                redirect_response.headers["Pragma"] = "no-cache"
                redirect_response.headers["Expires"] = "0"
                return redirect_response
                
        finally:
            # 釋放鎖，無論成功失敗
            try:
                user_lock.release()
                if settings.DEBUG:
                    logger.debug(f"用戶 {user.username} 的令牌刷新鎖已釋放 [請求ID: {request_id}]")
            except Exception as lock_error:
                logger.warning(f"釋放令牌刷新鎖失敗: {str(lock_error)} [請求ID: {request_id}]")
                
            # 定期清理過期的緩存結果 - 低頻率觸發清理
            if random.random() < 0.05:  # 只有5%的請求會觸發清理
                threading.Thread(
                    target=_clean_refresh_token_cache,
                    args=(request_id,),
                    daemon=True
                ).start()
    except HTTPException:
        # 直接重新拋出 HTTP 異常
        raise
    except Exception as e:
        # 捕獲所有其他異常
        logger.error(f"處理刷新令牌請求時發生錯誤: {str(e)} [請求ID: {request_id}]")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="處理刷新令牌請求時發生錯誤"
        )

@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    response: Response,
    refresh_token: str = Cookie(None, alias="refresh_token"),
    db: Session = Depends(get_db)
) -> Any:
    """
    登出並撤銷刷新令牌
    
    處理用戶登出請求，撤銷提供的刷新令牌，使其無法再用於獲取新的訪問令牌。
    這是安全登出流程的關鍵步驟，可防止刷新令牌被濫用。
    
    返回:
    - 成功登出的確認訊息
    """
    # 嘗試撤銷令牌
    if refresh_token:
        success = revoke_refresh_token(db, refresh_token)
        if success:
            logger.info("成功撤銷並刪除刷新令牌")
        else:
            logger.warning("撤銷刷新令牌失敗：令牌可能已過期或不存在")
    else:
        logger.info("未提供刷新令牌，無需撤銷")
    
    # 清除刷新令牌 cookie，無論撤銷是否成功
    clear_refresh_token_cookie(response)
    logger.info("已清除瀏覽器中的 refresh token cookie")
    
    return {"message": "成功登出"}

@router.get("/google/login")
async def google_login(request: Request, keep_logged_in: bool = False):
    """
    開始 Google OAuth2 登入流程
    
    生成並返回Google OAuth2授權URL，客戶端可將用戶重定向到此URL開始第三方登入流程。
    包含必要的狀態參數以確保安全性和正確的回調處理。
    
    參數:
    - keep_logged_in: 是否保持登入狀態（延長令牌有效期）
    
    返回:
    - authorization_url: Google授權頁面的URL
    """
    try:
        # 從環境變量獲取前端回調 URL
        frontend_callback_url = os.getenv("FRONTEND_CALLBACK_URL", "http://localhost:5175/auth/callback")
        
        # 生成 state 參數，包含前端回調 URL 和 CSRF token
        state_data = {
            "callback_url": frontend_callback_url,
            "csrf_token": secrets.token_urlsafe(32),
            "keep_logged_in": keep_logged_in  # 保存保持登入的選擇
        }
        state = base64.b64encode(json.dumps(state_data).encode()).decode()
        
        # 創建 flow 並傳入 state 參數
        flow = create_google_oauth_flow(state=state)
        
        authorization_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
            state=state
        )
        
        logger.info(f"Starting Google OAuth flow, redirect to: {authorization_url}, keep_logged_in: {keep_logged_in}")
        return {"authorization_url": authorization_url}
        
    except Exception as e:
        logger.error(f"Google OAuth login error: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to initialize Google login: {str(e)}"
        )

@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str = None,
    state: str = None,
    error: str = None,
    db: Session = Depends(get_db)
):
    """
    處理 Google OAuth2 回調
    
    接收並處理Google認證流程的回調請求，驗證用戶身份，創建或更新用戶資料，
    並生成系統訪問令牌，最後將用戶重定向到前端應用程式。
    
    參數:
    - code: Google授權碼
    - state: 狀態參數（包含前端回調URL和CSRF令牌）
    - error: 可能的錯誤訊息
    
    處理流程:
    1. 解析state參數獲取前端回調URL
    2. 驗證授權碼和狀態參數
    3. 交換授權碼獲取Google令牌
    4. 驗證ID令牌並獲取用戶資訊
    5. 在系統中創建或更新用戶
    6. 創建系統訪問令牌和刷新令牌
    7. 將用戶重定向到前端，附帶令牌資訊
    """
    try:
        # 首先嘗試解析state參數，獲取前端回調URL
        frontend_callback_url = None
        try:
            if state:
                state_data = json.loads(base64.b64decode(state).decode())
                frontend_callback_url = state_data.get("callback_url")
                logger.debug(f"從state解析的前端回調URL: {frontend_callback_url}")
        except Exception as state_error:
            logger.error(f"解析state參數失敗: {str(state_error)}")
            # 使用默認前端回調URL
            frontend_callback_url = os.getenv("FRONTEND_CALLBACK_URL", "http://localhost:5175/auth/callback")
            
        # 確保前端回調URL有效
        if not frontend_callback_url:
            frontend_callback_url = os.getenv("FRONTEND_CALLBACK_URL", "http://localhost:5175/auth/callback")
            logger.warning(f"使用默認前端回調URL: {frontend_callback_url}")
            
        # 檢查錯誤參數
        if error:
            logger.error(f"Google OAuth error: {error}")
            error_params = {"error": f"Google登入失敗: {error}"}
            return RedirectResponse(url=f"{frontend_callback_url}?{urlencode(error_params)}")
        
        # 檢查授權碼
        if not code:
            logger.error("Missing authorization code")
            error_params = {"error": "缺少授權碼"}
            return RedirectResponse(url=f"{frontend_callback_url}?{urlencode(error_params)}")

        # 檢查 state 參數
        if not state:
            logger.error("Missing state parameter")
            error_params = {"error": "缺少state參數"}
            return RedirectResponse(url=f"{frontend_callback_url}?{urlencode(error_params)}")

        # 解析 state 參數
        try:
            state_data = json.loads(base64.b64decode(state).decode())
            frontend_callback_url = state_data.get("callback_url", frontend_callback_url)
            csrf_token = state_data.get("csrf_token")
            keep_logged_in = state_data.get("keep_logged_in", False)
            
            logger.debug(f"Decoded state data: callback_url={frontend_callback_url}, keep_logged_in={keep_logged_in}")
            
            if not frontend_callback_url:
                raise ValueError("Missing callback URL in state")
        except Exception as e:
            logger.error(f"Invalid state parameter: {str(e)}")
            error_params = {"error": "無效的狀態參數"}
            return RedirectResponse(url=f"{frontend_callback_url}?{urlencode(error_params)}")

        # 創建 flow 並獲取憑證
        try:
            # 創建新的 flow 實例
            flow = create_google_oauth_flow()
            
            # 從存儲中獲取 code_verifier
            code_verifier = get_stored_code_verifier(state)
            if code_verifier:
                flow.code_verifier = code_verifier
            
            logger.debug("Created Google OAuth flow, fetching token...")
            
            # 構建完整的授權響應 URL
            authorization_response = str(request.url)
            if not authorization_response.startswith('https'):
                authorization_response = authorization_response.replace('http', 'https', 1)
            
            # 設置授權響應
            flow.fetch_token(
                authorization_response=authorization_response,
                code=code
            )
            
            logger.debug("Successfully fetched token from Google")
            
        except Exception as e:
            logger.error(f"Failed to fetch token: {str(e)}", exc_info=True)
            error_params = {"error": f"無法從Google獲取令牌: {str(e)}"}
            return RedirectResponse(url=f"{frontend_callback_url}?{urlencode(error_params)}")

        # 從 ID token 獲取用戶信息
        try:
            credentials = flow.credentials
            try:
                id_info = verify_google_token(credentials.id_token)
                
                # 驗證失敗時處理錯誤
                if id_info is None:
                    logger.error("Google token verification failed, redirecting to frontend with error")
                    
                    # 構建用戶友好的錯誤信息，特別是對於時間同步問題
                    error_message = "Google身份驗證失敗 - 令牌驗證錯誤。"
                    error_message += " 這可能是由於伺服器時間同步問題導致的。"
                    error_message += " 您可以嘗試刷新頁面重試，或稍後再試。"
                    error_message += " 如果問題持續存在，請聯絡系統管理員檢查伺服器時間設置。"
                    
                    error_params = {
                        "error": "token_verification_failed", 
                        "error_description": error_message
                    }
                    error_redirect = f"{frontend_callback_url}?{urlencode(error_params)}"
                    return RedirectResponse(url=error_redirect)
            except HTTPException as token_err:
                # 處理verify_google_token中抛出的HTTPException
                logger.error(f"Google token verification error: {token_err.detail}")
                
                # 檢查是否是時鐘同步問題
                if "時間同步" in token_err.detail or "clock" in token_err.detail.lower():
                    error_message = "伺服器時間同步問題。"
                    error_message += " 這是伺服器端的問題，與您的操作無關。"
                    error_message += " 請稍後再試，或聯絡系統管理員解決此問題。"
                    
                    error_params = {
                        "error": "server_clock_sync_error", 
                        "error_description": error_message
                    }
                else:
                    error_params = {
                        "error": "google_token_verification_failed", 
                        "error_description": token_err.detail
                    }
                
                error_redirect = f"{frontend_callback_url}?{urlencode(error_params)}"
                return RedirectResponse(url=error_redirect)
            
            # 提取用戶信息
            email = id_info.get("email")
            if not email:
                error_params = {
                    "error": "missing_email",
                    "error_description": "Google帳戶中未找到電子郵件地址"
                }
                return RedirectResponse(url=f"{frontend_callback_url}?{urlencode(error_params)}")
                
            # 記錄用戶信息
            logger.info(f"Received user info from Google: {email}")
            
            # 檢查用戶是否已存在
            user = db.query(User).filter(User.email == email).first()
            
            # 如果用戶不存在，創建新用戶
            if not user:
                # 生成隨機密碼
                random_password = secrets.token_urlsafe(16)
                hashed_password = get_password_hash(random_password)
                
                # 從 Google 獲取用戶名（使用 email 前綴或 name）
                name = id_info.get("name", "")
                email_prefix = email.split("@")[0]
                username = name.replace(" ", "") or email_prefix
                
                # 確保用戶名唯一
                base_username = username
                count = 1
                while db.query(User).filter(User.username == username).first():
                    username = f"{base_username}{count}"
                    count += 1
                
                # 生成唯一推薦碼
                referral_code = generate_referral_code(db)
                
                # 創建新用戶
                user = User(
                    username=username,
                    email=email,
                    hashed_password=hashed_password,
                    is_active=True,
                    is_verified=True,  # Google 已驗證
                    oauth_provider="google",
                    full_name=id_info.get("name", ""),
                    avatar_url=id_info.get("picture", ""),
                    referral_code=referral_code
                )
                
                db.add(user)
                db.commit()
                db.refresh(user)
                logger.info(f"Created new user with Google OAuth: {username}")
            else:
                # 更新現有用戶的 OAuth 信息
                user.oauth_provider = "google"
                user.is_verified = True
                user.full_name = id_info.get("name", user.full_name) if not user.full_name else user.full_name
                user.avatar_url = id_info.get("picture", user.avatar_url) if not user.avatar_url else user.avatar_url
                user.last_login_at = get_china_time()
                db.commit()
                logger.info(f"Updated existing user with Google OAuth: {user.username}")
            
            # 創建訪問令牌和刷新令牌
            # 設置access token始終使用標準過期時間（15分鐘）
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            
            # 創建訪問令牌
            access_token = create_access_token(
                data={"sub": user.username},
                expires_delta=access_token_expires
            )
            
            # 設置refresh token過期時間
            refresh_token_expires = None  # 默認與access token相同
            if keep_logged_in:
                # 如果保持登入，刷新令牌使用更長的過期時間(REFRESH_TOKEN_EXPIRE_DAYS天)
                refresh_token_expires = timedelta(days=int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "90")))
            
            # 獲取裝置資訊
            user_agent = request.headers.get("user-agent", "")
            device_info = parse_user_agent(user_agent)
            
            # 創建或更新刷新令牌
            try:
                # 注意：create_refresh_token 會自動檢測並更新現有令牌
                new_refresh_token, _ = create_refresh_token(
                    user_id=user.id, 
                    db=db,
                    expires_delta=refresh_token_expires,
                    device_info=str(device_info)
                )
                
                # 成功建立刷新令牌
                logger.info(f"成功為Google登入用戶 {user.username} 創建刷新令牌")
            except Exception as token_error:
                logger.error(f"更新刷新令牌失敗: {str(token_error)}")
                # 如果無法創建或更新令牌，無法繼續處理
                raise token_error
            
            # 計算並明確區分不同令牌的過期時間（秒）
            access_token_expires_in = int(access_token_expires.total_seconds())
            
            # 刷新令牌過期時間
            refresh_token_expires_in = access_token_expires_in
            if keep_logged_in:
                # 如果保持登入，刷新令牌使用90天有效期
                refresh_token_expires_in = int(timedelta(days=int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "90"))).total_seconds())
            
            # 獲取用戶代理和IP
            client_ip = request.client.host
            
            # 創建登入成功事件（Google登入）
            try:
                # 提取設備信息
                device_info = parse_user_agent(user_agent)
                
                # 創建登入成功事件
                login_event = UserActionEvent(
                    event_type=EventType.LOGIN_SUCCESS,
                    source="google_oauth_service",
                    user_ids=[user.id],
                    action_type="google_login",
                    device_info=device_info,
                    ip_address=client_ip,
                    location="未知位置",
                    data={
                        "username": user.username,
                        "login_time": datetime.now().isoformat(),
                        "keep_logged_in": keep_logged_in,
                        "user_agent": user_agent,
                        "login_method": "google"
                    }
                )
                
                # 實現延遲處理Google登入事件
                async def delayed_google_event_processing():
                    logger.info(f"延遲 {LOGIN_EVENT_DELAY_SECONDS} 秒後處理Google登入成功事件，用戶: {user.username}")
                    await asyncio.sleep(LOGIN_EVENT_DELAY_SECONDS)
                    try:
                        # 創建新的數據庫會話
                        from ...db.database import SessionLocal
                        async_db = SessionLocal()
                        try:
                            await event_manager.process_event(login_event, async_db)
                            logger.info(f"成功處理延遲的Google登入事件: {user.username}")
                        finally:
                            async_db.close()
                    except Exception as delayed_err:
                        logger.error(f"延遲處理Google登入事件時發生錯誤: {str(delayed_err)}")
                
                # 創建任務但不等待完成
                asyncio.create_task(delayed_google_event_processing())
                logger.info(f"已安排延遲處理Google登入事件: {user.username}")
            except Exception as event_error:
                # 記錄錯誤但不中斷登入流程
                logger.error(f"設置延遲Google登入事件失敗: {str(event_error)}")
            
            # 構建重定向 URL
            redirect_params = {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": access_token_expires_in,  # access token 過期時間
                "refresh_token_expires_in": refresh_token_expires_in,  # 新增: refresh token 過期時間
                "keep_logged_in": str(keep_logged_in).lower()
            }
            logger.debug(f"準備重定向，參數為: {redirect_params}")

            # 使用 urlencode 構建查詢字符串
            redirect_url = f"{frontend_callback_url}?{urlencode(redirect_params)}"
            logger.info(f"重定向到前端: {redirect_url}")

            # 重定向到前端
            redirect_response = RedirectResponse(url=redirect_url)
            
            # 設置 HTTP-only cookie 存儲 refresh_token
            set_refresh_token_cookie(redirect_response, new_refresh_token, expires_delta=refresh_token_expires)
            logger.info(f"已重新設置 refresh token cookie (用戶: {user.username})")
            
            redirect_response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            redirect_response.headers["Pragma"] = "no-cache"
            redirect_response.headers["Expires"] = "0"
            return redirect_response
            
        except Exception as e:
            logger.error(f"Google OAuth callback error: {str(e)}", exc_info=True)
            # 構建錯誤重定向 URL
            error_message = str(e)
            
            # 檢查是否是時鐘同步問題
            if "clock" in error_message.lower() or "time" in error_message.lower() or "expired" in error_message.lower():
                error_params = {
                    "error": "time_sync_error",
                    "error_description": "處理Google登入時遇到伺服器時間同步問題，請稍後再試。"
                }
            else:
                error_params = {
                    "error": "oauth_process_error",
                    "error_description": f"處理Google登入時發生錯誤: {error_message}"
                }
                
            error_redirect = f"{frontend_callback_url}?{urlencode(error_params)}"
            return RedirectResponse(url=error_redirect)
            
    except HTTPException as e:
        # 構建錯誤重定向 URL
        error_params = {
            "error": f"http_{e.status_code}",
            "error_description": e.detail
        }
        error_redirect = f"{frontend_callback_url}?{urlencode(error_params)}"
        return RedirectResponse(url=error_redirect)
    except Exception as e:
        # 捕獲所有其他錯誤
        logger.error(f"Unexpected error in Google callback: {str(e)}", exc_info=True)
        error_params = {
            "error": "server_error",
            "error_description": f"處理Google登入時發生伺服器內部錯誤，請稍後再試。"
        }
        error_redirect = f"{frontend_callback_url}?{urlencode(error_params)}"
        return RedirectResponse(url=error_redirect) 

@router.get("/config")
async def get_auth_config():
    """
    獲取身份驗證相關的配置信息
    
    這個接口讓前端可以動態獲取後端的配置參數，
    特別是與令牌過期時間相關的設置，這樣前端可以
    隨著後端環境變數的變化而自動適應。
    """
    # 將天數轉換為秒，方便前端直接使用
    refresh_token_expires_in = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    
    return {
        # 訪問令牌有效期（分鐘）
        "access_token_expire_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        
        # 刷新令牌有效期（天）
        "refresh_token_expire_days": settings.REFRESH_TOKEN_EXPIRE_DAYS,
        
        # 刷新令牌有效期（秒）- 前端計算過期時間更方便
        "refresh_token_expires_in": refresh_token_expires_in,
        
        # 刷新閾值（秒）- 當訪問令牌剩餘有效期少於此值時自動刷新
        "refresh_threshold_seconds": settings.REFRESH_THRESHOLD_SECONDS,
        
        # 兩因素認證碼有效期（分鐘）
        "two_factor_expire_minutes": settings.TWO_FACTOR_EXPIRE_MINUTES,
        
        # Cookie安全設定
        "use_secure_cookies": settings.USE_SECURE_COOKIES,
        "cookie_domain": settings.COOKIE_DOMAIN,
        "cookie_samesite": settings.COOKIE_SAMESITE,
    }

# 添加一個簡單的User Agent解析函數
def parse_user_agent(user_agent_string: str) -> Dict[str, str]:
    """解析User Agent字符串獲取設備信息"""
    device_info = {
        "name": "未知設備",
        "type": "unknown",
        "os": "未知系統",
        "browser": "未知瀏覽器"
    }
    
    if not user_agent_string:
        return device_info
        
    ua = user_agent_string.lower()
    
    # 檢測設備類型和操作系統
    if "mobile" in ua or "android" in ua or "iphone" in ua or "ipad" in ua:
        device_info["type"] = "mobile"
        
        if "iphone" in ua:
            device_info["name"] = "iPhone"
            device_info["os"] = "iOS"
        elif "ipad" in ua:
            device_info["name"] = "iPad"
            device_info["os"] = "iOS"
        elif "android" in ua:
            # 嘗試提取具體的Android設備名稱
            android_device_match = re.search(r"android.*?;\s*([^;)]+)[\s;)]", ua)
            if android_device_match:
                device_info["name"] = android_device_match.group(1).strip()
            else:
                device_info["name"] = "Android裝置"
            device_info["os"] = "Android"
    else:
        device_info["type"] = "desktop"
        
        if "windows" in ua:
            device_info["name"] = "Windows電腦"
            device_info["os"] = "Windows"
            # 檢測Windows版本
            if "windows nt 10" in ua:
                device_info["os"] = "Windows 10/11"
            elif "windows nt 6.3" in ua:
                device_info["os"] = "Windows 8.1"
            elif "windows nt 6.2" in ua:
                device_info["os"] = "Windows 8"
            elif "windows nt 6.1" in ua:
                device_info["os"] = "Windows 7"
        elif "macintosh" in ua or "mac os" in ua:
            device_info["name"] = "Mac電腦"
            device_info["os"] = "macOS"
        elif "linux" in ua:
            device_info["name"] = "Linux電腦"
            device_info["os"] = "Linux"
    
    # 檢測瀏覽器
    browser = "未知瀏覽器"
    if "chrome" in ua and "edg" not in ua and "opr" not in ua and "samsung" not in ua:
        browser = "Chrome瀏覽器"
    elif "firefox" in ua:
        browser = "Firefox瀏覽器"
    elif "safari" in ua and "chrome" not in ua:
        browser = "Safari瀏覽器"
    elif "edg" in ua:
        browser = "Edge瀏覽器"
    elif "opr" in ua or "opera" in ua:
        browser = "Opera瀏覽器"
    elif "samsung" in ua:
        browser = "Samsung瀏覽器"
    
    device_info["browser"] = browser
    
    # 整合設備和操作系統為更友好的顯示名稱
    if device_info["type"] == "desktop":
        device_info["display_name"] = f"{device_info['os']}設備"
    else:
        device_info["display_name"] = device_info["name"]
    
    return device_info 