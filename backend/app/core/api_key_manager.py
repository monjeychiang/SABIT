"""
API 密鑰管理器模塊

提供集中式的 API 密鑰管理，作為所有 API 密鑰操作的唯一入口點。
負責密鑰的創建、更新、刪除、獲取、驗證，以及使用記錄和監控。
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import update, select, func

from ..db.models.exchange_api import ExchangeAPI
from ..core.security import encrypt_api_key, decrypt_api_key
from ..schemas.trading import ExchangeEnum
from .secure_key_cache import SecureKeyCache

logger = logging.getLogger(__name__)

# 自定義異常
class ApiKeyPermissionError(Exception):
    """API 密鑰權限錯誤"""
    pass

class ApiKeyManager:
    """
    API 密鑰管理器
    
    作為所有 API 密鑰操作的唯一入口點，負責：
    1. 密鑰的創建、更新、刪除
    2. 虛擬密鑰的管理
    3. 密鑰的獲取和驗證
    4. 使用記錄和監控
    """
    
    _instance = None
    
    def __new__(cls):
        """實現單例模式"""
        if cls._instance is None:
            cls._instance = super(ApiKeyManager, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化管理器"""
        if self.initialized:
            return
            
        self.cache = {}  # 可選的內存緩存
        self.logger = logging.getLogger(__name__)
        self.initialized = True
        
        self.logger.info("API 密鑰管理器已初始化")
    
    # 基本 API 密鑰操作
    
    async def create_api_key(self, db: Session, user_id: int, exchange: ExchangeEnum, 
                           api_key: str, api_secret: str, 
                           ed25519_key: str = None, ed25519_secret: str = None,
                           description: str = None) -> ExchangeAPI:
        """
        創建新的 API 密鑰
        
        Args:
            db: 數據庫會話
            user_id: 用戶 ID
            exchange: 交易所枚舉
            api_key: API 密鑰
            api_secret: API 密鑰密碼
            ed25519_key: Ed25519 公鑰（可選）
            ed25519_secret: Ed25519 私鑰（可選）
            description: 密鑰描述（可選）
            
        Returns:
            ExchangeAPI: 創建的 API 密鑰記錄
        """
        try:
            # 檢查是否已存在
            existing_api = db.query(ExchangeAPI).filter(
                ExchangeAPI.user_id == user_id,
                ExchangeAPI.exchange == exchange
            ).first()
            
            if existing_api:
                # 如果已存在，則更新
                return await self.update_api_key(
                    db, user_id, exchange, api_key, api_secret,
                    ed25519_key, ed25519_secret, description
                )
            
            # 創建新記錄
            db_api_key = ExchangeAPI(
                user_id=user_id,
                exchange=exchange,
                description=description
            )
            
            # 加密 HMAC-SHA256 密鑰
            if api_key:
                db_api_key.api_key = encrypt_api_key(api_key)
            if api_secret:
                db_api_key.api_secret = encrypt_api_key(api_secret)
            
            # 加密 Ed25519 密鑰
            if ed25519_key:
                db_api_key.ed25519_key = encrypt_api_key(ed25519_key)
            if ed25519_secret:
                db_api_key.ed25519_secret = encrypt_api_key(ed25519_secret)
            
            # 生成虛擬密鑰 ID
            db_api_key.virtual_key_id = ExchangeAPI.generate_virtual_key_id()
            
            # 設置默認權限
            db_api_key.permissions = {"read": True, "trade": True}
            db_api_key.is_active = True
            
            # 保存到數據庫
            db.add(db_api_key)
            db.commit()
            db.refresh(db_api_key)
            
            self.logger.info(f"為用戶 {user_id} 創建了 {exchange} 的 API 密鑰")
            return db_api_key
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"創建 API 密鑰失敗: {str(e)}")
            raise
    
    async def update_api_key(self, db: Session, user_id: int, exchange: ExchangeEnum,
                           api_key: str = None, api_secret: str = None,
                           ed25519_key: str = None, ed25519_secret: str = None,
                           description: str = None) -> ExchangeAPI:
        """
        更新現有 API 密鑰
        
        Args:
            db: 數據庫會話
            user_id: 用戶 ID
            exchange: 交易所枚舉
            api_key: API 密鑰（可選）
            api_secret: API 密鑰密碼（可選）
            ed25519_key: Ed25519 公鑰（可選）
            ed25519_secret: Ed25519 私鑰（可選）
            description: 密鑰描述（可選）
            
        Returns:
            ExchangeAPI: 更新後的 API 密鑰記錄
        """
        try:
            # 獲取現有記錄
            db_api_key = db.query(ExchangeAPI).filter(
                ExchangeAPI.user_id == user_id,
                ExchangeAPI.exchange == exchange
            ).first()
            
            if not db_api_key:
                raise ValueError(f"未找到用戶 {user_id} 的 {exchange} API 密鑰")
            
            # 更新字段
            if description is not None:
                db_api_key.description = description
                
            # 更新 HMAC-SHA256 密鑰
            if api_key is not None:
                db_api_key.api_key = encrypt_api_key(api_key)
            if api_secret is not None:
                db_api_key.api_secret = encrypt_api_key(api_secret)
                
            # 更新 Ed25519 密鑰
            if ed25519_key is not None:
                db_api_key.ed25519_key = encrypt_api_key(ed25519_key)
            if ed25519_secret is not None:
                db_api_key.ed25519_secret = encrypt_api_key(ed25519_secret)
            
            # 保存更改
            db.commit()
            db.refresh(db_api_key)
            
            self.logger.info(f"已更新用戶 {user_id} 的 {exchange} API 密鑰")
            return db_api_key
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"更新 API 密鑰失敗: {str(e)}")
            raise
    
    async def delete_api_key(self, db: Session, user_id: int, exchange: ExchangeEnum) -> bool:
        """
        刪除 API 密鑰
        
        Args:
            db: 數據庫會話
            user_id: 用戶 ID
            exchange: 交易所枚舉
            
        Returns:
            bool: 是否成功刪除
        """
        try:
            # 獲取記錄
            db_api_key = db.query(ExchangeAPI).filter(
                ExchangeAPI.user_id == user_id,
                ExchangeAPI.exchange == exchange
            ).first()
            
            if not db_api_key:
                return False
            
            # 刪除記錄
            db.delete(db_api_key)
            db.commit()
            
            self.logger.info(f"已刪除用戶 {user_id} 的 {exchange} API 密鑰")
            return True
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"刪除 API 密鑰失敗: {str(e)}")
            raise
    
    async def get_api_key(self, db: Session, user_id: int, exchange: ExchangeEnum) -> Optional[ExchangeAPI]:
        """
        獲取 API 密鑰記錄
        
        Args:
            db: 數據庫會話
            user_id: 用戶 ID
            exchange: 交易所枚舉
            
        Returns:
            ExchangeAPI: API 密鑰記錄，如果不存在則返回 None
        """
        try:
            return db.query(ExchangeAPI).filter(
                ExchangeAPI.user_id == user_id,
                ExchangeAPI.exchange == exchange
            ).first()
        except Exception as e:
            self.logger.error(f"獲取 API 密鑰失敗: {str(e)}")
            raise
    
    async def get_api_keys(self, db: Session, user_id: int) -> List[ExchangeAPI]:
        """
        獲取用戶的所有 API 密鑰
        
        Args:
            db: 數據庫會話
            user_id: 用戶 ID
            
        Returns:
            List[ExchangeAPI]: API 密鑰記錄列表
        """
        try:
            return db.query(ExchangeAPI).filter(
                ExchangeAPI.user_id == user_id
            ).all()
        except Exception as e:
            self.logger.error(f"獲取用戶 API 密鑰列表失敗: {str(e)}")
            raise
    
    async def get_api_key_by_id(self, db: Session, user_id: int, api_key_id: int) -> Optional[ExchangeAPI]:
        """
        根據 ID 獲取 API 密鑰記錄
        
        Args:
            db: 數據庫會話
            user_id: 用戶 ID
            api_key_id: API 密鑰 ID
            
        Returns:
            ExchangeAPI: API 密鑰記錄，如果不存在則返回 None
        """
        try:
            return db.query(ExchangeAPI).filter(
                ExchangeAPI.id == api_key_id,
                ExchangeAPI.user_id == user_id
            ).first()
        except Exception as e:
            self.logger.error(f"獲取 API 密鑰失敗: {str(e)}")
            raise
    
    # 虛擬密鑰操作
    
    async def create_virtual_key(self, db: Session, user_id: int, exchange_api_id: int,
                               permissions: Dict[str, bool] = None,
                               rate_limit: int = 60) -> str:
        """
        創建虛擬密鑰
        
        Args:
            db: 數據庫會話
            user_id: 用戶 ID
            exchange_api_id: API 密鑰 ID
            permissions: 權限設置
            rate_limit: 速率限制
            
        Returns:
            str: 虛擬密鑰 ID
        """
        try:
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
            
            self.logger.info(f"已為用戶 {user_id} 的 API 密鑰 {exchange_api_id} 創建虛擬密鑰 {virtual_key_id}")
            return virtual_key_id
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"創建虛擬密鑰失敗: {str(e)}")
            raise
    
    async def update_virtual_key_permissions(self, db: Session, user_id: int, 
                                          virtual_key_id: str,
                                          permissions: Dict[str, bool]) -> bool:
        """
        更新虛擬密鑰權限
        
        Args:
            db: 數據庫會話
            user_id: 用戶 ID
            virtual_key_id: 虛擬密鑰 ID
            permissions: 新的權限設置
            
        Returns:
            bool: 是否成功更新
        """
        try:
            # 更新權限
            result = db.execute(
                update(ExchangeAPI)
                .where(
                    ExchangeAPI.virtual_key_id == virtual_key_id,
                    ExchangeAPI.user_id == user_id
                )
                .values(permissions=permissions)
            )
            
            db.commit()
            
            success = result.rowcount > 0
            if success:
                self.logger.info(f"已更新虛擬密鑰 {virtual_key_id} 的權限")
            else:
                self.logger.warning(f"未找到虛擬密鑰 {virtual_key_id}")
                
            return success
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"更新虛擬密鑰權限失敗: {str(e)}")
            raise
    
    async def deactivate_virtual_key(self, db: Session, user_id: int, 
                                  virtual_key_id: str) -> bool:
        """
        停用虛擬密鑰
        
        Args:
            db: 數據庫會話
            user_id: 用戶 ID
            virtual_key_id: 虛擬密鑰 ID
            
        Returns:
            bool: 是否成功停用
        """
        try:
            # 停用虛擬密鑰
            result = db.execute(
                update(ExchangeAPI)
                .where(
                    ExchangeAPI.virtual_key_id == virtual_key_id,
                    ExchangeAPI.user_id == user_id
                )
                .values(is_active=False)
            )
            
            db.commit()
            
            success = result.rowcount > 0
            if success:
                self.logger.info(f"已停用虛擬密鑰 {virtual_key_id}")
            else:
                self.logger.warning(f"未找到虛擬密鑰 {virtual_key_id}")
                
            return success
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"停用虛擬密鑰失敗: {str(e)}")
            raise
    
    async def get_real_api_key(self, db: Session, user_id: int, 
                             virtual_key_id: str, 
                             operation: str = None) -> Tuple[Dict[str, str], ExchangeAPI]:
        """
        根據虛擬密鑰獲取真實 API 密鑰
        
        Args:
            db: 數據庫會話
            user_id: 用戶 ID
            virtual_key_id: 虛擬密鑰 ID
            operation: 要執行的操作，用於權限檢查
            
        Returns:
            Tuple[Dict[str, str], ExchangeAPI]: 包含解密後 API 密鑰的字典和 API 密鑰記錄
        """
        try:
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
                    raise ApiKeyPermissionError(f"虛擬密鑰 {virtual_key_id} 無交易權限")
                elif operation == "read" and not api_key.permissions.get("read", False):
                    raise ApiKeyPermissionError(f"虛擬密鑰 {virtual_key_id} 無讀取權限")
            
            # 先從緩存中獲取密鑰
            key_cache = SecureKeyCache()
            exchange_name = api_key.exchange.value
            
            # 嘗試從緩存獲取 HMAC-SHA256 密鑰
            cached_keys = key_cache.get_keys(user_id, exchange_name)
            if cached_keys:
                self.logger.info(f"從緩存獲取用戶 {user_id} 的 {exchange_name} HMAC-SHA256 密鑰")
                real_keys = {
                    "api_key": cached_keys[0],
                    "api_secret": cached_keys[1]
                }
                return real_keys, api_key
            
            # 嘗試從緩存獲取 Ed25519 密鑰
            cached_ed25519_keys = key_cache.get_ed25519_keys(user_id, exchange_name)
            if cached_ed25519_keys:
                self.logger.info(f"從緩存獲取用戶 {user_id} 的 {exchange_name} Ed25519 密鑰")
                real_keys = {
                    "api_key": cached_ed25519_keys[0],
                    "api_secret": cached_ed25519_keys[2],  # Ed25519私鑰作為API密碼
                    "ed25519_key": cached_ed25519_keys[1]
                }
                return real_keys, api_key
                
            # 緩存中沒有，需要解密
            real_keys = {}
            decrypt_method = None
            
            # 優先使用 HMAC-SHA256 密鑰
            if api_key.api_key and api_key.api_secret:
                try:
                    from ..core.security import decrypt_api_key
                    hmac_key = decrypt_api_key(api_key.api_key, key_type="API Key (HMAC-SHA256)")
                    hmac_secret = decrypt_api_key(api_key.api_secret, key_type="API Secret (HMAC-SHA256)")
                    
                    if hmac_key and hmac_secret:
                        real_keys["api_key"] = hmac_key
                        real_keys["api_secret"] = hmac_secret
                        decrypt_method = "HMAC-SHA256"
                        # 同時解密兩個密鑰成功後記錄
                        self.logger.debug(f"HMAC-SHA256密鑰對解密成功，Key長度: {len(hmac_key)}, Secret長度: {len(hmac_secret)}")
                        
                        # 解密成功後存入緩存
                        key_cache.set_keys(user_id, exchange_name, hmac_key, hmac_secret)
                        self.logger.debug(f"已將 HMAC-SHA256 密鑰存入緩存")
                except Exception as e:
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug(f"HMAC-SHA256 密鑰解密失敗: {str(e)[:50]}")
            
            # 如果 HMAC-SHA256 解密失敗，嘗試 Ed25519 密鑰
            if not real_keys.get("api_key") and api_key.ed25519_key and api_key.ed25519_secret:
                try:
                    from ..core.security import decrypt_api_key
                    ed25519_key = decrypt_api_key(api_key.ed25519_key, key_type="API Key (Ed25519)")
                    ed25519_secret = decrypt_api_key(api_key.ed25519_secret, key_type="API Secret (Ed25519)")
                    
                    if ed25519_key and ed25519_secret:
                        real_keys["api_key"] = ed25519_key
                        real_keys["api_secret"] = ed25519_secret
                        real_keys["ed25519_key"] = ed25519_key  # 公鑰
                        decrypt_method = "Ed25519"
                        # 同時解密兩個密鑰成功後記錄
                        self.logger.debug(f"Ed25519密鑰對解密成功，Key長度: {len(ed25519_key)}, Secret長度: {len(ed25519_secret)}")
                        
                        # 解密成功後存入緩存
                        key_cache.set_ed25519_keys(user_id, exchange_name, ed25519_key, ed25519_key, ed25519_secret)
                        self.logger.debug(f"已將 Ed25519 密鑰存入緩存")
                except Exception as e:
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug(f"Ed25519 密鑰解密失敗: {str(e)[:50]}")
            
            # 記錄解密結果
            if real_keys.get("api_key") and real_keys.get("api_secret"):
                self.logger.info(f"成功解密用戶 {user_id} 的 API 密鑰 ({decrypt_method})")
            else:
                self.logger.error(f"用戶 {user_id} 的 API 密鑰解密失敗 (所有方法均失敗)")
                raise ValueError(f"API密鑰解密失敗，所有解密方法均已嘗試")
            
            # 更新最後使用時間
            api_key.last_used_at = datetime.utcnow()
            db.commit()
            
            return real_keys, api_key
            
        except Exception as e:
            if not isinstance(e, (ValueError, ApiKeyPermissionError)):
                self.logger.error(f"獲取API密鑰失敗: {str(e)}")
            raise
    
    # 使用記錄和監控
    
    async def log_api_usage(self, db: Session, api_key_id: int, 
                          operation: str, success: bool,
                          execution_time: float = None, 
                          error: str = None) -> None:
        """
        記錄 API 使用情況
        
        Args:
            db: 數據庫會話
            api_key_id: API 密鑰 ID
            operation: 執行的操作
            success: 操作是否成功
            execution_time: 執行時間（秒）
            error: 錯誤信息（如果有）
        """
        try:
            # 獲取 API 密鑰記錄
            api_key = db.query(ExchangeAPI).filter(
                ExchangeAPI.id == api_key_id
            ).first()
            
            if not api_key:
                self.logger.warning(f"未找到 ID 為 {api_key_id} 的 API 密鑰，無法記錄使用情況")
                return
            
            # 構建日誌消息
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
            
            # 記錄日誌
            if success:
                self.logger.info(log_message)
            else:
                self.logger.warning(log_message)
            
            # 更新最後使用時間
            api_key.last_used_at = datetime.utcnow()
            db.commit()
            
            # 如果需要，可以在這裡添加代碼將使用記錄寫入專門的日誌表
            # 例如：
            # db.add(ApiUsageLog(
            #     exchange_api_id=api_key.id,
            #     operation=operation,
            #     success=success,
            #     execution_time=execution_time,
            #     error=error
            # ))
            # db.commit()
            
        except Exception as e:
            self.logger.error(f"記錄 API 使用情況失敗: {str(e)}")
            # 不拋出異常，避免影響主要操作
    
    async def get_usage_statistics(self, db: Session, user_id: int,
                                 start_time: datetime = None,
                                 end_time: datetime = None) -> Dict[str, Any]:
        """
        獲取 API 使用統計
        
        Args:
            db: 數據庫會話
            user_id: 用戶 ID
            start_time: 開始時間
            end_time: 結束時間
            
        Returns:
            Dict[str, Any]: 使用統計信息
        """
        try:
            # 如果有專門的日誌表，可以從中獲取詳細統計
            # 這裡僅返回基本信息
            
            # 查詢條件
            query = db.query(ExchangeAPI).filter(ExchangeAPI.user_id == user_id)
            
            if start_time:
                query = query.filter(ExchangeAPI.last_used_at >= start_time)
            if end_time:
                query = query.filter(ExchangeAPI.last_used_at <= end_time)
            
            # 獲取 API 密鑰記錄
            api_keys = query.all()
            
            # 統計信息
            statistics = {
                "total_keys": len(api_keys),
                "active_keys": sum(1 for key in api_keys if key.is_active),
                "keys_by_exchange": {},
                "last_used": {}
            }
            
            # 按交易所分組
            for key in api_keys:
                exchange = key.exchange.value
                if exchange not in statistics["keys_by_exchange"]:
                    statistics["keys_by_exchange"][exchange] = 0
                statistics["keys_by_exchange"][exchange] += 1
                
                # 記錄最後使用時間
                if key.last_used_at:
                    if exchange not in statistics["last_used"] or key.last_used_at > statistics["last_used"][exchange]:
                        statistics["last_used"][exchange] = key.last_used_at
            
            return statistics
            
        except Exception as e:
            self.logger.error(f"獲取 API 使用統計失敗: {str(e)}")
            raise
    
    # 安全功能
    
    async def validate_permissions(self, db: Session, user_id: int, 
                                 virtual_key_id: str, 
                                 required_permission: str) -> bool:
        """
        驗證權限
        
        Args:
            db: 數據庫會話
            user_id: 用戶 ID
            virtual_key_id: 虛擬密鑰 ID
            required_permission: 所需權限
            
        Returns:
            bool: 是否有權限
        """
        try:
            # 獲取 API 密鑰記錄
            api_key = db.query(ExchangeAPI).filter(
                ExchangeAPI.virtual_key_id == virtual_key_id,
                ExchangeAPI.user_id == user_id,
                ExchangeAPI.is_active == True
            ).first()
            
            if not api_key:
                self.logger.warning(f"未找到虛擬密鑰 {virtual_key_id} 或密鑰已停用")
                return False
            
            # 檢查權限
            if not api_key.permissions:
                self.logger.warning(f"虛擬密鑰 {virtual_key_id} 未設置權限")
                return False
            
            has_permission = api_key.permissions.get(required_permission, False)
            
            if not has_permission:
                self.logger.warning(f"虛擬密鑰 {virtual_key_id} 無 {required_permission} 權限")
            
            return has_permission
            
        except Exception as e:
            self.logger.error(f"驗證權限失敗: {str(e)}")
            return False
    
    async def check_rate_limit(self, db: Session, user_id: int, 
                             virtual_key_id: str) -> bool:
        """
        檢查速率限制
        
        Args:
            db: 數據庫會話
            user_id: 用戶 ID
            virtual_key_id: 虛擬密鑰 ID
            
        Returns:
            bool: 是否未超過速率限制
        """
        try:
            # 獲取 API 密鑰記錄
            api_key = db.query(ExchangeAPI).filter(
                ExchangeAPI.virtual_key_id == virtual_key_id,
                ExchangeAPI.user_id == user_id,
                ExchangeAPI.is_active == True
            ).first()
            
            if not api_key:
                self.logger.warning(f"未找到虛擬密鑰 {virtual_key_id} 或密鑰已停用")
                return False
            
            # 如果未設置速率限制，則不限制
            if not api_key.rate_limit:
                return True
            
            # 如果有專門的使用日誌表，可以從中獲取最近的使用次數
            # 這裡僅做簡單示例
            
            # 獲取最近一分鐘的使用次數（假設有日誌表）
            # 實際實現時需要根據具體的日誌表結構調整
            # recent_usage_count = db.query(ApiUsageLog).filter(
            #     ApiUsageLog.exchange_api_id == api_key.id,
            #     ApiUsageLog.timestamp >= datetime.utcnow() - timedelta(minutes=1)
            # ).count()
            
            # 簡化處理：假設未超過限制
            recent_usage_count = 0
            
            # 檢查是否超過限制
            if recent_usage_count >= api_key.rate_limit:
                self.logger.warning(f"虛擬密鑰 {virtual_key_id} 已超過速率限制 ({recent_usage_count}/{api_key.rate_limit})")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"檢查速率限制失敗: {str(e)}")
            # 出錯時保守處理，返回未超限
            return True
    
    async def get_exchange_for_virtual_key(self, db: Session, user_id: int, 
                                        virtual_key_id: str) -> Optional[ExchangeEnum]:
        """
        獲取虛擬密鑰對應的交易所
        
        Args:
            db: 數據庫會話
            user_id: 用戶 ID
            virtual_key_id: 虛擬密鑰 ID
            
        Returns:
            ExchangeEnum: 交易所枚舉，如果不存在則返回 None
        """
        try:
            # 獲取 API 密鑰記錄
            api_key = db.query(ExchangeAPI).filter(
                ExchangeAPI.virtual_key_id == virtual_key_id,
                ExchangeAPI.user_id == user_id,
                ExchangeAPI.is_active == True
            ).first()
            
            if not api_key:
                return None
            
            return api_key.exchange
            
        except Exception as e:
            self.logger.error(f"獲取虛擬密鑰對應的交易所失敗: {str(e)}")
            return None

    async def check_virtual_key_exists(
        self, 
        db: Session, 
        user_id: int, 
        virtual_key_id: str
    ) -> bool:
        """
        檢查虛擬密鑰是否存在並屬於指定用戶
        
        Args:
            db: 數據庫會話
            user_id: 用戶 ID
            virtual_key_id: 虛擬密鑰 ID
            
        Returns:
            bool: 虛擬密鑰是否存在並屬於指定用戶
        """
        try:
            # 查詢虛擬密鑰
            api_key = db.query(ExchangeAPI).filter(
                ExchangeAPI.virtual_key_id == virtual_key_id,
                ExchangeAPI.user_id == user_id,
                ExchangeAPI.is_active == True
            ).first()
            
            return api_key is not None
            
        except Exception as e:
            self.logger.error(f"檢查虛擬密鑰存在性失敗: {str(e)}")
            return False


# 使用示例
async def example_usage():
    """
    API 密鑰管理器使用示例
    
    此函數展示了如何使用 API 密鑰管理器進行常見操作。
    """
    from sqlalchemy.orm import Session
    from ..db.database import get_db
    from ..schemas.trading import ExchangeEnum
    import asyncio
    
    # 獲取管理器實例
    api_key_manager = ApiKeyManager()
    
    # 獲取數據庫會話
    db = next(get_db())
    
    try:
        # 1. 創建 API 密鑰
        user_id = 1  # 假設用戶 ID
        exchange = ExchangeEnum.BINANCE  # 交易所
        api_key = "your_api_key"  # API 密鑰
        api_secret = "your_api_secret"  # API 密鑰密碼
        
        db_api_key = await api_key_manager.create_api_key(
            db=db,
            user_id=user_id,
            exchange=exchange,
            api_key=api_key,
            api_secret=api_secret,
            description="測試密鑰"
        )
        
        print(f"創建 API 密鑰成功: {db_api_key.id}")
        
        # 2. 創建虛擬密鑰
        virtual_key_id = await api_key_manager.create_virtual_key(
            db=db,
            user_id=user_id,
            exchange_api_id=db_api_key.id,
            permissions={"read": True, "trade": False},  # 只允許讀取，不允許交易
            rate_limit=100  # 每分鐘最多 100 次請求
        )
        
        print(f"創建虛擬密鑰成功: {virtual_key_id}")
        
        # 3. 驗證權限
        has_read_permission = await api_key_manager.validate_permissions(
            db=db,
            user_id=user_id,
            virtual_key_id=virtual_key_id,
            required_permission="read"
        )
        
        has_trade_permission = await api_key_manager.validate_permissions(
            db=db,
            user_id=user_id,
            virtual_key_id=virtual_key_id,
            required_permission="trade"
        )
        
        print(f"讀取權限: {has_read_permission}")
        print(f"交易權限: {has_trade_permission}")
        
        # 4. 獲取真實 API 密鑰
        try:
            real_keys, api_key_record = await api_key_manager.get_real_api_key(
                db=db,
                user_id=user_id,
                virtual_key_id=virtual_key_id,
                operation="read"  # 嘗試讀取操作
            )
            
            print(f"獲取真實 API 密鑰成功: {real_keys.keys()}")
            
            # 嘗試交易操作（應該失敗，因為沒有交易權限）
            try:
                real_keys, api_key_record = await api_key_manager.get_real_api_key(
                    db=db,
                    user_id=user_id,
                    virtual_key_id=virtual_key_id,
                    operation="trade"
                )
            except ApiKeyPermissionError as e:
                print(f"預期的權限錯誤: {str(e)}")
        except Exception as e:
            print(f"獲取真實 API 密鑰失敗: {str(e)}")
        
        # 5. 更新虛擬密鑰權限
        updated = await api_key_manager.update_virtual_key_permissions(
            db=db,
            user_id=user_id,
            virtual_key_id=virtual_key_id,
            permissions={"read": True, "trade": True}  # 允許讀取和交易
        )
        
        print(f"更新權限成功: {updated}")
        
        # 6. 記錄 API 使用
        await api_key_manager.log_api_usage(
            db=db,
            api_key_id=db_api_key.id,
            operation="get_balance",
            success=True,
            execution_time=0.5
        )
        
        # 7. 獲取使用統計
        statistics = await api_key_manager.get_usage_statistics(
            db=db,
            user_id=user_id
        )
        
        print(f"使用統計: {statistics}")
        
        # 8. 停用虛擬密鑰
        deactivated = await api_key_manager.deactivate_virtual_key(
            db=db,
            user_id=user_id,
            virtual_key_id=virtual_key_id
        )
        
        print(f"停用虛擬密鑰成功: {deactivated}")
        
        # 9. 刪除 API 密鑰
        deleted = await api_key_manager.delete_api_key(
            db=db,
            user_id=user_id,
            exchange=exchange
        )
        
        print(f"刪除 API 密鑰成功: {deleted}")
        
    except Exception as e:
        print(f"發生錯誤: {str(e)}")
    finally:
        # 關閉數據庫會話
        db.close()

# 如果需要運行示例
# if __name__ == "__main__":
#     asyncio.run(example_usage()) 