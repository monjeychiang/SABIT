import asyncio
import time
import logging
from typing import Dict, Any, Optional, Tuple
import ccxt.async_support as ccxt

# 修改導入路徑以適應新位置
from backend.app.schemas.trading import ExchangeEnum
from backend.utils.exchange import get_exchange_client
from backend.app.core.secure_key_cache import SecureKeyCache
from backend.app.core.api_key_manager import ApiKeyManager
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class ExchangeConnectionPool:
    """
    交易所连接池
    
    管理并复用交易所客户端连接，避免频繁创建和销毁连接
    提供连接获取、释放和健康检查等功能
    """
    
    def __init__(self, 
                 max_connections: int = 100,
                 max_idle_time: int = 300,
                 cleanup_interval: int = 120,
                 health_check_interval: int = 60):
        """
        初始化连接池
        
        Args:
            max_connections: 最大连接数限制
            max_idle_time: 连接最大空闲时间(秒)，超过后会被清理
            cleanup_interval: 定期清理的时间间隔(秒)
            health_check_interval: 健康检查结果缓存时间(秒)
        """
        self.pools: Dict[str, ccxt.Exchange] = {}  # 按用户ID和交易所分组的连接池
        self.last_used: Dict[str, float] = {}  # 记录每个连接的最后使用时间
        self.lock = asyncio.Lock()  # 用于并发访问保护
        self.max_connections = max_connections
        self.max_idle_time = max_idle_time
        self.cleanup_interval = cleanup_interval
        self.health_check_interval = health_check_interval
        
        # 健康状态缓存
        self.health_status: Dict[str, Tuple[float, bool]] = {}  # 键: pool_key, 值: (检查时间, 是否健康)
        
        # 连接使用统计
        self.reuse_counts: Dict[str, int] = {}  # 连接复用次数计数
        self.max_reuse_count = 1000  # 连接最大复用次数，超过后将刷新
        
        # 请求频率限制
        self.rate_limits = {
            ExchangeEnum.BINANCE: {"max_requests": 1200, "per_minute": 60},
            ExchangeEnum.BYBIT: {"max_requests": 600, "per_minute": 60},
            ExchangeEnum.okx: {"max_requests": 600, "per_minute": 60},
            ExchangeEnum.GATE: {"max_requests": 600, "per_minute": 60},
            ExchangeEnum.MEXC: {"max_requests": 500, "per_minute": 60},
        }
        self.request_counters: Dict[ExchangeEnum, Dict[str, Any]] = {}  # 按交易所记录请求次数
        
        # 连接统计信息
        self.stats = {
            "created": 0,          # 创建的连接总数
            "reused": 0,           # 重用的连接次数  
            "errors": 0,           # 连接错误次数
            "refreshed": 0,        # 刷新的连接数
            "cleaned": 0,          # 清理的连接数
            "rejected": 0,         # 由于频率限制被拒绝的请求数
            "avg_response_time": 0.0,  # 平均响应时间
            "total_response_time": 0.0,  # 总响应时间
            "total_operations": 0,  # 总操作次数
            "errors_by_type": {},  # 按类型统计错误
            "connections_by_exchange": {},  # 按交易所统计连接数
        }
        
        # 启动定期清理任务
        self._cleanup_task = asyncio.create_task(self._schedule_cleanup())
            
    async def get_client(self, 
                        user_id: int, 
                        exchange: ExchangeEnum, 
                        api_key: str, 
                        api_secret: str) -> ccxt.Exchange:
        """
        获取一个可用的交易所客户端
        
        如果连接池中已有可用连接，则返回该连接
        否则创建新连接并添加到连接池
        
        Args:
            user_id: 用户ID
            exchange: 交易所枚举
            api_key: API密钥
            api_secret: API密钥秘密
            
        Returns:
            ccxt.Exchange: 交易所客户端实例
        """
        start_time = time.time()
        pool_key = f"{user_id}:{exchange.value}"
        
        try:
            # 检查请求频率限制
            await self._check_rate_limit(exchange)
            
            async with self.lock:
                # 检查是否已有可用连接
                if pool_key in self.pools and self.pools[pool_key]:
                    # 检查复用次数是否超过限制
                    if pool_key in self.reuse_counts and self.reuse_counts[pool_key] >= self.max_reuse_count:
                        logger.info(f"连接 {pool_key} 已达到最大复用次数 {self.max_reuse_count}，刷新连接")
                        client = await self._refresh_client_internal(pool_key, exchange, api_key, api_secret)
                        self.reuse_counts[pool_key] = 0
                        return client
                        
                    # 复用连接
                    client = self.pools[pool_key]
                    self.last_used[pool_key] = time.time()
                    self.reuse_counts[pool_key] = self.reuse_counts.get(pool_key, 0) + 1
                    self.stats["reused"] += 1
                    return client
                    
                # 检查是否达到最大连接数
                if len(self.pools) >= self.max_connections:
                    # 释放最久未使用的连接
                    await self._release_oldest_connection()
                
                # 创建新连接
                try:
                    client = await get_exchange_client(exchange, api_key, api_secret)
                    self.pools[pool_key] = client
                    self.last_used[pool_key] = time.time()
                    self.reuse_counts[pool_key] = 0
                    
                    # 更新统计信息
                    self.stats["created"] += 1
                    
                    # 按交易所统计
                    exchange_key = exchange.value
                    if exchange_key not in self.stats["connections_by_exchange"]:
                        self.stats["connections_by_exchange"][exchange_key] = 0
                    self.stats["connections_by_exchange"][exchange_key] += 1
                    
                    return client
                except Exception as e:
                    self.stats["errors"] += 1
                    
                    # 错误统计
                    error_type = type(e).__name__
                    if error_type not in self.stats["errors_by_type"]:
                        self.stats["errors_by_type"][error_type] = 0
                    self.stats["errors_by_type"][error_type] += 1
                    
                    logger.error(f"创建交易所连接失败: {str(e)}")
                    raise
                    
        except Exception as e:
            # 记录错误但继续抛出
            logger.error(f"获取客户端异常: {str(e)}")
            raise
        finally:
            # 更新响应时间统计
            response_time = time.time() - start_time
            self.stats["total_response_time"] += response_time
            self.stats["total_operations"] += 1
            self.stats["avg_response_time"] = (
                self.stats["total_response_time"] / self.stats["total_operations"]
            )
            
    async def _release_oldest_connection(self) -> None:
        """
        释放最久未使用的连接
        在连接池已满时调用
        """
        if not self.last_used:
            return
            
        # 找出最久未使用的连接
        oldest_key = min(self.last_used.items(), key=lambda x: x[1])[0]
        logger.info(f"连接池已满，释放最久未使用的连接: {oldest_key}")
        
        # 解析key
        user_id_str, exchange_value = oldest_key.split(":")
        await self.close_client(int(user_id_str), ExchangeEnum(exchange_value))
    
    async def _check_rate_limit(self, exchange: ExchangeEnum) -> None:
        """
        检查请求频率限制
        超过限制时会等待适当时间
        
        Args:
            exchange: 交易所枚举
        """
        if exchange not in self.rate_limits:
            return
            
        current_time = time.time()
        minute_start = int(current_time / 60) * 60
        
        if exchange not in self.request_counters:
            self.request_counters[exchange] = {"count": 1, "minute_start": minute_start}
            return
            
        counter = self.request_counters[exchange]
        
        # 如果是新的一分钟，重置计数器
        if minute_start > counter["minute_start"]:
            counter["count"] = 1
            counter["minute_start"] = minute_start
            return
            
        # 检查是否超过限制
        if counter["count"] >= self.rate_limits[exchange]["max_requests"]:
            wait_time = 60 - (current_time - minute_start)
            logger.warning(f"已达到{exchange}请求频率限制，等待{wait_time:.2f}秒")
            self.stats["rejected"] += 1
            await asyncio.sleep(wait_time)
            # 重置计数器
            counter["count"] = 1
            counter["minute_start"] = int(time.time() / 60) * 60
            return
            
        # 增加计数
        counter["count"] += 1
            
    async def release_client(self, user_id: int, exchange: ExchangeEnum) -> None:
        """
        标记客户端为可用状态，不实际关闭连接
        
        Args:
            user_id: 用户ID
            exchange: 交易所枚举
        """
        pool_key = f"{user_id}:{exchange.value}"
        self.last_used[pool_key] = time.time()
    
    async def close_client(self, user_id: int, exchange: ExchangeEnum) -> None:
        """
        关闭并移除特定客户端
        
        Args:
            user_id: 用户ID
            exchange: 交易所枚举
        """
        pool_key = f"{user_id}:{exchange.value}"
        
        async with self.lock:
            if pool_key in self.pools:
                client = self.pools[pool_key]
                try:
                    await client.close()
                except Exception as e:
                    logger.warning(f"关闭连接出错: {str(e)}")
                
                del self.pools[pool_key]
                if pool_key in self.last_used:
                    del self.last_used[pool_key]
                if pool_key in self.reuse_counts:
                    del self.reuse_counts[pool_key]
                if pool_key in self.health_status:
                    del self.health_status[pool_key]
                
                self.stats["cleaned"] += 1
    
    async def _refresh_client_internal(self, 
                                     pool_key: str,
                                     exchange: ExchangeEnum, 
                                     api_key: str, 
                                     api_secret: str) -> ccxt.Exchange:
        """内部使用的刷新连接方法，无需再次获取锁"""
        if pool_key in self.pools:
            client = self.pools[pool_key]
            try:
                await client.close()
            except Exception as e:
                logger.warning(f"刷新连接时关闭旧连接出错: {str(e)}")
        
        # 创建新连接
        client = await get_exchange_client(exchange, api_key, api_secret)
        
        self.pools[pool_key] = client
        self.last_used[pool_key] = time.time()
        self.stats["refreshed"] += 1
        
        # 清除健康状态缓存
        if pool_key in self.health_status:
            del self.health_status[pool_key]
        
        return client
    
    async def refresh_client(self, 
                           user_id: int, 
                           exchange: ExchangeEnum, 
                           api_key: str, 
                           api_secret: str) -> ccxt.Exchange:
        """
        刷新连接，关闭旧连接并创建新连接
        
        Args:
            user_id: 用户ID
            exchange: 交易所枚举
            api_key: API密钥
            api_secret: API密钥秘密
            
        Returns:
            ccxt.Exchange: 新的交易所客户端实例
        """
        pool_key = f"{user_id}:{exchange.value}"
        
        async with self.lock:
            return await self._refresh_client_internal(pool_key, exchange, api_key, api_secret)
    
    async def check_client_health(self, 
                                user_id: int, 
                                exchange: ExchangeEnum) -> bool:
        """
        检查客户端连接是否健康
        
        使用缓存机制减少频繁检查，在缓存有效期内直接返回上次检查结果
        
        Args:
            user_id: 用户ID
            exchange: 交易所枚举
            
        Returns:
            bool: 连接是否健康
        """
        pool_key = f"{user_id}:{exchange.value}"
        
        # 检查是否有缓存的健康状态且未过期
        current_time = time.time()
        if pool_key in self.health_status:
            last_check_time, is_healthy = self.health_status[pool_key]
            if current_time - last_check_time < self.health_check_interval:
                return is_healthy
        
        # 执行实际的健康检查
        is_healthy = await self._perform_health_check(pool_key)
        
        # 缓存结果
        self.health_status[pool_key] = (current_time, is_healthy)
        return is_healthy
    
    async def _perform_health_check(self, pool_key: str) -> bool:
        """
        执行实际的健康检查
        
        Args:
            pool_key: 连接池键
            
        Returns:
            bool: 连接是否健康
        """
        if pool_key not in self.pools:
            return False
            
        client = self.pools[pool_key]
        
        try:
            # 使用较轻量的操作验证连接有效性
            await client.fetch_time()
            return True
        except Exception as e:
            logger.warning(f"连接健康检查失败: {pool_key} - {str(e)}")
            return False
    
    async def cleanup_idle_connections(self) -> None:
        """
        清理空闲连接
        
        关闭超过最大空闲时间的连接，释放资源
        """
        current_time = time.time()
        
        async with self.lock:
            for pool_key, last_used in list(self.last_used.items()):
                if current_time - last_used > self.max_idle_time:
                    if pool_key in self.pools:
                        client = self.pools[pool_key]
                        try:
                            await client.close()
                        except Exception as e:
                            logger.warning(f"关闭空闲连接出错: {str(e)}")
                            
                        del self.pools[pool_key]
                        del self.last_used[pool_key]
                        if pool_key in self.reuse_counts:
                            del self.reuse_counts[pool_key]
                        if pool_key in self.health_status:
                            del self.health_status[pool_key]
                            
                        self.stats["cleaned"] += 1
                        logger.info(f"已清理空闲连接: {pool_key}")
    
    async def _schedule_cleanup(self) -> None:
        """
        定期执行连接清理任务
        """
        try:
            while True:
                await asyncio.sleep(self.cleanup_interval)
                await self.cleanup_idle_connections()
        except asyncio.CancelledError:
            # 任务被取消，执行最后一次清理
            await self.cleanup_all()
    
    async def cleanup_all(self) -> None:
        """
        清理所有连接
        
        通常在服务关闭时调用，确保所有资源被释放
        """
        logger.info("正在清理所有交易所连接...")
        
        async with self.lock:
            for pool_key, client in list(self.pools.items()):
                try:
                    await client.close()
                    logger.debug(f"已关闭连接: {pool_key}")
                except Exception as e:
                    logger.warning(f"关闭连接出错: {pool_key} - {str(e)}")
            
            self.pools.clear()
            self.last_used.clear()
            self.reuse_counts.clear()
            self.health_status.clear()
            
        logger.info("所有交易所连接已清理完毕")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取连接池统计信息
        
        Returns:
            Dict: 连接池统计信息
        """
        return {
            "active_connections": len(self.pools),
            "stats": self.stats,
            "pools": list(self.pools.keys()),
            "rate_limits": {k.value: v for k, v in self.rate_limits.items()}
        } 

    async def get_client_with_cache(
        self,
        user_id: int,
        exchange: ExchangeEnum,
        db: Session
    ) -> ccxt.Exchange:
        """
        使用緩存系統獲取密鑰並創建客戶端
        
        如果緩存中存在有效的密鑰，則直接使用
        否則從ApiKeyManager獲取並存入緩存
        
        Args:
            user_id: 用戶ID
            exchange: 交易所枚舉
            db: 數據庫會話
            
        Returns:
            ccxt.Exchange: 交易所客戶端實例
        """
        try:
            # 獲取緩存實例
            key_cache = SecureKeyCache()
            
            # 嘗試從緩存獲取密鑰
            cached_keys = key_cache.get_keys(user_id, exchange.value)
            api_key = None
            api_secret = None
            
            # 檢查緩存命中情況
            if cached_keys and cached_keys[0] and cached_keys[1]:
                logger.debug(f"從緩存獲取密鑰成功 - 用戶:{user_id}, 交易所:{exchange.value}")
                api_key = cached_keys[0]
                api_secret = cached_keys[1]
            else:
                # 緩存未命中，嘗試使用 Ed25519 密鑰
                cached_ed25519_keys = key_cache.get_ed25519_keys(user_id, exchange.value)
                
                if cached_ed25519_keys and cached_ed25519_keys[0] and cached_ed25519_keys[1]:
                    logger.debug(f"從緩存獲取 Ed25519 密鑰成功 - 用戶:{user_id}, 交易所:{exchange.value}")
                    api_key = cached_ed25519_keys[0]
                    api_secret = cached_ed25519_keys[1]
                else:
                    # 緩存中都沒有，從 ApiKeyManager 獲取
                    logger.debug(f"緩存未命中，從 ApiKeyManager 獲取密鑰 - 用戶:{user_id}, 交易所:{exchange.value}")
                    api_key_manager = ApiKeyManager()
                    
                    # 獲取API密鑰記錄
                    api_key_record = await api_key_manager.get_api_key(db, user_id, exchange)
                    
                    if not api_key_record:
                        raise ValueError(f"未找到用戶 {user_id} 的 {exchange.value} API密鑰")
                    
                    # 獲取解密後的密鑰
                    api_keys, _ = await api_key_manager.get_real_api_key(
                        db=db,
                        user_id=user_id,
                        virtual_key_id=api_key_record.virtual_key_id,
                        operation="read"
                    )
                    
                    # 根據獲取結果分配密鑰
                    if "api_key" in api_keys and "api_secret" in api_keys:
                        api_key = api_keys["api_key"]
                        api_secret = api_keys["api_secret"]
                        
                        # 將獲取的密鑰存入緩存
                        key_cache.set_keys(user_id, exchange.value, api_key, api_secret)
                        logger.debug(f"HMAC-SHA256 密鑰已存入緩存 - 用戶:{user_id}, 交易所:{exchange.value}")
                    elif "ed25519_key" in api_keys and "ed25519_secret" in api_keys:
                        api_key = api_keys["ed25519_key"]
                        api_secret = api_keys["ed25519_secret"]
                        
                        # 將獲取的密鑰存入緩存
                        key_cache.set_ed25519_keys(user_id, exchange.value, api_key, api_key, api_secret)
                        logger.debug(f"Ed25519 密鑰已存入緩存 - 用戶:{user_id}, 交易所:{exchange.value}")
                    else:
                        raise ValueError(f"獲取的API密鑰格式無效 - 用戶:{user_id}, 交易所:{exchange.value}")
            
            # 使用獲取的密鑰創建客戶端
            if api_key and api_secret:
                return await self.get_client(user_id, exchange, api_key, api_secret)
            else:
                raise ValueError(f"無法獲取有效的API密鑰 - 用戶:{user_id}, 交易所:{exchange.value}")
                
        except Exception as e:
            logger.error(f"使用緩存獲取客戶端失敗: {str(e)}")
            raise

    async def refresh_client_with_cache(
        self,
        user_id: int,
        exchange: ExchangeEnum,
        db: Session
    ) -> ccxt.Exchange:
        """
        使用緩存系統刷新客戶端連接
        
        先從緩存或ApiKeyManager獲取密鑰，然後刷新連接
        
        Args:
            user_id: 用戶ID
            exchange: 交易所枚舉
            db: 數據庫會話
            
        Returns:
            ccxt.Exchange: 新的交易所客戶端實例
        """
        try:
            # 使用與get_client_with_cache相同的方式獲取密鑰
            key_cache = SecureKeyCache()
            api_key = None
            api_secret = None
            
            # 嘗試從緩存獲取密鑰
            cached_keys = key_cache.get_keys(user_id, exchange.value)
            if cached_keys and cached_keys[0] and cached_keys[1]:
                api_key = cached_keys[0]
                api_secret = cached_keys[1]
            else:
                # 嘗試獲取Ed25519密鑰
                cached_ed25519_keys = key_cache.get_ed25519_keys(user_id, exchange.value)
                if cached_ed25519_keys and cached_ed25519_keys[0] and cached_ed25519_keys[1]:
                    api_key = cached_ed25519_keys[0]
                    api_secret = cached_ed25519_keys[1]
                else:
                    # 從ApiKeyManager獲取
                    api_key_manager = ApiKeyManager()
                    api_key_record = await api_key_manager.get_api_key(db, user_id, exchange)
                    
                    if not api_key_record:
                        raise ValueError(f"未找到用戶 {user_id} 的 {exchange.value} API密鑰")
                    
                    api_keys, _ = await api_key_manager.get_real_api_key(
                        db=db,
                        user_id=user_id,
                        virtual_key_id=api_key_record.virtual_key_id,
                        operation="read"
                    )
                    
                    if "api_key" in api_keys and "api_secret" in api_keys:
                        api_key = api_keys["api_key"]
                        api_secret = api_keys["api_secret"]
                        key_cache.set_keys(user_id, exchange.value, api_key, api_secret)
                    elif "ed25519_key" in api_keys and "ed25519_secret" in api_keys:
                        api_key = api_keys["ed25519_key"]
                        api_secret = api_keys["ed25519_secret"]
                        key_cache.set_ed25519_keys(user_id, exchange.value, api_key, api_key, api_secret)
                    else:
                        raise ValueError(f"獲取的API密鑰格式無效")
            
            # 使用獲取的密鑰刷新客戶端
            if api_key and api_secret:
                return await self.refresh_client(user_id, exchange, api_key, api_secret)
            else:
                raise ValueError(f"無法獲取有效的API密鑰")
                
        except Exception as e:
            logger.error(f"使用緩存刷新客戶端失敗: {str(e)}")
            raise 

    async def check_client_health_with_cache(
        self, 
        user_id: int, 
        exchange: ExchangeEnum,
        db: Session
    ) -> bool:
        """
        使用緩存系統檢查客戶端連接是否健康
        
        如果池中沒有連接，則使用緩存獲取密鑰並創建連接
        然後檢查連接健康狀態
        
        Args:
            user_id: 用戶ID
            exchange: 交易所枚舉
            db: 數據庫會話
            
        Returns:
            bool: 連接是否健康
        """
        pool_key = f"{user_id}:{exchange.value}"
        
        # 檢查是否有緩存的健康狀態且未過期
        current_time = time.time()
        if pool_key in self.health_status:
            last_check_time, is_healthy = self.health_status[pool_key]
            if current_time - last_check_time < self.health_check_interval:
                return is_healthy
        
        # 檢查是否已有連接
        if pool_key not in self.pools:
            try:
                # 使用緩存獲取客戶端
                await self.get_client_with_cache(user_id, exchange, db)
            except Exception as e:
                logger.warning(f"使用緩存創建連接失敗: {str(e)}")
                self.health_status[pool_key] = (current_time, False)
                return False
        
        # 執行實際的健康檢查
        is_healthy = await self._perform_health_check(pool_key)
        
        # 緩存結果
        self.health_status[pool_key] = (current_time, is_healthy)
        return is_healthy 