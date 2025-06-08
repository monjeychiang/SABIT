from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List, Union
from decimal import Decimal
from datetime import datetime
from enum import Enum

class ExchangeEnum(str, Enum):
    """交易所枚舉"""
    BINANCE = "binance"
    okx = "okx"
    BYBIT = "bybit"
    GATE = "gate"
    MEXC = "mexc"

class OrderType(str, Enum):
    """訂單類型"""
    LIMIT = "limit"
    MARKET = "market"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    STOP_LOSS_LIMIT = "stop_loss_limit"
    TAKE_PROFIT_LIMIT = "take_profit_limit"

class OrderSide(str, Enum):
    """訂單方向"""
    BUY = "buy"
    SELL = "sell"

class PositionSide(str, Enum):
    """持倉方向"""
    LONG = "long"      # 做多
    SHORT = "short"    # 做空
    BOTH = "both"      # 雙向持倉

class TimeInForce(str, Enum):
    """訂單有效期"""
    GTC = "GTC"  # Good Till Cancel
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill

class OrderStatus(str, Enum):
    """訂單狀態"""
    OPEN = "open"
    CLOSED = "closed"
    CANCELED = "canceled"
    EXPIRED = "expired"
    REJECTED = "rejected"

class OrderRequest(BaseModel):
    """訂單請求"""
    symbol: str
    side: OrderSide
    type: OrderType
    amount: Decimal
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    leverage: Optional[int] = None
    reduce_only: bool = False
    post_only: bool = False
    time_in_force: Optional[str] = None

class OrderInfo(BaseModel):
    """訂單信息"""
    id: str
    exchange: ExchangeEnum
    symbol: str
    side: OrderSide
    type: OrderType
    status: OrderStatus
    amount: Decimal
    filled: Decimal
    remaining: Decimal
    price: Optional[Decimal]
    average_price: Optional[Decimal]
    cost: Optional[Decimal]
    fee: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: Optional[datetime]
    closed_at: Optional[datetime]
    raw_data: Dict[str, Any]

class Position(BaseModel):
    """持倉信息"""
    symbol: str
    side: OrderSide
    size: Decimal
    entry_price: Decimal
    mark_price: Decimal
    liquidation_price: Optional[Decimal]
    unrealized_pnl: Decimal
    leverage: int
    margin_type: str
    raw_data: Dict[str, Any]

class Balance(BaseModel):
    """資產餘額"""
    asset: str
    free: Decimal
    used: Decimal
    total: Decimal

class AccountInfo(BaseModel):
    """賬戶信息"""
    exchange: ExchangeEnum
    balances: List[Balance]
    total_equity: Decimal
    unrealized_pnl: Decimal
    margin_used: Decimal
    margin_free: Decimal

# API響應模型
class BaseResponse(BaseModel):
    """基礎響應模型"""
    success: bool
    message: Optional[str] = None
    exchange: Optional[ExchangeEnum] = None

class AccountInfoResponse(BaseResponse):
    """賬戶信息響應"""
    data: Optional[AccountInfo] = None

class BalanceResponse(BaseResponse):
    """餘額信息響應"""
    data: Optional[Balance] = None
    asset: Optional[str] = None

class OrderResponse(BaseResponse):
    """訂單響應"""
    data: Optional[OrderInfo] = None
    order_type: Optional[str] = None  # spot or futures

class TradeHistoryResponse(BaseResponse):
    """交易歷史響應"""
    data: Optional[List[OrderInfo]] = None
    total: Optional[int] = None
    page: Optional[int] = None
    per_page: Optional[int] = None

class PositionResponse(BaseResponse):
    """持倉信息響應"""
    data: Optional[List[Position]] = None

# 槓桿設置相關
class LeverageUpdate(BaseModel):
    """更新槓桿倍數請求"""
    symbol: str
    leverage: int = Field(..., gt=0, le=125, description="槓桿倍數，範圍 1-125")
    margin_type: str = Field(..., pattern="^(isolated|cross)$", description="保證金模式：isolated(逐倉) 或 cross(全倉)")

class LeverageResponse(BaseResponse):
    """槓桿設置響應"""
    data: Optional[Dict[str, Any]] = Field(None, example={
        "symbol": "BTCUSDT",
        "leverage": 10,
        "margin_type": "isolated",
        "max_notional_value": "1000000"
    })

# 止盈止損相關
class StopOrder(BaseModel):
    """止盈止損訂單"""
    symbol: str
    side: str = Field(..., pattern="^(BUY|SELL)$")
    quantity: Decimal
    stop_price: Decimal = Field(..., description="觸發價格")
    price: Optional[Decimal] = Field(None, description="限價單的執行價格，市價單可不填")
    type: str = Field(..., pattern="^(STOP_LOSS|STOP_LOSS_LIMIT|TAKE_PROFIT|TAKE_PROFIT_LIMIT)$")
    time_in_force: Optional[str] = Field("GTC", pattern="^(GTC|IOC|FOK)$")
    working_type: Optional[str] = Field("MARK_PRICE", pattern="^(MARK_PRICE|CONTRACT_PRICE)$")
    reduce_only: Optional[bool] = Field(False)
    close_position: Optional[bool] = Field(False)

class StopOrderResponse(BaseResponse):
    """止盈止損訂單響應"""
    data: Optional[Dict[str, Any]] = Field(None, example={
        "orderId": "123456789",
        "symbol": "BTCUSDT",
        "type": "STOP_LOSS",
        "side": "SELL",
        "quantity": "0.01",
        "stopPrice": "50000",
        "price": "49900",
        "status": "NEW",
        "createTime": 1678234567890
    })

# 批量訂單相關
class BatchOrderRequest(BaseModel):
    """批量訂單請求"""
    orders: List[Union[OrderRequest, StopOrder]] = Field(..., max_items=5, description="最多5個訂單")
    order_type: str = Field(..., pattern="^(spot|futures)$", description="訂單類型：spot(現貨) 或 futures(合約)")

class BatchOrderResponse(BaseResponse):
    """批量訂單響應"""
    data: Optional[List[Dict[str, Any]]] = Field(None, example=[
        {
            "orderId": "123456789",
            "symbol": "BTCUSDT",
            "status": "NEW",
            "message": "success"
        },
        {
            "orderId": None,
            "symbol": "ETHUSDT",
            "status": "FAILED",
            "message": "insufficient balance"
        }
    ])

class BatchCancelRequest(BaseModel):
    """批量取消訂單請求"""
    symbol: str
    order_ids: List[str] = Field(..., max_items=10, description="最多10個訂單ID")
    order_type: str = Field(..., pattern="^(spot|futures)$")

class BatchCancelResponse(BaseResponse):
    """批量取消訂單響應"""
    data: Optional[List[Dict[str, Any]]] = Field(None, example=[
        {
            "orderId": "123456789",
            "status": "CANCELED",
            "message": "success"
        },
        {
            "orderId": "987654321",
            "status": "FAILED",
            "message": "order filled"
        }
    ])

# 交易對信息相關
class SymbolInfo(BaseModel):
    """交易對信息"""
    symbol: str
    status: str = Field(..., pattern="^(TRADING|BREAK|HALT)$")
    base_asset: str
    quote_asset: str
    price_precision: int
    quantity_precision: int
    min_price: Decimal
    max_price: Decimal
    min_quantity: Decimal
    min_notional: Decimal
    max_leverage: Optional[int] = None
    margin_types: Optional[List[str]] = None
    order_types: List[str]
    time_in_force: List[str]

class SymbolInfoResponse(BaseResponse):
    """交易對信息響應"""
    data: Optional[Union[SymbolInfo, List[SymbolInfo]]] = None

# 添加缺少的響應類型
class OrderBookItem(BaseModel):
    """訂單簿項目"""
    price: Decimal
    amount: Decimal

class OrderBook(BaseModel):
    """訂單簿數據"""
    symbol: str
    bids: List[OrderBookItem]
    asks: List[OrderBookItem]
    timestamp: int

class OrderBookResponse(BaseResponse):
    """訂單簿響應"""
    data: Optional[OrderBook] = None

class MarketTrade(BaseModel):
    """市場成交數據"""
    id: str
    price: Decimal
    amount: Decimal
    cost: Decimal
    side: str
    timestamp: int

class MarketTradesResponse(BaseResponse):
    """市場成交響應"""
    data: Optional[List[MarketTrade]] = None

class Ticker(BaseModel):
    """行情數據"""
    symbol: str
    last: Decimal
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    volume: Optional[Decimal] = None
    change: Optional[Decimal] = None
    percentage: Optional[Decimal] = None
    timestamp: int

class TickerResponse(BaseResponse):
    """行情響應"""
    data: Optional[Ticker] = None 