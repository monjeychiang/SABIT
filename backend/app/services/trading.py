from typing import Dict, List, Optional, Any, Union
import ccxt.async_support as ccxt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
import logging
from decimal import Decimal
import asyncio
import random

# 导入Cython优化模块
try:
    from ..cython_modules import calculate_position_value, calculate_margin_requirement, CYTHON_ENABLED
    import logging
    logging.info("使用Cython加速版交易计算函数")
except ImportError:
    # 如果导入失败，使用原生Python版本
    CYTHON_ENABLED = False
    logging.warning("Cython模块导入失败，使用Python原生实现")

from ..core.security import decrypt_api_key
from ..db.models.user import User
from ..db.models.exchange_api import ExchangeAPI
from ..schemas.trading import (
    ExchangeEnum, OrderRequest, OrderType, OrderSide, 
    OrderInfo, Position, AccountInfo, Balance,
    StopOrder, BatchOrderRequest, BatchCancelRequest
)
from ..utils.exchange import get_exchange_client
from ..utils.connection_pool import ExchangeConnectionPool
from ..utils.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)

class TradingService:
    """
    交易服务类，处理与交易所的所有交互
    
    包括账户信息查询、下单、查询订单历史、持仓管理等功能。
    该类负责将用户的API密钥与交易所API进行连接，执行交易操作，
    并将结果格式化为统一的响应格式。
    """
    
    def __init__(self):
        """初始化交易服务，创建连接池和WebSocket管理器"""
        self.connection_pool = ExchangeConnectionPool(
            max_idle_time=300,  # 5分钟无活动自动清理
            cleanup_interval=120  # 2分钟清理一次
        )
        
        # 创建 WebSocket 管理器，用于实时账户数据推送
        self.ws_manager = WebSocketManager()
        
        # 账户数据缓存，用于优化账户信息查询
        self.account_data_cache = {}
        
        # 任务标记
        self._ws_cleanup_task = None
    
    async def _get_exchange_client_for_user(
        self, 
        user: User, 
        db: Session, 
        exchange: ExchangeEnum
    ) -> ccxt.Exchange:
        """
        获取用户特定交易所的客户端实例
        
        从连接池获取连接，如果不存在则创建新连接
        
        Args:
            user: 用户模型实例
            db: 数据库会话
            exchange: 交易所枚举值
            
        Returns:
            ccxt.Exchange: 交易所客户端实例
            
        Raises:
            HTTPException: 如果无法获取客户端
        """
        # 查询API密钥记录
        api_key_record = db.query(ExchangeAPI).filter(
            ExchangeAPI.user_id == user.id,
            ExchangeAPI.exchange == exchange
        ).first()
        
        if not api_key_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"未找到{exchange}的API密钥配置"
            )
        
        # 解密API密钥
        api_key = decrypt_api_key(api_key_record.api_key)
        api_secret = decrypt_api_key(api_key_record.api_secret)
        
        if not api_key or not api_secret:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="API密钥解密失败"
            )
        
        try:
            # 从连接池获取客户端
            client = await self.connection_pool.get_client(
                user.id, exchange, api_key, api_secret
            )
            
            # 检查连接健康状态
            is_healthy = await self.connection_pool.check_client_health(user.id, exchange)
            if not is_healthy:
                # 刷新不健康的连接
                logger.info(f"正在刷新不健康的连接: {user.id}:{exchange.value}")
                client = await self.connection_pool.refresh_client(
                    user.id, exchange, api_key, api_secret
                )
                
            return client
        except Exception as e:
            logger.error(f"获取交易所客户端失败: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"连接{exchange}交易所失败: {str(e)}"
            )
    
    async def execute_exchange_operation(self, user, db, exchange, operation_func, *args, **kwargs):
        """
        封装交易所操作的统一执行方式
        
        处理连接获取、错误处理和连接释放的通用逻辑
        
        Args:
            user: 用户模型实例
            db: 数据库会话
            exchange: 交易所枚举值
            operation_func: 要执行的操作函数
            *args, **kwargs: 传递给操作函数的参数
            
        Returns:
            操作函数的返回结果
            
        Raises:
            HTTPException: 如果操作执行失败
        """
        # 提取重试相关参数
        max_retries = kwargs.pop('max_retries', 3)  # 默认最多重试3次
        retry_delay_base = kwargs.pop('retry_delay_base', 0.5)  # 基础延迟0.5秒
        
        retries = 0
        last_error = None
        
        while retries <= max_retries:  # 允许初始尝试 + max_retries次重试
            try:
                # 获取客户端
                client = await self._get_exchange_client_for_user(user, db, exchange)
                
                # 执行操作
                result = await operation_func(client, *args, **kwargs)
                
                # 成功执行，标记客户端为可用并返回结果
                await self.connection_pool.release_client(user.id, exchange)
                return result
                
            except HTTPException:
                # 直接抛出HTTP异常，这些通常是业务逻辑错误不需要重试
                raise
                
            except Exception as e:
                last_error = e
                
                # 记录重试信息
                if retries < max_retries:
                    logger.warning(f"操作失败 (尝试 {retries+1}/{max_retries}): {str(e)}")
                    
                    # 判断是否是值得重试的错误
                    should_retry = False
                    error_str = str(e).lower()
                    
                    # 网络相关错误
                    if any(err in error_str for err in ["connection", "timeout", "network", "socket"]):
                        should_retry = True
                        
                        # 尝试刷新连接
                        try:
                            # 查询API密钥记录
                            api_key_record = db.query(ExchangeAPI).filter(
                                ExchangeAPI.user_id == user.id,
                                ExchangeAPI.exchange == exchange
                            ).first()
                            
                            if api_key_record:
                                api_key = decrypt_api_key(api_key_record.api_key)
                                api_secret = decrypt_api_key(api_key_record.api_secret)
                                
                                if api_key and api_secret:
                                    # 刷新连接
                                    logger.info(f"网络错误，正在刷新连接: {user.id}:{exchange.value}")
                                    await self.connection_pool.refresh_client(
                                        user.id, exchange, api_key, api_secret
                                    )
                        except Exception as refresh_err:
                            logger.error(f"刷新连接失败: {str(refresh_err)}")
                    
                    # 交易所临时错误
                    elif any(err in error_str for err in ["rate limit", "too many requests", "busy", "overloaded"]):
                        should_retry = True
                        # 这些错误通常需要等待更长时间
                        retry_delay_base = max(retry_delay_base * 2, 1.0)
                    
                    if not should_retry:
                        # 不值得重试的错误，直接抛出
                        break
                    
                    # 指数退避重试延迟
                    retry_delay = retry_delay_base * (2 ** retries)
                    # 添加随机抖动，避免多个客户端同时重试
                    jitter = random.uniform(0, 0.1 * retry_delay)  
                    wait_time = retry_delay + jitter
                    
                    logger.info(f"将在 {wait_time:.2f} 秒后重试...")
                    await asyncio.sleep(wait_time)
                    
                retries += 1
        
        # 所有重试都失败，记录错误并抛出异常
        if retries > 0:
            logger.error(f"执行操作失败，已重试{retries}次: {str(last_error)}")
        else:
            logger.error(f"执行操作失败: {str(last_error)}")
            
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"执行操作失败: {str(last_error)}"
        )
    
    async def get_account_info(
        self, 
        user: User, 
        db: Session, 
        exchange: ExchangeEnum
    ) -> AccountInfo:
        """
        获取账户信息
        
        获取指定交易所的账户详情，包括余额、权益等信息
        
        Args:
            user: 用户模型实例
            db: 数据库会话
            exchange: 交易所枚举值
            
        Returns:
            AccountInfo: 账户信息模型
            
        Raises:
            HTTPException: 如果获取账户信息失败
        """
        # 查询API密钥记录
        api_key_record = db.query(ExchangeAPI).filter(
            ExchangeAPI.user_id == user.id,
            ExchangeAPI.exchange == exchange
        ).first()
        
        if not api_key_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"未找到{exchange}的API密钥配置"
            )
        
        # 解密API密钥
        api_key = decrypt_api_key(api_key_record.api_key)
        api_secret = decrypt_api_key(api_key_record.api_secret)
        
        if not api_key or not api_secret:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="API密钥解密失败"
            )
        
        # 使用REST API获取账户信息
        logger.info(f"使用REST API获取账户信息 ({exchange.value})")
        
        async def _operation(client):
            # 获取账户信息
            account_data = await client.fetch_balance()
            
            # 转换为统一格式
            balances = []
            for currency, data in account_data.items():
                if currency not in ['info', 'timestamp', 'datetime', 'free', 'used', 'total']:
                    balances.append(Balance(
                        asset=currency,
                        free=Decimal(str(data.get('free', 0))),
                        used=Decimal(str(data.get('used', 0))),
                        total=Decimal(str(data.get('total', 0)))
                    ))
            
            # 处理账户总权益和未实现盈亏等信息
            # 注意：不同交易所可能返回不同的数据结构，需要适配
            total_equity = Decimal('0')
            unrealized_pnl = Decimal('0')
            margin_used = Decimal('0')
            margin_free = Decimal('0')
            
            # 尝试从账户数据中提取更多信息
            info = account_data.get('info', {})
            
            # 适配Binance期货账户格式
            if exchange == ExchangeEnum.BINANCE and 'totalMarginBalance' in info:
                total_equity = Decimal(str(info.get('totalMarginBalance', 0)))
                unrealized_pnl = Decimal(str(info.get('totalUnrealizedProfit', 0)))
                margin_used = Decimal(str(info.get('totalPositionInitialMargin', 0)))
                margin_free = Decimal(str(info.get('availableBalance', 0)))
            # 适配Bybit格式
            elif exchange == ExchangeEnum.BYBIT and 'result' in info:
                result = info.get('result', {})
                total_equity = Decimal(str(result.get('equity', 0)))
                unrealized_pnl = Decimal(str(result.get('unrealised_pnl', 0)))
                margin_used = Decimal(str(result.get('used_margin', 0)))
                margin_free = Decimal(str(result.get('available_balance', 0)))
            # 其他交易所...根据需要添加更多适配
            
            # 构建并返回账户信息
            account_info = AccountInfo(
                exchange=exchange,
                balances=balances,
                total_equity=total_equity,
                unrealized_pnl=unrealized_pnl,
                margin_used=margin_used,
                margin_free=margin_free
            )
            
            return account_info
        
        return await self.execute_exchange_operation(user, db, exchange, _operation)
    
    async def get_balance(
        self, 
        user: User, 
        db: Session, 
        exchange: ExchangeEnum, 
        asset: str
    ) -> Balance:
        """
        获取用户在特定交易所的特定资产余额
        
        尝试先从WebSocket数据获取，如果不可用则使用REST API
        
        Args:
            user: 用户模型实例
            db: 数据库会话
            exchange: 交易所枚举值
            asset: 资产符号（如BTC, USDT等）
            
        Returns:
            Balance: 资产余额信息
        """
        asset = asset.upper()  # 确保大写
        
        # 尝试从WebSocket缓存获取数据
        cache_key = f"{user.id}:{exchange.value}"
        cached_data = self.account_data_cache.get(cache_key)
        
        # 如果WebSocket数据可用并且新鲜，优先使用
        if cached_data and (datetime.now().timestamp() - cached_data['timestamp']) < 10:
            ws_data = cached_data['data']
            
            try:
                # 转换为AccountInfo并查找指定资产
                account_info = self._convert_ws_data_to_account_info(exchange, ws_data)
                
                # 查找指定资产
                for balance in account_info.balances:
                    if balance.asset == asset:
                        logger.info(f"使用WebSocket数据获取{asset}余额")
                        return balance
            except Exception as e:
                logger.error(f"处理WebSocket资产数据异常: {str(e)}")
                # 出错时回退到REST API
        
        # 使用REST API获取余额
        async def _operation(client):
            # 获取账户余额
            balance_data = await client.fetch_balance()
            
            # 检查资产是否存在
            if asset not in balance_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"资产{asset}不存在或余额为零"
                )
            
            # 转换为余额对象
            asset_data = balance_data[asset]
            balance = Balance(
                asset=asset,
                free=Decimal(str(asset_data.get('free', 0))),
                used=Decimal(str(asset_data.get('used', 0))),
                total=Decimal(str(asset_data.get('total', 0)))
            )
            
            return balance
        
        return await self.execute_exchange_operation(user, db, exchange, _operation)
    
    async def place_spot_order(
        self, 
        user: User, 
        db: Session, 
        exchange: ExchangeEnum, 
        order: OrderRequest
    ) -> OrderInfo:
        """
        在特定交易所下现货订单
        
        Args:
            user: 用户模型实例
            db: 数据库会话
            exchange: 交易所枚举值
            order: 订单请求对象
            
        Returns:
            OrderInfo: 订单信息
        """
        async def _operation(client):
            # 设置市场类型为现货
            client.options['defaultType'] = 'spot'
            
            # 准备订单参数
            symbol = order.symbol
            side = order.side.value
            type = order.type.value
            amount = float(order.amount)
            
            # 根据订单类型准备价格参数
            params = {}
            if order.type == OrderType.LIMIT:
                if not order.price:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="限价单必须指定价格"
                    )
                price = float(order.price)
            else:
                price = None
            
            # 添加可选参数
            if order.time_in_force:
                params['timeInForce'] = order.time_in_force
            if order.post_only:
                params['postOnly'] = True
                
            # 下单
            response = await client.create_order(
                symbol=symbol,
                type=type,
                side=side,
                amount=amount,
                price=price,
                params=params
            )
            
            # 转换为统一的订单信息格式
            order_info = OrderInfo(
                id=response['id'],
                exchange=exchange,
                symbol=response['symbol'],
                side=OrderSide(response['side']),
                type=OrderType(response['type']),
                status=response['status'],
                amount=Decimal(str(response['amount'])),
                filled=Decimal(str(response.get('filled', 0))),
                remaining=Decimal(str(response.get('remaining', response['amount']))),
                price=Decimal(str(response['price'])) if response.get('price') else None,
                average_price=Decimal(str(response['average'])) if response.get('average') else None,
                cost=Decimal(str(response['cost'])) if response.get('cost') else None,
                fee=response.get('fee'),
                created_at=datetime.fromtimestamp(response['timestamp'] / 1000) if response.get('timestamp') else datetime.now(),
                updated_at=None,
                closed_at=None,
                raw_data=response
            )
            
            return order_info
        
        return await self.execute_exchange_operation(user, db, exchange, _operation)

    async def place_futures_order(
        self, 
        user: User, 
        db: Session, 
        exchange: ExchangeEnum, 
        order: OrderRequest
    ) -> OrderInfo:
        """
        在特定交易所下合约订单
        
        Args:
            user: 用户模型实例
            db: 数据库会话
            exchange: 交易所枚举值
            order: 订单请求对象
            
        Returns:
            OrderInfo: 订单信息
        """
        async def _operation(client):
            # 设置市场类型为合约
            client.options['defaultType'] = 'future'
            
            # 准备订单参数
            symbol = order.symbol
            side = order.side.value
            type = order.type.value
            amount = float(order.amount)
            
            # 根据订单类型准备价格参数
            params = {}
            if order.type == OrderType.LIMIT:
                if not order.price:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="限价单必须指定价格"
                    )
                price = float(order.price)
            else:
                price = None
            
            # 添加合约特有参数
            if order.reduce_only:
                params['reduceOnly'] = True
            if order.leverage:
                # 注意：在某些交易所，设置杠杆可能需要单独的API调用
                pass
            
            # 添加止盈止损
            if order.take_profit:
                params['takeProfit'] = float(order.take_profit)
            if order.stop_loss:
                params['stopLoss'] = float(order.stop_loss)
                
            # 添加可选参数
            if order.time_in_force:
                params['timeInForce'] = order.time_in_force
            if order.post_only:
                params['postOnly'] = True
                
            # 处理币安特定的持仓模式
            if exchange == ExchangeEnum.BINANCE:
                try:
                    # 检查账户是单向模式还是对冲模式
                    position_mode_info = await client.fapiPrivate_get_positionside_dual()
                    dual_side_position = position_mode_info.get('dualSidePosition', False)
                    
                    # 如果是对冲模式，需要指定持仓方向
                    if dual_side_position:
                        # 根据订单方向确定持仓方向
                        if side == 'buy':
                            params['positionSide'] = 'LONG'
                        else:
                            params['positionSide'] = 'SHORT'
                        
                        logger.info(f"账户使用对冲模式，为{side}单设置持仓方向: {params['positionSide']}")
                except Exception as e:
                    # 如果获取持仓模式失败，记录错误但继续尝试下单
                    logger.warning(f"获取持仓模式失败，将使用默认参数: {str(e)}")
            
            # 下单
            response = await client.create_order(
                symbol=symbol,
                type=type,
                side=side,
                amount=amount,
                price=price,
                params=params
            )
            
            # 转换为统一的订单信息格式
            order_info = OrderInfo(
                id=response['id'],
                exchange=exchange,
                symbol=response['symbol'],
                side=OrderSide(response['side']),
                type=OrderType(response['type']),
                status=response['status'],
                amount=Decimal(str(response['amount'])),
                filled=Decimal(str(response.get('filled', 0))),
                remaining=Decimal(str(response.get('remaining', response['amount']))),
                price=Decimal(str(response['price'])) if response.get('price') else None,
                average_price=Decimal(str(response['average'])) if response.get('average') else None,
                cost=Decimal(str(response['cost'])) if response.get('cost') else None,
                fee=response.get('fee'),
                created_at=datetime.fromtimestamp(response['timestamp'] / 1000) if response.get('timestamp') else datetime.now(),
                updated_at=None,
                closed_at=None,
                raw_data=response
            )
            
            return order_info
        
        return await self.execute_exchange_operation(user, db, exchange, _operation)

    async def get_order_history(
        self,
        user: User,
        db: Session,
        exchange: ExchangeEnum,
        symbol: Optional[str] = None,
        order_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[OrderInfo]:
        """获取订单历史"""
        async def _operation(client):
            # 设置市场类型
            if order_type == 'spot':
                client.options['defaultType'] = 'spot'
            elif order_type == 'futures':
                client.options['defaultType'] = 'future'
            
            # 准备参数
            params = {}
            if start_time:
                params['since'] = int(start_time.timestamp() * 1000)
            if limit:
                params['limit'] = limit
                
            # 获取订单历史
            if symbol:
                orders = await client.fetch_orders(symbol=symbol, params=params)
            else:
                # 注意：并非所有交易所都支持不指定symbol的查询
                orders = []
                markets = await client.load_markets()
                # 获取主要市场的订单
                for market_symbol in list(markets.keys())[:10]:  # 限制查询的市场数量
                    try:
                        symbol_orders = await client.fetch_orders(symbol=market_symbol, params=params)
                        orders.extend(symbol_orders)
                    except Exception as e:
                        logger.warning(f"获取{market_symbol}订单历史失败: {str(e)}")
            
            # 转换为统一格式
            order_history = []
            for order in orders:
                order_info = OrderInfo(
                    id=order['id'],
                    exchange=exchange,
                    symbol=order['symbol'],
                    side=OrderSide(order['side']),
                    type=OrderType(order['type']),
                    status=order['status'],
                    amount=Decimal(str(order['amount'])),
                    filled=Decimal(str(order.get('filled', 0))),
                    remaining=Decimal(str(order.get('remaining', order['amount']))),
                    price=Decimal(str(order['price'])) if order.get('price') else None,
                    average_price=Decimal(str(order['average'])) if order.get('average') else None,
                    cost=Decimal(str(order['cost'])) if order.get('cost') else None,
                    fee=order.get('fee'),
                    created_at=datetime.fromtimestamp(order['timestamp'] / 1000) if order.get('timestamp') else None,
                    updated_at=datetime.fromtimestamp(order['lastTradeTimestamp'] / 1000) if order.get('lastTradeTimestamp') else None,
                    closed_at=None,
                    raw_data=order
                )
                order_history.append(order_info)
            
            return order_history
        
        return await self.execute_exchange_operation(user, db, exchange, _operation)

    async def get_positions(
        self,
        user: User,
        db: Session,
        exchange: ExchangeEnum,
        symbol: Optional[str] = None
    ) -> List[Position]:
        """获取当前持仓"""
        async def _operation(client):
            # 设置为期货市场
            client.options['defaultType'] = 'future'
            
            # 获取持仓
            positions_data = await client.fetch_positions(symbol)
            
            # 转换为统一格式
            positions = []
            for pos in positions_data:
                if float(pos['contracts']) > 0:  # 只返回有持仓的
                    position = Position(
                        symbol=pos['symbol'],
                        side=OrderSide.BUY if pos['side'] == 'long' else OrderSide.SELL,
                        size=Decimal(str(pos['contracts'])),
                        entry_price=Decimal(str(pos['entryPrice'])),
                        mark_price=Decimal(str(pos['markPrice'])),
                        liquidation_price=Decimal(str(pos['liquidationPrice'])) if pos.get('liquidationPrice') else None,
                        unrealized_pnl=Decimal(str(pos['unrealizedPnl'])),
                        leverage=int(pos['leverage']),
                        margin_type=pos.get('marginType', 'isolated'),
                        raw_data=pos
                    )
                    positions.append(position)
            
            return positions
        
        return await self.execute_exchange_operation(user, db, exchange, _operation)

    async def cancel_order(
        self,
        user: User,
        db: Session,
        exchange: ExchangeEnum,
        order_id: str,
        symbol: str,
        order_type: str
    ) -> Dict[str, Any]:
        """
        取消订单
        
        Args:
            user: 用户模型实例
            db: 数据库会话
            exchange: 交易所枚举值
            order_id: 订单ID
            symbol: 交易对
            order_type: 订单类型 ('spot' 或 'futures')
            
        Returns:
            Dict: 取消结果
        """
        async def _operation(client):
            # 设置市场类型
            if order_type == 'spot':
                client.options['defaultType'] = 'spot'
            elif order_type == 'futures':
                client.options['defaultType'] = 'future'
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="订单类型必须是 'spot' 或 'futures'"
                )
            
            # 取消订单
            result = await client.cancel_order(id=order_id, symbol=symbol)
            
            return result
        
        return await self.execute_exchange_operation(user, db, exchange, _operation)

    async def get_open_orders(
        self,
        user: User,
        db: Session,
        exchange: ExchangeEnum,
        symbol: Optional[str] = None,
        order_type: Optional[str] = None
    ) -> List[OrderInfo]:
        """
        获取未成交订单
        
        Args:
            user: 用户模型实例
            db: 数据库会话
            exchange: 交易所枚举值
            symbol: 交易对，可选
            order_type: 订单类型 ('spot' 或 'futures')，可选
            
        Returns:
            List[OrderInfo]: 未成交订单列表
        """
        async def _operation(client):
            # 设置市场类型
            if order_type == 'spot':
                client.options['defaultType'] = 'spot'
            elif order_type == 'futures':
                client.options['defaultType'] = 'future'
            
            # 获取未成交订单
            open_orders = await client.fetch_open_orders(symbol=symbol)
            
            # 转换为统一格式
            order_list = []
            for order in open_orders:
                order_info = OrderInfo(
                    id=order['id'],
                    exchange=exchange,
                    symbol=order['symbol'],
                    side=OrderSide(order['side']),
                    type=OrderType(order['type']),
                    status=order['status'],
                    amount=Decimal(str(order['amount'])),
                    filled=Decimal(str(order.get('filled', 0))),
                    remaining=Decimal(str(order.get('remaining', order['amount']))),
                    price=Decimal(str(order['price'])) if order.get('price') else None,
                    average_price=Decimal(str(order['average'])) if order.get('average') else None,
                    cost=Decimal(str(order['cost'])) if order.get('cost') else None,
                    fee=order.get('fee'),
                    created_at=datetime.fromtimestamp(order['timestamp'] / 1000) if order.get('timestamp') else None,
                    updated_at=None,
                    closed_at=None,
                    raw_data=order
                )
                order_list.append(order_info)
            
            return order_list
        
        return await self.execute_exchange_operation(user, db, exchange, _operation)

    async def set_leverage(
        self,
        user: User,
        db: Session,
        exchange: ExchangeEnum,
        symbol: str,
        leverage: int,
        margin_type: str
    ) -> Dict[str, Any]:
        """
        设置杠杆和保证金模式
        
        Args:
            user: 用户模型实例
            db: 数据库会话
            exchange: 交易所枚举值
            symbol: 交易对
            leverage: 杠杆倍数
            margin_type: 保证金模式 ('isolated' 或 'cross')
            
        Returns:
            Dict: 设置结果
        """
        async def _operation(client):
            # 设置为期货市场
            client.options['defaultType'] = 'future'
            
            # 验证杠杆倍数
            if leverage < 1 or leverage > 125:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="杠杆倍数必须在1-125之间"
                )
            
            # 验证保证金模式
            if margin_type not in ['isolated', 'cross']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="保证金模式必须是 'isolated' 或 'cross'"
                )
            
            # 设置杠杆倍数
            leverage_result = await client.set_leverage(leverage, symbol)
            
            # 设置保证金模式
            # 注意：不同交易所的API可能有所不同
            try:
                if exchange == ExchangeEnum.BINANCE:
                    margin_result = await client.set_margin_mode(margin_type, symbol)
                else:
                    # 针对其他交易所的处理
                    margin_result = {"margin_type": margin_type, "status": "success"}
            except Exception as e:
                logger.warning(f"设置保证金模式失败: {str(e)}")
                margin_result = {"margin_type": margin_type, "status": "failed", "error": str(e)}
            
            return {
                "symbol": symbol,
                "leverage": leverage,
                "leverage_result": leverage_result,
                "margin_type": margin_type,
                "margin_result": margin_result
            }
        
        return await self.execute_exchange_operation(user, db, exchange, _operation)

    async def place_stop_order(
        self,
        user: User,
        db: Session,
        exchange: ExchangeEnum,
        order: StopOrder
    ) -> Dict[str, Any]:
        """
        下止盈止损订单
        
        Args:
            user: 用户模型实例
            db: 数据库会话
            exchange: 交易所枚举值
            order: 止盈止损订单参数
            
        Returns:
            Dict: 下单结果
        """
        async def _operation(client):
            # 设置为期货市场
            client.options['defaultType'] = 'future'
            
            # 准备参数
            symbol = order.symbol
            side = order.side.upper()  # 确保大写
            quantity = float(order.quantity)
            stop_price = float(order.stop_price)
            params = {
                'stopPrice': stop_price,
                'workingType': order.working_type or 'MARK_PRICE',
                'reduceOnly': order.reduce_only or False,
                'closePosition': order.close_position or False
            }
            
            # 根据类型设置不同的参数
            order_type = order.type
            price = float(order.price) if order.price else None
            
            # 处理币安期货的持仓模式 (止盈止损订单通常用于期货)
            exchange_id = client.id
            if exchange_id == 'binance':
                try:
                    # 检查账户是单向模式还是对冲模式
                    position_mode_info = await client.fapiPrivate_get_positionside_dual()
                    dual_side_position = position_mode_info.get('dualSidePosition', False)
                    
                    # 如果是对冲模式，需要指定持仓方向
                    if dual_side_position:
                        # 根据止盈止损订单类型和方向确定持仓方向
                        # 这里逻辑可能需要根据业务规则调整
                        side_lower = side.lower()
                        if side_lower == 'buy':
                            # 买单通常是做多仓位的止盈止损
                            params['positionSide'] = 'LONG'
                        else:
                            # 卖单通常是做空仓位的止盈止损
                            params['positionSide'] = 'SHORT'
                        
                        logger.info(f"账户使用对冲模式，为止盈止损订单设置持仓方向: {params['positionSide']}")
                except Exception as e:
                    # 如果获取持仓模式失败，记录错误但继续尝试下单
                    logger.warning(f"获取持仓模式失败，将使用默认参数: {str(e)}")
            
            # 下单
            response = await client.create_order(
                symbol=symbol,
                type=order_type.lower(),
                side=side.lower(),
                amount=quantity,
                price=price,
                params=params
            )
            
            return {
                "orderId": response['id'],
                "symbol": response['symbol'],
                "type": response['type'],
                "side": response['side'],
                "quantity": str(response['amount']),
                "stopPrice": str(stop_price),
                "price": str(response['price']) if response.get('price') else None,
                "status": response['status'],
                "createTime": int(response['timestamp']) if response.get('timestamp') else int(datetime.now().timestamp() * 1000),
                "raw_data": response
            }
        
        return await self.execute_exchange_operation(user, db, exchange, _operation)
    
    async def batch_place_orders(
        self,
        user: User,
        db: Session,
        exchange: ExchangeEnum,
        batch_request: BatchOrderRequest
    ) -> List[Dict[str, Any]]:
        """
        批量下单
        
        Args:
            user: 用户模型实例
            db: 数据库会话
            exchange: 交易所枚举值
            batch_request: 批量订单请求
            
        Returns:
            List[Dict]: 批量下单结果
        """
        # 检查订单数量限制
        if len(batch_request.orders) > 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="批量下单最多支持5个订单"
            )
            
        async def _batch_operation(client):
            # 设置市场类型
            if batch_request.order_type == 'spot':
                client.options['defaultType'] = 'spot'
            elif batch_request.order_type == 'futures':
                client.options['defaultType'] = 'future'
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="订单类型必须是 'spot' 或 'futures'"
                )
            
            # 批量下单结果
            results = []
            
            # 逐个处理订单
            for order in batch_request.orders:
                try:
                    # 根据订单类型处理
                    if isinstance(order, StopOrder):
                        # 止盈止损订单
                        result = await self._place_single_stop_order(client, order)
                    else:
                        # 普通订单
                        result = await self._place_single_order(client, order)
                    
                    results.append({
                        "orderId": result['id'],
                        "symbol": result['symbol'],
                        "status": "NEW",
                        "message": "success"
                    })
                except Exception as e:
                    logger.error(f"批量下单中的单个订单失败: {str(e)}")
                    results.append({
                        "orderId": None,
                        "symbol": getattr(order, 'symbol', 'unknown'),
                        "status": "FAILED",
                        "message": str(e)
                    })
            
            return results
        
        return await self.execute_exchange_operation(user, db, exchange, _batch_operation)
    
    async def _place_single_order(
        self, 
        client: ccxt.Exchange, 
        order: OrderRequest
    ) -> Dict[str, Any]:
        """
        下单单个普通订单的辅助方法
        
        Args:
            client: 交易所客户端
            order: 订单请求
            
        Returns:
            Dict: 订单响应
        """
        # 准备订单参数
        symbol = order.symbol
        side = order.side.value
        type = order.type.value
        amount = float(order.amount)
        
        # 处理价格
        params = {}
        if order.type == OrderType.LIMIT:
            if not order.price:
                raise ValueError("限价单必须指定价格")
            price = float(order.price)
        else:
            price = None
        
        # 添加可选参数
        if order.time_in_force:
            params['timeInForce'] = order.time_in_force
        if order.post_only:
            params['postOnly'] = True
        if order.reduce_only:
            params['reduceOnly'] = True
            
        # 处理币安期货的持仓模式
        if 'defaultType' in client.options and client.options['defaultType'] == 'future':
            # 只对期货市场进行处理
            exchange_id = client.id
            if exchange_id == 'binance':
                try:
                    # 检查账户是单向模式还是对冲模式
                    position_mode_info = await client.fapiPrivate_get_positionside_dual()
                    dual_side_position = position_mode_info.get('dualSidePosition', False)
                    
                    # 如果是对冲模式，需要指定持仓方向
                    if dual_side_position:
                        # 根据订单方向确定持仓方向
                        if side == 'buy':
                            params['positionSide'] = 'LONG'
                        else:
                            params['positionSide'] = 'SHORT'
                        
                        logger.info(f"账户使用对冲模式，为{side}单设置持仓方向: {params['positionSide']}")
                except Exception as e:
                    # 如果获取持仓模式失败，记录错误但继续尝试下单
                    logger.warning(f"获取持仓模式失败，将使用默认参数: {str(e)}")
        
        # 下单并返回结果
        return await client.create_order(
            symbol=symbol,
            type=type,
            side=side,
            amount=amount,
            price=price,
            params=params
        )
    
    async def _place_single_stop_order(
        self, 
        client: ccxt.Exchange, 
        order: StopOrder
    ) -> Dict[str, Any]:
        """
        下单单个止盈止损订单的辅助方法
        
        Args:
            client: 交易所客户端
            order: 止盈止损订单
            
        Returns:
            Dict: 订单响应
        """
        # 准备参数
        symbol = order.symbol
        side = order.side.upper()
        quantity = float(order.quantity)
        stop_price = float(order.stop_price)
        params = {
            'stopPrice': stop_price,
            'workingType': order.working_type or 'MARK_PRICE',
            'reduceOnly': order.reduce_only or False,
            'closePosition': order.close_position or False
        }
        
        # 处理价格
        price = float(order.price) if order.price else None
        
        # 处理币安期货的持仓模式 (止盈止损订单通常用于期货)
        exchange_id = client.id
        if exchange_id == 'binance':
            try:
                # 检查账户是单向模式还是对冲模式
                position_mode_info = await client.fapiPrivate_get_positionside_dual()
                dual_side_position = position_mode_info.get('dualSidePosition', False)
                
                # 如果是对冲模式，需要指定持仓方向
                if dual_side_position:
                    # 根据止盈止损订单类型和方向确定持仓方向
                    # 这里逻辑可能需要根据业务规则调整
                    side_lower = side.lower()
                    if side_lower == 'buy':
                        # 买单通常是做多仓位的止盈止损
                        params['positionSide'] = 'LONG'
                    else:
                        # 卖单通常是做空仓位的止盈止损
                        params['positionSide'] = 'SHORT'
                    
                    logger.info(f"账户使用对冲模式，为止盈止损订单设置持仓方向: {params['positionSide']}")
            except Exception as e:
                # 如果获取持仓模式失败，记录错误但继续尝试下单
                logger.warning(f"获取持仓模式失败，将使用默认参数: {str(e)}")
        
        # 下单并返回结果
        return await client.create_order(
            symbol=symbol,
            type=order.type.lower(),
            side=side.lower(),
            amount=quantity,
            price=price,
            params=params
        )
    
    async def batch_cancel_orders(
        self,
        user: User,
        db: Session,
        exchange: ExchangeEnum,
        batch_request: BatchCancelRequest
    ) -> List[Dict[str, Any]]:
        """
        批量取消订单
        
        Args:
            user: 用户模型实例
            db: 数据库会话
            exchange: 交易所枚举值
            batch_request: 批量取消订单请求
            
        Returns:
            List[Dict]: 批量取消结果
        """
        # 检查订单数量限制
        if len(batch_request.order_ids) > 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="批量取消最多支持10个订单"
            )
        
        async def _batch_operation(client):
            # 设置市场类型
            if batch_request.order_type == 'spot':
                client.options['defaultType'] = 'spot'
            elif batch_request.order_type == 'futures':
                client.options['defaultType'] = 'future'
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="订单类型必须是 'spot' 或 'futures'"
                )
            
            # 批量取消结果
            results = []
            
            # 不同交易所的批量取消处理
            if exchange == ExchangeEnum.BINANCE and hasattr(client, 'cancel_orders'):
                # Binance支持批量取消
                try:
                    response = await client.cancel_orders(batch_request.order_ids, batch_request.symbol)
                    
                    # 处理响应
                    for order in response:
                        results.append({
                            "orderId": order['id'],
                            "status": "CANCELED",
                            "message": "success"
                        })
                except Exception as e:
                    logger.error(f"批量取消订单失败: {str(e)}")
                    # 如果批量取消失败，返回所有订单都失败的信息
                    for order_id in batch_request.order_ids:
                        results.append({
                            "orderId": order_id,
                            "status": "FAILED",
                            "message": str(e)
                        })
            else:
                # 其他交易所逐个取消
                for order_id in batch_request.order_ids:
                    try:
                        response = await client.cancel_order(id=order_id, symbol=batch_request.symbol)
                        results.append({
                            "orderId": order_id,
                            "status": "CANCELED",
                            "message": "success"
                        })
                    except Exception as e:
                        logger.error(f"取消订单 {order_id} 失败: {str(e)}")
                        results.append({
                            "orderId": order_id,
                            "status": "FAILED",
                            "message": str(e)
                        })
            
            return results
        
        return await self.execute_exchange_operation(user, db, exchange, _batch_operation)
    
    async def get_symbol_info(
        self,
        exchange: ExchangeEnum,
        symbol: Optional[str] = None
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        获取交易对信息
        
        Args:
            exchange: 交易所枚举值
            symbol: 交易对，可选
            
        Returns:
            Union[Dict, List[Dict]]: 单个或多个交易对信息
        """
        # 创建一个虚拟用户和会话用于获取公开市场数据
        # 这样我们可以利用连接池，而不必每次创建新连接
        class VirtualUser:
            def __init__(self):
                self.id = 0  # 使用特殊ID 0 表示系统查询
                
        class VirtualSession:
            def query(self, *args):
                return self
                
            def filter(self, *args):
                return self
                
            def first(self):
                # 返回一个虚拟的API密钥记录
                class ApiKeyRecord:
                    def __init__(self):
                        self.api_key = ""
                        self.api_secret = ""
                return ApiKeyRecord()
        
        try:
            virtual_user = VirtualUser()
            virtual_db = VirtualSession()
            
            # 使用execute_exchange_operation执行操作，这样就能利用连接池
            async def _operation(client):
                # 加载市场
                await client.load_markets()
                
                if symbol:
                    # 获取特定交易对信息
                    if symbol not in client.markets:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"交易对 {symbol} 不存在"
                        )
                    
                    market = client.markets[symbol]
                    result = self._format_symbol_info(market, exchange)
                else:
                    # 获取所有交易对信息
                    results = []
                    for market_symbol, market in client.markets.items():
                        # 只处理活跃的现货和永续合约
                        if market['active'] and (market['spot'] or market['swap']):
                            symbol_info = self._format_symbol_info(market, exchange)
                            results.append(symbol_info)
                    
                    result = results
                
                return result
                
            # 使用执行操作的通用方法，设置不重试
            return await self.execute_exchange_operation(virtual_user, virtual_db, exchange, _operation, max_retries=0)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取交易对信息失败: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"获取交易对信息失败: {str(e)}"
            )
    
    def _format_symbol_info(self, market: Dict[str, Any], exchange: ExchangeEnum) -> Dict[str, Any]:
        """
        格式化交易对信息
        
        Args:
            market: 市场数据
            exchange: 交易所枚举值
            
        Returns:
            Dict: 格式化后的交易对信息
        """
        # 获取精度信息
        precision = market.get('precision', {})
        price_precision = precision.get('price', 8)
        amount_precision = precision.get('amount', 8)
        
        # 获取限制信息
        limits = market.get('limits', {})
        price_limits = limits.get('price', {})
        amount_limits = limits.get('amount', {})
        cost_limits = limits.get('cost', {})
        
        # 构建统一格式
        result = {
            "symbol": market['symbol'],
            "status": "TRADING" if market['active'] else "BREAK",
            "base_asset": market['base'],
            "quote_asset": market['quote'],
            "price_precision": price_precision,
            "quantity_precision": amount_precision,
            "min_price": Decimal(str(price_limits.get('min', 0))),
            "max_price": Decimal(str(price_limits.get('max', 0))) if price_limits.get('max') else Decimal('1000000'),
            "min_quantity": Decimal(str(amount_limits.get('min', 0))),
            "min_notional": Decimal(str(cost_limits.get('min', 0))),
            "order_types": self._get_supported_order_types(exchange, market),
            "time_in_force": self._get_supported_time_in_force(exchange, market)
        }
        
        # 添加合约特有信息
        if market.get('linear') or market.get('inverse'):
            result["max_leverage"] = 125  # 默认值，实际应从交易所获取
            result["margin_types"] = ["isolated", "cross"]
        
        return result
    
    def _get_supported_order_types(self, exchange: ExchangeEnum, market: Dict[str, Any]) -> List[str]:
        """获取支持的订单类型"""
        # 默认支持的订单类型
        order_types = ["LIMIT", "MARKET"]
        
        # 根据交易所添加特殊订单类型
        if exchange == ExchangeEnum.BINANCE:
            order_types.extend(["STOP_LOSS", "STOP_LOSS_LIMIT", "TAKE_PROFIT", "TAKE_PROFIT_LIMIT"])
        elif exchange == ExchangeEnum.BYBIT:
            order_types.extend(["STOP", "STOP_MARKET", "STOP_LIMIT"])
        
        return order_types
    
    def _get_supported_time_in_force(self, exchange: ExchangeEnum, market: Dict[str, Any]) -> List[str]:
        """获取支持的时间有效性类型"""
        # 默认支持的时间有效性
        time_in_force = ["GTC"]
        
        # 根据交易所添加特殊类型
        if exchange in [ExchangeEnum.BINANCE, ExchangeEnum.BYBIT]:
            time_in_force.extend(["IOC", "FOK"])
        
        return time_in_force

    # 其他方法的代码将在后续添加... 

    # 当应用关闭时需要清理所有连接
    async def cleanup(self):
        """清理所有交易所连接和WebSocket连接"""
        logger.info("正在关闭交易服务，清理所有连接...")
        
        # 清理REST API连接
        await self.connection_pool.cleanup_all()
        
        # 清理WebSocket连接
        await self.ws_manager.cleanup()
        
        logger.info("交易服务已关闭")

    async def initialize_connection_if_needed(
        self, 
        user: User, 
        db: Session, 
        exchange: ExchangeEnum
    ) -> bool:
        """
        延迟加载策略：仅在必要时初始化连接
        
        此方法检查是否已存在连接，如不存在则创建
        适用于用户首次访问交易页面时调用
        
        Args:
            user: 用户模型实例
            db: 数据库会话
            exchange: 交易所枚举值
            
        Returns:
            bool: 连接是否成功初始化
        """
        try:
            # 检查连接池中是否已有此用户的连接
            pool_key = f"{user.id}:{exchange.value}"
            connection_exists = False
            
            # 检查REST API连接
            if hasattr(self.connection_pool, 'pools') and pool_key in self.connection_pool.pools:
                connection_exists = True
                logger.info(f"用户{user.id}已有{exchange.value}的REST API连接")
            
            # 如果没有连接，尝试建立
            if not connection_exists:
                # 查询用户的交易所API密钥
                api_key_record = db.query(ExchangeAPI).filter(
                    ExchangeAPI.user_id == user.id,
                    ExchangeAPI.exchange == exchange
                ).first()
                
                if not api_key_record:
                    logger.warning(f"未找到用户{user.id}的{exchange.value}API密钥配置")
                    return False
                
                # 解密API密钥
                api_key = decrypt_api_key(api_key_record.api_key)
                api_secret = decrypt_api_key(api_key_record.api_secret)
                
                if not api_key or not api_secret:
                    logger.error(f"用户{user.id}的API密钥解密失败")
                    return False
                
                # 仅检查连接可行性，不执行实际操作
                # 这会触发连接的创建但不会占用太多资源
                client = await self.connection_pool.get_client(
                    user.id, exchange, api_key, api_secret
                )
                await self.connection_pool.release_client(user.id, exchange)
                
                logger.info(f"成功为用户{user.id}初始化{exchange.value}连接")
                return True
            
            return connection_exists
            
        except Exception as e:
            logger.error(f"初始化连接失败: {str(e)}")
            return False 

    async def get_basic_account_info(
        self, 
        user: User, 
        db: Session, 
        exchange: ExchangeEnum
    ) -> Dict[str, Any]:
        """
        轻量级账户信息预加载
        
        在用户登录时获取基本账户信息，不建立完整的交易连接
        仅获取账户余额等基础信息，减少资源消耗
        
        Args:
            user: 用户模型实例
            db: 数据库会话
            exchange: 交易所枚举值
            
        Returns:
            Dict[str, Any]: 基本账户信息
        """
        # 查询用户的交易所API密钥
        api_key_record = db.query(ExchangeAPI).filter(
            ExchangeAPI.user_id == user.id,
            ExchangeAPI.exchange == exchange
        ).first()
        
        if not api_key_record:
            logger.warning(f"未找到用户{user.id}的{exchange.value}API密钥配置")
            return {"success": False, "message": f"未找到{exchange.value}的API密钥配置"}
        
        # 解密API密钥
        api_key = decrypt_api_key(api_key_record.api_key)
        api_secret = decrypt_api_key(api_key_record.api_secret)
        
        if not api_key or not api_secret:
            logger.error(f"用户{user.id}的API密钥解密失败")
            return {"success": False, "message": "API密钥解密失败"}
        
        try:
            # 使用临时客户端获取基本信息
            # 注意不将此客户端存入连接池
            temp_client = await get_exchange_client(exchange, api_key, api_secret)
            
            try:
                # 调用轻量级API获取基本账户信息
                if exchange == ExchangeEnum.BINANCE:
                    # 币安轻量级API调用
                    if hasattr(temp_client, 'fapiPrivate_get_account'):
                        # 合约账户
                        account_info = await temp_client.fapiPrivate_get_account()
                    else:
                        # 现货账户
                        account_info = await temp_client.privateGetAccount()
                elif exchange == ExchangeEnum.BYBIT:
                    # Bybit轻量级API调用
                    account_info = await temp_client.privateGetV2PrivateWalletBalance()
                elif exchange == ExchangeEnum.okx:
                    # OKX轻量级API调用
                    account_info = await temp_client.privateGetAccountBalance()
                else:
                    # 其他交易所使用通用方法
                    account_info = await temp_client.fetchBalance()
                
                # 处理并返回简化版的账户信息
                basic_info = self._extract_basic_account_info(exchange, account_info)
                basic_info["success"] = True
                return basic_info
                
            finally:
                # 确保临时客户端被关闭
                await temp_client.close()
                
        except Exception as e:
            logger.error(f"获取基本账户信息失败: {str(e)}")
            return {
                "success": False, 
                "message": f"获取账户信息失败: {str(e)}", 
                "exchange": exchange.value
            }
    
    def _extract_basic_account_info(self, exchange: ExchangeEnum, account_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        从完整账户信息中提取基本信息
        
        Args:
            exchange: 交易所枚举值
            account_info: 完整的账户信息
            
        Returns:
            Dict[str, Any]: 提取的基本账户信息
        """
        basic_info = {
            "exchange": exchange.value,
            "timestamp": datetime.now().isoformat(),
            "balances": []
        }
        
        try:
            # 根据不同交易所提取关键信息
            if exchange == ExchangeEnum.BINANCE:
                # 处理币安数据
                if "assets" in account_info:
                    # 合约账户
                    basic_info["total_equity"] = account_info.get("totalWalletBalance", "0")
                    basic_info["available_balance"] = account_info.get("availableBalance", "0")
                    
                    # 提取主要资产
                    for asset in account_info.get("assets", []):
                        if float(asset.get("walletBalance", 0)) > 0:
                            basic_info["balances"].append({
                                "asset": asset.get("asset", ""),
                                "total": asset.get("walletBalance", "0"),
                                "available": asset.get("availableBalance", "0")
                            })
                else:
                    # 现货账户
                    for balance in account_info.get("balances", []):
                        if float(balance.get("free", 0)) > 0 or float(balance.get("locked", 0)) > 0:
                            basic_info["balances"].append({
                                "asset": balance.get("asset", ""),
                                "total": str(float(balance.get("free", 0)) + float(balance.get("locked", 0))),
                                "available": balance.get("free", "0")
                            })
            
            elif exchange == ExchangeEnum.BYBIT:
                # 处理Bybit数据
                result = account_info.get("result", {})
                for coin, data in result.items():
                    if float(data.get("wallet_balance", 0)) > 0:
                        basic_info["balances"].append({
                            "asset": coin,
                            "total": data.get("wallet_balance", "0"),
                            "available": data.get("available_balance", "0")
                        })
                
                # 添加账户总值
                basic_info["total_equity"] = result.get("USDT", {}).get("equity", "0") if "USDT" in result else "0"
            
            elif exchange == ExchangeEnum.okx:
                # 处理OKX数据
                data = account_info.get("data", [{}])[0]
                basic_info["total_equity"] = data.get("totalEq", "0")
                
                for detail in data.get("details", []):
                    if float(detail.get("eq", 0)) > 0:
                        basic_info["balances"].append({
                            "asset": detail.get("ccy", ""),
                            "total": detail.get("eq", "0"),
                            "available": detail.get("availEq", "0")
                        })
            
            else:
                # 处理通用格式
                for currency, data in account_info.items():
                    if currency not in ['info', 'timestamp', 'datetime', 'free', 'used', 'total']:
                        if float(data.get('total', 0)) > 0:
                            basic_info["balances"].append({
                                "asset": currency,
                                "total": str(data.get('total', 0)),
                                "available": str(data.get('free', 0))
                            })
            
            # 添加统计信息
            basic_info["balance_count"] = len(basic_info["balances"])
            
            # 限制返回的资产数量，避免数据过大
            if len(basic_info["balances"]) > 20:
                # 按资产总值排序并取前20个
                basic_info["balances"] = sorted(
                    basic_info["balances"], 
                    key=lambda x: float(x.get("total", 0)), 
                    reverse=True
                )[:20]
                basic_info["limited"] = True
            
            return basic_info
            
        except Exception as e:
            logger.error(f"提取基本账户信息失败: {str(e)}")
            return {
                "exchange": exchange.value,
                "error": str(e),
                "balances": []
            } 

    async def initialize_websocket_for_account_page(
        self, 
        user: User, 
        db: Session, 
        exchange: ExchangeEnum
    ) -> Dict[str, Any]:
        """
        为账户页面初始化WebSocket连接
        
        Args:
            user: 用户模型实例
            db: 数据库会话
            exchange: 交易所枚举值
            
        Returns:
            Dict[str, Any]: 连接状态信息
        """
        try:
            # 由於不再使用WebSocket獲取帳戶資訊，返回基本的REST API狀態
            return {
                "success": True,
                "message": "使用REST API獲取帳戶數據",
                "exchange": exchange.value,
                "rest_api": True,
                "websocket": False
            }
        except Exception as e:
            logger.error(f"初始化WebSocket连接失败: {str(e)}")
            return {
                "success": False,
                "message": f"初始化WebSocket失败: {str(e)}",
                "exchange": exchange.value
            } 

    async def initialize_connections_for_vip_user(
        self, 
        user: User, 
        db: Session,
        is_high_frequency_trader: bool = False
    ) -> Dict[str, Any]:
        """
        为高级/VIP用户预初始化所有连接
        
        高频交易用户在登录时可预先建立所有连接，以提供最佳体验
        
        Args:
            user: 用户模型实例
            db: 数据库会话
            is_high_frequency_trader: 是否为高频交易用户
            
        Returns:
            Dict[str, Any]: 连接初始化结果
        """
        results = {
            "success": True,
            "message": "高级用户连接初始化完成",
            "connections": {},
            "websockets": {}
        }
        
        try:
            # 查询用户配置的所有API密钥
            api_keys = db.query(ExchangeAPI).filter(
                ExchangeAPI.user_id == user.id
            ).all()
            
            if not api_keys:
                return {
                    "success": False,
                    "message": "未找到任何API密钥配置"
                }
            
            # 初始化每个交易所的连接
            for api_key_record in api_keys:
                exchange = api_key_record.exchange
                exchange_name = exchange.value
                
                # 解密API密钥
                api_key = decrypt_api_key(api_key_record.api_key)
                api_secret = decrypt_api_key(api_key_record.api_secret)
                
                if not api_key or not api_secret:
                    results["connections"][exchange_name] = {
                        "success": False,
                        "message": "API密钥解密失败"
                    }
                    continue
                
                # 初始化WebSocket连接
                # 对于所有高级用户都优先初始化WebSocket
                ws_status = await self.initialize_websocket_for_account_page(
                    user, db, exchange
                )
                results["websockets"][exchange_name] = ws_status
                
                # 对于高频交易用户，同时初始化REST API连接
                if is_high_frequency_trader:
                    # 初始化REST API连接
                    try:
                        # 使用专门的方法初始化REST连接
                        # 这会创建连接并将其放入连接池，但不执行任何实际操作
                        rest_connected = await self.initialize_connection_if_needed(
                            user, db, exchange
                        )
                        
                        results["connections"][exchange_name] = {
                            "success": rest_connected,
                            "message": "REST API连接已预初始化" if rest_connected else "REST API连接初始化失败"
                        }
                        
                        # 为高频交易用户开启特殊的连接设置
                        if rest_connected:
                            pool_key = f"{user.id}:{exchange_name}"
                            
                            # 确保连接池中的设置适合高频交易
                            # 例如，调整复用次数限制
                            if pool_key in self.connection_pool.reuse_counts:
                                # 重置复用计数，确保新会话有足够的复用次数
                                self.connection_pool.reuse_counts[pool_key] = 0
                                
                            # 可以在这里设置其他高频交易专用配置...
                            
                    except Exception as e:
                        logger.error(f"高频交易用户连接初始化异常: {str(e)}")
                        results["connections"][exchange_name] = {
                            "success": False,
                            "message": f"连接初始化异常: {str(e)}"
                        }
            
            # 检查整体结果
            all_success = True
            failed_exchanges = []
            
            # 检查WebSocket连接结果
            for exchange, status in results["websockets"].items():
                if not status.get("success", False):
                    all_success = False
                    failed_exchanges.append(f"{exchange}(WS)")
            
            # 检查REST连接结果(如果是高频交易用户)
            if is_high_frequency_trader:
                for exchange, status in results["connections"].items():
                    if not status.get("success", False):
                        all_success = False
                        failed_exchanges.append(f"{exchange}(REST)")
            
            if not all_success:
                results["success"] = False
                results["message"] = f"部分连接初始化失败: {', '.join(failed_exchanges)}"
            
            return results
                
        except Exception as e:
            logger.error(f"高级用户连接初始化失败: {str(e)}")
            return {
                "success": False,
                "message": f"连接初始化过程异常: {str(e)}"
            }
            
    async def is_vip_or_high_frequency_user(self, user: User, db: Session) -> Dict[str, bool]:
        """
        检查用户是否为VIP用户或高频交易用户
        
        基于用户数据和交易历史判断用户类型
        
        Args:
            user: 用户模型实例
            db: 数据库会话
            
        Returns:
            Dict[str, bool]: 用户类型信息
        """
        # 这里应该实现实际的用户类型判断逻辑
        # 下面是一个简单的示例实现
        
        result = {
            "is_vip": False,
            "is_high_frequency_trader": False,
            "custom_connection_strategy": False
        }
        
        try:
            # 示例：检查用户VIP状态
            # 实际实现应该查询用户VIP状态表或其他数据
            result["is_vip"] = (user.is_active and user.id < 1000)  # 示例条件
            
            # 示例：检查是否为高频交易用户
            # 实际实现应该分析用户的交易历史和频率
            # 例如，可以查询过去24小时内用户的交易笔数
            
            # 这里只是示例，实际应该查询数据库
            result["is_high_frequency_trader"] = (
                result["is_vip"] and 
                user.id < 100  # 示例条件，实际应基于交易频率
            )
            
            # 是否启用自定义连接策略
            result["custom_connection_strategy"] = (
                result["is_vip"] or result["is_high_frequency_trader"]
            )
            
            return result
            
        except Exception as e:
            logger.error(f"检查用户类型失败: {str(e)}")
            # 出错时返回默认值
            return result

    def _calculate_position_value(self, position: Dict[str, Any], mark_price: float) -> float:
        """
        计算持仓价值
        
        Args:
            position: 持仓信息字典
            mark_price: 标记价格
                
        Returns:
            float: 持仓价值
        """
        # 使用Cython加速版本（如果可用）
        if CYTHON_ENABLED:
            return calculate_position_value(position, mark_price)
        
        # 否则使用原生Python实现
        position_amount = float(position.get("position_amount", 0))
        abs_position = abs(position_amount)
        
        # 计算持仓价值
        position_value = abs_position * mark_price
        
        return position_value
    
    def _calculate_margin_requirement(self, position: Dict[str, Any], 
                                    mark_price: float, 
                                    maintenance_margin_rate: float, 
                                    margin_type: str = "ISOLATED") -> Dict[str, float]:
        """
        计算保证金需求
        
        Args:
            position: 持仓信息字典
            mark_price: 标记价格
            maintenance_margin_rate: 维持保证金率
            margin_type: 保证金类型，可选 "ISOLATED" 或 "CROSS"
                
        Returns:
            Dict[str, float]: 包含保证金需求信息的字典
        """
        # 使用Cython加速版本（如果可用）
        if CYTHON_ENABLED:
            return calculate_margin_requirement(position, mark_price, maintenance_margin_rate, margin_type)
        
        # 否则使用原生Python实现
        position_amount = float(position.get("position_amount", 0))
        entry_price = float(position.get("entry_price", 0))
        isolated_wallet = float(position.get("isolated_wallet", 0))
        abs_position = abs(position_amount)
        
        # 计算持仓价值
        position_value = abs_position * mark_price
        
        # 计算未实现盈亏
        unrealized_pnl = 0.0
        if position_amount > 0:  # 多头
            unrealized_pnl = abs_position * (mark_price - entry_price)
        elif position_amount < 0:  # 空头
            unrealized_pnl = abs_position * (entry_price - mark_price)
        
        # 计算维持保证金
        maintenance_margin = position_value * maintenance_margin_rate
        
        # 计算保证金率
        margin_ratio = 0.0
        if margin_type == "ISOLATED":
            # 对于逐仓，保证金率 = (钱包余额 + 未实现盈亏) / 维持保证金
            if maintenance_margin > 0:
                margin_ratio = (isolated_wallet + unrealized_pnl) / maintenance_margin
        else:  # CROSS
            # 对于全仓，需要考虑账户余额，这里简化处理
            # 实际应用中需要传入更多参数
            if maintenance_margin > 0:
                margin_ratio = (isolated_wallet + unrealized_pnl) / maintenance_margin
        
        # 返回计算结果
        return {
            "position_value": position_value,
            "maintenance_margin": maintenance_margin,
            "unrealized_pnl": unrealized_pnl,
            "margin_ratio": margin_ratio,
            "liquidation_price": self._calculate_liquidation_price(
                position_amount, entry_price, isolated_wallet, 
                maintenance_margin_rate, margin_type
            )
        }
    
    def _calculate_liquidation_price(self, position_amount: float,
                                  entry_price: float,
                                  wallet_balance: float,
                                  maintenance_margin_rate: float,
                                  margin_type: str = "ISOLATED") -> float:
        """
        计算清算价格
        
        Args:
            position_amount: 持仓数量
            entry_price: 开仓均价
            wallet_balance: 钱包余额
            maintenance_margin_rate: 维持保证金率
            margin_type: 保证金类型
                
        Returns:
            float: 清算价格
        """
        # 如果没有持仓，返回0
        if position_amount == 0:
            return 0.0
        
        abs_position = abs(position_amount)
        maintenance_amount = wallet_balance - abs_position * entry_price * maintenance_margin_rate
        liquidation_price = 0.0
        
        if position_amount > 0:  # 多头
            # 对于多头，清算价格 = (开仓价值 - 钱包余额) / ((1 - 维持保证金率) * 持仓数量)
            if abs_position * (1 - maintenance_margin_rate) == 0:
                return 0.0  # 避免除以零
            liquidation_price = (abs_position * entry_price - wallet_balance) / (abs_position * (1 - maintenance_margin_rate))
        else:  # 空头
            # 对于空头，清算价格 = (开仓价值 + 钱包余额) / ((1 + 维持保证金率) * 持仓数量)
            if abs_position * (1 + maintenance_margin_rate) == 0:
                return 0.0  # 避免除以零
            liquidation_price = (abs_position * entry_price + wallet_balance) / (abs_position * (1 + maintenance_margin_rate))
        
        # 确保清算价格为正数
        return max(0.0, liquidation_price)