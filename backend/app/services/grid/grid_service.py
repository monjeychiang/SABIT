import asyncio
import logging
import json
from decimal import Decimal
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.db.models.grid import GridStrategy, GridOrder
from backend.app.db.models.user import User
from backend.app.services.grid.grid_strategy_factory import GridStrategyFactory

logger = logging.getLogger(__name__)

class GridService:
    """
    網格交易服務
    
    處理網格策略的創建、啟動、停止、監控等操作。
    此服務是網格交易功能的核心處理單元。
    """
    
    def __init__(self, db: Session):
        """
        初始化網格服務
        
        Args:
            db: 數據庫會話
        """
        self.db = db
    
    async def create_strategy(self, grid_config: Dict[str, Any], user_id: int, exchange: str) -> GridStrategy:
        """
        創建網格策略
        
        Args:
            grid_config: 網格策略配置
            user_id: 用戶ID
            exchange: 交易所
            
        Returns:
            創建的網格策略對象
            
        Raises:
            Exception: 創建失敗時拋出異常
        """
        try:
            # 創建網格策略記錄
            grid_strategy = GridStrategy(
                user_id=user_id,
                exchange=exchange,
                symbol=grid_config["symbol"],
                grid_type=grid_config["grid_type"],
                strategy_type=grid_config["strategy_type"],
                market_type="FUTURES",  # 目前只支援合約
                upper_price=grid_config["upper_price"],
                lower_price=grid_config["lower_price"],
                grid_number=grid_config["grid_number"],
                total_investment=grid_config["total_investment"],
                leverage=grid_config.get("leverage", 1),
                stop_loss=grid_config.get("stop_loss"),
                take_profit=grid_config.get("take_profit"),
                profit_collection=grid_config.get("profit_collection", False),
                status="CREATED",
                # 交易對規則緩存
                symbol_price_precision=grid_config.get("symbol_price_precision"),
                symbol_qty_precision=grid_config.get("symbol_qty_precision"),
                symbol_min_qty=grid_config.get("symbol_min_qty"),
                symbol_min_notional=grid_config.get("symbol_min_notional"),
                symbol_max_leverage=grid_config.get("symbol_max_leverage")
            )
            
            self.db.add(grid_strategy)
            self.db.commit()
            self.db.refresh(grid_strategy)
            
            logger.info(f"創建網格策略成功，ID: {grid_strategy.id}, 用戶: {user_id}")
            
            return grid_strategy
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"創建網格策略失敗: {str(e)}")
            raise
    
    async def start_strategy(self, 
                           grid_id: int, 
                           user_id: int, 
                           exchange: str, 
                           client: Any, 
                           current_price: Decimal
                          ) -> bool:
        """
        啟動網格策略
        
        Args:
            grid_id: 網格策略ID
            user_id: 用戶ID
            exchange: 交易所
            client: 交易所客戶端
            current_price: 當前市場價格
            
        Returns:
            啟動是否成功
            
        Raises:
            Exception: 啟動失敗時拋出異常
        """
        try:
            # 獲取網格策略
            grid_strategy = self.db.query(GridStrategy).filter(
                GridStrategy.id == grid_id,
                GridStrategy.user_id == user_id,
                GridStrategy.exchange == exchange
            ).first()
            
            if not grid_strategy:
                logger.error(f"未找到網格策略: {grid_id}")
                return False
                
            if grid_strategy.status == "RUNNING":
                logger.warning(f"網格策略 {grid_id} 已經在運行中")
                return True
            
            # 創建策略實例
            strategy = GridStrategyFactory.create_strategy(grid_strategy, self.db)
            
            # 計算初始訂單
            initial_orders = strategy.calculate_initial_orders(current_price)
            
            # 下單並記錄
            for order in initial_orders:
                # 通過客戶端下單
                order_result = await client.place_order(
                    symbol=grid_strategy.symbol,
                    side=order["side"],
                    order_type="LIMIT",
                    quantity=float(order["quantity"]),
                    price=float(order["price"]),
                    time_in_force="GTC"
                )
                
                # 保存訂單信息
                grid_order = GridOrder(
                    strategy_id=grid_strategy.id,
                    exchange=grid_strategy.exchange,
                    symbol=grid_strategy.symbol,
                    grid_index=order["grid_index"],
                    price=order["price"],
                    quantity=order["quantity"],
                    side=order["side"],
                    order_id=order_result.get("orderId"),
                    status="PLACED",
                    created_at=datetime.utcnow()
                )
                
                self.db.add(grid_order)
            
            # 更新策略狀態
            grid_strategy.status = "RUNNING"
            grid_strategy.updated_at = datetime.utcnow()
            
            self.db.commit()
            logger.info(f"啟動網格策略成功，ID: {grid_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"啟動網格策略失敗: {str(e)}")
            raise
    
    async def stop_strategy(self, grid_id: int, user_id: int, exchange: str, client: Any) -> bool:
        """
        停止網格策略
        
        Args:
            grid_id: 網格策略ID
            user_id: 用戶ID
            exchange: 交易所
            client: 交易所客戶端
            
        Returns:
            停止是否成功
            
        Raises:
            Exception: 停止失敗時拋出異常
        """
        try:
            # 獲取網格策略
            grid_strategy = self.db.query(GridStrategy).filter(
                GridStrategy.id == grid_id,
                GridStrategy.user_id == user_id,
                GridStrategy.exchange == exchange
            ).first()
            
            if not grid_strategy:
                logger.error(f"未找到網格策略: {grid_id}")
                return False
                
            if grid_strategy.status != "RUNNING":
                logger.warning(f"網格策略 {grid_id} 不在運行中")
                return True
            
            # 取消所有未成交訂單
            active_orders = self.db.query(GridOrder).filter(
                GridOrder.strategy_id == grid_id,
                GridOrder.status == "PLACED"
            ).all()
            
            for order in active_orders:
                try:
                    # 通過客戶端取消訂單
                    await client.cancel_order(
                        symbol=order.symbol,
                        order_id=order.order_id
                    )
                    
                    # 更新訂單狀態
                    order.status = "CANCELED"
                    order.updated_at = datetime.utcnow()
                    
                except Exception as e:
                    logger.error(f"取消訂單失敗, order_id={order.order_id}: {str(e)}")
            
            # 更新策略狀態
            grid_strategy.status = "STOPPED"
            grid_strategy.updated_at = datetime.utcnow()
            
            self.db.commit()
            logger.info(f"停止網格策略成功，ID: {grid_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"停止網格策略失敗: {str(e)}")
            raise
    
    async def handle_order_filled(self, order_id: str, client: Any) -> Optional[GridStrategy]:
        """
        處理訂單成交事件
        
        當網格訂單成交時，自動創建下一個訂單
        
        Args:
            order_id: 成交訂單ID
            client: 交易所客戶端
            
        Returns:
            對應的網格策略對象，如果找不到或處理失敗則返回None
        """
        try:
            # 查找對應的網格訂單
            grid_order = self.db.query(GridOrder).filter(
                GridOrder.order_id == order_id,
                GridOrder.status == "PLACED"
            ).first()
            
            if not grid_order:
                return None
                
            # 獲取網格策略
            grid_strategy = self.db.query(GridStrategy).filter(
                GridStrategy.id == grid_order.strategy_id,
                GridStrategy.status == "RUNNING"
            ).first()
            
            if not grid_strategy:
                return None
            
            # 更新訂單狀態
            grid_order.status = "FILLED"
            grid_order.filled_at = datetime.utcnow()
            
            # 計算利潤
            profit = self.calculate_order_profit(grid_order)
            grid_order.profit = profit
            
            # 創建策略實例
            strategy = GridStrategyFactory.create_strategy(grid_strategy, self.db)
            
            # 計算下一個訂單
            next_order = strategy.calculate_next_order(grid_order)
            
            if next_order:
                # 通過客戶端下單
                order_result = await client.place_order(
                    symbol=grid_strategy.symbol,
                    side=next_order["side"],
                    order_type="LIMIT",
                    quantity=float(next_order["quantity"]),
                    price=float(next_order["price"]),
                    time_in_force="GTC"
                )
                
                # 保存新訂單
                new_order = GridOrder(
                    strategy_id=grid_strategy.id,
                    exchange=grid_strategy.exchange,
                    symbol=grid_strategy.symbol,
                    grid_index=next_order["grid_index"],
                    price=next_order["price"],
                    quantity=next_order["quantity"],
                    side=next_order["side"],
                    order_id=order_result.get("orderId"),
                    status="PLACED",
                    created_at=datetime.utcnow()
                )
                
                self.db.add(new_order)
                
                # 更新策略時間
                grid_strategy.updated_at = datetime.utcnow()
            
            self.db.commit()
            logger.info(f"處理訂單成交成功，order_id: {order_id}")
            
            return grid_strategy
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"處理訂單成交事件失敗: {str(e)}")
            return None
    
    def calculate_order_profit(self, order: GridOrder) -> Decimal:
        """
        計算訂單利潤
        
        對於賣單，計算與上一個買單之間的價差收益
        
        Args:
            order: 訂單對象
            
        Returns:
            訂單利潤
        """
        # 對於賣單，我們需要找到對應的買單計算利潤
        if order.side == "SELL":
            # 查找相同網格策略中成交的買單
            buy_orders = self.db.query(GridOrder).filter(
                GridOrder.strategy_id == order.strategy_id,
                GridOrder.side == "BUY",
                GridOrder.status == "FILLED"
            ).order_by(desc(GridOrder.filled_at)).all()
            
            if buy_orders:
                # 使用最近成交的買單計算利潤
                buy_order = buy_orders[0]
                price_diff = Decimal(str(order.price)) - Decimal(str(buy_order.price))
                profit = price_diff * Decimal(str(order.quantity))
                return profit
        
        # 買單或無法計算時返回0
        return Decimal("0") 