"""
令牌驗證優化模組

此模組實現了高效的令牌驗證策略，通過分層驗證和內存緩存
大幅提高令牌驗證性能，減少不必要的計算和數據庫查詢。
採用階層式驗證方法，根據需要進行不同深度的驗證。
"""

import base64
import hashlib
import json
import time
import logging
import threading
import jwt
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List, Union

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.user import User

# 設置日誌記錄
logger = logging.getLogger(__name__)

class TokenValidationResult:
    """
    令牌驗證結果，包含不同級別的信息
    
    保存令牌驗證的各種結果信息，包括驗證級別、用戶信息等。
    根據驗證深度，可能包含不同程度的信息。
    """
    def __init__(self):
        self.valid = False
        self.token_payload = None
        self.user_id = None
        self.username = None
        self.validation_level = 0  # 0:無效, 1:結構有效, 2:簽名有效, 3:數據庫確認
        self.error = None

class JWTSignatureCache:
    """
    JWT簽名緩存，減少重複的密碼學運算
    
    使用進程內記憶體緩存JWT令牌的驗證結果，避免重複執行
    昂貴的密碼學運算。實現定時清理過期項目，確保緩存大小可控。
    """
    
    def __init__(self, max_size=10000, ttl_seconds=300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache = {}
        self.expiry = {}
        self.lock = threading.RLock()
        self.last_cleanup = time.time()
        self.cleanup_interval = 60  # 每分鐘清理一次
        
    def get(self, token_signature):
        """獲取緩存的簽名驗證結果"""
        with self.lock:
            current_time = time.time()
            
            # 檢查是否在緩存中且未過期
            if token_signature in self.cache and self.expiry.get(token_signature, 0) > current_time:
                # 更新使用時間
                self.expiry[token_signature] = current_time + self.ttl_seconds
                return self.cache[token_signature]
                
            return None
            
    def set(self, token_signature, validation_result):
        """緩存簽名驗證結果"""
        with self.lock:
            current_time = time.time()
            
            # 定期清理
            if current_time - self.last_cleanup > self.cleanup_interval:
                self._cleanup_expired()
                self.last_cleanup = current_time
            
            # 檢查緩存大小
            if len(self.cache) >= self.max_size:
                # 刪除最舊的10%項目
                self._remove_oldest(int(self.max_size * 0.1))
                
            # 添加到緩存
            self.cache[token_signature] = validation_result
            self.expiry[token_signature] = current_time + self.ttl_seconds
            
    def _cleanup_expired(self):
        """清理過期的緩存項"""
        current_time = time.time()
        expired_keys = [k for k, v in self.expiry.items() if v <= current_time]
        
        for k in expired_keys:
            if k in self.cache:
                del self.cache[k]
            if k in self.expiry:
                del self.expiry[k]
        
        if expired_keys and settings.DEBUG:
            logger.debug(f"已清理 {len(expired_keys)} 個過期令牌緩存項")
            
    def _remove_oldest(self, count):
        """刪除最舊的緩存項"""
        if not self.expiry:
            return
            
        # 按過期時間排序，刪除最早過期的項目
        sorted_items = sorted(self.expiry.items(), key=lambda x: x[1])
        to_remove = sorted_items[:count]
        
        for k, _ in to_remove:
            if k in self.cache:
                del self.cache[k]
            if k in self.expiry:
                del self.expiry[k]
                
        if to_remove and settings.DEBUG:
            logger.debug(f"已刪除 {len(to_remove)} 個最舊令牌緩存項")
            
    def clear(self):
        """清空緩存"""
        with self.lock:
            self.cache.clear()
            self.expiry.clear()

class TokenValidationCache:
    """
    完整令牌驗證結果緩存
    
    緩存完整的令牌驗證結果，包括用戶信息，避免重複驗證
    相同的令牌。使用內存緩存，定期清理過期項目。
    """
    
    def __init__(self, max_size=5000, ttl_seconds=60):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache = {}
        self.expiry = {}
        self.lock = threading.RLock()
        self.last_cleanup = time.time()
        self.cleanup_interval = 30  # 每30秒清理一次
        
    def get(self, token_key):
        """獲取緩存的令牌驗證結果"""
        with self.lock:
            current_time = time.time()
            
            # 檢查是否在緩存中且未過期
            if token_key in self.cache and self.expiry.get(token_key, 0) > current_time:
                return self.cache[token_key]
                
            return None
            
    def set(self, token_key, result: TokenValidationResult):
        """緩存令牌驗證結果"""
        with self.lock:
            current_time = time.time()
            
            # 定期清理
            if current_time - self.last_cleanup > self.cleanup_interval:
                self._cleanup_expired()
                self.last_cleanup = current_time
            
            # 檢查緩存大小
            if len(self.cache) >= self.max_size:
                # 刪除最舊的10%項目
                self._remove_oldest(int(self.max_size * 0.1))
                
            # 添加到緩存
            self.cache[token_key] = result
            self.expiry[token_key] = current_time + self.ttl_seconds
            
    def _cleanup_expired(self):
        """清理過期的緩存項"""
        current_time = time.time()
        expired_keys = [k for k, v in self.expiry.items() if v <= current_time]
        
        for k in expired_keys:
            if k in self.cache:
                del self.cache[k]
            if k in self.expiry:
                del self.expiry[k]
        
        if expired_keys and settings.DEBUG:
            logger.debug(f"已清理 {len(expired_keys)} 個過期驗證結果緩存")
            
    def _remove_oldest(self, count):
        """刪除最舊的緩存項"""
        if not self.expiry:
            return
            
        # 按過期時間排序，刪除最早過期的項目
        sorted_items = sorted(self.expiry.items(), key=lambda x: x[1])
        to_remove = sorted_items[:count]
        
        for k, _ in to_remove:
            if k in self.cache:
                del self.cache[k]
            if k in self.expiry:
                del self.expiry[k]
                
        if to_remove and settings.DEBUG:
            logger.debug(f"已刪除 {len(to_remove)} 個最舊驗證結果緩存")
            
    def clear(self):
        """清空緩存"""
        with self.lock:
            self.cache.clear()
            self.expiry.clear()

# 創建全局緩存實例
jwt_sig_cache = JWTSignatureCache()
token_validation_cache = TokenValidationCache()

def validate_token_tiered(token: str, db: Session, required_level: int = 3) -> TokenValidationResult:
    """
    實現階層式令牌驗證，根據需要的級別進行不同深度的驗證
    
    驗證級別:
    1 - 結構驗證: 檢查令牌格式和基本結構
    2 - 密碼驗證: 驗證簽名和過期時間
    3 - 數據庫驗證: 確認用戶存在且令牌有效
    
    參數:
        token: 要驗證的令牌
        db: 數據庫會話
        required_level: 需要的驗證級別(1-3)
        
    返回:
        TokenValidationResult: 驗證結果對象
    """
    result = TokenValidationResult()
    
    # 快速失敗檢查
    if not token:
        result.error = "缺少令牌"
        return result
        
    # 生成用於緩存的令牌鍵
    token_fingerprint = hashlib.md5(token.encode()).hexdigest()[:16]
    cache_key = f"token_validation:{token_fingerprint}"
    
    # 檢查完整令牌驗證緩存
    cached_result = token_validation_cache.get(cache_key)
    if cached_result and cached_result.validation_level >= required_level:
        return cached_result
    
    try:
        # 級別 1: 結構驗證
        try:
            # 檢查令牌基本結構，不驗證簽名
            token_parts = token.split('.')
            if len(token_parts) != 3:
                result.error = "令牌結構無效"
                return result
                
            # 解碼頭部和載荷
            header_raw = token_parts[0] + '=' * (-len(token_parts[0]) % 4)  # 添加填充
            payload_raw = token_parts[1] + '=' * (-len(token_parts[1]) % 4)  # 添加填充
            
            try:
                header = json.loads(base64.b64decode(header_raw).decode())
                payload = json.loads(base64.b64decode(payload_raw).decode())
            except Exception as e:
                result.error = f"令牌解碼失敗: {str(e)}"
                return result
            
            # 檢查必要字段
            if 'alg' not in header or 'sub' not in payload or 'exp' not in payload:
                result.error = "令牌缺少必要字段"
                return result
                
            # 檢查令牌是否已過期
            if payload.get('exp', 0) < time.time():
                result.error = "令牌已過期"
                return result
                
            result.validation_level = 1
            result.token_payload = payload
        except Exception as e:
            result.error = f"令牌結構驗證失敗: {str(e)}"
            return result
            
        # 如果只需要結構驗證，提前返回
        if required_level == 1:
            result.valid = True
            token_validation_cache.set(cache_key, result)
            return result
            
        # 級別 2: 密碼驗證
        try:
            # 提取令牌簽名部分作為緩存鍵
            signature_key = f"{token_parts[0]}.{token_parts[2]}"
            
            # 檢查簽名緩存
            sig_valid = jwt_sig_cache.get(signature_key)
            
            if sig_valid is None:
                # 如果緩存中沒有，執行完整驗證
                try:
                    # 驗證簽名
                    payload = jwt.decode(
                        token, 
                        settings.SECRET_KEY, 
                        algorithms=[settings.ALGORITHM]
                    )
                    # 驗證成功
                    sig_valid = True
                    # 緩存結果
                    jwt_sig_cache.set(signature_key, True)
                except jwt.InvalidTokenError:
                    # 驗證失敗
                    sig_valid = False
                    # 緩存結果
                    jwt_sig_cache.set(signature_key, False)
                    
            if not sig_valid:
                result.error = "令牌簽名無效"
                return result
                
            result.validation_level = 2
            result.token_payload = payload
        except Exception as e:
            result.error = f"令牌簽名驗證失敗: {str(e)}"
            return result
            
        # 如果只需要密碼驗證，提前返回
        if required_level == 2:
            result.valid = True
            token_validation_cache.set(cache_key, result)
            return result
            
        # 級別 3: 數據庫驗證
        try:
            # 從令牌獲取用戶名
            username = payload.get("sub")
            if not username:
                result.error = "令牌缺少用戶標識"
                return result
                
            # 查詢數據庫中的用戶
            user = db.query(User).filter(User.username == username).first()
            
            if not user:
                result.error = "用戶不存在"
                return result
                
            if not user.is_active:
                result.error = "用戶已停用"
                return result
                
            result.validation_level = 3
            result.valid = True
            result.user_id = user.id
            result.username = user.username
            
            # 緩存完整驗證結果
            token_validation_cache.set(cache_key, result)
            
            return result
            
        except Exception as e:
            result.error = f"數據庫驗證失敗: {str(e)}"
            return result
    
    except Exception as e:
        result.error = f"令牌驗證過程中發生錯誤: {str(e)}"
        return result

def verify_token_optimized(token: str, db: Session) -> dict:
    """
    優化的令牌驗證函數，使用階層式驗證和緩存提高性能
    
    參數:
        token: 要驗證的令牌
        db: 數據庫會話
        
    返回:
        dict: 令牌載荷
        
    異常:
        HTTPException: 如果令牌無效則引發異常
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少認證令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 階層式驗證
    validation_result = validate_token_tiered(token, db, required_level=3)
    
    if not validation_result.valid:
        # 根據錯誤類型設置適當的錯誤消息
        error_detail = validation_result.error or "無效的認證令牌"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_detail,
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    return validation_result.token_payload

def cleanup_token_caches():
    """
    清理令牌相關的所有緩存
    
    定期調用此函數以確保系統不會佔用過多記憶體
    """
    try:
        jwt_sig_cache._cleanup_expired()
        token_validation_cache._cleanup_expired()
        logger.debug("已完成令牌緩存清理")
    except Exception as e:
        logger.error(f"清理令牌緩存時發生錯誤: {str(e)}") 