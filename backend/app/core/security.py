import os
import json
import secrets
import logging
import string
import random
import time
import uuid
import base64
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple, Union

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests

from app.db.database import get_db
from app.db.models.user import User, RefreshToken
from app.core.token_grace_store import token_grace_store
from app.core.config import settings

# 設定日誌記錄器
logger = logging.getLogger(__name__)

# 載入環境變數，確保能夠獲取敏感配置信息
load_dotenv()

# 配置密碼上下文，使用 bcrypt 演算法進行密碼雜湊和驗證
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT相關配置，用於使用者認證及授權
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")  # 從環境變數獲取密鑰
ALGORITHM = "HS256"  # 使用 HMAC-SHA-256 演算法
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))  # 存取令牌有效期
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))  # 刷新令牌預設30天有效

# API密鑰加密密鑰（從SECRET_KEY派生或直接從環境變數獲取）
API_ENCRYPTION_KEY = os.getenv("API_ENCRYPTION_KEY", None)
if not API_ENCRYPTION_KEY:
    # 如果未設置專用加密密鑰，則從SECRET_KEY派生
    # 不直接使用SECRET_KEY作為加密密鑰，以便可以在需要時單獨更換兩個密鑰
    salt = b'cryptotrading_salt_for_api_keys'  # 注意：在生產環境中應使用隨機鹽值並安全存儲
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),  # 使用SHA-256演算法
        length=32,                  # 生成32位元組長度的密鑰
        salt=salt,                  # 使用預定義的鹽值
        iterations=100000,          # 執行10萬次迭代以增強安全性
    )
    # 從SECRET_KEY派生一個密鑰
    derived_key = base64.urlsafe_b64encode(kdf.derive(SECRET_KEY.encode()))
    API_ENCRYPTION_KEY = derived_key

# 確保API_ENCRYPTION_KEY是位元組類型
if isinstance(API_ENCRYPTION_KEY, str):
    API_ENCRYPTION_KEY = API_ENCRYPTION_KEY.encode()

# 創建Fernet加密器，用於對API密鑰等敏感資料進行加密和解密
fernet = Fernet(API_ENCRYPTION_KEY)

# 創建OAuth2密碼驗證器，用於API端點的身份驗證
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# Google OAuth2 配置，用於第三方身份驗證
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "your-google-client-id")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "your-google-client-secret")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/v1/auth/google/callback")

# Google OAuth2 權限範圍定義
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/userinfo.email",     # 請求獲取使用者電子郵件
    "https://www.googleapis.com/auth/userinfo.profile",   # 請求獲取使用者個人資料
    "openid"                                              # OpenID Connect認證
]

# 用於存儲 PKCE 驗證碼的字典（PKCE: Proof Key for Code Exchange，用於增強OAuth安全性）
_code_verifier_store = {}

def clean_api_key(api_key: str) -> str:
    """
    清理API密鑰字符串
    
    移除可能影響API密鑰使用的無用字符，如引號、空格等。
    
    參數:
        api_key: 原始API密鑰字符串
        
    返回:
        清理後的API密鑰字符串
    """
    if not api_key:
        return None
        
    # 記錄原始長度（不顯示實際內容，保護敏感信息）
    original_length = len(api_key)
    
    # 移除首尾引號（處理多種引號情況）
    for quote in ['"', "'", '"', '"', ''', ''']:
        if api_key.startswith(quote) and api_key.endswith(quote):
            api_key = api_key[1:-1]
            break
            
    # 移除空白字符和控制字符
    api_key = api_key.strip()
    
    # 移除不可見字符和控制字符
    printable_set = set(string.printable)
    api_key = ''.join(c for c in api_key if c in printable_set)
    
    # 檢查是否有轉義字符（如 \n, \t 等）並移除
    api_key = api_key.replace('\\n', '').replace('\\r', '').replace('\\t', '')
    
    # 記錄清理後的長度和變化
    cleaned_length = len(api_key)
    if original_length != cleaned_length:
        logger.debug(f"API密鑰清理: 原始長度 {original_length} -> 清理後長度 {cleaned_length}")
    
    return api_key

def standardize_api_key(api_key: str) -> str:
    """
    標準化API密鑰格式
    
    確保API密鑰格式一致，以便後續加密和使用。
    這是clean_api_key的增強版，添加了更多針對API密鑰的特定處理。
    
    參數:
        api_key: 原始API密鑰字符串
        
    返回:
        標準化後的API密鑰字符串
    """
    if not api_key:
        return None
        
    # 先進行基本清理
    api_key = clean_api_key(api_key)
    
    # 針對API密鑰的特殊處理
    
    # 1. 移除常見的前綴（如果有的話）
    prefixes = ["key:", "apikey:", "key=", "apikey="]
    for prefix in prefixes:
        if api_key.lower().startswith(prefix):
            api_key = api_key[len(prefix):]
            break
            
    # 2. 移除URL編碼字符
    api_key = api_key.replace('%20', '').replace('%0A', '').replace('%0D', '')
    
    # 3. 移除可能的HTML實體
    api_key = api_key.replace('&nbsp;', '').replace('&quot;', '').replace('&apos;', '')
    
    # 4. 如果密鑰包含明顯分隔符，只取實際部分
    separators = ["|", ":", ";", ","]
    for sep in separators:
        if sep in api_key and api_key.count(sep) == 1:
            parts = api_key.split(sep)
            # 選擇看起來像密鑰的部分（通常更長且包含字母和數字）
            if len(parts[0].strip()) > len(parts[1].strip()):
                api_key = parts[0].strip()
            else:
                api_key = parts[1].strip()
            break
    
    # 再次清理空白字符，確保結果乾淨
    api_key = api_key.strip()
    
    return api_key

def encrypt_api_key(api_key: str) -> str:
    """
    加密API密鑰
    
    將使用者的API密鑰進行加密，以確保存儲在資料庫中的敏感資料安全。
    使用Fernet對稱加密演算法，該演算法提供了認證加密機制。
    
    參數:
        api_key: 明文API密鑰
        
    返回:
        加密後的API密鑰（base64編碼的字符串）
        
    若輸入為空，則返回None
    """
    if not api_key:
        return None
    
    # 先標準化API密鑰
    api_key = standardize_api_key(api_key)
    
    # 記錄標準化後的長度
    logger.debug(f"準備加密的API密鑰長度: {len(api_key)}")
    
    try:
        # 加密API密鑰
        encrypted_data = fernet.encrypt(api_key.encode())
        # 返回base64編碼的字符串
        encrypted_str = encrypted_data.decode()
        logger.debug(f"加密後的API密鑰長度: {len(encrypted_str)}")
        return encrypted_str
    except Exception as e:
        logger.error(f"API密鑰加密失敗: {str(e)}")
        return None

def decrypt_api_key(encrypted_api_key: str, key_type: str = "未指定") -> str:
    """
    解密API密鑰
    
    解密從資料庫中讀取的加密API密鑰，使其可用於API呼叫。
    優先使用utf-8解碼，失敗則嘗試latin-1編碼。
    
    參數:
        encrypted_api_key: 加密的API密鑰（base64編碼的字符串）
        key_type: 密鑰類型標識，用於日誌記錄（例如："API Key", "API Secret"）
        
    返回:
        解密後的API密鑰明文
        
    若輸入為空或解密失敗，則返回None
    """
    if not encrypted_api_key:
        return None
    
    # 我們不再在這裡記錄解密過程，讓調用者決定如何記錄
    
    try:
        # 解密API密鑰
        decrypted_data = fernet.decrypt(encrypted_api_key.encode())
        decrypted_api_key = decrypted_data.decode()
        
        # 標準化並返回解密後的API密鑰
        result = standardize_api_key(decrypted_api_key)
        
        return result
    except UnicodeDecodeError:
        # 嘗試使用latin-1編碼
        try:
            decrypted_data = fernet.decrypt(encrypted_api_key.encode())
            decrypted_api_key = decrypted_data.decode('latin-1')
            result = standardize_api_key(decrypted_api_key)
            
            return result
        except Exception as e:
            logger.error(f"{key_type}使用latin-1編碼解密失敗: {str(e)[:50]}")
            return None
    except Exception as e:
        logger.error(f"{key_type}解密失敗: {str(e)[:50]}")
        return None

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    驗證密碼
    
    比較明文密碼與存儲的雜湊密碼是否匹配。首先嘗試使用CryptContext進行驗證，
    如果失敗則嘗試使用bcrypt直接驗證（處理可能存在的不同雜湊格式）。
    
    參數:
        plain_password: 使用者輸入的明文密碼
        hashed_password: 資料庫中存儲的雜湊密碼
        
    返回:
        密碼是否匹配的布林值
    """
    try:
        # 嘗試使用 pwd_context 進行驗證
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        # 記錄錯誤，但不拋出異常
        logger.warning(f"密碼驗證錯誤: {str(e)}")

        # 嘗試處理不同格式的密碼雜湊
        # 如果是bcrypt格式但前綴不匹配
        if hashed_password.startswith('$2b$') or hashed_password.startswith('$2a$'):
            import bcrypt
            try:
                return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
            except Exception as bcrypt_err:
                logger.warning(f"bcrypt驗證錯誤: {str(bcrypt_err)}")

        return False

def get_password_hash(password: str) -> str:
    """
    生成密碼雜湊
    
    對明文密碼進行雜湊處理，使用bcrypt演算法確保安全性。
    
    參數:
        password: 需要雜湊的明文密碼
        
    返回:
        雜湊後的密碼字符串
    """
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    創建存取令牌
    
    生成JWT（JSON Web Token）作為使用者身份驗證的存取令牌。
    
    參數:
        data: 要編碼到令牌中的資料，通常包含使用者標識
        expires_delta: 令牌過期時間增量，如未提供則預設15分鐘
        
    返回:
        JWT格式的存取令牌
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def clean_revoked_tokens_for_user_device(db: Session, user_id: int, device_id: str) -> int:
    """
    清理用戶在特定設備上的已撤銷或過期令牌
    
    確保在創建新的令牌前，清除可能導致唯一約束衝突的舊令牌。
    
    參數:
        db: 資料庫會話
        user_id: 使用者ID
        device_id: 設備ID
        
    返回:
        已刪除的令牌數量
    """
    try:
        count = db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.device_id == device_id,
            (RefreshToken.is_revoked == True) | (RefreshToken.expires_at < datetime.utcnow())
        ).delete()
        
        if count > 0:
            db.commit()
            logger.info(f"已刪除用戶 {user_id} 在設備 {device_id} 上的 {count} 個無效令牌")
        
        return count
    except Exception as e:
        db.rollback()
        logger.error(f"清理已撤銷令牌時發生錯誤: {e}")
        return 0

def create_refresh_token(
    db: Session, 
    user_id: int,
    expires_delta: Optional[timedelta] = None,
    device_info: Optional[str] = None
) -> Tuple[str, RefreshToken]:
    """
    創建或更新刷新令牌
    
    如果指定用戶在指定設備上已有令牌，則更新該令牌而非創建新令牌。
    這種"更新而非新增"的策略可以減少資料庫中的冗餘記錄，提高查詢效能。
    
    參數:
        db: 資料庫會話
        user_id: 使用者ID
        expires_delta: 可選的過期時間，如果不提供則使用預設值（30天）
        device_info: 裝置資訊，用於識別令牌來源
    
    返回:
        Tuple[str, RefreshToken]: 刷新令牌字符串和資料庫中的刷新令牌物件
    """
    # 生成隨機令牌
    token = secrets.token_urlsafe(32)
    
    # 對令牌進行雜湊處理
    token_hash = pwd_context.hash(token)
    
    # 計算過期時間
    if expires_delta:
        expires = datetime.utcnow() + expires_delta
    else:
        expires = datetime.utcnow() + timedelta(days=30)  # 預設30天過期
    
    # 從設備資訊中提取設備ID，如果沒有則使用預設值
    device_id = None
    if device_info:
        # 嘗試從設備資訊中解析出唯一標識符
        try:
            device_info_dict = json.loads(device_info) if isinstance(device_info, str) else device_info
            if isinstance(device_info_dict, dict):
                # 使用設備資訊的組合作為設備ID
                parts = []
                if device_info_dict.get('browser'):
                    parts.append(device_info_dict['browser'])
                if device_info_dict.get('os'):
                    parts.append(device_info_dict['os'])
                if device_info_dict.get('device'):
                    parts.append(device_info_dict['device'])
                if parts:
                    device_id = "_".join(parts)
        except:
            # 如果解析失敗，使用原始字符串的雜湊作為設備ID
            import hashlib
            device_id = hashlib.md5(str(device_info).encode()).hexdigest()[:20]
    
    # 如果沒有提取到設備ID，使用預設值
    if not device_id:
        device_id = "default_device"
    
    # 重要：清理該用戶在當前設備上的已撤銷或過期令牌，避免唯一約束衝突
    clean_revoked_tokens_for_user_device(db, user_id, device_id)
    
    # 查找該用戶在該設備上是否已有未撤銷的令牌
    existing_token = db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.device_id == device_id,
        RefreshToken.is_revoked == False
    ).first()
    
    if existing_token:
        # 更新前先將舊令牌添加到寬限期存儲
        try:
            # 為了安全起見，驗證舊令牌存在
            old_token_hash = existing_token.token_hash
            # 由於我們無法還原原始令牌，這裡使用令牌雜湊作為識別
            # 在實際應用中，可能需要另外的機制來處理這種情況
            old_token_id = f"{existing_token.id}-{device_id}"
            
            # 將舊令牌ID加入寬限期緩存
            token_grace_store.add_revoked_token(old_token_id, str(user_id))
            logger.debug(f"將用戶 {user_id} 的舊令牌添加到寬限期緩存")
        except Exception as e:
            logger.warning(f"添加舊令牌到寬限期緩存失敗: {e}")
        
        # 更新現有令牌
        logger.info(f"更新用戶 {user_id} 在設備 {device_id} 上的現有令牌")
        existing_token.token_hash = token_hash
        existing_token.expires_at = expires
        existing_token.updated_at = datetime.utcnow()
        existing_token.device_info = device_info
        db_token = existing_token
    else:
        # 創建新的刷新令牌記錄
        logger.info(f"為用戶 {user_id} 在設備 {device_id} 上創建新令牌")
        db_token = RefreshToken(
            token_hash=token_hash,  # 存儲雜湊值，而非原始令牌
            user_id=user_id,
            device_id=device_id,
            expires_at=expires,
            is_revoked=False,
            device_info=device_info
        )
        db.add(db_token)
    
    # 提交變更到資料庫
    try:
        db.commit()
        db.refresh(db_token)
    except Exception as e:
        db.rollback()
        logger.error(f"保存令牌時發生錯誤: {e}")
        # 再次嘗試清理可能的衝突記錄並重試
        clean_revoked_tokens_for_user_device(db, user_id, device_id)
        if existing_token:
            db.refresh(existing_token)
        else:
            db.add(db_token)
        db.commit()
        db.refresh(db_token)
    
    return token, db_token

def verify_refresh_token(db: Session, token: str) -> Optional[User]:
    """
    驗證刷新令牌並返回相關聯的使用者
    
    檢查刷新令牌是否有效且未過期，並返回對應的使用者資訊。
    透過雜湊比對方式驗證令牌，增強安全性。
    
    如果令牌不在數據庫中但在寬限期內，會嘗試獲取該用戶的當前有效令牌。
    
    參數:
        db: 資料庫會話
        token: 刷新令牌
        
    返回:
        如果令牌有效，則返回使用者物件，否則返回None
    """
    # 輕量級初步驗證 - 快速過濾明顯無效的令牌
    if not token or len(token) < 16:
        if settings.DEBUG:
            logger.debug("令牌格式無效或過短")
        return None
    
    # 添加簡單的令牌驗證結果緩存
    if not hasattr(verify_refresh_token, "cache"):
        verify_refresh_token.cache = {}
    
    # 生成高效的令牌指紋 (不是完整的哈希，僅用於緩存鍵)
    token_fingerprint = f"{token[:4]}..{token[-4:]}"
    cache_key = f"token:{token_fingerprint}"
    
    # 檢查緩存 - 緩存讀取優先採用無鎖設計
    now = time.time()
    if cache_key in verify_refresh_token.cache:
        cache_data = verify_refresh_token.cache[cache_key]
        # 緩存有效期5秒，適合高頻刷新場景
        if now - cache_data["timestamp"] < 5:
            if settings.DEBUG:
                logger.debug(f"使用緩存的令牌驗證結果: {token_fingerprint}")
            return cache_data["user"]
            
    try:
        # 使用更高效的查詢策略
        now_dt = datetime.utcnow()
        
        # 檢查寬限期存儲 - 這通常比數據庫查詢更快
        grace_user_id = token_grace_store.get_user_id(token)
        
        if grace_user_id:
            # 令牌在寬限期內，查找該用戶的當前有效令牌
            # 避免詳細日誌，減少IO開銷
            if settings.DEBUG:
                logger.debug(f"令牌在寬限期內，用戶ID: {grace_user_id}")
            
            # 快速查詢：只獲取必要欄位的用戶信息
            user = db.query(User).filter(User.id == grace_user_id).first()
            
            # 添加標記，表示這是通過寬限期機制驗證的
            if user:
                setattr(user, "_from_grace_period", True)
                
                # 存入緩存
                verify_refresh_token.cache[cache_key] = {
                    "user": user,
                    "timestamp": now
                }
                
                return user
        
        # 高效的活動令牌查詢：限制查詢範圍和返回數量
        # 首先嘗試使用索引查詢，只返回最近更新的有限數量令牌
        active_tokens = db.query(RefreshToken).filter(
            RefreshToken.is_revoked == False,
            RefreshToken.expires_at > now_dt
        ).order_by(RefreshToken.updated_at.desc()).limit(10).all()
        
        # 找到匹配的令牌 - 使用預先過濾減少密碼驗證次數
        matched_token = None
        for db_token in active_tokens:
            try:
                # 快速預過濾：如果令牌長度和特徵不匹配，跳過昂貴的密碼驗證
                if db_token.token_hash.startswith('$2') and pwd_context.verify(token, db_token.token_hash):
                    matched_token = db_token
                    
                    # 最小化更新：只更新必要字段
                    if (now_dt - db_token.updated_at).total_seconds() > 60:
                        db_token.updated_at = now_dt
                        db.commit()
                    
                    break
            except Exception as e:
                # 減少日誌噪音，只記錄非預期錯誤
                if not isinstance(e, ValueError):
                    logger.warning(f"令牌雜湊驗證異常: {e}")
                continue
        
        # 查詢關聯的用戶
        user = None
        if matched_token:
            # 延遲載入：只在需要時查詢用戶
            user = db.query(User).filter(User.id == matched_token.user_id).first()
        
        if not user:
            # 減少日誌噪音，使用簡潔信息
            if settings.DEBUG:
                if matched_token:
                    logger.debug(f"找不到與令牌關聯的用戶，用戶ID: {matched_token.user_id}")
                else:
                    logger.debug("找不到有效的刷新令牌")
            return None
        
        # 存入緩存
        verify_refresh_token.cache[cache_key] = {
            "user": user,
            "timestamp": now
        }
        
        # 簡單的緩存清理 - 非阻塞且高效
        if len(verify_refresh_token.cache) > 100 and random.random() < 0.1:
            # 在10%的調用中清理緩存，避免每次調用都清理
            threading.Thread(
                target=lambda: _clean_verify_token_cache(verify_refresh_token.cache),
                daemon=True
            ).start()
            
        return user
    except Exception as e:
        logger.error(f"驗證刷新令牌時發生錯誤: {e}")
        return None

# 非阻塞緩存清理函數
def _clean_verify_token_cache(cache):
    """清理令牌驗證緩存的過期項目"""
    try:
        # 獲取當前時間
        now = time.time()
        # 找出過期的鍵
        expired_keys = [
            k for k, v in cache.items() 
            if now - v["timestamp"] > 60  # 60秒後過期
        ]
        # 刪除過期項目
        for k in expired_keys:
            cache.pop(k, None)
    except Exception as e:
        logger.error(f"清理令牌驗證緩存時出錯: {e}")

def revoke_refresh_token(db: Session, token: str) -> bool:
    """
    撤銷刷新令牌（直接刪除而非標記）
    
    找到並直接從數據庫中刪除對應的刷新令牌記錄，避免唯一約束衝突。
    同時將令牌添加到寬限期存儲中，以允許在短時間內仍然可用。
    
    參數:
        db: 資料庫會話
        token: 刷新令牌
        
    返回:
        如果成功刪除，則返回True，否則返回False
    """
    try:
        # 查詢未過期的令牌
        active_tokens = db.query(RefreshToken).filter(
            RefreshToken.expires_at > datetime.utcnow()
        ).all()
        
        # 找到匹配的令牌
        deleted = False
        for db_token in active_tokens:
            try:
                if pwd_context.verify(token, db_token.token_hash):
                    # 記錄要刪除的令牌信息（用於日誌）
                    user_id = db_token.user_id
                    device_id = db_token.device_id
                    
                    # 將令牌添加到寬限期存儲中
                    try:
                        # 由於我們無法還原原始令牌，使用一個標識符
                        token_id = f"{db_token.id}-{device_id}"
                        token_grace_store.add_revoked_token(token_id, str(user_id))
                        logger.debug(f"已將用戶 {user_id} 的刷新令牌添加到寬限期緩存")
                    except Exception as e:
                        logger.warning(f"添加令牌到寬限期緩存失敗: {e}")
                    
                    # 直接刪除令牌而非標記為已撤銷
                    db.delete(db_token)
                    db.commit()
                    logger.info(f"已刪除用戶 {user_id} 在設備 {device_id} 上的刷新令牌")
                    deleted = True
                    break
            except Exception as e:
                logger.warning(f"令牌雜湊驗證失敗: {e}")
                continue
                
        return deleted
    except Exception as e:
        db.rollback()
        logger.error(f"刪除刷新令牌時發生錯誤: {e}")
        return False

def verify_token(token: str) -> dict:
    """
    驗證令牌
    
    解碼並驗證JWT令牌的有效性，確保其未被篡改且未過期。
    
    參數:
        token: JWT令牌
        
    返回:
        解碼後的令牌載荷（包含使用者資訊）
        
    若令牌無效或已過期，則拋出HTTPException異常
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無效的認證憑據",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    """
    獲取當前使用者
    
    從請求中的JWT令牌獲取當前已認證的使用者資訊。
    
    參數:
        db: 資料庫會話
        token: JWT認證令牌（從請求中獲取）
        
    返回:
        當前已認證的使用者物件
        
    若令牌無效、已過期或使用者不存在，則拋出相應的異常
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="無效的認證憑據",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # 解碼JWT令牌
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    # 查詢資料庫中的使用者
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="使用者不存在"
        )
    return user

async def get_current_active_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    """
    獲取當前活動使用者
    
    從請求中的JWT令牌獲取當前已認證的使用者，並確保該使用者處於活動狀態。
    
    參數:
        db: 資料庫會話
        token: JWT認證令牌（從請求中獲取）
        
    返回:
        當前已認證且處於活動狀態的使用者物件
        
    若使用者被禁用或令牌無效，則拋出相應的異常
    """
    # 首先獲取使用者資訊
    try:
        # 解碼JWT令牌
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="無效的認證憑據",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無效的認證憑據",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 查詢資料庫中的使用者
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="使用者不存在"
        )
    
    # 檢查使用者是否處於活動狀態
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="使用者已被禁用"
        )
        
    return user

async def get_current_admin_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    獲取當前管理員使用者
    
    確認當前使用者是否具有管理員權限，用於保護管理員專用的API端點。
    
    參數:
        current_user: 當前已認證的活動使用者
        
    返回:
        當前已認證且具有管理員權限的使用者物件
        
    若使用者沒有管理員權限，則拋出權限不足異常
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理員權限",
        )
    return current_user

def create_google_oauth_flow(state: str = None) -> Flow:
    """
    創建Google OAuth2認證流程
    
    配置OAuth2認證流程，用於實現使用Google帳號登入系統。
    
    參數:
        state: 狀態字符串，用於防止CSRF攻擊
        
    返回:
        配置好的Google OAuth2認證流程物件
    """
    # 獲取當前目錄路徑
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 創建OAuth流程
    flow = Flow.from_client_config(
        client_config={
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "project_id": "your-project-id",  # 可以安全地使用預設值
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uris": [GOOGLE_REDIRECT_URI],
                "javascript_origins": ["http://localhost:8000"]
            }
        },
        scopes=GOOGLE_SCOPES,
        redirect_uri=GOOGLE_REDIRECT_URI
    )
    
    # 使用PKCE增強流程安全性
    code_verifier = secrets.token_urlsafe(64)  # 生成隨機驗證碼
    code_challenge = code_verifier  # 簡化實現，在生產環境中應使用SHA-256哈希
    
    # 如果提供了狀態，則存儲驗證碼
    if state:
        _code_verifier_store[state] = code_verifier
        flow.code_verifier = code_verifier
        
    # 配置額外參數
    flow.authorization_url_kwargs = {
        "access_type": "offline",  # 啟用離線訪問，以便獲取refresh_token
        "include_granted_scopes": "true",  # 包括先前授予的範圍
        "prompt": "consent",  # 強制顯示同意頁面
        "response_type": "code",
        "code_challenge": code_challenge,
        "code_challenge_method": "plain"  # 簡化實現，生產環境應使用"S256"
    }
    
    # 添加狀態，用於防止CSRF攻擊
    if state:
        flow.authorization_url_kwargs["state"] = state
    
    return flow

def get_stored_code_verifier(state: str) -> Optional[str]:
    """
    獲取存儲的PKCE驗證碼
    
    根據狀態字符串獲取先前存儲的PKCE驗證碼，用於OAuth2授權流程。
    
    參數:
        state: 狀態字符串，用於識別特定的OAuth流程
        
    返回:
        與給定狀態關聯的PKCE驗證碼，如果不存在則返回None
    """
    # 從存儲中獲取驗證碼
    code_verifier = _code_verifier_store.get(state)
    
    # 如果找到了驗證碼，則從存儲中移除它（一次性使用）
    if code_verifier:
        del _code_verifier_store[state]
        
    return code_verifier

def verify_google_token(token: str) -> dict:
    """
    驗證Google ID令牌
    
    參數:
        token: Google提供的ID令牌
        
    返回:
        令牌中包含的使用者資訊
        
    若令牌無效或驗證失敗，則拋出HTTPException異常
    """
    try:
        # 設置時鐘偏差容許值（5秒）
        clock_skew_in_seconds = 5
        
        # 驗證ID令牌，增加時鐘偏差容許值
        idinfo = id_token.verify_oauth2_token(
            token, 
            requests.Request(), 
            GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=clock_skew_in_seconds
        )
        
        # 確認發行人
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise ValueError('發行人無效')
            
        # 返回令牌中的使用者資訊
        return idinfo
    except ValueError as e:
        # 捕獲驗證錯誤，記錄詳細錯誤信息
        error_message = str(e)
        logger.error(f"Google令牌驗證失敗: {error_message}")
        
        # 根據錯誤類型提供不同的錯誤消息
        if "Token used too early" in error_message:
            logger.error("時鐘同步問題: 伺服器時間可能不準確，請檢查系統時間設置")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="伺服器時間同步問題，請稍後再試或聯繫管理員"
            )
        elif "Token expired" in error_message:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google認證已過期，請重新登入"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="無效的Google認證令牌"
            ) 

def generate_referral_code(db: Session, length: int = 6) -> str:
    """
    生成唯一的用户推荐码
    
    参数:
        db: 数据库会话
        length: 推荐码长度，默认为6位
        
    返回:
        6位英数混合的唯一推荐码
    """
    from ..db.models import User
    
    # 字符集：大写字母和数字
    chars = string.ascii_uppercase + string.digits
    
    # 尝试最多100次生成唯一的推荐码
    for _ in range(100):
        # 生成随机推荐码
        code = ''.join(random.choice(chars) for _ in range(length))
        
        # 检查推荐码是否已存在
        exists = db.query(User).filter(User.referral_code == code).first()
        if not exists:
            return code
    
    # 如果100次都无法生成唯一码，则加入时间戳确保唯一性
    timestamp = str(int(time.time()))[-4:]
    code = ''.join(random.choice(chars) for _ in range(length - 4)) + timestamp
    
    return code 

async def verify_token_ws(token: str, db: Session) -> Optional[User]:
    """
    验证WebSocket连接的Token并返回对应用户
    
    此函数专门用于WebSocket连接的Token验证。与HTTP路由不同，
    WebSocket连接不能使用标准的依赖注入系统返回HTTP异常，
    因此此函数直接返回用户对象或None。
    
    参数:
        token: JWT认证令牌
        db: 数据库会话
        
    返回:
        验证成功时返回User对象，失败时返回None
    """
    try:
        # 解码JWT令牌
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
            
        # 查询数据库中的用户
        user = db.query(User).filter(User.username == username).first()
        if user is None or not user.is_active:
            return None
            
        return user
    except JWTError:
        return None 