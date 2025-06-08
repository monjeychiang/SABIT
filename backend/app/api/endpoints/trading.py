from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Body, Query, Path
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator
from decimal import Decimal
import logging
from datetime import datetime

from ...db.database import get_db
from ...db.models import User
from ...core.security import oauth2_scheme, get_current_user, get_current_active_user
from ...schemas.trading import (
    OrderRequest, OrderResponse, AccountInfoResponse, BalanceResponse,
    TradeHistoryResponse, PositionResponse, ExchangeEnum, LeverageResponse,
    LeverageUpdate, StopOrderResponse, StopOrder, BatchOrderResponse,
    BatchOrderRequest, BatchCancelResponse, BatchCancelRequest, SymbolInfoResponse,
    BaseResponse, OrderType, OrderSide, TimeInForce
)
from ...services.trading import TradingService
from ...core.api_key_manager import ApiKeyManager
from ...schemas.common import StandardResponse

router = APIRouter()
logger = logging.getLogger(__name__)
trading_service = TradingService()

# 獲取支持的交易所列表
@router.get("/exchanges", response_model=List[str])
async def get_supported_exchanges() -> Any:
    """
    獲取系統支持的交易所列表
    """
    return [e.value for e in ExchangeEnum]

# 獲取賬戶信息
@router.get("/account/{exchange}", response_model=AccountInfoResponse)
async def get_account_info(
    exchange: ExchangeEnum,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    獲取指定交易所的賬戶信息
    """
    try:
        account_info = await trading_service.get_account_info(current_user, db, exchange)
        return {
            "success": True,
            "data": account_info,
            "exchange": exchange
        }
    except Exception as e:
        logger.error(f"獲取賬戶信息失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"獲取{exchange}賬戶信息失敗"
        )

# 獲取資產餘額
@router.get("/balance/{exchange}/{asset}", response_model=BalanceResponse)
async def get_asset_balance(
    exchange: ExchangeEnum,
    asset: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    獲取指定交易所特定資產的餘額
    """
    try:
        balance = await trading_service.get_balance(current_user, db, exchange, asset)
        return {
            "success": True,
            "data": balance,
            "exchange": exchange,
            "asset": asset
        }
    except Exception as e:
        logger.error(f"獲取資產餘額失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"獲取{exchange} {asset}餘額失敗"
        )

# 現貨下單
@router.post("/spot/order/{exchange}", response_model=OrderResponse)
async def place_spot_order(
    exchange: ExchangeEnum,
    order: OrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    在指定交易所下現貨訂單
    """
    try:
        result = await trading_service.place_spot_order(
            current_user, db, exchange, order
        )
        return {
            "success": True,
            "data": result,
            "exchange": exchange,
            "order_type": "spot"
        }
    except Exception as e:
        logger.error(f"現貨下單失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{exchange}現貨下單失敗"
        )

# 合約下單
@router.post("/futures/order/{exchange}", response_model=OrderResponse)
async def place_futures_order(
    exchange: ExchangeEnum,
    order: OrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    在指定交易所下合約訂單
    """
    try:
        result = await trading_service.place_futures_order(
            current_user, db, exchange, order
        )
        return {
            "success": True,
            "data": result,
            "exchange": exchange,
            "order_type": "futures"
        }
    except Exception as e:
        logger.error(f"合約下單失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{exchange}合約下單失敗"
        )

# 獲取訂單歷史
@router.get("/orders/history/{exchange}", response_model=TradeHistoryResponse)
async def get_order_history(
    exchange: ExchangeEnum,
    symbol: Optional[str] = None,
    order_type: Optional[str] = None,  # spot or futures
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    獲取指定交易所的訂單歷史
    """
    try:
        history = await trading_service.get_order_history(
            current_user, db, exchange, symbol, order_type,
            start_time, end_time, limit
        )
        return {
            "success": True,
            "data": history,
            "exchange": exchange
        }
    except Exception as e:
        logger.error(f"獲取訂單歷史失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"獲取{exchange}訂單歷史失敗"
        )

# 獲取當前持倉
@router.get("/positions/{exchange}", response_model=PositionResponse)
async def get_positions(
    exchange: ExchangeEnum,
    symbol: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    獲取指定交易所的當前持倉
    """
    try:
        positions = await trading_service.get_positions(
            current_user, db, exchange, symbol
        )
        return {
            "success": True,
            "data": positions,
            "exchange": exchange
        }
    except Exception as e:
        logger.error(f"獲取持倉信息失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"獲取{exchange}持倉信息失敗"
        )

# 取消訂單
@router.delete("/order/{exchange}/{order_id}", response_model=OrderResponse)
async def cancel_order(
    exchange: ExchangeEnum,
    order_id: str,
    symbol: str,
    order_type: str,  # spot or futures
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    取消指定交易所的訂單
    """
    try:
        result = await trading_service.cancel_order(
            current_user, db, exchange, order_id, symbol, order_type
        )
        return {
            "success": True,
            "data": result,
            "exchange": exchange
        }
    except Exception as e:
        logger.error(f"取消訂單失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"取消{exchange}訂單失敗"
        )

# 獲取未成交訂單
@router.get("/open-orders/{exchange}", response_model=OrderResponse)
async def get_open_orders(
    exchange: ExchangeEnum,
    symbol: Optional[str] = None,
    order_type: Optional[str] = None,  # spot or futures
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    獲取指定交易所的未成交訂單
    """
    try:
        orders = await trading_service.get_open_orders(
            current_user, db, exchange, symbol, order_type
        )
        return {
            "success": True,
            "data": orders,
            "exchange": exchange
        }
    except Exception as e:
        logger.error(f"獲取未成交訂單失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"獲取{exchange}未成交訂單失敗"
        )

# 設置槓桿
@router.post("/leverage/{exchange}", response_model=LeverageResponse)
async def set_leverage(
    exchange: ExchangeEnum,
    leverage_data: LeverageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    設置槓桿倍數和保證金模式
    """
    try:
        result = await trading_service.set_leverage(
            current_user, db, exchange,
            leverage_data.symbol,
            leverage_data.leverage,
            leverage_data.margin_type
        )
        return {
            "success": True,
            "data": result,
            "exchange": exchange
        }
    except Exception as e:
        logger.error(f"設置槓桿失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"設置槓桿失敗: {str(e)}"
        )

# 下止盈止損訂單
@router.post("/stop-order/{exchange}", response_model=StopOrderResponse)
async def place_stop_order(
    exchange: ExchangeEnum,
    order: StopOrder,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    下止盈止損訂單
    """
    try:
        result = await trading_service.place_stop_order(
            current_user, db, exchange, order
        )
        return {
            "success": True,
            "data": result,
            "exchange": exchange
        }
    except Exception as e:
        logger.error(f"下止盈止損訂單失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"下止盈止損訂單失敗: {str(e)}"
        )

# 批量下單
@router.post("/batch-orders/{exchange}", response_model=BatchOrderResponse)
async def batch_place_orders(
    exchange: ExchangeEnum,
    batch_request: BatchOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    批量下單（最多5個訂單）
    """
    try:
        results = await trading_service.batch_place_orders(
            current_user, db, exchange, batch_request
        )
        return {
            "success": True,
            "data": results,
            "exchange": exchange
        }
    except Exception as e:
        logger.error(f"批量下單失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量下單失敗: {str(e)}"
        )

# 批量取消訂單
@router.post("/batch-cancel/{exchange}", response_model=BatchCancelResponse)
async def batch_cancel_orders(
    exchange: ExchangeEnum,
    batch_request: BatchCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    批量取消訂單（最多10個訂單）
    """
    try:
        results = await trading_service.batch_cancel_orders(
            current_user, db, exchange, batch_request
        )
        return {
            "success": True,
            "data": results,
            "exchange": exchange
        }
    except Exception as e:
        logger.error(f"批量取消訂單失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量取消訂單失敗: {str(e)}"
        )

# 獲取交易對信息
@router.get("/symbols/{exchange}", response_model=SymbolInfoResponse)
async def get_symbol_info(
    exchange: ExchangeEnum,
    symbol: Optional[str] = None
) -> Any:
    """
    獲取交易對信息
    """
    try:
        result = await trading_service.get_symbol_info(exchange, symbol)
        return {
            "success": True,
            "data": result,
            "exchange": exchange
        }
    except Exception as e:
        logger.error(f"獲取交易對信息失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"獲取交易對信息失敗: {str(e)}"
        )

@router.post("/system/connection-pool-stats", tags=["system"])
async def get_connection_pool_stats(
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    獲取連接池統計信息
    
    僅限管理員使用，用於監控系統性能和連接使用情況
    """
    # 檢查用戶是否是管理員
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理員可以訪問此接口"
        )
        
    try:
        # 獲取連接池統計信息
        stats = trading_service.connection_pool.get_stats()
        
        return {
            "success": True,
            "data": {
                "active_connections": stats["active_connections"],
                "stats": stats["stats"],
                "rate_limits": stats.get("rate_limits", {}),
                "pools": stats["pools"]
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"獲取連接池統計信息失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"獲取連接池統計信息失敗: {str(e)}"
        )

@router.post("/initialize/account-page/{exchange}")
async def initialize_account_page_websocket(
    exchange: ExchangeEnum,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    WebSocket連接已被移除 - 改為僅使用REST API
    
    此端點仍然保留以保持與前端的兼容性
    """
    try:
        return {
            "success": True,
            "message": f"使用REST API獲取{exchange.value}帳戶數據",
            "exchange": exchange.value,
            "rest_api": True
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"初始化連接失敗: {str(e)}"
        )

# 添加虛擬密鑰支持
class VirtualKeyOrderRequest(BaseModel):
    """使用虛擬密鑰的訂單請求"""
    virtual_key_id: str = Field(..., description="虛擬密鑰 ID")
    order: OrderRequest = Field(..., description="訂單詳情")

@router.post("/virtual-trade", response_model=OrderResponse)
async def place_order_with_virtual_key(
    request: VirtualKeyOrderRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """使用虛擬密鑰下單接口"""
    try:
        # 檢查虛擬密鑰是否存在並屬於當前用戶
        api_key_manager = ApiKeyManager()
        virtual_key_exists = await api_key_manager.check_virtual_key_exists(
            db=db,
            user_id=current_user.id,
            virtual_key_id=request.virtual_key_id
        )
        
        if not virtual_key_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"找不到虛擬密鑰 {request.virtual_key_id} 或該密鑰不屬於當前用戶"
            )
        
        trading_service = TradingService()
        
        # 根據訂單類型決定使用哪個方法
        if request.order.type in [OrderType.LIMIT, OrderType.MARKET]:
            result = await trading_service.place_spot_order(
                user=current_user,
                db=db,
                exchange=request.order.exchange,
                order=request.order,
                virtual_key_id=request.virtual_key_id
            )
        else:
            result = await trading_service.place_futures_order(
                user=current_user,
                db=db,
                exchange=request.order.exchange,
                order=request.order,
                virtual_key_id=request.virtual_key_id
            )
        
        return {
            "success": True,
            "message": "訂單已提交",
            "order_id": result.get("id") or result.get("order_id"),
            "details": result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"使用虛擬密鑰下單失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"下單失敗: {str(e)}"
        )

# 預熱 CCXT 連接的端點
@router.post("/preheat", response_model=StandardResponse)
async def preheat_ccxt_connection(
    exchange_data: Dict[str, str] = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    預熱 CCXT 連接
    
    在用戶登入後調用此端點，預先初始化 CCXT 連接，以減少首次交易操作的延遲
    
    - **exchange**: 交易所名稱 (binance, okx, bybit, gate, mexc)
    """
    try:
        # 獲取請求中的交易所參數
        exchange_name = exchange_data.get("exchange", "binance").lower()
        
        # 將字符串轉換為 ExchangeEnum
        try:
            exchange = ExchangeEnum(exchange_name)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的交易所: {exchange_name}"
            )
        
        # 使用交易服務預熱連接
        result = await trading_service.preheat_exchange_connection(
            user_id=current_user.id,
            exchange=exchange,
            db=db
        )
        
        # 返回預熱結果
        return {
            "status": "success",
            "message": f"{exchange.value} 連接預熱成功",
            "data": {
                "exchange": exchange.value,
                "connected": result
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"預熱 CCXT 連接失敗: {str(e)}"
        ) 