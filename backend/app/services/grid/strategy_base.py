from abc import ABC, abstractmethod
from decimal import Decimal
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session

from backend.app.db.models.grid import GridStrategy, GridOrder

class GridStrategyBase(ABC):
    """網格策略的抽象基類"""
    
    def __init__(self, grid_config: GridStrategy, db: Session = None):
        """
        初始化網格策略基類
        
        Args:
            grid_config: 網格策略配置對象
            db: 數據庫會話
        """
        self.grid_config = grid_config
        self.db = db
        
    @abstractmethod
    def calculate_grid_prices(self) -> List[Decimal]:
        """
        計算網格價格點
        
        根據網格策略參數計算每個網格點的價格
        
        Returns:
            網格價格點列表
        """
        pass
        
    @abstractmethod
    def calculate_initial_orders(self, current_price: Decimal) -> List[Dict[str, Any]]:
        """
        計算初始下單計劃
        
        根據當前價格和網格配置計算初始的訂單列表
        
        Args:
            current_price: 當前市場價格
            
        Returns:
            初始訂單列表，每個訂單包含價格、數量、方向等信息
        """
        pass
        
    @abstractmethod
    def calculate_next_order(self, filled_order: GridOrder) -> Dict[str, Any]:
        """
        計算下一個訂單（當前訂單成交後）
        
        當一個網格訂單成交後，計算應該創建的下一個訂單
        
        Args:
            filled_order: 已成交的訂單對象
            
        Returns:
            下一個訂單的參數，包含價格、數量、方向等信息
        """
        pass
        
    @abstractmethod
    def is_stop_loss_triggered(self, current_price: Decimal) -> bool:
        """
        檢查是否觸發止損
        
        根據當前價格檢查是否應該觸發止損
        
        Args:
            current_price: 當前市場價格
            
        Returns:
            是否觸發止損
        """
        pass
        
    @abstractmethod
    def is_take_profit_triggered(self, current_price: Decimal) -> bool:
        """
        檢查是否觸發止盈
        
        根據當前價格檢查是否應該觸發止盈
        
        Args:
            current_price: 當前市場價格
            
        Returns:
            是否觸發止盈
        """
        pass
        
    def round_price(self, price: Decimal) -> Decimal:
        """
        依照交易對精度格式化價格
        
        Args:
            price: 原始價格
            
        Returns:
            按照精度格式化後的價格
        """
        precision = self.grid_config.symbol_price_precision
        if precision is None:
            return price
        factor = Decimal("10") ** precision
        return Decimal(round(float(price) * factor) / factor)
        
    def round_quantity(self, quantity: Decimal) -> Decimal:
        """
        依照交易對精度格式化數量
        
        Args:
            quantity: 原始數量
            
        Returns:
            按照精度格式化後的數量
        """
        precision = self.grid_config.symbol_qty_precision
        if precision is None:
            return quantity
        factor = Decimal("10") ** precision
        return Decimal(round(float(quantity) * factor) / factor)
        
    def ensure_min_requirements(self, price: Decimal, quantity: Decimal) -> Tuple[Decimal, Decimal]:
        """
        確保滿足最小訂單要求
        
        檢查訂單是否滿足交易所的最小訂單要求，並進行調整
        
        Args:
            price: 訂單價格
            quantity: 訂單數量
            
        Returns:
            調整後的價格和數量
        """
        min_qty = Decimal(str(self.grid_config.symbol_min_qty or "0"))
        min_notional = Decimal(str(self.grid_config.symbol_min_notional or "0"))
        
        if quantity < min_qty:
            quantity = min_qty
            
        if quantity * price < min_notional:
            quantity = self.round_quantity(min_notional / price)
            
        return price, quantity 