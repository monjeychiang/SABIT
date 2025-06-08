import asyncio
import logging
from typing import Any, List, Optional, Dict
from decimal import Decimal
import time

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ...db.database import get_db
from ...core.security import get_current_active_user
from backend.app.db.models.user import User
from backend.app.db.models.grid import GridStrategy, GridOrder
from backend.app.schemas.grid import (
    GridCreateRequest, GridResponse, GridDetailResponse, 
    GridUpdateRequest, GridOrder as GridOrderSchema, 
    GridStrategy as GridStrategySchema
)
from backend.app.services.grid.grid_service import GridService
from backend.app.services.grid.grid_strategy_factory import GridStrategyFactory
from backend.utils.exchange_connection_manager import exchange_connection_manager
from backend.app.api.endpoints.settings import get_user_api_keys
from backend.app.services.market_data import MarketDataService

router = APIRouter()
logger = logging.getLogger(__name__)

# 網格策略監控任務
grid_monitor_tasks = {}  # {grid_id: asyncio.Task}


@router.post("/grid/create/{exchange}", response_model=GridResponse)
async def create_grid_strategy(
    exchange: str,
    grid_request: GridCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    創建網格交易策略
    
    根據提供的參數創建一個新的網格交易策略，但不會立即啟動。
    使用交易所連接管理器獲取連接，確保與其他模塊共享同一WebSocket連接。
    """
    user_id = current_user.id
    
    # 檢查API密鑰
    api_key_data = await get_user_api_keys(current_user, db)
    if exchange not in api_key_data:
        logger.warning(f"未找到交易所API密鑰 - user:{user_id}, exchange:{exchange}")
        raise HTTPException(status_code=400, detail="未找到對應交易所的API密鑰")
    
    # 使用連接管理器獲取連接
    try:
        # 獲取交易所連接
        client, is_new = await exchange_connection_manager.get_connection(user_id, exchange, db)
        
        if not client or not client.is_connected():
            logger.error(f"無法獲取交易所連接 - user:{user_id}, exchange:{exchange}")
            raise HTTPException(status_code=500, detail="無法連接到交易所")
        
        # 獲取交易對信息
        exchange_info = await client.get_exchange_info()
        symbol_info = next((s for s in exchange_info["symbols"] if s["symbol"] == grid_request.symbol), None)
        
        if not symbol_info:
            logger.warning(f"未找到交易對信息 - user:{user_id}, symbol:{grid_request.symbol}")
            raise HTTPException(status_code=400, detail=f"未找到交易對 {grid_request.symbol} 的信息")
        
        # 解析規則
        price_precision = symbol_info["pricePrecision"]
        qty_precision = symbol_info["quantityPrecision"]
        filters = {f["filterType"]: f for f in symbol_info["filters"]}
        
        min_qty = float(filters["LOT_SIZE"]["minQty"])
        min_notional = float(filters["MIN_NOTIONAL"]["notional"])
        max_leverage = int(symbol_info.get("leverageFilter", {}).get("maxLeverage", 125))
        
        # 獲取交易所費率
        fee_info = await client.get_fee_info(grid_request.symbol)
        maker_fee = float(fee_info["maker"])
        taker_fee = float(fee_info["taker"])
        
        logger.info(f"成功獲取交易對規則 - user:{user_id}, symbol:{grid_request.symbol}, "
                   f"price_precision:{price_precision}, qty_precision:{qty_precision}, "
                   f"min_qty:{min_qty}, min_notional:{min_notional}, max_leverage:{max_leverage}, "
                   f"maker_fee:{maker_fee}, taker_fee:{taker_fee}")
        
    except Exception as e:
        logger.error(f"獲取交易對規則失敗: {str(e)} - user:{user_id}, symbol:{grid_request.symbol}")
        raise HTTPException(status_code=500, detail=f"獲取交易對規則失敗: {str(e)}")
    
    # 創建網格服務
    grid_service = GridService(db)
    
    # 創建網格策略
    grid_config = {
        "symbol": grid_request.symbol,
        "grid_type": grid_request.grid_type,
        "strategy_type": grid_request.strategy_type,
        "upper_price": grid_request.upper_price,
        "lower_price": grid_request.lower_price,
        "grid_number": grid_request.grid_number,
        "total_investment": grid_request.total_investment,
        "leverage": grid_request.leverage,
        "stop_loss": grid_request.stop_loss,
        "take_profit": grid_request.take_profit,
        "profit_collection": grid_request.profit_collection,
        # 交易對規則
        "symbol_price_precision": price_precision,
        "symbol_qty_precision": qty_precision,
        "symbol_min_qty": min_qty,
        "symbol_min_notional": min_notional,
        "symbol_max_leverage": max_leverage,
        # 交易所費率
        "maker_fee": maker_fee,
        "taker_fee": taker_fee
    }
    
    try:
        grid_strategy = await grid_service.create_strategy(grid_config, user_id, exchange)
        logger.info(f"成功創建網格策略 - user:{user_id}, grid_id:{grid_strategy.id}, symbol:{grid_request.symbol}")
        
        return {
            "success": True,
            "message": "網格策略已創建",
            "grid_id": grid_strategy.id
        }
    except Exception as e:
        logger.error(f"創建網格策略失敗: {str(e)} - user:{user_id}, symbol:{grid_request.symbol}")
        raise HTTPException(status_code=500, detail=f"創建網格策略失敗: {str(e)}")


@router.post("/grid/start/{exchange}/{grid_id}", response_model=GridResponse)
async def start_grid_strategy(
    exchange: str,
    grid_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    啟動網格交易策略
    
    啟動現有的網格交易策略，開始執行交易
    
    使用交易所連接管理器獲取連接，確保與其他模塊共享同一WebSocket連接
    """
    user_id = current_user.id
    
    try:
        # 檢查策略是否存在且屬於當前用戶
        grid = db.query(GridStrategy).filter(
            GridStrategy.id == grid_id, 
            GridStrategy.user_id == user_id,
            GridStrategy.exchange == exchange
        ).first()
        
        if not grid:
            logger.warning(f"無法找到網格策略 - user:{user_id}, grid_id:{grid_id}")
            raise HTTPException(status_code=404, detail="網格策略不存在")
            
        if grid.status == "RUNNING":
            logger.info(f"策略已經在運行中 - user:{user_id}, grid_id:{grid_id}")
            return {
                "message": "策略已經在運行中",
                "success": True
            }
            
        # 獲取當前市場價格
        # 理想情況下這應該從市場數據服務中獲取，這裡簡單示例
        current_price = Decimal("0")
        
        try:
            # 使用連接管理器獲取客戶端
            client, is_new = await exchange_connection_manager.get_connection(user_id, exchange, db)
            
            if not client or not client.is_connected():
                logger.error(f"無法獲取交易所連接 - user:{user_id}, exchange:{exchange}")
                raise HTTPException(status_code=500, detail="無法連接到交易所")
                
            # 在這裡通過API獲取當前價格
            # 例如: 
            # 獲取賬戶信息，可能包含持倉信息和當前價格
            account_data = await exchange_connection_manager.get_account_data(user_id, exchange, db)
            
            # 嘗試從持倉或最新成交價中獲取價格
            for position in account_data.get("positions", []):
                if position.get("symbol") == grid.symbol:
                    current_price = Decimal(str(position.get("markPrice", 0)))
                    break
                    
            # 如果無法從持倉中獲取價格，則需要另外獲取市場數據
            if current_price == 0:
                # 此處應實現獲取最新市場價格的邏輯
                # 暫時使用策略中的定義價格範圍中點作為替代
                current_price = (Decimal(str(grid.upper_price)) + Decimal(str(grid.lower_price))) / Decimal("2")
            
            logger.info(f"獲取當前市場價格: {current_price} - user:{user_id}, grid_id:{grid_id}")
            
        except Exception as e:
            logger.error(f"獲取市場價格失敗: {str(e)} - user:{user_id}, grid_id:{grid_id}")
            raise HTTPException(status_code=500, detail=f"獲取市場價格失敗: {str(e)}")
            
        # 啟動策略
        grid_service = GridService(db)
        success = await grid_service.start_strategy(grid_id, user_id, exchange, client, current_price)
        
        if not success:
            logger.error(f"啟動網格策略失敗 - user:{user_id}, grid_id:{grid_id}")
            raise HTTPException(status_code=500, detail="啟動網格策略失敗")
        
        # 啟動監控任務
        await start_grid_monitor(grid_id, user_id, exchange, db)
        
        return {
            "message": "成功啟動網格策略",
            "success": True
        }
        
    except Exception as e:
        logger.error(f"啟動網格策略時出錯: {str(e)} - user:{user_id}, grid_id:{grid_id}")
        raise HTTPException(status_code=500, detail=f"啟動策略失敗: {str(e)}")


@router.post("/grid/stop/{exchange}/{grid_id}", response_model=GridResponse)
async def stop_grid_strategy(
    exchange: str,
    grid_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    停止網格交易策略
    
    停止正在運行的網格交易策略，取消所有未成交訂單
    
    使用交易所連接管理器獲取連接，確保與其他模塊共享同一WebSocket連接
    """
    user_id = current_user.id
    
    try:
        # 檢查策略是否存在且屬於當前用戶
        grid = db.query(GridStrategy).filter(
            GridStrategy.id == grid_id, 
            GridStrategy.user_id == user_id,
            GridStrategy.exchange == exchange
        ).first()
        
        if not grid:
            logger.warning(f"無法找到網格策略 - user:{user_id}, grid_id:{grid_id}")
            raise HTTPException(status_code=404, detail="網格策略不存在")
            
        if grid.status != "RUNNING":
            logger.info(f"策略未運行，無需停止 - user:{user_id}, grid_id:{grid_id}")
            return {
                "message": "策略未運行",
                "success": True
            }
        
        try:
            # 使用連接管理器獲取客戶端
            client, is_new = await exchange_connection_manager.get_connection(user_id, exchange, db)
            
            if not client or not client.is_connected():
                logger.error(f"無法獲取交易所連接 - user:{user_id}, exchange:{exchange}")
                raise HTTPException(status_code=500, detail="無法連接到交易所")
                
        except Exception as e:
            logger.error(f"獲取交易所連接失敗: {str(e)} - user:{user_id}, grid_id:{grid_id}")
            raise HTTPException(status_code=500, detail=f"無法連接到交易所: {str(e)}")
            
        # 停止策略
        grid_service = GridService(db)
        success = await grid_service.stop_strategy(grid_id, user_id, exchange, client)
        
        if not success:
            logger.error(f"停止網格策略失敗 - user:{user_id}, grid_id:{grid_id}")
            raise HTTPException(status_code=500, detail="停止網格策略失敗")
        
        # 停止監控任務
        await stop_grid_monitor(grid_id)
        
        return {
            "message": "成功停止網格策略",
            "success": True
        }
        
    except Exception as e:
        logger.error(f"停止網格策略時出錯: {str(e)} - user:{user_id}, grid_id:{grid_id}")
        raise HTTPException(status_code=500, detail=f"停止策略失敗: {str(e)}")


@router.get("/grid/list/{exchange}", response_model=List[GridStrategySchema])
async def list_grid_strategies(
    exchange: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    獲取用戶的網格策略列表
    """
    grid_strategies = db.query(GridStrategy).filter(
        GridStrategy.user_id == current_user.id,
        GridStrategy.exchange == exchange
    ).all()
    
    return grid_strategies


@router.get("/grid/detail/{exchange}/{grid_id}", response_model=GridDetailResponse)
async def get_grid_strategy_detail(
    exchange: str,
    grid_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    獲取網格策略的詳細信息
    """
    grid_strategy = db.query(GridStrategy).filter(
        GridStrategy.id == grid_id,
        GridStrategy.user_id == current_user.id,
        GridStrategy.exchange == exchange
    ).first()
    
    if not grid_strategy:
        raise HTTPException(status_code=404, detail="未找到指定的網格策略")
    
    # 獲取網格訂單
    grid_orders = db.query(GridOrder).filter(
        GridOrder.strategy_id == grid_id
    ).all()
    
    return {
        "strategy": grid_strategy,
        "orders": grid_orders
    }


@router.put("/grid/update/{exchange}/{grid_id}", response_model=GridResponse)
async def update_grid_strategy(
    exchange: str,
    grid_id: int,
    update_request: GridUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    更新網格策略參數
    
    可以更新止盈止損設置、利潤回收設置等
    """
    # 檢查網格策略是否存在
    grid_strategy = db.query(GridStrategy).filter(
        GridStrategy.id == grid_id,
        GridStrategy.user_id == current_user.id,
        GridStrategy.exchange == exchange
    ).first()
    
    if not grid_strategy:
        raise HTTPException(status_code=404, detail="未找到指定的網格策略")
    
    try:
        # 更新策略參數
        if update_request.stop_loss is not None:
            grid_strategy.stop_loss = update_request.stop_loss
            
        if update_request.take_profit is not None:
            grid_strategy.take_profit = update_request.take_profit
            
        if update_request.profit_collection is not None:
            grid_strategy.profit_collection = update_request.profit_collection
            
        if update_request.status is not None:
            # 若請求更改狀態為RUNNING或STOPPED，使用相應的API
            if update_request.status == "RUNNING" and grid_strategy.status != "RUNNING":
                # 重定向到啟動策略API
                return await start_grid_strategy(exchange, grid_id, db, current_user)
            elif update_request.status == "STOPPED" and grid_strategy.status != "STOPPED":
                # 重定向到停止策略API
                return await stop_grid_strategy(exchange, grid_id, db, current_user)
            else:
                grid_strategy.status = update_request.status
        
        db.commit()
        
        return {
            "success": True,
            "message": "網格策略已更新",
            "grid_id": grid_id
        }
    except Exception as e:
        db.rollback()
        logger.error(f"更新網格策略失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=f"更新網格策略失敗: {str(e)}")


@router.delete("/grid/delete/{exchange}/{grid_id}", response_model=GridResponse)
async def delete_grid_strategy(
    exchange: str,
    grid_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    刪除網格策略
    
    如果策略正在運行，會先停止策略，然後刪除
    """
    # 檢查網格策略是否存在
    grid_strategy = db.query(GridStrategy).filter(
        GridStrategy.id == grid_id,
        GridStrategy.user_id == current_user.id,
        GridStrategy.exchange == exchange
    ).first()
    
    if not grid_strategy:
        raise HTTPException(status_code=404, detail="未找到指定的網格策略")
    
    try:
        # 如果策略正在運行，先停止
        if grid_strategy.status == "RUNNING":
            await stop_grid_strategy(exchange, grid_id, db, current_user)
        
        # 刪除相關訂單
        db.query(GridOrder).filter(GridOrder.strategy_id == grid_id).delete()
        
        # 刪除策略
        db.delete(grid_strategy)
        db.commit()
        
        return {
            "success": True,
            "message": "網格策略已刪除",
            "grid_id": grid_id
        }
    except Exception as e:
        db.rollback()
        logger.error(f"刪除網格策略失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=f"刪除網格策略失敗: {str(e)}")


# 監控相關函數
async def start_grid_monitor(grid_id: int, user_id: int, exchange: str, db: Session) -> bool:
    """
    啟動網格監控任務
    
    Args:
        grid_id: 網格策略ID
        user_id: 用戶ID
        exchange: 交易所
        db: 數據庫會話
        
    Returns:
        啟動是否成功
    """
    try:
        # 如果已有監控任務，則先停止
        if grid_id in grid_monitor_tasks and not grid_monitor_tasks[grid_id].done():
            logger.info(f"停止現有監控任務 - user:{user_id}, grid_id:{grid_id}")
            await stop_grid_monitor(grid_id)
            
        # 建立新的監控任務
        logger.info(f"啟動新的監控任務 - user:{user_id}, grid_id:{grid_id}, exchange:{exchange}")
        task = asyncio.create_task(monitor_grid(grid_id, user_id, exchange))
        grid_monitor_tasks[grid_id] = task
        
        # 添加任務完成回調，用於清理
        def on_task_done(task):
            try:
                # 檢查任務是否有異常
                if task.exception():
                    logger.error(f"網格監控任務異常終止 - user:{user_id}, grid_id:{grid_id}, error:{task.exception()}")
                else:
                    logger.info(f"網格監控任務正常完成 - user:{user_id}, grid_id:{grid_id}")
                
                # 從任務字典中移除
                if grid_id in grid_monitor_tasks:
                    del grid_monitor_tasks[grid_id]
            except Exception as e:
                logger.error(f"處理監控任務完成回調時出錯: {str(e)} - user:{user_id}, grid_id:{grid_id}")
        
        # 添加回調
        task.add_done_callback(on_task_done)
        
        return True
    except Exception as e:
        logger.error(f"啟動網格監控任務失敗: {str(e)} - user:{user_id}, grid_id:{grid_id}")
        return False


async def stop_grid_monitor(grid_id: int) -> bool:
    """
    停止網格監控任務
    
    Args:
        grid_id: 網格策略ID
        
    Returns:
        停止是否成功
    """
    try:
        if grid_id in grid_monitor_tasks:
            task = grid_monitor_tasks[grid_id]
            
            if not task.done():
                logger.info(f"取消網格監控任務 - grid_id:{grid_id}")
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.debug(f"網格監控任務已取消 - grid_id:{grid_id}")
                except Exception as e:
                    logger.error(f"取消網格監控任務時出錯: {str(e)} - grid_id:{grid_id}")
            else:
                logger.debug(f"網格監控任務已完成，無需取消 - grid_id:{grid_id}")
                
            # 從任務字典中移除
            del grid_monitor_tasks[grid_id]
            return True
        else:
            logger.debug(f"未找到網格監控任務 - grid_id:{grid_id}")
            return False
    except Exception as e:
        logger.error(f"停止網格監控任務時出錯: {str(e)} - grid_id:{grid_id}")
        return False


async def monitor_grid(grid_id: int, user_id: int, exchange: str):
    """
    網格監控任務
    
    訂閱WebSocket用戶數據流，處理網格訂單成交，檢查止損止盈條件
    
    Args:
        grid_id: 網格策略ID
        user_id: 用戶ID
        exchange: 交易所
    """
    from ...db.database import get_db as get_db_session
    
    db = next(get_db_session())
    user_stream = None
    client = None
    
    try:
        # 獲取用戶對象
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"未找到用戶 {user_id}，退出監控")
            return
        
        # 獲取網格策略
        grid = db.query(GridStrategy).filter(
            GridStrategy.id == grid_id,
            GridStrategy.user_id == user_id
        ).first()
        
        if not grid:
            logger.error(f"網格策略 {grid_id} 不存在，退出監控")
            return
            
        # 記錄交易對
        symbol = grid.symbol
        logger.info(f"啟動網格監控 - user:{user_id}, grid_id:{grid_id}, symbol:{symbol}")
        
        # 使用連接管理器獲取連接
        try:
            client, is_new = await exchange_connection_manager.get_connection(
                user_id, exchange, db
            )
            
            if not client or not client.is_connected():
                logger.error(f"無法獲取交易所連接 - user:{user_id}, exchange:{exchange}")
                return
                
        except Exception as e:
            logger.error(f"獲取交易所連接失敗: {str(e)} - user:{user_id}, grid_id:{grid_id}")
            return
            
        # 創建網格服務
        grid_service = GridService(db)
        
        # 訂單更新回調函數
        async def order_update_callback(data):
            try:
                # 只處理訂單更新事件
                if data.get("e") != "ORDER_TRADE_UPDATE":
                    return
                
                # 提取訂單信息
                order_update = data.get("o", {})
                order_symbol = order_update.get("s")  # 交易對
                order_id = order_update.get("i")  # 訂單ID
                order_status = order_update.get("X")  # 訂單狀態
                
                # 只處理特定交易對的訂單
                if order_symbol != symbol:
                    return
                
                # 查詢是否為該策略的訂單
                grid_order = db.query(GridOrder).filter(
                    GridOrder.strategy_id == grid_id,
                    GridOrder.order_id == str(order_id)
                ).first()
                
                if not grid_order:
                    return
                
                logger.info(f"網格策略訂單狀態更新 - user:{user_id}, grid_id:{grid_id}, order_id:{order_id}, status:{order_status}")
                
                # 處理已成交訂單
                if order_status == "FILLED" and grid_order.status != "FILLED":
                    logger.info(f"訂單已成交，處理後續操作 - user:{user_id}, grid_id:{grid_id}, order_id:{order_id}")
                    await grid_service.handle_order_filled(order_id, client)
            
            except Exception as e:
                logger.error(f"處理訂單更新回調時出錯: {str(e)} - user:{user_id}, grid_id:{grid_id}, order_id:{order_id if 'order_id' in locals() else 'unknown'}")
        
        # 訂閱用戶數據流
        logger.info(f"為網格策略訂閱用戶數據流 - user:{user_id}, grid_id:{grid_id}")
        user_stream = await client.subscribe_user_data_stream(order_update_callback)
        
        # 上次檢查止損止盈的時間
        last_sl_tp_check = time.time()
        
        # 持續監控 (保持輪詢檢查網格策略狀態和止損止盈條件)
        while True:
            try:
                # 檢查網格策略狀態
                grid = db.query(GridStrategy).filter(
                    GridStrategy.id == grid_id,
                    GridStrategy.user_id == user_id,
                    GridStrategy.status == "RUNNING"
                ).first()
                
                if not grid:
                    logger.info(f"網格策略已停止或不存在，退出監控 - user:{user_id}, grid_id:{grid_id}")
                    break
                
                # 確保客戶端仍然連接
                if not client.is_connected():
                    logger.warning(f"客戶端連接已斷開，嘗試重新連接 - user:{user_id}, grid_id:{grid_id}")
                    client, _ = await exchange_connection_manager.get_connection(user_id, exchange, db, force_new=True)
                    if not client or not client.is_connected():
                        logger.error(f"重新連接失敗，退出監控 - user:{user_id}, grid_id:{grid_id}")
                        break
                    
                    # 重新訂閱用戶數據流
                    if user_stream:
                        # 清理舊的訂閱
                        for task_name in ['listen_task', 'keepalive_task']:
                            if task_name in user_stream and not user_stream[task_name].done():
                                user_stream[task_name].cancel()
                        if 'user_ws' in user_stream:
                            await user_stream['user_ws'].close()
                    
                    # 創建新的訂閱
                    user_stream = await client.subscribe_user_data_stream(order_update_callback)
                    logger.info(f"已重新訂閱用戶數據流 - user:{user_id}, grid_id:{grid_id}")
                
                # 每30秒檢查一次止損止盈條件
                current_time = time.time()
                if current_time - last_sl_tp_check >= 30:
                    try:
                        # 獲取當前價格
                        market_data = await MarketDataService.get_latest_price(exchange, symbol)
                        current_price = Decimal(str(market_data["price"]))
                        
                        # 檢查止損止盈
                        if grid.stop_loss is not None or grid.take_profit is not None:
                            # 創建策略實例
                            strategy = GridStrategyFactory.create_strategy(grid, db)
                            
                            # 檢查止損
                            if strategy.is_stop_loss_triggered(current_price):
                                logger.info(f"網格策略觸發止損 - user:{user_id}, grid_id:{grid_id}, price:{current_price}, stop_loss:{grid.stop_loss}")
                                # 停止策略
                                await grid_service.stop_strategy(grid_id, user_id, exchange, client)
                                break
                                
                            # 檢查止盈
                            if strategy.is_take_profit_triggered(current_price):
                                logger.info(f"網格策略觸發止盈 - user:{user_id}, grid_id:{grid_id}, price:{current_price}, take_profit:{grid.take_profit}")
                                # 停止策略
                                await grid_service.stop_strategy(grid_id, user_id, exchange, client)
                                break
                                
                        # 更新檢查時間
                        last_sl_tp_check = current_time
                        
                    except Exception as e:
                        logger.error(f"檢查止損止盈時出錯: {str(e)} - user:{user_id}, grid_id:{grid_id}")
                
                # 短暫睡眠，避免CPU佔用過高
                await asyncio.sleep(5)
                
            except asyncio.CancelledError:
                logger.info(f"網格監控任務被取消 - user:{user_id}, grid_id:{grid_id}")
                break
                
            except Exception as e:
                logger.error(f"網格監控處理出錯: {str(e)} - user:{user_id}, grid_id:{grid_id}")
                await asyncio.sleep(5)  # 出錯後等待5秒再重試
                
    except Exception as e:
        logger.error(f"網格監控主任務出錯: {str(e)} - user:{user_id}, grid_id:{grid_id}")
    finally:
        # 最後確保關閉資源
        try:
            if user_stream:
                for task_name in ['listen_task', 'keepalive_task']:
                    if task_name in user_stream and not user_stream[task_name].done():
                        user_stream[task_name].cancel()
                if 'user_ws' in user_stream:
                    await user_stream['user_ws'].close()
            # 不要關閉client，因為它是由連接管理器管理的
        except Exception as e:
            logger.error(f"清理網格監控資源時出錯: {str(e)} - user:{user_id}, grid_id:{grid_id}")
        finally:
            db.close()
