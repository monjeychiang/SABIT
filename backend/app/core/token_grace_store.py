"""
令牌寬限期存儲模塊

此模塊提供了一個內存中的存儲機制，用於實現令牌寬限期功能。
當令牌被撤銷或更新時，舊令牌在一段時間內仍然有效，這段時間稱為寬限期。
這有助於減少前端因令牌過期而導致的錯誤，特別是在多個標籤頁或設備同時使用時。
"""

import threading
import time
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta

from app.core.config import settings

# 設置日誌記錄
logger = logging.getLogger(__name__)

class TokenGraceStore:
    """
    令牌寬限期存儲類
    
    提供一個內存中的緩存機制，用於存儲最近撤銷或更新的令牌信息，
    使這些令牌在短時間內仍然可用，同時定期清理過期的令牌。
    """
    
    def __init__(self):
        """初始化令牌寬限期存儲"""
        # 存儲結構: {token_id: (user_id, expiry_time)}
        self._store: Dict[str, Tuple[str, float]] = {}
        self._lock = threading.RLock()  # 使用可重入鎖保證線程安全
        
        # 從配置獲取設置
        self.grace_period_seconds = settings.TOKEN_GRACE_PERIOD_SECONDS
        self.cleanup_interval = settings.TOKEN_GRACE_CLEANUP_INTERVAL
        self.debug_log = settings.TOKEN_GRACE_DEBUG_LOG
        
        # 啟動清理線程
        self._stop_cleanup = False
        self._cleanup_thread = threading.Thread(target=self._cleanup_task, daemon=True)
        self._cleanup_thread.start()
        
        logger.info(f"TokenGraceStore 初始化完成，寬限期: {self.grace_period_seconds}秒，清理間隔: {self.cleanup_interval}秒")
    
    def add_revoked_token(self, token_id: str, user_id: str) -> None:
        """
        添加一個撤銷的令牌到寬限期存儲
        
        參數:
            token_id: 令牌標識符
            user_id: 用戶ID
        """
        expiry_time = time.time() + self.grace_period_seconds
        
        with self._lock:
            self._store[token_id] = (user_id, expiry_time)
            
        if self.debug_log:
            logger.debug(f"添加令牌到寬限期存儲: token_id={token_id}, user_id={user_id}, 過期時間={datetime.fromtimestamp(expiry_time).isoformat()}")
    
    def get_user_id(self, token_id: str) -> Optional[str]:
        """
        檢查令牌是否在寬限期內，如果是則返回相關的用戶ID
        
        參數:
            token_id: 令牌標識符
            
        返回:
            用戶ID或None（如果令牌不在寬限期內）
        """
        with self._lock:
            if token_id in self._store:
                user_id, expiry_time = self._store[token_id]
                if time.time() < expiry_time:
                    if self.debug_log:
                        logger.debug(f"令牌在寬限期內: token_id={token_id}, user_id={user_id}")
                    return user_id
                else:
                    # 如果令牌已過期，立即刪除
                    if self.debug_log:
                        logger.debug(f"令牌已過寬限期: token_id={token_id}")
                    del self._store[token_id]
                    
        return None
    
    def _cleanup_task(self) -> None:
        """後台任務，定期清理過期的令牌"""
        while not self._stop_cleanup:
            try:
                time.sleep(self.cleanup_interval)
                self._cleanup_expired()
            except Exception as e:
                logger.error(f"令牌寬限期清理任務異常: {e}")
    
    def _cleanup_expired(self) -> None:
        """清理所有過期的令牌"""
        now = time.time()
        removed_count = 0
        
        with self._lock:
            # 找出所有過期的令牌
            expired_tokens = [token_id for token_id, (_, expiry_time) in self._store.items() if now >= expiry_time]
            
            # 刪除過期的令牌
            for token_id in expired_tokens:
                del self._store[token_id]
                removed_count += 1
            
            if self.debug_log and removed_count > 0:
                logger.debug(f"已清理 {removed_count} 個過期令牌，當前存儲大小: {len(self._store)}")
    
    def __del__(self):
        """析構函數，停止清理線程"""
        self._stop_cleanup = True
        
        # 等待清理線程終止，但最多等待1秒
        if hasattr(self, '_cleanup_thread') and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=1.0)

# 全局單例實例
token_grace_store = TokenGraceStore() 