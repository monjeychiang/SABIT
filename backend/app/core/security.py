from datetime import datetime, timedelta
from typing import Optional, Tuple
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordBearer
from fastapi import HTTPException, status, Depends
import os
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..db.models.user import User, RefreshToken
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import secrets
import uuid
import logging
import json
import string
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests
import random
import time

# 配置日誌記錄器，用於安全模組的日誌記錄
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

def decrypt_api_key(encrypted_api_key: str) -> str:
    """
    解密API密鑰
    
    解密從資料庫中讀取的加密API密鑰，使其可用於API呼叫。
    解密失敗會記錄錯誤，但不會中斷程序執行。
    
    參數:
        encrypted_api_key: 加密的API密鑰（base64編碼的字符串）
        
    返回:
        解密後的API密鑰明文
        
    若輸入為空或解密失敗，則返回None
    """
    if not encrypted_api_key:
        return None
    
    try:
        logger.debug(f"開始解密API密鑰，加密密鑰長度: {len(encrypted_api_key)}")
        
        # 解密API密鑰
        decrypted_data = fernet.decrypt(encrypted_api_key.encode())
        # 獲取解密後的字符串
        decrypted_api_key = decrypted_data.decode()
        
        # 記錄原始解密結果的長度（不顯示實際內容，保護敏感信息）
        logger.debug(f"原始解密API密鑰長度: {len(decrypted_api_key)}")
        
        # 標準化並返回解密後的API密鑰
        cleaned_api_key = standardize_api_key(decrypted_api_key)
        
        # 記錄清理前後長度差異
        if cleaned_api_key and len(cleaned_api_key) != len(decrypted_api_key):
            logger.debug(f"API密鑰清理: 原始長度 {len(decrypted_api_key)} -> 清理後長度 {len(cleaned_api_key)}")
        
        return cleaned_api_key
    except Exception as e:
        logger.error(f"API密鑰解密失敗: {str(e)}")
        if isinstance(e, UnicodeDecodeError):
            logger.error(f"這可能是編碼問題，嘗試不同的編碼...")
            try:
                # 嘗試使用latin-1編碼解碼
                decrypted_data = fernet.decrypt(encrypted_api_key.encode())
                decrypted_api_key = decrypted_data.decode('latin-1')
                return standardize_api_key(decrypted_api_key)
            except Exception as latin_err:
                logger.error(f"使用latin-1編碼解碼失敗: {str(latin_err)}")
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

def create_refresh_token(
    db: Session, 
    user_id: int,
    expires_delta: Optional[timedelta] = None
) -> Tuple[str, RefreshToken]:
    """
    創建刷新令牌
    
    生成刷新令牌並在資料庫中存儲相關資訊，用於獲取新的存取令牌。
    
    參數:
        db: 資料庫會話
        user_id: 使用者ID
        expires_delta: 可選的過期時間，如果不提供則使用預設值（30天）
    
    返回:
        Tuple[str, RefreshToken]: 刷新令牌字符串和資料庫中的刷新令牌物件
    """
    # 生成隨機令牌
    token = secrets.token_urlsafe(32)
    
    # 計算過期時間
    if expires_delta:
        expires = datetime.utcnow() + expires_delta
    else:
        expires = datetime.utcnow() + timedelta(days=30)  # 預設30天過期
    
    # 創建刷新令牌記錄
    db_token = RefreshToken(
        token=token,
        user_id=user_id,
        expires_at=expires,
        is_revoked=False
    )
    
    # 存儲到資料庫
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    
    return token, db_token

def verify_refresh_token(db: Session, token: str) -> Optional[User]:
    """
    驗證刷新令牌並返回相關聯的使用者
    
    檢查刷新令牌是否有效且未過期，並返回對應的使用者資訊。
    
    參數:
        db: 資料庫會話
        token: 刷新令牌
        
    返回:
        如果令牌有效，則返回使用者物件，否則返回None
    """
    # 查詢令牌
    db_token = db.query(RefreshToken).filter(
        RefreshToken.token == token,
        RefreshToken.is_revoked == False
    ).first()
    
    # 如果找不到令牌或已過期，則返回None
    if not db_token or db_token.expires_at < datetime.utcnow():
        return None
    
    # 查詢關聯的使用者
    user = db.query(User).filter(User.id == db_token.user_id).first()
    
    return user

def revoke_refresh_token(db: Session, token: str) -> bool:
    """
    撤銷刷新令牌
    
    直接從資料庫刪除指定的刷新令牌，而不是標記為已撤銷。
    用於使用者登出或密碼變更等場景。
    
    參數:
        db: 資料庫會話
        token: 刷新令牌
        
    返回:
        如果成功刪除，則返回True，否則返回False
    """
    try:
        # 直接刪除令牌記錄
        result = db.query(RefreshToken).filter(RefreshToken.token == token).delete()
        db.commit()
        
        # 如果刪除了記錄，返回True
        return result > 0
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