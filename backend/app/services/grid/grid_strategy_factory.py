"""
網格策略工廠類別
用於創建不同類型的網格策略
整合了市場方向預期和網格分佈方式兩個維度
"""

import logging
from typing import Optional, Type
from decimal import Decimal
from sqlalchemy.orm import Session

from backend.app.db.models.grid import GridStrategy

logger = logging.getLogger(__name__)


class GridStrategyBase:
    """網格策略基類"""
    
    def __init__(self, strategy: GridStrategy, db: Session):
        self.strategy = strategy
        self.db = db
        
    def is_stop_loss_triggered(self, current_price: Decimal) -> bool:
        """
        檢查是否觸發止損
        
        Args:
            current_price: 當前價格
            
        Returns:
            是否觸發止損
        """
        if self.strategy.stop_loss is None:
            return False
        
        # 多頭倉位的止損判斷
        if self.strategy.strategy_type == "LONG" and current_price <= self.strategy.stop_loss:
            return True
        
        # 空頭倉位的止損判斷
        if self.strategy.strategy_type == "SHORT" and current_price >= self.strategy.stop_loss:
            return True
            
        return False
        
    def is_take_profit_triggered(self, current_price: Decimal) -> bool:
        """
        檢查是否觸發止盈
        
        Args:
            current_price: 當前價格
            
        Returns:
            是否觸發止盈
        """
        if self.strategy.take_profit is None:
            return False
            
        # 多頭倉位的止盈判斷
        if self.strategy.strategy_type == "LONG" and current_price >= self.strategy.take_profit:
            return True
            
        # 空頭倉位的止盈判斷
        if self.strategy.strategy_type == "SHORT" and current_price <= self.strategy.take_profit:
            return True
            
        return False


# 根據網格分佈方式的策略類
class ArithmeticGridMixin:
    """算術網格策略 - 網格間價差相等"""
    
    def calculate_grid_prices(self):
        """
        計算等差網格價格點位
        """
        upper_price = self.strategy.upper_price
        lower_price = self.strategy.lower_price
        grid_number = self.strategy.grid_number
        
        # 等差數列，每個網格價差相等
        grid_interval = (upper_price - lower_price) / grid_number
        grid_prices = []
        
        for i in range(grid_number + 1):
            price = lower_price + grid_interval * i
            grid_prices.append(price)
            
        return grid_prices


class GeometricGridMixin:
    """幾何網格策略 - 網格間價差按比例變化"""
    
    def calculate_grid_prices(self):
        """
        計算等比網格價格點位
        """
        upper_price = self.strategy.upper_price
        lower_price = self.strategy.lower_price
        grid_number = self.strategy.grid_number
        
        # 等比數列，比例相等
        price_ratio = (upper_price / lower_price) ** (1 / grid_number)
        grid_prices = []
        
        for i in range(grid_number + 1):
            price = lower_price * (price_ratio ** i)
            grid_prices.append(price)
            
        return grid_prices


# 根據市場方向預期的策略類
class NeutralGridStrategy(GridStrategyBase):
    """中性網格策略 - 不預期市場方向"""
    
    def __init__(self, strategy: GridStrategy, db: Session):
        super().__init__(strategy, db)


class BullishGridStrategy(GridStrategyBase):
    """看漲網格策略 - 預期市場上漲"""
    
    def __init__(self, strategy: GridStrategy, db: Session):
        super().__init__(strategy, db)


class BearishGridStrategy(GridStrategyBase):
    """看跌網格策略 - 預期市場下跌"""
    
    def __init__(self, strategy: GridStrategy, db: Session):
        super().__init__(strategy, db)


# 組合不同維度的具體策略類
class ArithmeticNeutralGridStrategy(NeutralGridStrategy, ArithmeticGridMixin):
    """等差中性網格策略"""
    pass


class GeometricNeutralGridStrategy(NeutralGridStrategy, GeometricGridMixin):
    """等比中性網格策略"""
    pass


class ArithmeticBullishGridStrategy(BullishGridStrategy, ArithmeticGridMixin):
    """等差看漲網格策略"""
    pass


class GeometricBullishGridStrategy(BullishGridStrategy, GeometricGridMixin):
    """等比看漲網格策略"""
    pass


class ArithmeticBearishGridStrategy(BearishGridStrategy, ArithmeticGridMixin):
    """等差看跌網格策略"""
    pass


class GeometricBearishGridStrategy(BearishGridStrategy, GeometricGridMixin):
    """等比看跌網格策略"""
    pass


class GridStrategyFactory:
    """
    整合後的網格策略工廠
    綜合考慮市場方向預期和網格分佈方式兩個維度
    """
    
    # 策略映射表：用於根據 strategy_type 和 grid_type 選擇對應的策略類
    STRATEGY_MAP = {
        "NEUTRAL": {
            "ARITHMETIC": ArithmeticNeutralGridStrategy,
            "GEOMETRIC": GeometricNeutralGridStrategy
        },
        "BULLISH": {
            "ARITHMETIC": ArithmeticBullishGridStrategy,
            "GEOMETRIC": GeometricBullishGridStrategy
        },
        "BEARISH": {
            "ARITHMETIC": ArithmeticBearishGridStrategy,
            "GEOMETRIC": GeometricBearishGridStrategy
        }
    }
    
    @staticmethod
    def create_strategy(strategy: GridStrategy, db: Session) -> GridStrategyBase:
        """
        創建網格策略實例
        
        Args:
            strategy: 網格策略資訊
            db: 資料庫會話
            
        Returns:
            網格策略實例
            
        Raises:
            ValueError: 不支持的策略類型或網格類型
        """
        strategy_type = strategy.strategy_type
        grid_type = strategy.grid_type
        
        # 檢查策略類型是否支持
        if strategy_type not in GridStrategyFactory.STRATEGY_MAP:
            # 默認使用中性策略
            logger.warning(f"不支持的策略類型: {strategy_type}，使用默認的中性策略")
            strategy_type = "NEUTRAL"
        
        # 檢查網格類型是否支持
        grid_strategies = GridStrategyFactory.STRATEGY_MAP[strategy_type]
        if grid_type not in grid_strategies:
            # 默認使用算術網格
            logger.warning(f"不支持的網格類型: {grid_type}，使用默認的算術網格")
            grid_type = "ARITHMETIC"
        
        # 創建策略實例
        strategy_class = GridStrategyFactory.STRATEGY_MAP[strategy_type][grid_type]
        return strategy_class(strategy, db) 