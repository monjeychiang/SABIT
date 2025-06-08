from typing import Dict, List, Optional, Any, Union, Callable
import ccxt.async_support as ccxt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
import logging
from decimal import Decimal
import asyncio
import random
import time
import traceback

# 導入Cython優化模組
try:
    from ..cython_modules import calculate_position_value, calculate_margin_requirement, CYTHON_ENABLED
    import logging
    logging.info("使用Cython加速版交易計算函數")
except ImportError:
    # 如果導入失敗，使用原生Python版本
    CYTHON_ENABLED = False
    logging.warning("Cython模組導入失敗，使用Python原生實現")

from ..core.security import decrypt_api_key
from ..db.models.user import User
from ..db.models.exchange_api import ExchangeAPI
from ..schemas.trading import (
    ExchangeEnum, OrderRequest, OrderType, OrderSide, 
    OrderInfo, Position, AccountInfo, Balance,
    StopOrder, BatchOrderRequest, BatchCancelRequest,
    OrderResponse, OrderStatus, PositionResponse, BalanceResponse,
    AccountInfoResponse, OrderBookResponse, MarketTradesResponse,
    TickerResponse
)
from backend.utils.exchange import get_exchange_client
from backend.utils.connection_pool import ExchangeConnectionPool

logger = logging.getLogger(__name__)

# 創建連接池實例
exchange_pool = ExchangeConnectionPool()

class TradingService:
    """
    交易服務類，處理與交易所的所有交互
    
    包括賬戶信息查詢、下單、查詢訂單歷史、持倉管理等功能。
    該類負責將用戶的API密鑰與交易所API進行連接，執行交易操作，
    並將結果格式化為統一的響應格式。
    """
    
    def __init__(self):
        """初始化交易服務，創建連接池"""
        self.connection_pool = ExchangeConnectionPool(
            max_idle_time=300,  # 5分鐘無活動自動清理
            cleanup_interval=120  # 2分鐘清理一次
        )
        
    async def _get_exchange_client_for_user(
        self, 
        user: User, 
        db: Session, 
        exchange: ExchangeEnum,
        virtual_key_id: str = None
    ) -> ccxt.Exchange:
        """
        獲取用戶特定交易所的客戶端實例
        
        從連接池獲取連接，如果不存在則創建新連接
        CCXT 僅支持 HMAC-SHA256 密鑰格式，不支持 Ed25519 密鑰
        
        Args:
            user: 用戶模型實例
            db: 數據庫會話
            exchange: 交易所枚舉值
            virtual_key_id: 虛擬密鑰標識符（可選）
            
        Returns:
            ccxt.Exchange: 交易所客戶端實例
            
        Raises:
            HTTPException: 如果無法獲取客戶端或密鑰類型不匹配
        """
        try:
            # 獲取 API 密鑰管理器
            from ..core.api_key_manager import ApiKeyManager
            api_key_manager = ApiKeyManager()
            
            # 如果提供了虛擬密鑰 ID，使用 API 密鑰管理器獲取真實密鑰
            if virtual_key_id:
                # 獲取真實 API 密鑰
                real_keys, api_key_record = await api_key_manager.get_real_api_key(
                    db=db,
                    user_id=user.id,
                    virtual_key_id=virtual_key_id,
                    operation="trade"  # 假設是交易操作
                )
                
                # 檢查交易所是否匹配
                if api_key_record.exchange != exchange:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"虛擬密鑰 {virtual_key_id} 不屬於交易所 {exchange}"
                    )
                
                # 僅獲取 HMAC-SHA256 密鑰，CCXT 不支持 Ed25519 密鑰
                api_key = real_keys.get("api_key")
                api_secret = real_keys.get("api_secret")
                
                if not api_key or not api_secret:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="CCXT 需要 HMAC-SHA256 API 密鑰，但用戶未配置此類型密鑰或解密失敗"
                    )
            else:
                # 原有邏輯：直接查詢 API 密鑰記錄
                api_key_record = await api_key_manager.get_api_key(db, user.id, exchange)
                
                if not api_key_record:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"未找到{exchange}的API密鑰配置"
                    )
                
                # 解密 HMAC-SHA256 API 密鑰
                api_key = decrypt_api_key(api_key_record.api_key)
                api_secret = decrypt_api_key(api_key_record.api_secret)
                
                if not api_key or not api_secret:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="CCXT 需要 HMAC-SHA256 API 密鑰，但用戶未配置此類型密鑰或解密失敗"
                    )
            
            # 從連接池獲取客戶端
            client = await self.connection_pool.get_client(
                user.id, exchange, api_key, api_secret
            )
            
            # 檢查連接健康狀態
            is_healthy = await self.connection_pool.check_client_health(user.id, exchange)
            if not is_healthy:
                # 刷新不健康的連接
                logger.info(f"正在刷新不健康的連接: {user.id}:{exchange.value}")
                client = await self.connection_pool.refresh_client(
                    user.id, exchange, api_key, api_secret
                )
                
            return client
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"獲取交易所客戶端失敗: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"連接{exchange}交易所失敗: {str(e)}"
            )
    
    async def execute_exchange_operation(
        self,
        user: User,
        db: Session,
        exchange: ExchangeEnum,
        operation_func: Callable,
        operation_name: str,
        virtual_key_id: Optional[str] = None,
        *args,
        **kwargs
    ):
        """
        執行交易所操作的通用方法
        
        此方法封裝了執行交易所操作的常見邏輯：
        1. 獲取交易所客戶端
        2. 執行操作
        3. 處理錯誤和重試
        4. 記錄 API 使用情況
        
        Args:
            user: 用戶模型實例
            db: 數據庫會話
            exchange: 交易所枚舉
            operation_func: 要執行的操作函數
            operation_name: 操作名稱（用於日誌記錄）
            virtual_key_id: 虛擬密鑰 ID（可選）
            *args, **kwargs: 傳遞給操作函數的參數
            
        Returns:
            操作函數的返回值
            
        Raises:
            HTTPException: 如果操作失敗
        """
        from ..core.api_key_manager import ApiKeyManager
        api_key_manager = ApiKeyManager()
        
        # 獲取交易所客戶端
        client = await self._get_exchange_client_for_user(user, db, exchange, virtual_key_id)
        
        # 重試計數器
        retry_count = 0
        max_retries = 3
        backoff_factor = 2  # 指數退避因子
        
        while True:
            try:
                # 執行操作
                start_time = time.time()
                result = await operation_func(client, *args, **kwargs)
                execution_time = time.time() - start_time
                
                # 記錄 API 使用情況
                if virtual_key_id:
                    await api_key_manager.log_api_usage(
                        db=db,
                        user_id=user.id,
                        virtual_key_id=virtual_key_id,
                        operation=operation_name,
                        execution_time=execution_time,
                        success=True,
                        details={"args": str(args), "kwargs": str(kwargs)}
                    )
                
                logger.info(
                    f"用戶 {user.id} 在 {exchange.value} 成功執行 {operation_name}，"
                    f"耗時: {execution_time:.2f}秒"
                )
                return result
                
            except ccxt.NetworkError as e:
                # 網絡錯誤可以重試
                if retry_count < max_retries:
                    retry_count += 1
                    wait_time = backoff_factor ** retry_count
                    logger.warning(
                        f"用戶 {user.id} 在 {exchange.value} 執行 {operation_name} 時遇到網絡錯誤: {str(e)}。"
                        f"重試 {retry_count}/{max_retries}，等待 {wait_time} 秒"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # 記錄失敗的 API 使用情況
                    if virtual_key_id:
                        await api_key_manager.log_api_usage(
                            db=db,
                            user_id=user.id,
                            virtual_key_id=virtual_key_id,
                            operation=operation_name,
                            execution_time=time.time() - start_time,
                            success=False,
                            details={"error": str(e), "args": str(args), "kwargs": str(kwargs)}
                        )
                    
                    logger.error(
                        f"用戶 {user.id} 在 {exchange.value} 執行 {operation_name} 失敗，"
                        f"網絡錯誤，已達最大重試次數: {str(e)}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=f"連接交易所失敗，請稍後再試: {str(e)}"
                    )
                    
            except ccxt.ExchangeError as e:
                # 記錄失敗的 API 使用情況
                if virtual_key_id:
                    await api_key_manager.log_api_usage(
                        db=db,
                        user_id=user.id,
                        virtual_key_id=virtual_key_id,
                        operation=operation_name,
                        execution_time=time.time() - start_time if 'start_time' in locals() else 0,
                        success=False,
                        details={"error": str(e), "args": str(args), "kwargs": str(kwargs)}
                    )
                
                logger.error(
                    f"用戶 {user.id} 在 {exchange.value} 執行 {operation_name} 失敗，"
                    f"交易所錯誤: {str(e)}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"交易所操作失敗: {str(e)}"
                )
                
            except Exception as e:
                # 記錄失敗的 API 使用情況
                if virtual_key_id:
                    await api_key_manager.log_api_usage(
                        db=db,
                        user_id=user.id,
                        virtual_key_id=virtual_key_id,
                        operation=operation_name,
                        execution_time=time.time() - start_time if 'start_time' in locals() else 0,
                        success=False,
                        details={"error": str(e), "args": str(args), "kwargs": str(kwargs)}
                    )
                
                logger.error(
                    f"用戶 {user.id} 在 {exchange.value} 執行 {operation_name} 失敗，"
                    f"未知錯誤: {str(e)}"
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"執行操作失敗: {str(e)}"
                )
    
    async def get_account_info(
        self, 
        user: User, 
        db: Session, 
        exchange: ExchangeEnum,
        virtual_key_id: str = None
    ) -> AccountInfo:
        """
        獲取賬戶信息
        
        獲取指定交易所的賬戶詳情，包括餘額、權益等信息
        
        Args:
            user: 用戶模型實例
            db: 數據庫會話
            exchange: 交易所枚舉值
            virtual_key_id: 虛擬密鑰 ID（可選）
            
        Returns:
            AccountInfo: 賬戶信息模型
            
        Raises:
            HTTPException: 如果獲取賬戶信息失敗
        """
        try:
            # 使用交易所客戶端獲取賬戶信息
            logger.info(f"使用API獲取賬戶信息 ({exchange.value})")
            
            async def _operation(client):
                # 獲取賬戶信息
                account_data = await client.fetch_balance()
                
                # 轉換為統一格式
                balances = []
                for currency, data in account_data.items():
                    if currency not in ['info', 'timestamp', 'datetime', 'free', 'used', 'total']:
                        balances.append(Balance(
                            asset=currency,
                            free=Decimal(str(data.get('free', 0))),
                            used=Decimal(str(data.get('used', 0))),
                            total=Decimal(str(data.get('total', 0)))
                        ))
                
                # 處理賬戶總權益和未實現盈虧等信息
                # 注意：不同交易所可能返回不同的數據結構，需要適配
                total_equity = Decimal('0')
                unrealized_pnl = Decimal('0')
                margin_used = Decimal('0')
                margin_free = Decimal('0')
                
                # 嘗試從賬戶數據中提取更多信息
                info = account_data.get('info', {})
                
                # 適配Binance期貨賬戶格式
                if exchange == ExchangeEnum.BINANCE and 'totalMarginBalance' in info:
                    total_equity = Decimal(str(info.get('totalMarginBalance', 0)))
                    unrealized_pnl = Decimal(str(info.get('totalUnrealizedProfit', 0)))
                    margin_used = Decimal(str(info.get('totalPositionInitialMargin', 0)))
                    margin_free = Decimal(str(info.get('availableBalance', 0)))
                # 適配Bybit格式
                elif exchange == ExchangeEnum.BYBIT and 'result' in info:
                    result = info.get('result', {})
                    total_equity = Decimal(str(result.get('equity', 0)))
                    unrealized_pnl = Decimal(str(result.get('unrealised_pnl', 0)))
                    margin_used = Decimal(str(result.get('used_margin', 0)))
                    margin_free = Decimal(str(result.get('available_balance', 0)))
                
                
                # 構建並返回賬戶信息
                account_info = AccountInfo(
                    exchange=exchange,
                    balances=balances,
                    total_equity=total_equity,
                    unrealized_pnl=unrealized_pnl,
                    margin_used=margin_used,
                    margin_free=margin_free
                )
                
                return account_info
            
            # 使用 execute_exchange_operation 執行操作
            return await self.execute_exchange_operation(
                user, db, exchange, _operation, "get_account_info", 
                virtual_key_id=virtual_key_id  # 傳遞虛擬密鑰 ID
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"獲取賬戶信息失敗: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"獲取賬戶信息失敗: {str(e)}"
            )
    
    async def get_balance(
        self, 
        user: User, 
        db: Session, 
        exchange: ExchangeEnum, 
        asset: str
    ) -> Balance:
        """
        獲取用戶在特定交易所的特定資產餘額
        
        使用REST API獲取資產餘額
        
        Args:
            user: 用戶模型實例
            db: 數據庫會話
            exchange: 交易所枚舉值
            asset: 資產符號（如BTC, USDT等）
            
        Returns:
            Balance: 資產餘額信息
        """
        asset = asset.upper()  # 確保大寫
        
        # 直接使用REST API獲取餘額，移除WebSocket緩存相關代碼
        async def _operation(client):
            # 獲取賬戶餘額
            balance_data = await client.fetch_balance()
            
            # 檢查資產是否存在
            if asset not in balance_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"資產{asset}不存在或餘額為零"
                )
            
            # 轉換為餘額對象
            asset_data = balance_data[asset]
            balance = Balance(
                asset=asset,
                free=Decimal(str(asset_data.get('free', 0))),
                used=Decimal(str(asset_data.get('used', 0))),
                total=Decimal(str(asset_data.get('total', 0)))
            )
            
            return balance
        
        return await self.execute_exchange_operation(user, db, exchange, _operation, "get_balance", asset)
    
    async def place_spot_order(
        self, 
        user: User, 
        db: Session, 
        exchange: ExchangeEnum, 
        order: OrderRequest,
        virtual_key_id: str = None
    ) -> OrderInfo:
        """
        在現貨市場下單
        
        Args:
            user: 用戶模型實例
            db: 數據庫會話
            exchange: 交易所枚舉值
            order: 訂單請求數據
            virtual_key_id: 虛擬密鑰 ID（可選）
            
        Returns:
            OrderInfo: 訂單信息
        """
        logger.info(f"用戶 {user.id} 在 {exchange} 現貨市場下單: {order.dict()}")
        
        async def _operation(client):
            # 設置市場類型為現貨
            client.options['defaultType'] = 'spot'
            
            # 執行下單操作
            return await self._place_single_order(client, order)
        
        # 使用統一的操作執行方法
        return await self.execute_exchange_operation(
            user, db, exchange, _operation, "place_spot_order", 
            virtual_key_id=virtual_key_id  # 傳遞虛擬密鑰 ID
        )

    async def place_futures_order(
        self, 
        user: User, 
        db: Session, 
        exchange: ExchangeEnum, 
        order: OrderRequest,
        virtual_key_id: str = None
    ) -> OrderInfo:
        """
        在合約市場下單
        
        Args:
            user: 用戶模型實例
            db: 數據庫會話
            exchange: 交易所枚舉值
            order: 訂單請求數據
            virtual_key_id: 虛擬密鑰 ID（可選）
            
        Returns:
            OrderInfo: 訂單信息
        """
        logger.info(f"用戶 {user.id} 在 {exchange} 合約市場下單: {order.dict()}")
        
        async def _operation(client):
            # 設置市場類型為合約
            client.options['defaultType'] = 'future'
            
            # 執行下單操作
            return await self._place_single_order(client, order)
        
        # 使用統一的操作執行方法
        return await self.execute_exchange_operation(
            user, db, exchange, _operation, "place_futures_order",
            virtual_key_id=virtual_key_id  # 傳遞虛擬密鑰 ID
        )

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
        """獲取訂單歷史"""
        async def _operation(client):
            # 設置市場類型
            if order_type == 'spot':
                client.options['defaultType'] = 'spot'
            elif order_type == 'futures':
                client.options['defaultType'] = 'future'
            
            # 準備參數
            params = {}
            if start_time:
                params['since'] = int(start_time.timestamp() * 1000)
            if limit:
                params['limit'] = limit
                
            # 獲取訂單歷史
            if symbol:
                orders = await client.fetch_orders(symbol=symbol, params=params)
            else:
                # 注意：並非所有交易所都支持不指定symbol的查詢
                orders = []
                markets = await client.load_markets()
                # 獲取主要市場的訂單
                for market_symbol in list(markets.keys())[:10]:  # 限制查詢的市場數量
                    try:
                        symbol_orders = await client.fetch_orders(symbol=market_symbol, params=params)
                        orders.extend(symbol_orders)
                    except Exception as e:
                        logger.warning(f"獲取{market_symbol}訂單歷史失敗: {str(e)}")
            
            # 轉換為統一格式
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
        
        return await self.execute_exchange_operation(user, db, exchange, _operation, "get_order_history", symbol, order_type, start_time, end_time, limit)

    async def get_positions(
        self,
        user: User,
        db: Session,
        exchange: ExchangeEnum,
        symbol: Optional[str] = None
    ) -> List[Position]:
        """獲取當前持倉"""
        async def _operation(client):
            # 設置為期貨市場
            client.options['defaultType'] = 'future'
            
            # 獲取持倉
            positions_data = await client.fetch_positions(symbol)
            
            # 轉換為統一格式
            positions = []
            for pos in positions_data:
                if float(pos['contracts']) > 0:  # 只返回有持倉的
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
        
        return await self.execute_exchange_operation(user, db, exchange, _operation, "get_positions", symbol)

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
        取消訂單
        
        Args:
            user: 用戶模型實例
            db: 數據庫會話
            exchange: 交易所枚舉值
            order_id: 訂單ID
            symbol: 交易對
            order_type: 訂單類型 ('spot' 或 'futures')
            
        Returns:
            Dict: 取消結果
        """
        async def _operation(client):
            # 設置市場類型
            if order_type == 'spot':
                client.options['defaultType'] = 'spot'
            elif order_type == 'futures':
                client.options['defaultType'] = 'future'
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="訂單類型必須是 'spot' 或 'futures'"
                )
            
            # 取消訂單
            result = await client.cancel_order(id=order_id, symbol=symbol)
            
            return result
        
        return await self.execute_exchange_operation(user, db, exchange, _operation, "cancel_order", order_id, symbol, order_type)

    async def get_open_orders(
        self,
        user: User,
        db: Session,
        exchange: ExchangeEnum,
        symbol: Optional[str] = None,
        order_type: Optional[str] = None
    ) -> List[OrderInfo]:
        """
        獲取未成交訂單
        
        Args:
            user: 用戶模型實例
            db: 數據庫會話
            exchange: 交易所枚舉值
            symbol: 交易對，可選
            order_type: 訂單類型 ('spot' 或 'futures')，可選
            
        Returns:
            List[OrderInfo]: 未成交訂單列表
        """
        async def _operation(client):
            # 設置市場類型
            if order_type == 'spot':
                client.options['defaultType'] = 'spot'
            elif order_type == 'futures':
                client.options['defaultType'] = 'future'
            
            # 獲取未成交訂單
            open_orders = await client.fetch_open_orders(symbol=symbol)
            
            # 轉換為統一格式
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
        
        return await self.execute_exchange_operation(user, db, exchange, _operation, "get_open_orders", symbol, order_type)

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
        設置槓桿和保證金模式
        
        Args:
            user: 用戶模型實例
            db: 數據庫會話
            exchange: 交易所枚舉值
            symbol: 交易對
            leverage: 槓桿倍數
            margin_type: 保證金模式 ('isolated' 或 'cross')
            
        Returns:
            Dict: 設置結果
        """
        async def _operation(client):
            # 設置為期貨市場
            client.options['defaultType'] = 'future'
            
            # 驗證槓桿倍數
            if leverage < 1 or leverage > 125:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="槓桿倍數必須在1-125之間"
                )
            
            # 驗證保證金模式
            if margin_type not in ['isolated', 'cross']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="保證金模式必須是 'isolated' 或 'cross'"
                )
            
            # 設置槓桿倍數
            leverage_result = await client.set_leverage(leverage, symbol)
            
            # 設置保證金模式
            # 注意：不同交易所的API可能有所不同
            try:
                if exchange == ExchangeEnum.BINANCE:
                    margin_result = await client.set_margin_mode(margin_type, symbol)
                else:
                    # 針對其他交易所的處理
                    margin_result = {"margin_type": margin_type, "status": "success"}
            except Exception as e:
                logger.warning(f"設置保證金模式失敗: {str(e)}")
                margin_result = {"margin_type": margin_type, "status": "failed", "error": str(e)}
            
            return {
                "symbol": symbol,
                "leverage": leverage,
                "leverage_result": leverage_result,
                "margin_type": margin_type,
                "margin_result": margin_result
            }
        
        return await self.execute_exchange_operation(user, db, exchange, _operation, "set_leverage", symbol, leverage, margin_type)

    async def place_stop_order(
        self,
        user: User,
        db: Session,
        exchange: ExchangeEnum,
        order: StopOrder
    ) -> Dict[str, Any]:
        """
        下止盈止損訂單
        
        Args:
            user: 用戶模型實例
            db: 數據庫會話
            exchange: 交易所枚舉值
            order: 止盈止損訂單參數
            
        Returns:
            Dict: 下單結果
        """
        async def _operation(client):
            # 設置為期貨市場
            client.options['defaultType'] = 'future'
            
            # 準備參數
            symbol = order.symbol
            side = order.side.upper()  # 確保大寫
            quantity = float(order.quantity)
            stop_price = float(order.stop_price)
            params = {
                'stopPrice': stop_price,
                'workingType': order.working_type or 'MARK_PRICE',
                'reduceOnly': order.reduce_only or False,
                'closePosition': order.close_position or False
            }
            
            # 根據類型設置不同的參數
            order_type = order.type
            price = float(order.price) if order.price else None
            
            # 處理幣安期貨的持倉模式 (止盈止損訂單通常用於期貨)
            exchange_id = client.id
            if exchange_id == 'binance':
                try:
                    # 檢查賬戶是單向模式還是對沖模式
                    position_mode_info = await client.fapiPrivate_get_positionside_dual()
                    dual_side_position = position_mode_info.get('dualSidePosition', False)
                    
                    # 如果是對沖模式，需要指定持倉方向
                    if dual_side_position:
                        # 根據止盈止損訂單類型和方向確定持倉方向
                        # 這裡邏輯可能需要根據業務規則調整
                        side_lower = side.lower()
                        if side_lower == 'buy':
                            # 買單通常是做多倉位的止盈止損
                            params['positionSide'] = 'LONG'
                        else:
                            # 賣單通常是做空倉位的止盈止損
                            params['positionSide'] = 'SHORT'
                        
                        logger.info(f"賬戶使用對沖模式，為止盈止損訂單設置持倉方向: {params['positionSide']}")
                except Exception as e:
                    # 如果獲取持倉模式失敗，記錄錯誤但繼續嘗試下單
                    logger.warning(f"獲取持倉模式失敗，將使用默認參數: {str(e)}")
            
            # 下單
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
        
        return await self.execute_exchange_operation(user, db, exchange, _operation, "place_stop_order", order)
    
    async def batch_place_orders(
        self,
        user: User,
        db: Session,
        exchange: ExchangeEnum,
        batch_request: BatchOrderRequest
    ) -> List[Dict[str, Any]]:
        """
        批量下單
        
        Args:
            user: 用戶模型實例
            db: 數據庫會話
            exchange: 交易所枚舉值
            batch_request: 批量訂單請求
            
        Returns:
            List[Dict]: 批量下單結果
        """
        # 檢查訂單數量限制
        if len(batch_request.orders) > 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="批量下單最多支持5個訂單"
            )
            
        async def _batch_operation(client):
            # 設置市場類型
            if batch_request.order_type == 'spot':
                client.options['defaultType'] = 'spot'
            elif batch_request.order_type == 'futures':
                client.options['defaultType'] = 'future'
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="訂單類型必須是 'spot' 或 'futures'"
                )
            
            # 批量下單結果
            results = []
            
            # 逐個處理訂單
            for order in batch_request.orders:
                try:
                    # 根據訂單類型處理
                    if isinstance(order, StopOrder):
                        # 止盈止損訂單
                        result = await self._place_single_stop_order(client, order)
                    else:
                        # 普通訂單
                        result = await self._place_single_order(client, order)
                    
                    results.append({
                        "orderId": result['id'],
                        "symbol": result['symbol'],
                        "status": "NEW",
                        "message": "success"
                    })
                except Exception as e:
                    logger.error(f"批量下單中的單個訂單失敗: {str(e)}")
                    results.append({
                        "orderId": None,
                        "symbol": getattr(order, 'symbol', 'unknown'),
                        "status": "FAILED",
                        "message": str(e)
                    })
            
            return results
        
        return await self.execute_exchange_operation(user, db, exchange, _batch_operation, "batch_place_orders", batch_request)
    
    async def _place_single_order(
        self, 
        client: ccxt.Exchange, 
        order: OrderRequest
    ) -> Dict[str, Any]:
        """
        下單單個普通訂單的輔助方法
        
        Args:
            client: 交易所客戶端
            order: 訂單請求
            
        Returns:
            Dict: 訂單響應
        """
        # 準備訂單參數
        symbol = order.symbol
        side = order.side.value
        type = order.type.value
        amount = float(order.amount)
        
        # 處理價格
        params = {}
        if order.type == OrderType.LIMIT:
            if not order.price:
                raise ValueError("限價單必須指定價格")
            price = float(order.price)
        else:
            price = None
        
        # 添加可選參數
        if order.time_in_force:
            params['timeInForce'] = order.time_in_force
        if order.post_only:
            params['postOnly'] = True
        if order.reduce_only:
            params['reduceOnly'] = True
            
        # 處理幣安期貨的持倉模式
        if 'defaultType' in client.options and client.options['defaultType'] == 'future':
            # 只對期貨市場進行處理
            exchange_id = client.id
            if exchange_id == 'binance':
                try:
                    # 檢查賬戶是單向模式還是對沖模式
                    position_mode_info = await client.fapiPrivate_get_positionside_dual()
                    dual_side_position = position_mode_info.get('dualSidePosition', False)
                    
                    # 如果是對沖模式，需要指定持倉方向
                    if dual_side_position:
                        # 根據訂單方向確定持倉方向
                        if side == 'buy':
                            params['positionSide'] = 'LONG'
                        else:
                            params['positionSide'] = 'SHORT'
                        
                        logger.info(f"賬戶使用對沖模式，為{side}單設置持倉方向: {params['positionSide']}")
                except Exception as e:
                    # 如果獲取持倉模式失敗，記錄錯誤但繼續嘗試下單
                    logger.warning(f"獲取持倉模式失敗，將使用默認參數: {str(e)}")
        
        # 下單並返回結果
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
        下單單個止盈止損訂單的輔助方法
        
        Args:
            client: 交易所客戶端
            order: 止盈止損訂單
            
        Returns:
            Dict: 訂單響應
        """
        # 準備參數
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
        
        # 處理價格
        price = float(order.price) if order.price else None
        
        # 處理幣安期貨的持倉模式 (止盈止損訂單通常用於期貨)
        exchange_id = client.id
        if exchange_id == 'binance':
            try:
                # 檢查賬戶是單向模式還是對沖模式
                position_mode_info = await client.fapiPrivate_get_positionside_dual()
                dual_side_position = position_mode_info.get('dualSidePosition', False)
                
                # 如果是對沖模式，需要指定持倉方向
                if dual_side_position:
                    # 根據止盈止損訂單類型和方向確定持倉方向
                    # 這裡邏輯可能需要根據業務規則調整
                    side_lower = side.lower()
                    if side_lower == 'buy':
                        # 買單通常是做多倉位的止盈止損
                        params['positionSide'] = 'LONG'
                    else:
                        # 賣單通常是做空倉位的止盈止損
                        params['positionSide'] = 'SHORT'
                    
                    logger.info(f"賬戶使用對沖模式，為止盈止損訂單設置持倉方向: {params['positionSide']}")
            except Exception as e:
                # 如果獲取持倉模式失敗，記錄錯誤但繼續嘗試下單
                logger.warning(f"獲取持倉模式失敗，將使用默認參數: {str(e)}")
        
        # 下單並返回結果
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
        批量取消訂單
        
        Args:
            user: 用戶模型實例
            db: 數據庫會話
            exchange: 交易所枚舉值
            batch_request: 批量取消訂單請求
            
        Returns:
            List[Dict]: 批量取消結果
        """
        # 檢查訂單數量限制
        if len(batch_request.order_ids) > 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="批量取消最多支持10個訂單"
            )
        
        async def _batch_operation(client):
            # 設置市場類型
            if batch_request.order_type == 'spot':
                client.options['defaultType'] = 'spot'
            elif batch_request.order_type == 'futures':
                client.options['defaultType'] = 'future'
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="訂單類型必須是 'spot' 或 'futures'"
                )
            
            # 批量取消結果
            results = []
            
            # 不同交易所的批量取消處理
            if exchange == ExchangeEnum.BINANCE and hasattr(client, 'cancel_orders'):
                # Binance支持批量取消
                try:
                    response = await client.cancel_orders(batch_request.order_ids, batch_request.symbol)
                    
                    # 處理響應
                    for order in response:
                        results.append({
                            "orderId": order['id'],
                            "status": "CANCELED",
                            "message": "success"
                        })
                except Exception as e:
                    logger.error(f"批量取消訂單失敗: {str(e)}")
                    # 如果批量取消失敗，返回所有訂單都失敗的信息
                    for order_id in batch_request.order_ids:
                        results.append({
                            "orderId": order_id,
                            "status": "FAILED",
                            "message": str(e)
                        })
            else:
                # 其他交易所逐個取消
                for order_id in batch_request.order_ids:
                    try:
                        response = await client.cancel_order(id=order_id, symbol=batch_request.symbol)
                        results.append({
                            "orderId": order_id,
                            "status": "CANCELED",
                            "message": "success"
                        })
                    except Exception as e:
                        logger.error(f"取消訂單 {order_id} 失敗: {str(e)}")
                        results.append({
                            "orderId": order_id,
                            "status": "FAILED",
                            "message": str(e)
                        })
            
            return results
        
        return await self.execute_exchange_operation(user, db, exchange, _batch_operation, "batch_cancel_orders", batch_request)
    
    async def get_symbol_info(
        self,
        exchange: ExchangeEnum,
        symbol: Optional[str] = None
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        獲取交易對信息
        
        Args:
            exchange: 交易所枚舉值
            symbol: 交易對，可選
            
        Returns:
            Union[Dict, List[Dict]]: 單個或多個交易對信息
        """
        # 創建一個虛擬用戶和會話用於獲取公開市場數據
        # 這樣我們可以利用連接池，而不必每次創建新連接
        class VirtualUser:
            def __init__(self):
                self.id = 0  # 使用特殊ID 0 表示系統查詢
                
        class VirtualSession:
            def query(self, *args):
                return self
                
            def filter(self, *args):
                return self
                
            def first(self):
                # 返回一個虛擬的API密鑰記錄
                class ApiKeyRecord:
                    def __init__(self):
                        self.api_key = ""
                        self.api_secret = ""
                return ApiKeyRecord()
        
        try:
            virtual_user = VirtualUser()
            virtual_db = VirtualSession()
            
            # 使用execute_exchange_operation執行操作，這樣就能利用連接池
            async def _operation(client):
                # 加載市場
                await client.load_markets()
                
                if symbol:
                    # 獲取特定交易對信息
                    if symbol not in client.markets:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"交易對 {symbol} 不存在"
                        )
                    
                    market = client.markets[symbol]
                    result = self._format_symbol_info(market, exchange)
                else:
                    # 獲取所有交易對信息
                    results = []
                    for market_symbol, market in client.markets.items():
                        # 只處理活躍的現貨和永續合約
                        if market['active'] and (market['spot'] or market['swap']):
                            symbol_info = self._format_symbol_info(market, exchange)
                            results.append(symbol_info)
                    
                    result = results
                
                return result
                
            # 使用執行操作的通用方法，設置不重試
            return await self.execute_exchange_operation(virtual_user, virtual_db, exchange, _operation, "get_symbol_info", symbol)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"獲取交易對信息失敗: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"獲取交易對信息失敗: {str(e)}"
            )
    
    def _format_symbol_info(self, market: Dict[str, Any], exchange: ExchangeEnum) -> Dict[str, Any]:
        """
        格式化交易對信息
        
        Args:
            market: 市場數據
            exchange: 交易所枚舉值
            
        Returns:
            Dict: 格式化後的交易對信息
        """
        # 獲取精度信息
        precision = market.get('precision', {})
        price_precision = precision.get('price', 8)
        amount_precision = precision.get('amount', 8)
        
        # 獲取限制信息
        limits = market.get('limits', {})
        price_limits = limits.get('price', {})
        amount_limits = limits.get('amount', {})
        cost_limits = limits.get('cost', {})
        
        # 構建統一格式
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
        
        # 添加合約特有信息
        if market.get('linear') or market.get('inverse'):
            result["max_leverage"] = 125  # 默認值，實際應從交易所獲取
            result["margin_types"] = ["isolated", "cross"]
        
        return result
    
    def _get_supported_order_types(self, exchange: ExchangeEnum, market: Dict[str, Any]) -> List[str]:
        """獲取支持的訂單類型"""
        # 默認支持的訂單類型
        order_types = ["LIMIT", "MARKET"]
        
        # 根據交易所添加特殊訂單類型
        if exchange == ExchangeEnum.BINANCE:
            order_types.extend(["STOP_LOSS", "STOP_LOSS_LIMIT", "TAKE_PROFIT", "TAKE_PROFIT_LIMIT"])
        elif exchange == ExchangeEnum.BYBIT:
            order_types.extend(["STOP", "STOP_MARKET", "STOP_LIMIT"])
        
        return order_types
    
    def _get_supported_time_in_force(self, exchange: ExchangeEnum, market: Dict[str, Any]) -> List[str]:
        """獲取支持的時間有效性類型"""
        # 默認支持的時間有效性
        time_in_force = ["GTC"]
        
        # 根據交易所添加特殊類型
        if exchange in [ExchangeEnum.BINANCE, ExchangeEnum.BYBIT]:
            time_in_force.extend(["IOC", "FOK"])
        
        return time_in_force

    # 其他方法的代碼將在後續添加... 

    # 當應用關閉時需要清理所有連接
    async def cleanup(self):
        """清理所有交易所連接"""
        logger.info("正在關閉交易服務，清理所有連接...")
        
        # 清理REST API連接
        await self.connection_pool.cleanup_all()
        
        # 移除WebSocket連接清理代碼
        
        logger.info("交易服務已關閉")

    async def initialize_websocket_for_account_page(
        self, 
        user: User, 
        db: Session, 
        exchange: ExchangeEnum
    ) -> Dict[str, Any]:
        """
        為賬戶頁面初始化連接
        
        WebSocket功能已移除，此方法僅返回REST API狀態
        
        Args:
            user: 用戶模型實例
            db: 數據庫會話
            exchange: 交易所枚舉值
            
        Returns:
            Dict[str, Any]: 連接狀態信息
        """
        try:
            # 返回使用REST API狀態
            return {
                "success": True,
                "message": "使用REST API獲取帳戶數據",
                "exchange": exchange.value,
                "rest_api": True,
                "websocket": False
            }
        except Exception as e:
            logger.error(f"初始化連接失敗: {str(e)}")
            return {
                "success": False,
                "message": f"初始化連接失敗: {str(e)}",
                "exchange": exchange.value
            }

    def _calculate_position_value(self, position: Dict[str, Any], mark_price: float) -> float:
        """
        計算持倉價值
        
        Args:
            position: 持倉信息字典
            mark_price: 標記價格
                
        Returns:
            float: 持倉價值
        """
        # 使用Cython加速版本（如果可用）
        if CYTHON_ENABLED:
            return calculate_position_value(position, mark_price)
        
        # 否則使用原生Python實現
        position_amount = float(position.get("position_amount", 0))
        abs_position = abs(position_amount)
        
        # 計算持倉價值
        position_value = abs_position * mark_price
        
        return position_value
    
    def _calculate_margin_requirement(self, position: Dict[str, Any], 
                                    mark_price: float, 
                                    maintenance_margin_rate: float, 
                                    margin_type: str = "ISOLATED") -> Dict[str, float]:
        """
        計算保證金需求
        
        Args:
            position: 持倉信息字典
            mark_price: 標記價格
            maintenance_margin_rate: 維持保證金率
            margin_type: 保證金類型，可選 "ISOLATED" 或 "CROSS"
                
        Returns:
            Dict[str, float]: 包含保證金需求信息的字典
        """
        # 使用Cython加速版本（如果可用）
        if CYTHON_ENABLED:
            return calculate_margin_requirement(position, mark_price, maintenance_margin_rate, margin_type)
        
        # 否則使用原生Python實現
        position_amount = float(position.get("position_amount", 0))
        entry_price = float(position.get("entry_price", 0))
        isolated_wallet = float(position.get("isolated_wallet", 0))
        abs_position = abs(position_amount)
        
        # 計算持倉價值
        position_value = abs_position * mark_price
        
        # 計算未實現盈虧
        unrealized_pnl = 0.0
        if position_amount > 0:  # 多頭
            unrealized_pnl = abs_position * (mark_price - entry_price)
        elif position_amount < 0:  # 空頭
            unrealized_pnl = abs_position * (entry_price - mark_price)
        
        # 計算維持保證金
        maintenance_margin = position_value * maintenance_margin_rate
        
        # 計算保證金率
        margin_ratio = 0.0
        if margin_type == "ISOLATED":
            # 對於逐倉，保證金率 = (錢包餘額 + 未實現盈虧) / 維持保證金
            if maintenance_margin > 0:
                margin_ratio = (isolated_wallet + unrealized_pnl) / maintenance_margin
        else:  # CROSS
            # 對於全倉，需要考慮帳戶餘額，這裡簡化處理
            # 實際應用中需要傳入更多參數
            if maintenance_margin > 0:
                margin_ratio = (isolated_wallet + unrealized_pnl) / maintenance_margin
        
        # 返回計算結果
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
        計算清算價格
        
        Args:
            position_amount: 持倉數量
            entry_price: 開倉均價
            wallet_balance: 錢包餘額
            maintenance_margin_rate: 維持保證金率
            margin_type: 保證金類型
                
        Returns:
            float: 清算價格
        """
        # 如果沒有持倉，返回0
        if position_amount == 0:
            return 0.0
        
        abs_position = abs(position_amount)
        maintenance_amount = wallet_balance - abs_position * entry_price * maintenance_margin_rate
        liquidation_price = 0.0
        
        if position_amount > 0:  # 多頭
            # 對於多頭，清算價格 = (開倉價值 - 錢包餘額) / ((1 - 維持保證金率) * 持倉數量)
            if abs_position * (1 - maintenance_margin_rate) == 0:
                return 0.0  # 避免除以零
            liquidation_price = (abs_position * entry_price - wallet_balance) / (abs_position * (1 - maintenance_margin_rate))
        else:  # 空頭
            # 對於空頭，清算價格 = (開倉價值 + 錢包餘額) / ((1 + 維持保證金率) * 持倉數量)
            if abs_position * (1 + maintenance_margin_rate) == 0:
                return 0.0  # 避免除以零
            liquidation_price = (abs_position * entry_price + wallet_balance) / (abs_position * (1 + maintenance_margin_rate))
        
        # 確保清算價格為正數
        return max(0.0, liquidation_price)

    async def preheat_exchange_connection(
        self,
        user_id: int,
        exchange: ExchangeEnum,
        db: Session
    ) -> bool:
        """
        預熱交易所連接
        
        在用戶登入後調用此方法，預先初始化 CCXT 連接，以減少首次交易操作的延遲
        
        Args:
            user_id: 用戶ID
            exchange: 交易所枚舉
            db: 數據庫會話
            
        Returns:
            bool: 預熱是否成功
        """
        # 保存原始日誌級別
        ccxt_logger = logging.getLogger("ccxt")
        ccxt_base_logger = logging.getLogger("ccxt.base.exchange")
        original_ccxt_level = ccxt_logger.level
        original_ccxt_base_level = ccxt_base_logger.level
        
        try:
            # 臨時提高 CCXT 日誌級別，減少詳細日誌
            ccxt_logger.setLevel(logging.WARNING)
            ccxt_base_logger.setLevel(logging.WARNING)
            
            logger.info(f"開始預熱用戶 {user_id} 的 {exchange.value} 連接")
            
            # 檢查連接池中是否已有此用戶的連接
            pool_key = f"{user_id}:{exchange.value}"
            has_connection = False
            
            # 使用連接池的方法檢查是否已有連接
            async with exchange_pool.lock:
                has_connection = pool_key in exchange_pool.pools
            
            if has_connection:
                logger.info(f"用戶 {user_id} 的 {exchange.value} 連接已存在於連接池中")
                
                # 檢查連接健康狀態
                is_healthy = await exchange_pool.check_client_health_with_cache(user_id, exchange, db)
                if not is_healthy:
                    logger.warning(f"用戶 {user_id} 的 {exchange.value} 連接不健康，嘗試刷新")
                    await exchange_pool.refresh_client_with_cache(user_id, exchange, db)
                    logger.info(f"用戶 {user_id} 的 {exchange.value} 連接已刷新")
                
                return True
            
            # 如果沒有連接，創建新連接
            logger.info(f"用戶 {user_id} 的 {exchange.value} 連接不存在，嘗試創建")
            
            # 從數據庫獲取 User 對象
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                logger.error(f"找不到用戶 ID {user_id}")
                return False
            
            # 使用 User 對象調用 _get_exchange_client_for_user 方法
            client = await self._get_exchange_client_for_user(user, db, exchange)
            
            # 執行一個輕量級的操作來驗證連接
            await client.fetch_time()
            
            logger.info(f"用戶 {user_id} 的 {exchange.value} 連接預熱成功")
            return True
        except Exception as e:
            logger.error(f"預熱 {exchange.value} 連接失敗: {str(e)}")
            return False
        finally:
            # 恢復原始日誌級別
            ccxt_logger.setLevel(original_ccxt_level)
            ccxt_base_logger.setLevel(original_ccxt_base_level)