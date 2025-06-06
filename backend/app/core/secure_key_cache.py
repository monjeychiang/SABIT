from typing import Dict, Tuple, Optional, Any
import time
import threading
import logging
import os
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


class SecureKeyCache:
    """安全的API密鑰緩存管理器，用於存儲解密後的密鑰"""
    
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(SecureKeyCache, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.logger = logging.getLogger(__name__)
        
        # 使用內存加密保護緩存
        self._memory_key = os.urandom(32)  # 生成隨機內存加密密鑰
        self._cache = {}  # 加密後的密鑰緩存
        self._expiry = {}  # 密鑰過期時間
        self._default_ttl = 3600  # 預設過期時間(秒)
        
        # 啟動定期清理過期密鑰的線程
        self._cleanup_thread = threading.Thread(target=self._cleanup_expired_keys, daemon=True)
        self._cleanup_thread.start()
        
        self._initialized = True
        self.logger.info("安全密鑰緩存管理器已初始化")
    
    def _encrypt_value(self, value: str) -> bytes:
        """加密存儲在內存中的值"""
        iv = os.urandom(16)
        cipher = Cipher(
            algorithms.AES(self._memory_key),
            modes.CFB(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(value.encode()) + encryptor.finalize()
        return base64.b64encode(iv + encrypted)
    
    def _decrypt_value(self, encrypted: bytes) -> str:
        """解密存儲在內存中的值"""
        data = base64.b64decode(encrypted)
        iv = data[:16]
        cipher = Cipher(
            algorithms.AES(self._memory_key),
            modes.CFB(iv),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(data[16:]) + decryptor.finalize()
        return decrypted.decode()
    
    def set_keys(self, user_id: int, exchange: str, api_key: str, api_secret: str, ttl: int = None) -> None:
        """
        存儲用戶的API密鑰對
        
        Args:
            user_id: 用戶ID
            exchange: 交易所名稱
            api_key: 解密後的API Key
            api_secret: 解密後的API Secret
            ttl: 密鑰在緩存中的存活時間(秒)，None表示使用預設值
        """
        with self._lock:
            cache_key = (user_id, exchange)
            
            # 加密存儲密鑰
            encrypted_key = self._encrypt_value(api_key)
            encrypted_secret = self._encrypt_value(api_secret)
            
            self._cache[cache_key] = (encrypted_key, encrypted_secret)
            
            # 設置過期時間
            if ttl is None:
                ttl = self._default_ttl
            self._expiry[cache_key] = time.time() + ttl
            
            self.logger.debug(f"已安全緩存用戶 {user_id} 的 {exchange} API密鑰，過期時間 {ttl} 秒")
    
    def get_keys(self, user_id: int, exchange: str) -> Optional[Tuple[str, str]]:
        """
        獲取用戶的API密鑰對
        
        Args:
            user_id: 用戶ID
            exchange: 交易所名稱
            
        Returns:
            (api_key, api_secret) 元組，如果未找到則返回None
        """
        with self._lock:
            cache_key = (user_id, exchange)
            
            # 檢查是否存在且未過期
            if cache_key not in self._cache or time.time() > self._expiry.get(cache_key, 0):
                return None
            
            # 獲取並解密密鑰
            encrypted_key, encrypted_secret = self._cache[cache_key]
            
            try:
                api_key = self._decrypt_value(encrypted_key)
                api_secret = self._decrypt_value(encrypted_secret)
                
                # 刷新過期時間 (延長50%的原TTL)
                original_ttl = self._expiry[cache_key] - time.time()
                if original_ttl > 0:
                    extension = original_ttl * 0.5
                    self._expiry[cache_key] = time.time() + original_ttl + extension
                    
                self.logger.debug(f"從緩存獲取用戶 {user_id} 的 {exchange} API密鑰成功")
                return api_key, api_secret
            except Exception as e:
                self.logger.error(f"解密緩存的API密鑰失敗: {str(e)}")
                # 刪除可能損壞的緩存項
                self._remove_key(cache_key)
                return None
    
    def _remove_key(self, cache_key: Tuple[int, str]) -> None:
        """移除緩存中的密鑰"""
        if cache_key in self._cache:
            del self._cache[cache_key]
        if cache_key in self._expiry:
            del self._expiry[cache_key]
    
    def remove_keys(self, user_id: int, exchange: str) -> None:
        """
        從緩存中移除用戶的API密鑰
        
        Args:
            user_id: 用戶ID
            exchange: 交易所名稱
        """
        with self._lock:
            cache_key = (user_id, exchange)
            self._remove_key(cache_key)
            self.logger.debug(f"已從緩存移除用戶 {user_id} 的 {exchange} API密鑰")
    
    def clear_all(self) -> None:
        """清空所有緩存的密鑰"""
        with self._lock:
            self._cache.clear()
            self._expiry.clear()
            self.logger.info("已清空所有緩存的API密鑰")
    
    def _cleanup_expired_keys(self) -> None:
        """定期清理過期的密鑰"""
        while True:
            try:
                # 等待一段時間
                time.sleep(60)  # 每分鐘檢查一次
                
                with self._lock:
                    current_time = time.time()
                    expired_keys = [k for k, exp_time in self._expiry.items() if current_time > exp_time]
                    
                    # 移除過期的密鑰
                    for key in expired_keys:
                        self._remove_key(key)
                    
                    if expired_keys:
                        self.logger.debug(f"已清理 {len(expired_keys)} 個過期的API密鑰緩存")
            except Exception as e:
                self.logger.error(f"清理過期密鑰時出錯: {str(e)}")

    def set_ed25519_keys(self, user_id: int, exchange: str, api_key: str, ed25519_key: str, ed25519_secret: str, ttl: int = None) -> None:
        """
        存儲用戶的ED25519密鑰對
        
        Args:
            user_id: 用戶ID
            exchange: 交易所名稱
            api_key: 解密後的API Key
            ed25519_key: 解密後的ED25519公鑰
            ed25519_secret: 解密後的ED25519私鑰
            ttl: 密鑰在緩存中的存活時間(秒)，None表示使用預設值
        """
        with self._lock:
            cache_key = (user_id, exchange, "ed25519")
            
            # 加密存儲密鑰
            encrypted_api_key = self._encrypt_value(api_key)
            encrypted_ed25519_key = self._encrypt_value(ed25519_key)
            encrypted_ed25519_secret = self._encrypt_value(ed25519_secret)
            
            self._cache[cache_key] = (encrypted_api_key, encrypted_ed25519_key, encrypted_ed25519_secret)
            
            # 設置過期時間
            if ttl is None:
                ttl = self._default_ttl
            self._expiry[cache_key] = time.time() + ttl
            
            self.logger.debug(f"已安全緩存用戶 {user_id} 的 {exchange} ED25519密鑰，過期時間 {ttl} 秒")
    
    def get_ed25519_keys(self, user_id: int, exchange: str) -> Optional[Tuple[str, str, str]]:
        """
        獲取用戶的ED25519密鑰對
        
        Args:
            user_id: 用戶ID
            exchange: 交易所名稱
            
        Returns:
            (api_key, ed25519_key, ed25519_secret) 元組，如果未找到則返回None
        """
        with self._lock:
            cache_key = (user_id, exchange, "ed25519")
            
            # 檢查是否存在且未過期
            if cache_key not in self._cache or time.time() > self._expiry.get(cache_key, 0):
                return None
            
            # 獲取並解密密鑰
            encrypted_api_key, encrypted_ed25519_key, encrypted_ed25519_secret = self._cache[cache_key]
            
            try:
                api_key = self._decrypt_value(encrypted_api_key)
                ed25519_key = self._decrypt_value(encrypted_ed25519_key)
                ed25519_secret = self._decrypt_value(encrypted_ed25519_secret)
                
                # 刷新過期時間
                original_ttl = self._expiry[cache_key] - time.time()
                if original_ttl > 0:
                    extension = original_ttl * 0.5
                    self._expiry[cache_key] = time.time() + original_ttl + extension
                    
                self.logger.debug(f"從緩存獲取用戶 {user_id} 的 {exchange} ED25519密鑰成功")
                return api_key, ed25519_key, ed25519_secret
            except Exception as e:
                self.logger.error(f"解密緩存的ED25519密鑰失敗: {str(e)}")
                # 刪除可能損壞的緩存項
                self._remove_key(cache_key)
                return None
                
    def remove_ed25519_keys(self, user_id: int, exchange: str) -> None:
        """
        從緩存中移除用戶的ED25519密鑰
        
        Args:
            user_id: 用戶ID
            exchange: 交易所名稱
        """
        with self._lock:
            cache_key = (user_id, exchange, "ed25519")
            self._remove_key(cache_key)
            self.logger.debug(f"已從緩存移除用戶 {user_id} 的 {exchange} ED25519密鑰") 