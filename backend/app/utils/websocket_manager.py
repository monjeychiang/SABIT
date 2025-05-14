"""
WebSocket连接管理器

管理与各交易所的WebSocket连接，处理账户数据推送，
支持实时获取账户余额、持仓和订单更新信息
"""

import asyncio
import logging
import json
from typing import Dict, Any, Optional, Callable, Coroutine
import time

from ..schemas.trading import ExchangeEnum
from .ws_data_formatter import WebSocketDataFormatter

logger = logging.getLogger(__name__)

class WebSocketManager:
    """WebSocket连接管理器"""
    
    def __init__(self, max_reconnect_attempts: int = 5):
        """
        初始化WebSocket管理器
        
        Args:
            max_reconnect_attempts: 最大重连尝试次数
        """
        # 连接管理
        self.connections: Dict[str, Dict] = {}  # 格式: {user_id:exchange: {连接相关信息}}
        self.account_data: Dict[str, Dict] = {}  # 缓存账户数据
        self.tasks: Dict[str, asyncio.Task] = {}  # 管理WebSocket任务
        self.max_reconnect_attempts = max_reconnect_attempts
        self.lock = asyncio.Lock()  # 防止并发问题
        
        # 统计信息
        self.stats = {
            "total_messages": 0,
            "messages_by_exchange": {},
            "connections_total": 0,
            "active_connections": 0,
            "reconnect_attempts": 0,
            "last_message_time": {}
        }
    
    async def connect(
        self, 
        user_id: int, 
        exchange: ExchangeEnum, 
        api_key: str,
        api_secret: str,
        callback: Optional[Callable[[Dict[str, Any]], Coroutine]] = None
    ) -> bool:
        """
        建立WebSocket连接
        
        Args:
            user_id: 用户ID
            exchange: 交易所枚举
            api_key: API密钥
            api_secret: API密钥秘密
            callback: 可选的数据更新回调函数
            
        Returns:
            bool: 连接是否成功
        """
        pool_key = f"{user_id}:{exchange.value}"
        
        async with self.lock:
            # 检查是否已有连接
            if pool_key in self.connections and self.connections[pool_key].get("connected", False):
                if callback:
                    # 更新回调函数
                    self.connections[pool_key]["callback"] = callback
                return True
                
            # 创建连接配置
            connection_config = {
                "user_id": user_id,
                "exchange": exchange,
                "api_key": api_key,
                "api_secret": api_secret,
                "callback": callback,
                "connected": False,
                "last_ping": time.time(),
                "reconnect_count": 0,
                "last_message_time": time.time()
            }
            
            self.connections[pool_key] = connection_config
            
            # 启动WebSocket任务
            self.tasks[pool_key] = asyncio.create_task(
                self._ws_client_task(pool_key)
            )
            
            # 更新统计信息
            self.stats["connections_total"] += 1
            self.stats["active_connections"] += 1
            
            # 等待连接建立，最多30秒
            max_wait = 30
            while max_wait > 0 and not self.connections[pool_key].get("connected", False):
                await asyncio.sleep(1)
                max_wait -= 1
                
            return self.connections[pool_key].get("connected", False)
    
    async def _ws_client_task(self, pool_key: str) -> None:
        """
        WebSocket客户端任务
        
        处理连接建立、消息接收和重连逻辑
        
        Args:
            pool_key: 连接池键
        """
        if pool_key not in self.connections:
            logger.error(f"连接配置不存在: {pool_key}")
            return
            
        connection = self.connections[pool_key]
        user_id = connection["user_id"]
        exchange = connection["exchange"]
        
        # 在任务中捕获所有异常
        try:
            while True:
                try:
                    # 如果重连次数超过限制，停止尝试
                    if connection["reconnect_count"] >= self.max_reconnect_attempts:
                        logger.error(f"WebSocket超过最大重连次数，停止重连: {pool_key}")
                        break
                        
                    if connection["reconnect_count"] > 0:
                        # 使用指数回退重连
                        backoff = min(30, 1 * (2 ** (connection["reconnect_count"] - 1)))
                        logger.info(f"WebSocket重连中，等待{backoff}秒: {pool_key}")
                        await asyncio.sleep(backoff)
                    
                    # 连接到WebSocket
                    await self._connect_to_exchange(pool_key)
                    
                    # 如果连接失败，增加重连计数
                    if not connection["connected"]:
                        connection["reconnect_count"] += 1
                        self.stats["reconnect_attempts"] += 1
                        continue
                    
                    # 重置重连计数
                    connection["reconnect_count"] = 0
                    
                    # 启动心跳任务
                    heartbeat_task = asyncio.create_task(self._heartbeat_task(pool_key))
                    
                    # 接收消息循环
                    while connection["connected"]:
                        # 模拟接收消息
                        # 在实际实现中，这里应该是从WebSocket接收消息
                        message = await self._receive_message(pool_key)
                        
                        if message:
                            # 更新最后消息时间
                            connection["last_message_time"] = time.time()
                            self.stats["last_message_time"][pool_key] = time.time()
                            
                            # 处理消息
                            await self._process_message(pool_key, message)
                        
                        # 添加小延迟，避免CPU占用过高
                        await asyncio.sleep(0.01)
                    
                    # 如果连接断开，取消心跳任务
                    heartbeat_task.cancel()
                    
                except asyncio.CancelledError:
                    logger.info(f"WebSocket任务被取消: {pool_key}")
                    await self._disconnect(pool_key)
                    break
                    
                except Exception as e:
                    logger.error(f"WebSocket任务异常: {pool_key} - {str(e)}")
                    await self._disconnect(pool_key)
                    connection["reconnect_count"] += 1
                    self.stats["reconnect_attempts"] += 1
        
        except Exception as e:
            logger.error(f"WebSocket客户端任务外部异常: {pool_key} - {str(e)}")
        finally:
            # 最终清理
            if pool_key in self.connections:
                await self._disconnect(pool_key)
                logger.info(f"WebSocket任务结束: {pool_key}")
    
    async def _connect_to_exchange(self, pool_key: str) -> None:
        """
        连接到指定交易所的WebSocket
        
        基于不同交易所实现具体的连接逻辑
        
        Args:
            pool_key: 连接池键
        """
        if pool_key not in self.connections:
            return
            
        connection = self.connections[pool_key]
        exchange = connection["exchange"]
        api_key = connection["api_key"]
        api_secret = connection["api_secret"]
        
        try:
            # 实现具体交易所的连接逻辑 - 只保留市场数据，移除帐户资金的WebSocket连接
            if exchange == ExchangeEnum.BINANCE:
                # 连接到币安市场数据WebSocket
                logger.info(f"正在连接币安行情数据WebSocket: {pool_key}")
                
                # 设置连接为已连接状态，实际应用中应建立真正的WebSocket连接
                connection["connected"] = True
                logger.info(f"币安行情数据WebSocket连接成功: {pool_key}")
                
            elif exchange == ExchangeEnum.BYBIT:
                # 连接到Bybit市场数据WebSocket
                logger.info(f"正在连接Bybit行情数据WebSocket: {pool_key}")
                
                # 设置连接为已连接状态
                connection["connected"] = True
                logger.info(f"Bybit行情数据WebSocket连接成功: {pool_key}")
                
            elif exchange == ExchangeEnum.okx:
                # 连接到OKX市场数据WebSocket
                logger.info(f"正在连接OKX行情数据WebSocket: {pool_key}")
                
                # 设置连接为已连接状态
                connection["connected"] = True
                logger.info(f"OKX行情数据WebSocket连接成功: {pool_key}")
                
            else:
                logger.warning(f"不支持的交易所WebSocket: {exchange.value}")
                
        except Exception as e:
            logger.error(f"连接到交易所WebSocket失败: {pool_key} - {str(e)}")
            connection["connected"] = False
    
    async def _receive_message(self, pool_key: str) -> Optional[Dict[str, Any]]:
        """
        从WebSocket接收消息
        
        这里是模拟实现，实际应从WebSocket读取数据
        
        Args:
            pool_key: 连接池键
            
        Returns:
            Optional[Dict]: 接收到的消息，如果没有则为None
        """
        # 这里应该是实际从WebSocket读取数据的逻辑
        # 此处只是模拟，返回None表示当前没有新消息
        return None
    
    async def _process_message(self, pool_key: str, message: Dict[str, Any]) -> None:
        """
        处理WebSocket消息
        
        解析消息内容，更新账户数据，调用回调函数
        
        Args:
            pool_key: 连接池键
            message: 接收到的消息
        """
        if pool_key not in self.connections:
            return
            
        connection = self.connections[pool_key]
        exchange = connection["exchange"]
        callback = connection["callback"]
        
        # 更新统计信息
        self.stats["total_messages"] += 1
        if exchange.value not in self.stats["messages_by_exchange"]:
            self.stats["messages_by_exchange"][exchange.value] = 0
        self.stats["messages_by_exchange"][exchange.value] += 1
        
        try:
            # 将消息转换为统一格式
            formatted_data = WebSocketDataFormatter.format_account_update(exchange, message)
            
            # 缓存账户数据
            self.account_data[pool_key] = formatted_data
            
            # 如果有回调函数，调用回调
            if callback:
                await callback(formatted_data)
                
            # 记录消息摘要
            logger.debug(f"接收到{exchange.value}消息: {WebSocketDataFormatter.get_human_readable_summary(exchange, message)}")
            
        except Exception as e:
            logger.error(f"处理WebSocket消息失败: {pool_key} - {str(e)}")
    
    async def _heartbeat_task(self, pool_key: str) -> None:
        """
        心跳任务
        
        定期发送心跳包保持连接活跃
        
        Args:
            pool_key: 连接池键
        """
        if pool_key not in self.connections:
            return
            
        connection = self.connections[pool_key]
        
        try:
            while connection["connected"]:
                # 每30秒发送一次心跳
                await asyncio.sleep(30)
                
                # 检查是否需要发送心跳
                current_time = time.time()
                if current_time - connection["last_ping"] > 25:  # 确保至少间隔25秒
                    connection["last_ping"] = current_time
                    
                    # 发送心跳包
                    # 实际实现中，这里应该向WebSocket发送心跳消息
                    logger.debug(f"发送WebSocket心跳: {pool_key}")
                    
                    # 检查最后消息时间，如果太久没消息，可能连接已断开
                    if current_time - connection["last_message_time"] > 300:  # 5分钟没消息
                        logger.warning(f"WebSocket连接可能已断开，尝试重连: {pool_key}")
                        connection["connected"] = False
                        break
        except asyncio.CancelledError:
            # 任务被取消，正常退出
            pass
        except Exception as e:
            logger.error(f"WebSocket心跳任务异常: {pool_key} - {str(e)}")
            connection["connected"] = False
    
    async def _disconnect(self, pool_key: str) -> None:
        """
        断开WebSocket连接
        
        清理资源并标记连接为断开
        
        Args:
            pool_key: 连接池键
        """
        if pool_key in self.connections:
            connection = self.connections[pool_key]
            
            if connection.get("connected", False):
                # 实际实现中，这里应该关闭WebSocket连接
                logger.info(f"断开WebSocket连接: {pool_key}")
                connection["connected"] = False
                
                # 更新统计信息
                self.stats["active_connections"] -= 1
    
    async def disconnect(self, user_id: int, exchange: ExchangeEnum) -> None:
        """
        断开指定用户的WebSocket连接
        
        Args:
            user_id: 用户ID
            exchange: 交易所枚举
        """
        pool_key = f"{user_id}:{exchange.value}"
        
        async with self.lock:
            if pool_key in self.tasks:
                # 取消任务
                self.tasks[pool_key].cancel()
                
                try:
                    await self.tasks[pool_key]
                except asyncio.CancelledError:
                    pass
                    
                del self.tasks[pool_key]
                
            await self._disconnect(pool_key)
            
            # 清理连接数据
            if pool_key in self.connections:
                del self.connections[pool_key]
                
            # 清理账户数据
            if pool_key in self.account_data:
                del self.account_data[pool_key]
    
    async def get_account_data(self, user_id: int, exchange: ExchangeEnum) -> Optional[Dict[str, Any]]:
        """
        获取账户数据
        
        获取最新的账户WebSocket推送数据
        
        Args:
            user_id: 用户ID
            exchange: 交易所枚举
            
        Returns:
            Optional[Dict]: 账户数据，如果没有则为None
        """
        pool_key = f"{user_id}:{exchange.value}"
        
        return self.account_data.get(pool_key)
    
    async def get_formatted_account_data(self, user_id: int, exchange: ExchangeEnum) -> Optional[Dict[str, Any]]:
        """
        获取格式化的账户数据
        
        获取经过格式化处理的账户数据，易于阅读和理解
        
        Args:
            user_id: 用户ID
            exchange: 交易所枚举
            
        Returns:
            Optional[Dict]: 格式化的账户数据，如果没有则为None
        """
        raw_data = await self.get_account_data(user_id, exchange)
        if not raw_data:
            return None
            
        # 由于原始数据已经是格式化过的，直接返回
        return raw_data
    
    async def get_connection_status(self, user_id: int, exchange: ExchangeEnum) -> Dict[str, Any]:
        """
        获取WebSocket连接状态
        
        Args:
            user_id: 用户ID
            exchange: 交易所枚举
            
        Returns:
            Dict: 连接状态信息
        """
        pool_key = f"{user_id}:{exchange.value}"
        
        if pool_key not in self.connections:
            return {
                "connected": False,
                "status": "not_initialized",
                "message": "WebSocket连接未初始化"
            }
            
        connection = self.connections[pool_key]
        
        # 检查连接活跃度
        last_message_time = connection.get("last_message_time", 0)
        current_time = time.time()
        message_age = current_time - last_message_time
        
        status = {
            "connected": connection.get("connected", False),
            "reconnect_count": connection.get("reconnect_count", 0),
            "last_message_age": message_age,
            "message_received": pool_key in self.account_data,
        }
        
        # 添加健康状态评估
        if not status["connected"]:
            status["health"] = "disconnected"
            status["message"] = "WebSocket未连接"
        elif message_age > 600:  # 10分钟没收到消息
            status["health"] = "stale"
            status["message"] = f"长时间({int(message_age)}秒)未收到消息，连接可能不健康"
        elif message_age > 300:  # 5分钟没收到消息
            status["health"] = "warning"
            status["message"] = f"较长时间({int(message_age)}秒)未收到消息，请关注连接状态"
        elif status["reconnect_count"] > 0:
            status["health"] = "recovering"
            status["message"] = f"连接曾经断开过{status['reconnect_count']}次，但当前已恢复"
        else:
            status["health"] = "healthy"
            status["message"] = "WebSocket连接正常"
            
        return status
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取WebSocket统计信息
        
        Returns:
            Dict: WebSocket统计信息
        """
        return {
            "active_connections": self.stats["active_connections"],
            "total_connections": self.stats["connections_total"],
            "reconnect_attempts": self.stats["reconnect_attempts"],
            "total_messages": self.stats["total_messages"],
            "messages_by_exchange": self.stats["messages_by_exchange"],
            "connections": list(self.connections.keys())
        }
    
    async def cleanup(self) -> None:
        """
        清理所有WebSocket连接
        
        通常在应用关闭时调用
        """
        logger.info("正在清理所有WebSocket连接...")
        
        # 复制一份键列表，避免在迭代过程中修改字典
        keys = list(self.connections.keys())
        
        for pool_key in keys:
            user_id, exchange_value = pool_key.split(":")
            await self.disconnect(int(user_id), ExchangeEnum(exchange_value))
            
        logger.info("所有WebSocket连接已清理完毕") 