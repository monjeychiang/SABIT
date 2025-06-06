from decimal import Decimal
from typing import List, Dict, Any, Optional

from backend.app.services.grid.strategy_base import GridStrategyBase
from backend.app.db.models.grid import GridOrder

class NeutralGridStrategy(GridStrategyBase):
    """
    中性網格策略
    
    針對震盪行情的網格交易策略，在價格區間內均勻分布買賣訂單，
    適合預期價格在一定區間內波動的市場情況。
    """
    
    def calculate_grid_prices(self) -> List[Decimal]:
        """
        計算網格價格點
        
        根據網格類型（等距或等比）計算每個網格點的價格
        
        Returns:
            網格價格點列表
        """
        upper_price = Decimal(str(self.grid_config.upper_price))
        lower_price = Decimal(str(self.grid_config.lower_price))
        grid_number = self.grid_config.grid_number
        
        grid_prices = []
        
        if self.grid_config.grid_type == "ARITHMETIC":
            # 等距網格
            step = (upper_price - lower_price) / grid_number
            for i in range(grid_number + 1):
                price = lower_price + i * step
                grid_prices.append(self.round_price(price))
        else:  # GEOMETRIC
            # 等比網格
            ratio = (upper_price / lower_price) ** (Decimal("1.0") / grid_number)
            for i in range(grid_number + 1):
                price = lower_price * (ratio ** i)
                grid_prices.append(self.round_price(price))
        
        return grid_prices
    
    def calculate_initial_orders(self, current_price: Decimal) -> List[Dict[str, Any]]:
        """
        計算初始下單計劃
        
        根據當前價格和網格配置計算初始的訂單列表，
        上方放置賣單，下方放置買單
        
        Args:
            current_price: 當前市場價格
            
        Returns:
            初始訂單列表，每個訂單包含價格、數量、方向等信息
        """
        grid_prices = self.calculate_grid_prices()
        per_grid_investment = Decimal(str(self.grid_config.total_investment)) / self.grid_config.grid_number
        orders = []
        
        # 找出當前價格所在的網格位置
        current_grid_index = -1
        for i in range(len(grid_prices) - 1):
            if grid_prices[i] <= current_price < grid_prices[i+1]:
                current_grid_index = i
                break
        
        if current_grid_index == -1:
            # 如果價格不在網格範圍內，選擇最近的位置
            if current_price < grid_prices[0]:
                current_grid_index = 0
            else:
                current_grid_index = len(grid_prices) - 2
        
        # 上方掛賣單
        for i in range(current_grid_index + 1, len(grid_prices)):
            price = grid_prices[i]
            quantity = per_grid_investment / price
            price, quantity = self.ensure_min_requirements(price, quantity)
            
            orders.append({
                "price": price,
                "quantity": self.round_quantity(quantity),
                "side": "SELL",
                "grid_index": i
            })
        
        # 下方掛買單
        for i in range(current_grid_index, -1, -1):
            price = grid_prices[i]
            quantity = per_grid_investment / price
            price, quantity = self.ensure_min_requirements(price, quantity)
            
            orders.append({
                "price": price,
                "quantity": self.round_quantity(quantity),
                "side": "BUY",
                "grid_index": i
            })
        
        return orders
    
    def calculate_next_order(self, filled_order: GridOrder) -> Optional[Dict[str, Any]]:
        """
        計算下一個訂單（當前訂單成交後）
        
        當一個網格訂單成交後，計算應該創建的下一個訂單
        
        Args:
            filled_order: 已成交的訂單對象
            
        Returns:
            下一個訂單的參數，包含價格、數量、方向等信息，如果超出網格範圍則返回None
        """
        # 獲取網格價格
        grid_prices = self.calculate_grid_prices()
        
        # 獲取網格信息
        if filled_order.side == "BUY":
            # 買單成交後，在上一格創建賣單
            next_grid_index = filled_order.grid_index + 1
            
            # 檢查是否已經超出網格上限
            if next_grid_index >= len(grid_prices):
                return None
                
            next_price = grid_prices[next_grid_index]
            next_side = "SELL"
            
        else:  # SELL
            # 賣單成交後，在下一格創建買單
            next_grid_index = filled_order.grid_index - 1
            
            # 檢查是否已經超出網格下限
            if next_grid_index < 0:
                return None
                
            next_price = grid_prices[next_grid_index]
            next_side = "BUY"
        
        # 計算訂單數量
        per_grid_investment = Decimal(str(self.grid_config.total_investment)) / self.grid_config.grid_number
        quantity = per_grid_investment / next_price
        
        # 格式化並確保最小訂單要求
        next_price, quantity = self.ensure_min_requirements(next_price, quantity)
        
        return {
            "grid_index": next_grid_index,
            "price": next_price,
            "quantity": self.round_quantity(quantity),
            "side": next_side
        }
    
    def is_stop_loss_triggered(self, current_price: Decimal) -> bool:
        """
        檢查是否觸發止損
        
        當價格低於止損價時觸發止損
        
        Args:
            current_price: 當前市場價格
            
        Returns:
            是否觸發止損
        """
        if not self.grid_config.stop_loss:
            return False
        
        # 對於中性網格，當價格低於止損價時觸發
        return current_price <= Decimal(str(self.grid_config.stop_loss))
    
    def is_take_profit_triggered(self, current_price: Decimal) -> bool:
        """
        檢查是否觸發止盈
        
        當價格高於止盈價時觸發止盈
        
        Args:
            current_price: 當前市場價格
            
        Returns:
            是否觸發止盈
        """
        if not self.grid_config.take_profit:
            return False
        
        # 對於中性網格，當價格高於止盈價時觸發
        return current_price >= Decimal(str(self.grid_config.take_profit)) 