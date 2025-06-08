"""
交易所連接管理器

為系統提供統一的交易所連接管理服務，確保所有模塊共享相同的WebSocket連接池，
避免重複創建連接並提高系統資源利用效率。
"""

import logging
import time
import asyncio
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
import string

# 設置日誌
logger = logging.getLogger(__name__)

# 直接導入BinanceWebSocketClient，不再依賴account.py
from backend.utils.binance_ws_client import BinanceWebSocketClient

# 修改導入路徑以適應新位置
from backend.app.db.models import ExchangeAPI, User
from backend.app.core.security import decrypt_api_key
# 導入 ApiKeyManager
from backend.app.core.api_key_manager import ApiKeyManager
# 導入 SecureKeyCache
from backend.app.core.secure_key_cache import SecureKeyCache

class ExchangeConnectionManager:
    """
    統一的交易所連接管理器
    
    為系統提供統一的交易所連接管理接口，使不同模塊（網格交易、策略交易等）
    都能共享同一個連接池，避免重複創建連接並簡化連接管理邏輯。
    """
    
    def __init__(self):
        # 初始化時不創建任何連接，僅在需要時才創建
        self._initialized = False
        # 自己管理連接緩存，不依賴account.py
        self.ws_clients = {}
        # 創建 ApiKeyManager 實例
        self.api_key_manager = ApiKeyManager()
        # 獲取安全密鑰緩存實例
        self.key_cache = SecureKeyCache()
        
    async def initialize(self):
        """
        初始化連接管理器
        
        在應用啟動時調用，確保連接管理器正確初始化
        """
        if self._initialized:
            return
            
        self._initialized = True
        logger.info("[連接管理器] 成功初始化獨立的WebSocket客戶端池")
    
    async def ensure_initialized(self):
        """確保管理器已初始化"""
        if not self._initialized:
            await self.initialize()
    
    async def get_connection(
        self, 
        user_id: int, 
        exchange: str = "binance", 
        db_session: Optional[Session] = None, 
        force_new: bool = False,
        connection_type: str = "websocket"  # 新增參數，默認為 "websocket"，可選值還有 "rest"
    ) -> Tuple[Any, bool]:
        """
        獲取交易所連接
        
        首先檢查是否有現有連接可用，如有則直接返回
        否則嘗試從數據庫獲取API密鑰創建新連接
        
        Args:
            user_id: 用戶ID
            exchange: 交易所名稱，默認為"binance"
            db_session: 數據庫會話，如需創建新連接則必須提供
            force_new: 是否強制創建新連接，即使有可用連接
            connection_type: 連接類型，"websocket" 或 "rest"，決定使用的密鑰類型
            
        Returns:
            (client, is_new): 客戶端和是否為新創建的連接
            
        Raises:
            ValueError: 當無法獲取連接時
        """
        await self.ensure_initialized()
        
        # 根據連接類型確定需要的密鑰類型
        key_type = "ed25519" if connection_type == "websocket" else "hmac_sha256"
        
        # 構造緩存鍵 - 加入連接類型以區分不同類型的連接
        cache_key = f"{user_id}_{connection_type}"
        
        # 如果不強制創建新連接，檢查緩存中是否有可用連接
        if not force_new and cache_key in self.ws_clients:
            client = self.ws_clients[cache_key]
            
            # 檢查連接是否有效
            if client.is_connected():
                client.last_activity_time = time.time()  # 更新最後活動時間
                return client, False
            else:
                logger.info(f"緩存連接已斷開，為用戶 {user_id} 重新創建 {connection_type} 連接")
                # 從緩存中移除
                try:
                    await client.disconnect()
                except:
                    pass
                del self.ws_clients[cache_key]
        
        # 如果沒有可用連接且未提供數據庫會話，無法繼續
        if db_session is None:
            raise ValueError(f"未找到現有連接且未提供數據庫會話")
            
        # 首先嘗試從安全密鑰緩存獲取，根據連接類型選擇密鑰類型
        api_key = None
        api_secret = None
        
        # 根據連接類型選擇獲取密鑰的方式
        if key_type == "hmac_sha256":
            # 僅嘗試從緩存獲取 HMAC-SHA256 密鑰
            cached_keys = self.key_cache.get_keys(user_id, exchange)
            if cached_keys:
                logger.info(f"從安全緩存獲取用戶 {user_id} 的 {exchange} HMAC-SHA256 密鑰")
                api_key, api_secret = cached_keys
        else:  # key_type == "ed25519"
            # 僅嘗試從緩存獲取 Ed25519 密鑰
            cached_ed25519_keys = self.key_cache.get_ed25519_keys(user_id, exchange)
            if cached_ed25519_keys:
                logger.info(f"從安全緩存獲取用戶 {user_id} 的 {exchange} Ed25519 密鑰")
                api_key, _, api_secret = cached_ed25519_keys  # api_key, ed25519_key, ed25519_secret
        
        # 如果從緩存獲取成功，直接創建連接
        if api_key and api_secret:
            logger.info(f"使用緩存密鑰為用戶 {user_id} 創建新的 {connection_type} 連接")
            try:
                return await self.get_or_create_connection(
                    api_key, api_secret, exchange, testnet=False, user_id=cache_key
                )
            except Exception as e:
                logger.error(f"使用緩存密鑰創建連接失敗: {str(e)}")
                # 緩存密鑰可能已過期，繼續使用原來的方法
        
        # 使用 ApiKeyManager 獲取 API 密鑰
        api_key_record = await self.api_key_manager.get_api_key(db_session, user_id, exchange)
        
        if not api_key_record:
            raise ValueError(f"未找到對應交易所的API密鑰")
            
        # 解密API密鑰 - 使用 ApiKeyManager
        try:
            # 檢查是否有虛擬密鑰ID
            if api_key_record.virtual_key_id:
                # 獲取真實API密鑰，明確指定密鑰類型
                real_keys, _ = await self.api_key_manager.get_real_api_key(
                    db=db_session,
                    user_id=user_id,
                    virtual_key_id=api_key_record.virtual_key_id,
                    operation="read",  # 讀取操作
                    key_type=key_type  # 明確指定需要的密鑰類型
                )
                
                # 檢查解密結果
                if not real_keys.get("api_key") or not real_keys.get("api_secret"):
                    raise ValueError(f"{key_type} API密鑰解密失敗")
                    
                api_key = real_keys.get("api_key")
                api_secret = real_keys.get("api_secret")
            else:
                # 直接解密（舊方法）
                logger.info(f"使用直接解密方式獲取 {key_type} API密鑰")
                from ..app.core.security import decrypt_api_key
                
                if key_type == "ed25519":
                    # 僅解密 Ed25519 密鑰
                    api_key = decrypt_api_key(api_key_record.ed25519_key, key_type="API Key (Ed25519)")
                    api_secret = decrypt_api_key(api_key_record.ed25519_secret, key_type="API Secret (Ed25519)")
                    
                    # 如果 Ed25519 密鑰解密成功，存入緩存
                    if api_key and api_secret:
                        self.key_cache.set_ed25519_keys(user_id, exchange, api_key, api_key, api_secret)
                        logger.debug(f"已將 Ed25519 密鑰存入緩存")
                    else:
                        raise ValueError(f"Ed25519 密鑰解密失敗，WebSocket API 需要 Ed25519 密鑰")
                else:  # key_type == "hmac_sha256"
                    # 僅解密 HMAC-SHA256 密鑰
                    api_key = decrypt_api_key(api_key_record.api_key, key_type="API Key (HMAC-SHA256)")
                    api_secret = decrypt_api_key(api_key_record.api_secret, key_type="API Secret (HMAC-SHA256)")
                    
                    # 如果 HMAC-SHA256 密鑰解密成功，存入緩存
                    if api_key and api_secret:
                        self.key_cache.set_keys(user_id, exchange, api_key, api_secret)
                        logger.debug(f"已將 HMAC-SHA256 密鑰存入緩存")
                    else:
                        raise ValueError(f"HMAC-SHA256 密鑰解密失敗，REST API 需要 HMAC-SHA256 密鑰")
                
                if not api_key or not api_secret:
                    raise ValueError(f"{key_type} API密鑰解密失敗，請確保已在交易所設置頁面配置正確類型的密鑰")
        except Exception as e:
            logger.error(f"{key_type} API密鑰解密失敗: {str(e)}")
            if key_type == "ed25519":
                raise ValueError(f"WebSocket API 需要 Ed25519 密鑰，但未找到或解密失敗: {str(e)}")
            else:
                raise ValueError(f"REST API 需要 HMAC-SHA256 密鑰，但未找到或解密失敗: {str(e)}")
        
        # 創建連接
        logger.info(f"為用戶 {user_id} 創建新的 {connection_type} 連接，使用 {key_type} 密鑰")
        try:
            return await self.get_or_create_connection(
                api_key, api_secret, exchange, testnet=False, user_id=cache_key
            )
        except Exception as e:
            logger.error(f"創建 {connection_type} 連接失敗: {str(e)}")
            raise ValueError(f"無法創建交易所 {connection_type} 連接: {str(e)}")
    
    async def check_connection(self, user_id: int, exchange: str = "binance") -> bool:
        """
        檢查用戶是否有可用的交易所連接
        
        僅檢查連接是否存在且連接狀態正常，不創建新連接
        
        Args:
            user_id: 用戶ID
            exchange: 交易所名稱
            
        Returns:
            bool: 是否有可用連接
        """
        await self.ensure_initialized()
        
        # 構造緩存鍵
        cache_key = user_id
        
        # 檢查緩存中是否有可用連接
        if cache_key in self.ws_clients:
            client = self.ws_clients[cache_key]
            is_connected = client.is_connected()
            
            logger.debug(f"[連接管理器] 檢測連接狀態 - 用戶:{user_id}, 連接狀態:{is_connected}")
            return is_connected
            
        logger.debug(f"[連接管理器] 未找到連接 - 用戶:{user_id}")
        return False
    
    async def get_account_data(self, user_id: int, exchange: str = "binance", db_session: Optional[Session] = None) -> Dict:
        """
        獲取用戶的賬戶數據
        
        Args:
            user_id: 用戶ID
            exchange: 交易所名稱
            db_session: 數據庫會話，如需創建新連接則必須提供
            
        Returns:
            Dict: 賬戶數據
            
        Raises:
            ValueError: 當無法獲取連接或賬戶數據時
        """
        client, _ = await self.get_connection(user_id, exchange, db_session)
        
        try:
            # 使用客戶端獲取賬戶數據
            account_info = await client.get_account_info()
            logger.debug(f"[連接管理器] 獲取賬戶數據成功 - 用戶:{user_id}")
            
            # 格式化返回數據
            account_data = {
                "balances": [],
                "positions": [],
                "api_type": "WebSocket API (Ed25519)",  # 標記API類型
            }
            
            # 處理賬戶資訊
            if isinstance(account_info, dict):
                if "assets" in account_info:
                    account_data["balances"] = account_info["assets"]
                    
                    # 提取總權益和可用餘額
                    for asset in account_info["assets"]:
                        if asset.get("asset") == "USDT":
                            account_data["totalWalletBalance"] = asset.get("walletBalance", "0")
                            account_data["availableBalance"] = asset.get("availableBalance", "0")
                            break
                
                if "positions" in account_info:
                    account_data["positions"] = account_info["positions"]
                    
                    # 計算未實現盈虧總和
                    total_unrealized_profit = sum(
                        float(pos.get("unrealizedProfit", 0)) 
                        for pos in account_info["positions"]
                    )
                    account_data["totalUnrealizedProfit"] = str(total_unrealized_profit)
            
            return account_data
            
        except Exception as e:
            logger.error(f"[連接管理器] 獲取賬戶數據時出錯 - 用戶:{user_id}, 錯誤:{str(e)}")
            raise ValueError(f"無法獲取賬戶數據: {str(e)}")

    async def place_order(
        self, 
        user_id: int,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        exchange: str = "binance",
        db_session: Optional[Session] = None,
        **kwargs
    ) -> Dict:
        """
        執行下單操作
        
        Args:
            user_id: 用戶ID
            symbol: 交易對
            side: 訂單方向 (BUY 或 SELL)
            order_type: 訂單類型 (LIMIT, MARKET, STOP_LOSS, 等)
            quantity: 數量
            price: 價格（對於限價單必須提供）
            exchange: 交易所名稱
            db_session: 數據庫會話，如需創建新連接則必須提供
            **kwargs: 其他訂單參數
            
        Returns:
            Dict: 訂單結果
            
        Raises:
            ValueError: 當無法獲取連接或下單失敗時
        """
        client, _ = await self.get_connection(user_id, exchange, db_session)
        
        try:
            # 構建訂單參數
            order_params = {
                "quantity": quantity,
                "price": price,
                **kwargs
            }
            
            # 去除None值
            order_params = {k: v for k, v in order_params.items() if v is not None}
            
            # 使用客戶端下單
            logger.info(f"[連接管理器] 執行下單 - 用戶:{user_id}, 交易對:{symbol}, 方向:{side}, 類型:{order_type}")
            result = await client.place_order(symbol, side, order_type, **order_params)
            
            return result
        except Exception as e:
            logger.error(f"[連接管理器] 下單時出錯 - 用戶:{user_id}, 交易對:{symbol}, 錯誤:{str(e)}")
            raise ValueError(f"下單失敗: {str(e)}")
    
    async def cancel_order(
        self,
        user_id: int,
        symbol: str,
        order_id: Optional[str] = None,
        client_order_id: Optional[str] = None,
        exchange: str = "binance",
        db_session: Optional[Session] = None
    ) -> Dict:
        """
        取消訂單
        
        Args:
            user_id: 用戶ID
            symbol: 交易對
            order_id: 訂單ID（與client_order_id二選一）
            client_order_id: 客戶端訂單ID（與order_id二選一）
            exchange: 交易所名稱
            db_session: 數據庫會話，如需創建新連接則必須提供
            
        Returns:
            Dict: 取消結果
            
        Raises:
            ValueError: 當無法獲取連接或取消訂單失敗時
        """
        client, _ = await self.get_connection(user_id, exchange, db_session)
        
        try:
            # 構建參數
            params = {
                "symbol": symbol,
                "orderId": order_id,
                "origClientOrderId": client_order_id
            }
            
            # 去除None值
            params = {k: v for k, v in params.items() if v is not None}
            
            # 使用客戶端取消訂單
            logger.info(f"[連接管理器] 取消訂單 - 用戶:{user_id}, 交易對:{symbol}")
            result = await client.cancel_order(**params)
            
            return result
        except Exception as e:
            logger.error(f"[連接管理器] 取消訂單時出錯 - 用戶:{user_id}, 交易對:{symbol}, 錯誤:{str(e)}")
            raise ValueError(f"取消訂單失敗: {str(e)}")

    async def create_ws_client(self, api_key: str, api_secret: str, exchange: str = "binance", testnet: bool = False, user_id = None):
        """
        創建一個新的WebSocket客戶端
        
        直接創建與交易所的WebSocket連接，不再依賴account.py
        
        Args:
            api_key: API密鑰
            api_secret: API密鑰密碼
            exchange: 交易所名稱
            testnet: 是否使用測試網
            user_id: 用戶ID，用於連接標識
            
        Returns:
            client: WebSocket客戶端實例
            
        Raises:
            ValueError: 當無法創建連接時
        """
        if exchange.lower() == "binance":
            logger.info(f"[連接管理器] 創建新的WebSocket客戶端 - exchange:{exchange}, testnet:{testnet}")
            
            # 創建WebSocket客戶端
            client = BinanceWebSocketClient(api_key, api_secret)
            
            # 記錄最後活動時間以用於連接管理
            client.last_activity_time = time.time()
            
            # 連接到WebSocket API
            connected = await client.connect()
            
            if not connected:
                raise ValueError(f"無法連接到{exchange} WebSocket API")
                
            return client
        else:
            raise ValueError(f"不支持的交易所: {exchange}")
            
    async def get_or_create_connection(self, api_key: str, api_secret: str, exchange: str = "binance", 
                                      testnet: bool = False, user_id = None):
        """
        獲取或創建WebSocket客戶端，實現連接重用
        
        獨立的連接管理方法，不再依賴account.py
        
        Args:
            api_key: API密鑰
            api_secret: API密鑰密碼
            exchange: 交易所名稱
            testnet: 是否使用測試網
            user_id: 用戶ID，用於緩存鍵
            
        Returns:
            (client, is_new): 客戶端和是否為新創建的連接
        """
        await self.ensure_initialized()
        
        # 構造緩存鍵
        cache_key = user_id if user_id else f"{exchange}_{api_key[:8]}_{testnet}"
        
        # 檢查是否需要執行緩存清理
        await self._cleanup_inactive_connections()
        
        # 檢查緩存中是否有可用的客戶端
        if cache_key in self.ws_clients:
            client = self.ws_clients[cache_key]
            
            # 檢查客戶端是否仍然連接
            if client.is_connected():
                logger.debug(f"[連接管理器] 使用已有的WebSocket客戶端 - key:{cache_key}")
                
                # 更新最後活動時間，確保客戶端不會被閒置回收
                client.last_activity_time = time.time()
                
                return client, False
            else:
                # 如果連接已斷開，從緩存中移除
                logger.debug(f"[連接管理器] 客戶端連接已斷開，將創建新連接 - key:{cache_key}")
                try:
                    await client.disconnect()
                except:
                    pass
                del self.ws_clients[cache_key]
        
        # 創建新的客戶端
        client = await self.create_ws_client(api_key, api_secret, exchange, testnet, user_id)
        
        # 儲存到緩存中
        self.ws_clients[cache_key] = client
        
        # 啟動心跳任務，確保連接不會因為長時間閒置而斷開
        asyncio.create_task(self._maintain_client_heartbeat(client, cache_key))
        
        logger.info(f"[連接管理器] 成功創建並連接WebSocket客戶端 - key:{cache_key}")
        
        return client, True

    async def _maintain_client_heartbeat(self, client, cache_key, heartbeat_interval=300):
        """
        維護客戶端心跳，確保長連接不斷開
        
        Args:
            client: WebSocket客戶端
            cache_key: 緩存鍵
            heartbeat_interval: 心跳檢查間隔（秒），默認300秒(5分鐘)
        """
        try:
            max_reconnect_attempts = 5  # 最大重連嘗試次數
            reconnect_attempts = 0  # 當前重連嘗試次數
            backoff_multiplier = 1.5  # 重連間隔倍增因子
            
            # 連接健康管理參數
            max_connection_age = 20 * 3600  # 連接最大存活時間（20小時）
            last_health_check = time.time()
            connection_start_time = time.time()  # 初始化連接開始時間
            
            # 檢查連接狀態的間隔
            idle_check_interval = heartbeat_interval  # 閒置連接檢查間隔: 5分鐘
            active_check_interval = 60  # 活躍連接檢查間隔: 1分鐘（僅用於最近使用的連接）
            
            logger.info(f"[連接管理器] 啟動心跳維護任務 - key:{cache_key}，閒置檢查間隔: {heartbeat_interval}秒")
            
            while cache_key in self.ws_clients:
                # 檢查客戶端是否已從緩存中移除
                if cache_key not in self.ws_clients:
                    logger.debug(f"[連接管理器] 客戶端已從緩存中移除，停止心跳監控 - key:{cache_key}")
                    break
                    
                # 獲取當前時間
                current_time = time.time()
                
                # 根據連接活躍度調整檢查間隔
                check_interval = idle_check_interval  # 默認使用閒置檢查間隔
                
                if hasattr(client, 'last_activity_time'):
                    idle_time = current_time - client.last_activity_time
                    # 如果連接最近活躍（過去10分鐘內有活動），使用更短的檢查間隔
                    if idle_time < 600:  # 10分鐘內有活動的連接
                        check_interval = active_check_interval
                
                # 健康檢查 - 僅在間隔足夠長時執行（5分鐘一次）
                if current_time - last_health_check > 300:  # 每5分鐘檢查一次
                    last_health_check = current_time
                    
                    # 檢查連接是否超過最大存活時間
                    connection_age = current_time - connection_start_time
                    if connection_age > max_connection_age:
                        logger.info(f"[連接管理器] 連接已存活 {connection_age/3600:.2f} 小時，超過預設閾值 {max_connection_age/3600} 小時，進行預防性重建 - key:{cache_key}")
                        
                        try:
                            # 清理現有連接
                            old_client = self.ws_clients.get(cache_key)
                            
                            # 獲取API密鑰信息
                            api_key = getattr(old_client, 'api_key', None)
                            api_secret = getattr(old_client, 'api_secret', None)
                            
                            if api_key and api_secret:
                                # 斷開舊連接但不從緩存中移除
                                try:
                                    await old_client.disconnect()
                                    logger.info(f"[連接管理器] 已斷開舊連接，準備重建 - key:{cache_key}")
                                except Exception as disc_err:
                                    logger.warning(f"[連接管理器] 斷開舊連接時出錯: {str(disc_err)}")
                                
                                # 創建新連接
                                logger.info(f"[連接管理器] 開始預防性重建連接 - key:{cache_key}")
                                new_client = await self.create_ws_client(
                                    api_key, api_secret, exchange="binance", testnet=False, user_id=None
                                )
                                
                                if new_client.is_connected():
                                    # 更新緩存
                                    self.ws_clients[cache_key] = new_client
                                    # 更新連接開始時間
                                    connection_start_time = time.time()
                                    logger.info(f"[連接管理器] 預防性重建連接成功 - key:{cache_key}")
                                    reconnect_attempts = 0  # 重置重連計數
                                else:
                                    logger.error(f"[連接管理器] 預防性重建連接失敗 - key:{cache_key}")
                            else:
                                logger.warning(f"[連接管理器] 無法獲取API密鑰，無法進行預防性重建 - key:{cache_key}")
                        except Exception as e:
                            logger.error(f"[連接管理器] 預防性重建連接時出錯: {str(e)}")
                
                # 連接狀態檢查
                if hasattr(client, 'last_activity_time'):
                    idle_time = current_time - client.last_activity_time
                    # 檢查上次活動時間，如果超過一定時間沒有活動，檢查連接狀態
                    if idle_time > check_interval:
                        logger.debug(f"[連接管理器] 檢查連接狀態 - key:{cache_key}, 閒置時間:{idle_time:.1f}秒")
                        try:
                            # 檢查連接狀態
                            connection_status = client.is_connected()
                            
                            if not connection_status:
                                # 連接可能斷開 - 添加雙重檢查機制
                                logger.info(f"[連接管理器] 初步檢測到連接可能已斷開，等待1秒後再次檢查 - key:{cache_key}")
                                
                                # 等待一小段時間後再次檢查
                                await asyncio.sleep(1)
                                
                                # 第二次檢查連接狀態
                                second_check = client.is_connected()
                                if not second_check:
                                    # 確認連接已斷開，進行重連流程
                                    logger.info(f"[連接管理器] 確認連接已斷開，嘗試重新連接 - key:{cache_key}")
                                    
                                    # 如果超過最大重連嘗試次數，不再嘗試重連
                                    if reconnect_attempts >= max_reconnect_attempts:
                                        logger.warning(f"[連接管理器] 超過最大重連嘗試次數，從緩存中移除 - key:{cache_key}")
                                        
                                        # 清理連接並從緩存中移除
                                        try:
                                            await client.disconnect()
                                        except:
                                            pass
                                            
                                        if cache_key in self.ws_clients:
                                            del self.ws_clients[cache_key]
                                            
                                        break
                                    
                                    # 嘗試重連
                                    try:
                                        reconnected = await client.connect()
                                        if reconnected:
                                            logger.info(f"[連接管理器] 重新連接成功 - key:{cache_key}")
                                            client.last_activity_time = time.time()
                                            connection_start_time = time.time()
                                            reconnect_attempts = 0
                                        else:
                                            logger.error(f"[連接管理器] 重新連接失敗 - key:{cache_key}")
                                            reconnect_attempts += 1
                                    except Exception as e:
                                        logger.error(f"[連接管理器] 重新連接出錯 - key:{cache_key}, error:{str(e)}")
                                        reconnect_attempts += 1
                                        
                                    # 使用指數退避策略增加等待時間
                                    backoff_time = check_interval * (backoff_multiplier ** reconnect_attempts)
                                    logger.info(f"[連接管理器] 等待 {backoff_time:.1f} 秒後再次檢查連接狀態 - key:{cache_key}")
                                    await asyncio.sleep(backoff_time)
                                else:
                                    # 假陽性，連接實際上是正常的
                                    logger.info(f"[連接管理器] 連接狀態假陽性：第一次檢查報告斷開，但第二次檢查正常 - key:{cache_key}")
                                    client.last_activity_time = time.time()
                            else:
                                # 連接正常，更新最後活動時間
                                client.last_activity_time = time.time()
                                
                                # 檢測是否支持ping/pong
                                try:
                                    if hasattr(client.ws, 'pong') and callable(getattr(client.ws, 'pong')):
                                        # 每10分鐘發送一次ping以確保連接活躍
                                        if idle_time > 600:  # 10分鐘
                                            await client.ws.pong()
                                            logger.debug(f"[連接管理器] 發送pong幀以保持連接 - key:{cache_key}")
                                except Exception as ping_error:
                                    logger.warning(f"[連接管理器] 發送ping/pong時出錯: {str(ping_error)}")
                        except Exception as e:
                            logger.error(f"[連接管理器] 檢查連接狀態出錯 - key:{cache_key}, error:{str(e)}")
                
                # 等待下一次檢查
                await asyncio.sleep(check_interval)
        except asyncio.CancelledError:
            logger.info(f"[連接管理器] 心跳維護任務被取消 - key:{cache_key}")
        except Exception as e:
            logger.error(f"[連接管理器] 心跳維護任務發生錯誤: {str(e)}")
        finally:
            logger.info(f"[連接管理器] 心跳維護任務結束 - key:{cache_key}")

    async def _cleanup_inactive_connections(self):
        """
        清理長時間未使用的WebSocket客戶端
        """
        # 只有在客戶端數量較多時才執行清理
        if len(self.ws_clients) <= 10:
            return
            
        current_time = time.time()
        # 超過24小時未活動的連接
        inactive_threshold = current_time - 86400
        keys_to_remove = []
        
        for key, client in self.ws_clients.items():
            try:
                # 檢查上次活動時間
                if hasattr(client, 'last_activity_time') and client.last_activity_time < inactive_threshold:
                    logger.info(f"[連接管理器] 發現長時間未活動的客戶端 - key:{key}, 最後活動: {int(current_time - client.last_activity_time)}秒前")
                    keys_to_remove.append(key)
                # 檢查連接狀態
                elif not client.is_connected():
                    logger.info(f"[連接管理器] 發現已斷開連接的客戶端 - key:{key}")
                    keys_to_remove.append(key)
            except Exception as e:
                logger.error(f"[連接管理器] 檢查客戶端狀態時出錯 - key:{key}, error:{str(e)}")
                keys_to_remove.append(key)
        
        # 清理
        for key in keys_to_remove:
            try:
                client = self.ws_clients[key]
                logger.info(f"[連接管理器] 清理未使用的WebSocket客戶端 - key:{key}")
                await self._release_client(client, True, key)
            except Exception as e:
                logger.error(f"[連接管理器] 清理客戶端時出錯 - key:{key}, error:{str(e)}")
                if key in self.ws_clients:
                    del self.ws_clients[key]
    
    async def _release_client(self, client, force_disconnect=False, cache_key=None):
        """
        釋放WebSocket客戶端資源
        
        Args:
            client: WebSocket客戶端實例
            force_disconnect: 是否強制斷開連接
            cache_key: 緩存鍵，如果提供則從緩存中移除
        """
        if not client:
            return
            
        try:
            # 斷開連接
            if force_disconnect:
                await client.disconnect()
                
            # 從緩存中移除
            if cache_key and cache_key in self.ws_clients:
                del self.ws_clients[cache_key]
                
        except Exception as e:
            logger.error(f"[連接管理器] 釋放客戶端資源時出錯: {str(e)}")

    async def _has_account_data_changed(self, new_data, old_data):
        """
        檢查帳戶數據是否發生變化
        
        比較兩次獲取的帳戶數據，判斷是否有變化。比較關鍵字段：
        1. 餘額（資產、總額、可用額）
        2. 持倉（倉位大小、開倉價格、未實現盈虧）
        
        Args:
            new_data: 新獲取的帳戶數據
            old_data: 上次獲取的帳戶數據
            
        Returns:
            bool: 如有變化返回True，否則返回False
        """
        if not old_data or not new_data:
            return True
        
        # 比較總額和可用餘額
        if ("totalWalletBalance" in new_data and "totalWalletBalance" in old_data and 
                new_data["totalWalletBalance"] != old_data["totalWalletBalance"]):
            return True
        
        if ("availableBalance" in new_data and "availableBalance" in old_data and 
                new_data["availableBalance"] != old_data["availableBalance"]):
            return True
        
        if ("totalUnrealizedProfit" in new_data and "totalUnrealizedProfit" in old_data and 
                new_data["totalUnrealizedProfit"] != old_data["totalUnrealizedProfit"]):
            return True
        
        # 比較餘額
        new_balances = {b.get("asset"): b for b in new_data.get("balances", [])}
        old_balances = {b.get("asset"): b for b in old_data.get("balances", [])}
        
        # 檢查資產數量是否不同
        if len(new_balances) != len(old_balances):
            return True
        
        # 檢查每個資產的餘額
        for asset, new_balance in new_balances.items():
            old_balance = old_balances.get(asset)
            if not old_balance:
                return True  # 新增資產
            
            # 比較關鍵數據
            for key in ["walletBalance", "availableBalance", "locked"]:
                if key in new_balance and key in old_balance:
                    if new_balance[key] != old_balance[key]:
                        return True
        
        # 比較持倉
        new_positions = {f"{p.get('symbol')}_{p.get('positionSide', 'BOTH')}": p for p in new_data.get("positions", [])}
        old_positions = {f"{p.get('symbol')}_{p.get('positionSide', 'BOTH')}": p for p in old_data.get("positions", [])}
        
        # 檢查持倉數量是否不同
        if len(new_positions) != len(old_positions):
            return True
        
        # 檢查每個持倉的詳情
        for key, new_position in new_positions.items():
            old_position = old_positions.get(key)
            if not old_position:
                return True  # 新增持倉
            
            # 比較關鍵數據
            for k in ["positionAmt", "entryPrice", "unrealizedProfit"]:
                if k in new_position and k in old_position:
                    if new_position[k] != old_position[k]:
                        return True
        
        # 沒有發現變化
        return False
    
    async def _compute_account_data_diff(self, new_data, old_data):
        """
        計算帳戶數據的差異
        
        比較兩次獲取的帳戶數據，計算差異部分，用於增量更新。
        
        Args:
            new_data: 新獲取的帳戶數據
            old_data: 上次獲取的帳戶數據
            
        Returns:
            dict: 包含差異數據的字典
        """
        if not old_data or not new_data:
            return {"full_update": True}  # 第一次無法比較，返回完整更新標記
        
        diff = {
            "balances": {},
            "positions": {}
        }
        
        # 比較總額和可用餘額
        if "totalWalletBalance" in new_data and "totalWalletBalance" in old_data:
            old_val = float(old_data.get("totalWalletBalance", 0))
            new_val = float(new_data.get("totalWalletBalance", 0))
            if old_val != new_val:
                diff["totalWalletBalance"] = {
                    "old": str(old_val),
                    "new": str(new_val),
                    "change": str(new_val - old_val)
                }
        
        if "availableBalance" in new_data and "availableBalance" in old_data:
            old_val = float(old_data.get("availableBalance", 0))
            new_val = float(new_data.get("availableBalance", 0))
            if old_val != new_val:
                diff["availableBalance"] = {
                    "old": str(old_val),
                    "new": str(new_val),
                    "change": str(new_val - old_val)
                }
        
        if "totalUnrealizedProfit" in new_data and "totalUnrealizedProfit" in old_data:
            old_val = float(old_data.get("totalUnrealizedProfit", 0))
            new_val = float(new_data.get("totalUnrealizedProfit", 0))
            if old_val != new_val:
                diff["totalUnrealizedProfit"] = {
                    "old": str(old_val),
                    "new": str(new_val),
                    "change": str(new_val - old_val)
                }
        
        # 比較每個資產的餘額
        new_balances = {b.get("asset"): b for b in new_data.get("balances", [])}
        old_balances = {b.get("asset"): b for b in old_data.get("balances", [])}
        
        # 檢查新增的資產
        for asset, new_balance in new_balances.items():
            if asset not in old_balances:
                diff["balances"][asset] = {"added": new_balance}
                continue
            
            old_balance = old_balances[asset]
            asset_diff = {}
            
            # 比較每個字段
            for key in ["walletBalance", "availableBalance", "locked"]:
                if key in new_balance and key in old_balance:
                    old_val = float(old_balance.get(key, 0))
                    new_val = float(new_balance.get(key, 0))
                    if old_val != new_val:
                        asset_diff[key] = {
                            "old": str(old_val),
                            "new": str(new_val),
                            "change": str(new_val - old_val)
                        }
            
            if asset_diff:
                diff["balances"][asset] = asset_diff
        
        # 檢查刪除的資產
        for asset, old_balance in old_balances.items():
            if asset not in new_balances:
                diff["balances"][asset] = {"removed": old_balance}
        
        # 比較每個持倉
        new_positions = {f"{p.get('symbol')}_{p.get('positionSide', 'BOTH')}": p for p in new_data.get("positions", [])}
        old_positions = {f"{p.get('symbol')}_{p.get('positionSide', 'BOTH')}": p for p in old_data.get("positions", [])}
        
        # 檢查新增的持倉
        for key, new_position in new_positions.items():
            if key not in old_positions:
                diff["positions"][key] = {"added": new_position}
                continue
            
            old_position = old_positions[key]
            position_diff = {}
            
            # 比較每個字段
            for field in ["positionAmt", "entryPrice", "unrealizedProfit"]:
                if field in new_position and field in old_position:
                    old_val = float(old_position.get(field, 0))
                    new_val = float(new_position.get(field, 0))
                    if old_val != new_val:
                        position_diff[field] = {
                            "old": str(old_val),
                            "new": str(new_val),
                            "change": str(new_val - old_val)
                        }
            
            if position_diff:
                diff["positions"][key] = position_diff
        
        # 檢查刪除的持倉
        for key, old_position in old_positions.items():
            if key not in new_positions:
                diff["positions"][key] = {"removed": old_position}
        
        # 如果沒有任何變化，返回空字典
        if not diff["balances"] and not diff["positions"] and len(diff) <= 2:
            return {}
        
        return diff

# 創建全局實例
exchange_connection_manager = ExchangeConnectionManager()

# 添加初始化函數，可以在任何地方調用
async def initialize_connection_manager():
    """
    初始化連接管理器
    
    可以在應用啟動時調用，也可以在第一次使用時自動調用
    """
    await exchange_connection_manager.initialize() 