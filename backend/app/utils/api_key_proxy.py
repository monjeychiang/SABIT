"""
API 密鑰代理模組 - 輕量級中間層實現

此模組提供了 API 密鑰的虛擬化、權限控制和使用追蹤功能，
作為一個最小改動的中間層解決方案。
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import update
from ..db.models.exchange_api import ExchangeAPI
from ..core.security import decrypt_api_key
from ..schemas.trading import ExchangeEnum
from ..core.secure_key_cache import SecureKeyCache

logger = logging.getLogger(__name__)

class ApiKeyProxy:
    """API 密鑰代理類 - 輕量級中間層"""
    
    @staticmethod
    async def register_virtual_key(
        db: Session, 
        user_id: int, 
        exchange_api_id: int,
        permissions: Dict[str, bool] = None,
        rate_limit: int = 60
    ) -> str:
        """
        為現有 API 密鑰註冊虛擬密鑰
        
        Args:
            db: 數據庫會話
            user_id: 用戶 ID
            exchange_api_id: 交易所 API 密鑰 ID
            permissions: 權限設置，默認為 {"read": True, "trade": True}
            rate_limit: 速率限制（每分鐘請求數）
            
        Returns:
            虛擬密鑰標識符
        """
        # 獲取 API 密鑰記錄
        api_key = db.query(ExchangeAPI).filter(
            ExchangeAPI.id == exchange_api_id,
            ExchangeAPI.user_id == user_id
        ).first()
        
        if not api_key:
            raise ValueError(f"未找到 ID 為 {exchange_api_id} 的 API 密鑰")
        
        # 設置默認權限
        if permissions is None:
            permissions = {"read": True, "trade": True}
        
        # 生成虛擬密鑰 ID
        virtual_key_id = ExchangeAPI.generate_virtual_key_id()
        
        # 更新 API 密鑰記錄
        api_key.virtual_key_id = virtual_key_id
        api_key.permissions = permissions
        api_key.rate_limit = rate_limit
        api_key.is_active = True
        
        db.commit()
        
        logger.info(f"已為用戶 {user_id} 的 API 密鑰 {exchange_api_id} 註冊虛擬密鑰 {virtual_key_id}")
        return virtual_key_id
    
    @staticmethod
    async def get_real_api_key(
        db: Session, 
        user_id: int, 
        virtual_key_id: str,
        operation: str = None
    ) -> Tuple[Dict[str, str], ExchangeAPI]:
        """
        根據虛擬密鑰獲取真實 API 密鑰
        
        Args:
            db: 數據庫會話
            user_id: 用戶 ID
            virtual_key_id: 虛擬密鑰標識符
            operation: 要執行的操作，用於權限檢查
            
        Returns:
            包含解密後 API 密鑰的字典和 API 密鑰記錄
        """
        # 獲取 API 密鑰記錄
        api_key = db.query(ExchangeAPI).filter(
            ExchangeAPI.virtual_key_id == virtual_key_id,
            ExchangeAPI.user_id == user_id,
            ExchangeAPI.is_active == True
        ).first()
        
        if not api_key:
            raise ValueError(f"未找到虛擬密鑰 {virtual_key_id} 或密鑰已停用")
        
        # 檢查權限
        if operation and api_key.permissions:
            if operation == "trade" and not api_key.permissions.get("trade", False):
                raise PermissionError(f"虛擬密鑰 {virtual_key_id} 無交易權限")
            elif operation == "read" and not api_key.permissions.get("read", False):
                raise PermissionError(f"虛擬密鑰 {virtual_key_id} 無讀取權限")
        
        # 解密 API 密鑰
        real_keys = {}
        
        # 嘗試從緩存獲取密鑰
        key_cache = SecureKeyCache()
        exchange_name = api_key.exchange.value
        
        # HMAC-SHA256 密鑰
        if api_key.api_key and api_key.api_secret:
            # 嘗試從緩存獲取 HMAC-SHA256 密鑰
            cached_keys = key_cache.get_keys(user_id, exchange_name)
            
            if cached_keys and cached_keys[0] and cached_keys[1]:
                logger.debug(f"從緩存獲取 HMAC-SHA256 密鑰成功: {exchange_name}")
                real_keys["api_key"] = cached_keys[0]
                real_keys["api_secret"] = cached_keys[1]
            else:
                # 緩存未命中，解密並存入緩存
                real_keys["api_key"] = decrypt_api_key(api_key.api_key, "API Key (HMAC-SHA256)")
                real_keys["api_secret"] = decrypt_api_key(api_key.api_secret, "API Secret (HMAC-SHA256)")
                
                # 將解密後的密鑰存入緩存
                key_cache.set_keys(
                    user_id, 
                    exchange_name, 
                    real_keys["api_key"], 
                    real_keys["api_secret"]
                )
                logger.debug(f"已將 HMAC-SHA256 密鑰存入緩存: {exchange_name}")
        
        # Ed25519 密鑰
        if api_key.ed25519_key and api_key.ed25519_secret:
            # 嘗試從緩存獲取 Ed25519 密鑰
            cached_ed25519_keys = key_cache.get_ed25519_keys(user_id, exchange_name)
            
            if cached_ed25519_keys and cached_ed25519_keys[0] and cached_ed25519_keys[1]:
                logger.debug(f"從緩存獲取 Ed25519 密鑰成功: {exchange_name}")
                real_keys["ed25519_key"] = cached_ed25519_keys[0]
                real_keys["ed25519_secret"] = cached_ed25519_keys[1]
            else:
                # 緩存未命中，解密並存入緩存
                real_keys["ed25519_key"] = decrypt_api_key(api_key.ed25519_key, "API Key (Ed25519)")
                real_keys["ed25519_secret"] = decrypt_api_key(api_key.ed25519_secret, "API Secret (Ed25519)")
                
                # 將解密後的密鑰存入緩存
                key_cache.set_ed25519_keys(
                    user_id, 
                    exchange_name, 
                    real_keys["ed25519_key"], 
                    real_keys["ed25519_secret"]
                )
                logger.debug(f"已將 Ed25519 密鑰存入緩存: {exchange_name}")
        
        # 更新最後使用時間
        api_key.last_used_at = datetime.utcnow()
        db.commit()
        
        return real_keys, api_key
    
    @staticmethod
    async def update_permissions(
        db: Session, 
        user_id: int, 
        virtual_key_id: str,
        permissions: Dict[str, bool]
    ) -> bool:
        """
        更新虛擬密鑰的權限
        
        Args:
            db: 數據庫會話
            user_id: 用戶 ID
            virtual_key_id: 虛擬密鑰標識符
            permissions: 新的權限設置
            
        Returns:
            更新是否成功
        """
        result = db.execute(
            update(ExchangeAPI)
            .where(
                ExchangeAPI.virtual_key_id == virtual_key_id,
                ExchangeAPI.user_id == user_id
            )
            .values(permissions=permissions)
        )
        
        db.commit()
        return result.rowcount > 0
    
    @staticmethod
    async def deactivate_virtual_key(
        db: Session, 
        user_id: int, 
        virtual_key_id: str
    ) -> bool:
        """
        停用虛擬密鑰
        
        Args:
            db: 數據庫會話
            user_id: 用戶 ID
            virtual_key_id: 虛擬密鑰標識符
            
        Returns:
            停用是否成功
        """
        result = db.execute(
            update(ExchangeAPI)
            .where(
                ExchangeAPI.virtual_key_id == virtual_key_id,
                ExchangeAPI.user_id == user_id
            )
            .values(is_active=False)
        )
        
        db.commit()
        return result.rowcount > 0
    
    @staticmethod
    async def log_api_usage(
        db: Session,
        api_key: ExchangeAPI,
        operation: str,
        success: bool,
        execution_time: float = None,
        error: str = None
    ) -> None:
        """
        記錄 API 使用情況
        
        此方法僅記錄基本信息，如需詳細日誌可擴展為使用專門的日誌表
        
        Args:
            db: 數據庫會話
            api_key: API 密鑰記錄
            operation: 執行的操作
            success: 操作是否成功
            execution_time: 執行時間（秒）
            error: 錯誤信息（如果有）
        """
        # 簡單記錄到日誌文件，可以擴展為寫入數據庫
        log_message = (
            f"API使用: user_id={api_key.user_id}, "
            f"exchange={api_key.exchange}, "
            f"virtual_key_id={api_key.virtual_key_id}, "
            f"operation={operation}, "
            f"success={success}"
        )
        
        if execution_time is not None:
            log_message += f", execution_time={execution_time:.3f}s"
        
        if error:
            log_message += f", error={error}"
        
        if success:
            logger.info(log_message)
        else:
            logger.warning(log_message)
            
        # 如果需要，可以在這裡添加代碼將使用記錄寫入數據庫
        # 例如：
        # db.add(ApiUsageLog(
        #     exchange_api_id=api_key.id,
        #     operation=operation,
        #     success=success,
        #     execution_time=execution_time,
        #     error=error
        # ))
        # db.commit()


# 使用示例
async def execute_api_operation(
    db: Session,
    user_id: int,
    virtual_key_id: str,
    operation: str,
    exchange_operation: str,
    params: Dict[str, Any] = None
) -> Any:
    """
    使用虛擬密鑰執行 API 操作的示例函數
    
    Args:
        db: 數據庫會話
        user_id: 用戶 ID
        virtual_key_id: 虛擬密鑰標識符
        operation: 操作類型（"read" 或 "trade"）
        exchange_operation: 交易所操作名稱
        params: 操作參數
        
    Returns:
        操作結果
    """
    start_time = time.time()
    api_key_record = None
    
    try:
        # 獲取真實 API 密鑰
        real_keys, api_key_record = await ApiKeyProxy.get_real_api_key(
            db=db,
            user_id=user_id,
            virtual_key_id=virtual_key_id,
            operation=operation
        )
        
        # 這裡應該使用真實密鑰執行實際操作
        # 例如：
        # client = get_exchange_client(api_key_record.exchange, real_keys)
        # result = await client.execute_operation(exchange_operation, params)
        
        # 模擬結果
        result = {"status": "success", "operation": exchange_operation}
        
        # 記錄成功使用
        execution_time = time.time() - start_time
        if api_key_record:
            await ApiKeyProxy.log_api_usage(
                db=db,
                api_key=api_key_record,
                operation=f"{operation}:{exchange_operation}",
                success=True,
                execution_time=execution_time
            )
        
        return result
    
    except Exception as e:
        # 記錄失敗使用
        execution_time = time.time() - start_time
        if api_key_record:
            await ApiKeyProxy.log_api_usage(
                db=db,
                api_key=api_key_record,
                operation=f"{operation}:{exchange_operation}",
                success=False,
                execution_time=execution_time,
                error=str(e)
            )
        
        # 重新拋出異常
        raise 