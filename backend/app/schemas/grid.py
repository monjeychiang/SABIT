from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, validator, model_validator
from decimal import Decimal
from datetime import datetime

# 請求模式
class GridCreateRequest(BaseModel):
    """網格交易策略創建請求"""
    symbol: str = Field(..., description="交易對名稱，如 BTCUSDT")
    grid_type: str = Field(..., description="網格類型：ARITHMETIC (等距網格) 或 GEOMETRIC (等比網格)")
    strategy_type: str = Field("NEUTRAL", description="策略類型：NEUTRAL (中性), BULLISH (看漲), BEARISH (看跌)")
    upper_price: float = Field(..., description="網格上限價格")
    lower_price: float = Field(..., description="網格下限價格")
    grid_number: int = Field(..., description="網格數量，一般為5-50")
    total_investment: float = Field(..., description="總投資金額（USDT）")
    leverage: int = Field(1, description="槓桿倍數")
    stop_loss: Optional[float] = Field(None, description="止損價格")
    take_profit: Optional[float] = Field(None, description="止盈價格")
    profit_collection: bool = Field(False, description="是否回收利潤")
    
    @validator('grid_type')
    def validate_grid_type(cls, v):
        if v not in ["ARITHMETIC", "GEOMETRIC"]:
            raise ValueError('grid_type 必須是 ARITHMETIC 或 GEOMETRIC')
        return v
    
    @validator('strategy_type')
    def validate_strategy_type(cls, v):
        if v not in ["NEUTRAL", "BULLISH", "BEARISH"]:
            raise ValueError('strategy_type 必須是 NEUTRAL, BULLISH 或 BEARISH')
        return v
    
    @validator('grid_number')
    def validate_grid_number(cls, v):
        if v < 2 or v > 100:
            raise ValueError('grid_number 必須在 2-100 之間')
        return v
    
    @validator('leverage')
    def validate_leverage(cls, v):
        if v < 1 or v > 125:
            raise ValueError('leverage 必須在 1-125 之間')
        return v
    
    @model_validator(mode='after')
    def validate_prices(self):
        upper = self.upper_price
        lower = self.lower_price
        if upper is not None and lower is not None:
            if lower >= upper:
                raise ValueError('lower_price 必須小於 upper_price')
            
            # 檢查網格價差是否過小
            min_price_diff_percent = 0.001  # 0.1% 最小價差
            price_diff_percent = (upper - lower) / lower
            if price_diff_percent < min_price_diff_percent:
                raise ValueError(f'價格範圍過小，至少需要 {min_price_diff_percent*100}% 的價格差')
                
        # 檢查止盈止損
        stop_loss = self.stop_loss
        take_profit = self.take_profit
        
        if stop_loss is not None and lower is not None:
            if stop_loss >= lower:
                raise ValueError('stop_loss 必須小於 lower_price')
                
        if take_profit is not None and upper is not None:
            if take_profit <= upper:
                raise ValueError('take_profit 必須大於 upper_price')
                
        return self


class GridUpdateRequest(BaseModel):
    """網格交易策略更新請求"""
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    profit_collection: Optional[bool] = None
    status: Optional[str] = None
    
    @validator('status')
    def validate_status(cls, v):
        if v not in ["RUNNING", "STOPPED", "FINISHED"]:
            raise ValueError('status 必須是 RUNNING, STOPPED 或 FINISHED')
        return v


# 響應模式
class GridStrategy(BaseModel):
    """網格交易策略模型"""
    id: int
    user_id: int
    exchange: str
    symbol: str
    grid_type: str
    strategy_type: str
    market_type: str
    upper_price: float
    lower_price: float
    grid_number: int
    total_investment: float
    per_grid_amount: Optional[float] = None
    leverage: Optional[int] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    profit_collection: bool
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


class GridOrder(BaseModel):
    """網格訂單模型"""
    id: int
    strategy_id: int
    exchange: str
    symbol: str
    grid_index: int
    price: float
    quantity: float
    side: str
    order_id: Optional[str] = None
    status: str
    created_at: datetime
    filled_at: Optional[datetime] = None
    profit: Optional[float] = None
    
    class Config:
        orm_mode = True


class GridResponse(BaseModel):
    """網格交易通用響應"""
    success: bool
    message: str
    grid_id: Optional[int] = None
    error: Optional[str] = None


class GridDetailResponse(BaseModel):
    """網格策略詳情響應"""
    strategy: GridStrategy
    orders: List[GridOrder]


class GridPerformanceResponse(BaseModel):
    """網格策略績效響應"""
    grid_id: int
    total_profit: float
    completed_trades: int
    win_rate: float
    avg_holding_time: Optional[float] = None
    roi: float  # 投資回報率
    annualized_roi: Optional[float] = None  # 年化投資回報率
    details: Dict[str, Any] 