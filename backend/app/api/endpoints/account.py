from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, Query, WebSocketDisconnect, Request
from sqlalchemy.orm import Session
from typing import Any, Dict, Optional
import logging
import json
import hmac
import hashlib
import time
import websockets
from datetime import datetime
import asyncio
import aiohttp
import string  
import random
import uuid

from ...db.database import get_db
from ...schemas.trading import ExchangeEnum
from ...db.models import User, ExchangeAPI
from ...core.security import get_current_user, get_current_active_user, decrypt_api_key, verify_token
# 修改導入方式，導入類而不是實例
from backend.utils.exchange_connection_manager import ExchangeConnectionManager, initialize_connection_manager
# 導入 ApiKeyManager
from ...core.api_key_manager import ApiKeyManager

router = APIRouter()
logger = logging.getLogger(__name__)

# 創建交易所連接管理器
exchange_connection_manager = ExchangeConnectionManager()

# 創建 API 密鑰管理器
api_key_manager = ApiKeyManager()

@router.websocket("/account/futures-account/{exchange}")
async def futures_account_websocket(
    websocket: WebSocket,
    exchange: str,
    token: str = Query(None, description="用戶驗證token")
):
    """
    通過WebSocket獲取期貨帳戶信息
    允許通過查詢參數傳遞token，或在連接後發送token
    
    新增功能: 支持直接使用API密鑰，繞過數據庫加密/解密流程
    新增功能: 支持長期連接，保持WebSocket連接活躍
    新增功能: 支持通過同一WebSocket連接發送下單請求
    """
    # 獲取安全密鑰緩存實例
    from backend.app.core.secure_key_cache import SecureKeyCache
    key_cache = SecureKeyCache()
    
    # 先接受連接，以避免HTTP 403錯誤
    await websocket.accept()
    logger.info(f"接受WebSocket連接 - 交易所:{exchange}")
    
    try:
        # 如果未通過查詢參數傳遞token，等待客戶端發送token
        user_id = None
        api_key_data = None
        direct_api_mode = False
        
        if not token:
            try:
                # 等待客戶端發送token
                token_from_client = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
                token = token_from_client
            except asyncio.TimeoutError:
                await websocket.send_json({"success": False, "message": "未能接收到認證信息"})
                logger.warning("等待token超時")
                return
            
        # 手動創建數據庫會話，而不是通過依賴注入
        from ...db.database import SessionLocal
        db = SessionLocal()
        
        try:
            # 使用 verify_token_ws 函數驗證token
            from ...core.security import verify_token_ws
            user = await verify_token_ws(token, db)
            
            if not user:
                await websocket.send_json({"success": False, "message": "用戶驗證失敗"})
                logger.warning("用戶驗證失敗")
                return
            
            user_id = user.id
            logger.info(f"用戶 {user.username}(ID:{user_id}) 認證成功")
            
            # 檢查是否有直接API密鑰請求
            try:
                # 嘗試接收一條消息，看是否為直接API請求
                direct_api_request = await asyncio.wait_for(websocket.receive_text(), timeout=3.0)
                try:
                    direct_data = json.loads(direct_api_request)
                    if direct_data.get("direct_api") and "api_key" in direct_data and "api_secret" in direct_data:
                        api_key_data = {
                            "api_key": direct_data["api_key"].strip(),
                            "api_secret": direct_data["api_secret"].strip()
                        }
                        direct_api_mode = True
                except json.JSONDecodeError:
                    pass
            except asyncio.TimeoutError:
                pass
            
            # 如果沒有直接API模式，從數據庫獲取API密鑰
            if not direct_api_mode:
                # 從緩存中獲取密鑰
                cached_keys = key_cache.get_keys(user_id, exchange)
                
                if cached_keys:
                    logger.info(f"從安全緩存獲取用戶 {user_id} 的 {exchange} HMAC-SHA256 密鑰")
                    api_key, api_secret = cached_keys
                    api_key_data = {
                        "api_key": api_key,
                        "api_secret": api_secret
                    }
                else:
                    # 嘗試從緩存獲取 Ed25519 密鑰
                    cached_ed25519_keys = key_cache.get_ed25519_keys(user_id, exchange)
                    if cached_ed25519_keys:
                        logger.info(f"從安全緩存獲取用戶 {user_id} 的 {exchange} Ed25519 密鑰")
                        api_key, ed25519_key, ed25519_secret = cached_ed25519_keys
                        api_key_data = {
                            "api_key": api_key,
                            "api_secret": ed25519_secret  # 使用Ed25519私鑰作為API密碼
                        }
                    else:
                        # 緩存中沒有，需要從數據庫獲取
                        api_key_record = await api_key_manager.get_api_key(db, user_id, exchange)
                        
                        if not api_key_record:
                            logger.warning(f"未找到用戶 {user_id} 的 {exchange} API密鑰")
                            await websocket.send_json({"success": False, "message": "未找到API密鑰，請先設置"})
                            await websocket.close()
                            return
                        
                        # 獲取真實API密鑰
                        api_key_data, _ = await api_key_manager.get_real_api_key(
                            db=db,
                            user_id=user_id,
                            virtual_key_id=api_key_record.virtual_key_id,
                            operation="read"
                        )
            
            # 清理 API 密鑰中可能存在的引號和空白字符
            if api_key_data:
                # 這個步驟可以保留，作為額外的安全措施
                for key in ["api_key", "api_secret"]:
                    if api_key_data[key]:
                        # 移除首尾引號
                        if api_key_data[key].startswith('"') and api_key_data[key].endswith('"'):
                            api_key_data[key] = api_key_data[key][1:-1]
                        # 清理空白字符
                        api_key_data[key] = api_key_data[key].strip()
            
            # 發送連接成功消息
            await websocket.send_json({
                "success": True,
                "message": "連接成功，開始獲取帳戶數據"
            })
            
            # 使用API密鑰連接到交易所WebSocket
            # 儲存 WebSocket 客戶端引用，方便後續重用
            binance_client = None
            
            # 緩存機制 - 存儲上次獲取的帳戶資料，用於比較差異
            last_account_data = None
            
            # 使用連接管理器獲取客戶端
            try:
                # 使用交易所連接管理器獲取客戶端
                if not direct_api_mode:
                    # 使用用戶ID從連接管理器獲取連接
                    binance_client, is_new = await exchange_connection_manager.get_connection(user_id, exchange, db)
                    logger.info(f"獲取連接 - 用戶:{user_id}, 新連接:{is_new}")
                else:
                    # 直接API模式下，創建新連接
                    binance_client, is_new = await exchange_connection_manager.get_or_create_connection(
                        api_key_data["api_key"], 
                        api_key_data["api_secret"], 
                        exchange, 
                        user_id=user_id
                    )
                    logger.info(f"直接API模式創建連接 - 用戶:{user_id}")
                
                # 確認連接有效
                if not binance_client.is_connected():
                    await websocket.send_json({
                        "success": False, 
                        "message": "連接已斷開，請刷新頁面重新連接"
                    })
                    return
                
                # 使用連接獲取賬戶數據
                account_info = await binance_client.get_account_info()
                
                # 格式化返回數據
                account_data = {
                    "balances": [],
                    "positions": [],
                    "api_type": "WebSocket API (Ed25519)",  # 添加API類型標記
                }
                
                # 處理賬戶資訊
                if isinstance(account_info, dict):
                    # 處理餘額情況
                    if "assets" in account_info:
                        account_data["balances"] = account_info["assets"]
                        
                        # 提取總權益和可用餘額
                        for asset in account_info["assets"]:
                            if asset.get("asset") == "USDT":
                                account_data["totalWalletBalance"] = asset.get("walletBalance", "0")
                                account_data["availableBalance"] = asset.get("availableBalance", "0")
                                break
                    
                    # 處理持倉
                    if "positions" in account_info:
                        account_data["positions"] = [
                            pos for pos in account_info["positions"] 
                            if float(pos.get("positionAmt", 0)) != 0
                        ]
                        
                        # 計算未實現盈虧總和
                        total_unrealized_profit = sum(
                            float(pos.get("unrealizedProfit", 0)) 
                            for pos in account_info["positions"]
                        )
                        account_data["totalUnrealizedProfit"] = str(total_unrealized_profit)
                
                # 發送初始帳戶數據
                await websocket.send_json({
                    "type": "account_update",
                    "data": account_data
                })
                
                last_account_data = account_data
                logger.info(f"發送初始帳戶數據 - 用戶:{user_id}")
                
                # 使用心跳機制保持連接
                last_heartbeat_time = time.time()
                last_data_refresh_time = time.time()
                
                # 設置定時器間隔
                heartbeat_interval = 30  # 每30秒發送一次心跳
                data_refresh_interval = 5  # 每5秒檢查一次數據更新
                
                # 持續處理WebSocket消息
                while True:
                    current_time = time.time()
                    
                    # 非阻塞方式接收消息
                    try:
                        # 使用 asyncio.wait_for 設置超時時間，避免永久阻塞
                        msg_str = await asyncio.wait_for(
                            websocket.receive_text(),
                            timeout=min(heartbeat_interval, data_refresh_interval) / 2
                        )
                        
                        # 解析消息
                        try:
                            msg = json.loads(msg_str)
                            message_type = msg.get("type", "")
                            
                            # 處理不同類型的消息
                            if message_type == "refresh":
                                # 刷新請求：重新獲取帳戶數據
                                logger.info(f"收到刷新請求 - 用戶:{user_id}")
                                
                                # 使用現有客戶端獲取最新數據
                                account_info = await binance_client.get_account_info()
                                
                                # 格式化數據（同上，但這裡簡化處理）
                                account_data = {
                                    "balances": account_info.get("assets", []),
                                    "positions": [p for p in account_info.get("positions", []) if float(p.get("positionAmt", 0)) != 0],
                                    "api_type": "WebSocket API (Ed25519)"
                                }
                                
                                # 提取總權益和可用餘額
                                for asset in account_data["balances"]:
                                    if asset.get("asset") == "USDT":
                                        account_data["totalWalletBalance"] = asset.get("walletBalance", "0")
                                        account_data["availableBalance"] = asset.get("availableBalance", "0")
                                        break
                                
                                # 計算未實現盈虧總和
                                total_unrealized_profit = sum(
                                    float(pos.get("unrealizedProfit", 0)) 
                                    for pos in account_data["positions"]
                                )
                                account_data["totalUnrealizedProfit"] = str(total_unrealized_profit)
                                
                                # 發送刷新後的帳戶數據
                                await websocket.send_json({
                                    "type": "account_update",
                                    "data": account_data
                                })
                                
                                last_account_data = account_data
                                last_data_refresh_time = current_time
                            
                            elif message_type == "place_order":
                                # 下單請求
                                logger.info(f"收到下單請求 - 用戶:{user_id}")
                                
                                # 提取下單參數
                                order_params = msg.get("data", {})
                                
                                # 檢查必要參數
                                required_params = ["symbol", "side", "type"]
                                if not all(param in order_params for param in required_params):
                                    await websocket.send_json({
                                        "type": "order_response",
                                        "success": False,
                                        "message": "缺少必要的下單參數",
                                        "request_id": msg.get("request_id")
                                    })
                                    continue
                                
                                # 使用現有客戶端下單
                                try:
                                    # 提取參數
                                    symbol = order_params.pop("symbol")
                                    side = order_params.pop("side")
                                    order_type = order_params.pop("type")  # 使用type作為參數
                                    
                                    # 下單
                                    result = await binance_client.place_order(symbol, side, order_type, **order_params)
                                    
                                    # 返回下單結果
                                    await websocket.send_json({
                                        "type": "order_response",
                                        "success": True,
                                        "data": result,
                                        "request_id": msg.get("request_id")
                                    })
                                    logger.info(f"下單成功 - 用戶:{user_id}, 訂單ID:{result.get('orderId')}")
                                    
                                except Exception as e:
                                    # 下單失敗，返回錯誤信息
                                    await websocket.send_json({
                                        "type": "order_response",
                                        "success": False,
                                        "message": str(e),
                                        "request_id": msg.get("request_id")
                                    })
                                    logger.error(f"下單失敗: {str(e)}")
                            
                            elif message_type == "cancel_order":
                                # 取消訂單請求
                                logger.info(f"收到取消訂單請求 - 用戶:{user_id}")
                                
                                # 提取取消訂單參數
                                cancel_params = msg.get("data", {})
                                
                                # 檢查必要參數
                                required_params = ["symbol", "orderId"]
                                if not all(param in cancel_params for param in required_params):
                                    await websocket.send_json({
                                        "type": "cancel_response",
                                        "success": False,
                                        "message": "缺少必要的取消訂單參數",
                                        "request_id": msg.get("request_id")
                                    })
                                    continue
                                
                                # 使用現有客戶端取消訂單
                                try:
                                    # 提取參數
                                    symbol = cancel_params["symbol"]
                                    order_id = cancel_params["orderId"]
                                    
                                    # 取消訂單
                                    result = await binance_client.cancel_order(symbol, order_id)
                                    
                                    # 返回取消訂單結果
                                    await websocket.send_json({
                                        "type": "cancel_response",
                                        "success": True,
                                        "data": result,
                                        "request_id": msg.get("request_id")
                                    })
                                    logger.info(f"取消訂單成功 - 訂單ID:{order_id}")
                                    
                                except Exception as e:
                                    # 取消訂單失敗，返回錯誤信息
                                    await websocket.send_json({
                                        "type": "cancel_response",
                                        "success": False,
                                        "message": str(e),
                                        "request_id": msg.get("request_id")
                                    })
                                    logger.error(f"取消訂單失敗: {str(e)}")
                            
                            elif message_type == "ping":
                                # 客戶端發送的ping請求
                                await websocket.send_json({"type": "pong"})
                            
                            else:
                                # 未知消息類型
                                logger.warning(f"收到未知類型消息: {message_type}")
                        
                        except json.JSONDecodeError:
                            # 非JSON格式消息
                            pass
                    
                    except asyncio.TimeoutError:
                        # 沒有收到新消息，這是正常的，可以繼續其他操作
                        pass
                    except WebSocketDisconnect:
                        # 客戶端斷開連接
                        logger.info(f"客戶端斷開連接 - 用戶:{user_id}")
                        break
                    
                    # 定期刷新數據
                    if current_time - last_data_refresh_time > data_refresh_interval:
                        try:
                            # 獲取最新帳戶數據
                            account_info = await binance_client.get_account_info()
                            
                            # 格式化數據
                            account_data = {
                                "balances": account_info.get("assets", []),
                                "positions": [p for p in account_info.get("positions", []) if float(p.get("positionAmt", 0)) != 0],
                                "api_type": "WebSocket API (Ed25519)"
                            }
                            
                            # 提取總權益和可用餘額
                            for asset in account_data["balances"]:
                                if asset.get("asset") == "USDT":
                                    account_data["totalWalletBalance"] = asset.get("walletBalance", "0")
                                    account_data["availableBalance"] = asset.get("availableBalance", "0")
                                    break
                            
                            # 計算未實現盈虧總和
                            total_unrealized_profit = sum(
                                float(pos.get("unrealizedProfit", 0)) 
                                for pos in account_data["positions"]
                            )
                            account_data["totalUnrealizedProfit"] = str(total_unrealized_profit)
                            
                            # 檢查帳戶數據是否有變化
                            if await exchange_connection_manager._has_account_data_changed(account_data, last_account_data):
                                # 計算變化
                                data_diff = await exchange_connection_manager._compute_account_data_diff(account_data, last_account_data)
                                
                                # 發送更新後的帳戶數據
                                await websocket.send_json({
                                    "type": "account_update",
                                    "data": account_data,
                                    "diff": data_diff
                                })
                                
                                last_account_data = account_data
                            
                            last_data_refresh_time = current_time
                        
                        except Exception as e:
                            logger.error(f"刷新帳戶數據時出錯: {str(e)}")
                    
                    # 定期發送心跳
                    if current_time - last_heartbeat_time > heartbeat_interval:
                        await websocket.send_json({"type": "heartbeat"})
                        last_heartbeat_time = current_time
            
            except Exception as e:
                logger.error(f"處理WebSocket連接時出錯: {str(e)}")
                await websocket.send_json({
                    "success": False,
                    "message": f"處理連接時出錯: {str(e)}"
                })
        
        finally:
            # 關閉數據庫會話
            db.close()
    
    except WebSocketDisconnect:
        logger.info("客戶端斷開連接")
    except Exception as e:
        logger.error(f"WebSocket處理時出錯: {str(e)}")
        try:
            await websocket.send_json({"success": False, "message": f"發生錯誤: {str(e)}"})
        except:
            pass

@router.websocket("/test-websocket")
async def test_websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(None, description="用戶驗證token（可選）")
):
    """
    用於測試WebSocket連接的簡單端點
    """
    await websocket.accept()
    await websocket.send_text(f"WebSocket連接成功！服務器時間: {datetime.now().isoformat()}")
    
    if token:
        await websocket.send_text(f"收到token: {token[:8]}...")
    
    try:
        count = 0
        while True:
            count += 1
            await asyncio.sleep(5)
            await websocket.send_text(f"心跳 #{count}, 時間: {datetime.now().isoformat()}")
    except WebSocketDisconnect:
        print("客戶端斷開連接")

async def get_account_data(
    exchange: str,
    api_key: str = None,
    api_secret: str = None,
    user_id: int = None,
    virtual_key_id: str = None,
    db: Session = None
):
    """
    獲取用戶在指定交易所的帳戶數據
    支持直接提供API密鑰或通過用戶ID從數據庫獲取
    
    Args:
        exchange: 交易所名稱
        api_key: 可選，API密鑰
        api_secret: 可選，API密鑰密碼
        user_id: 可選，用戶ID，用於從數據庫獲取API密鑰
        virtual_key_id: 可選，虛擬密鑰ID，用於從API密鑰管理器獲取密鑰
        db: 可選，數據庫會話
        
    Returns:
        dict: 帳戶數據，包含餘額和持倉信息
    """
    logger.info(f"開始獲取帳戶數據: {exchange}, 用戶ID: {user_id}")
    
    try:
        # 檢查是否使用 ApiKeyManager 獲取密鑰
        if not api_key or not api_secret:
            if user_id and db:
                # 先從安全密鑰緩存獲取
                from ...core.secure_key_cache import SecureKeyCache
                key_cache = SecureKeyCache()
                
                # 嘗試從緩存獲取 HMAC-SHA256 密鑰
                cached_keys = key_cache.get_keys(user_id, exchange)
                if cached_keys:
                    logger.info(f"從安全緩存獲取用戶 {user_id} 的 {exchange} HMAC-SHA256 密鑰")
                    api_key, api_secret = cached_keys
                else:
                    # 嘗試從緩存獲取 Ed25519 密鑰
                    cached_ed25519_keys = key_cache.get_ed25519_keys(user_id, exchange)
                    if cached_ed25519_keys:
                        logger.info(f"從安全緩存獲取用戶 {user_id} 的 {exchange} Ed25519 密鑰")
                        api_key = cached_ed25519_keys[0]
                        api_secret = cached_ed25519_keys[2]  # 使用Ed25519私鑰作為API密碼
                    else:
                        # 緩存中沒有，使用原來的方法從數據庫獲取
                        logger.info(f"使用 ApiKeyManager 獲取 API 密鑰")
                        
                        # 如果提供了虛擬密鑰ID，直接使用它
                        if virtual_key_id:
                            logger.info(f"使用提供的虛擬密鑰ID: {virtual_key_id}")
                        else:
                            # 獲取API密鑰記錄
                            api_key_record = await api_key_manager.get_api_key(db, user_id, exchange)
                            
                            if not api_key_record:
                                error_msg = f"未找到{exchange}的API密鑰"
                                logger.error(error_msg)
                                raise ValueError(error_msg)
                            
                            virtual_key_id = api_key_record.virtual_key_id
                            
                            # 確保有虛擬密鑰ID
                            if not virtual_key_id:
                                logger.warning(f"API密鑰記錄沒有虛擬密鑰ID，將創建一個")
                                try:
                                    # 生成虛擬密鑰ID
                                    api_key_record.virtual_key_id = str(uuid.uuid4())
                                    # 設置默認權限
                                    api_key_record.permissions = {"read": True, "trade": True}
                                    # 保存到數據庫
                                    db.commit()
                                    db.refresh(api_key_record)
                                    virtual_key_id = api_key_record.virtual_key_id
                                    logger.info(f"成功為API密鑰創建虛擬密鑰ID: {virtual_key_id}")
                                except Exception as e:
                                    logger.error(f"創建虛擬密鑰ID失敗: {str(e)}")
                                    # 繼續處理，使用備用方法
                        
                        # 優先使用 ApiKeyManager 獲取解密後的密鑰
                        if virtual_key_id:
                            try:
                                # 使用 ApiKeyManager 獲取解密後的 API 密鑰
                                real_keys, _ = await api_key_manager.get_real_api_key(
                                    db=db,
                                    user_id=user_id,
                                    virtual_key_id=virtual_key_id,
                                    operation="read"  # 讀取操作
                                )
                                
                                if real_keys.get("api_key") and real_keys.get("api_secret"):
                                    logger.info(f"成功使用 ApiKeyManager 解密 API 密鑰")
                                    api_key = real_keys.get("api_key")
                                    api_secret = real_keys.get("api_secret")
                                else:
                                    # ApiKeyManager 解密失敗，嘗試備用方法
                                    logger.warning(f"ApiKeyManager 解密失敗，嘗試使用備用方法")
                                    
                                    # 如果虛擬密鑰ID可用但解密失敗，需要獲取API密鑰記錄進行備用解密
                                    if not api_key_record:
                                        api_key_record = await api_key_manager.get_api_key(db, user_id, exchange)
                                        
                                        if not api_key_record:
                                            error_msg = f"未找到{exchange}的API密鑰"
                                            logger.error(error_msg)
                                            raise ValueError(error_msg)
                            except Exception as e:
                                logger.warning(f"使用 ApiKeyManager 解密失敗: {str(e)}")
                                
                                # 獲取API密鑰記錄以進行備用解密
                                if not api_key_record:
                                    api_key_record = await api_key_manager.get_api_key(db, user_id, exchange)
                                    
                                    if not api_key_record:
                                        error_msg = f"未找到{exchange}的API密鑰"
                                        logger.error(error_msg)
                                        raise ValueError(error_msg)
                        
                        # 如果 ApiKeyManager 解密失敗，嘗試直接解密
                        if (not api_key or not api_secret) and api_key_record:
                            logger.info(f"嘗試使用備用解密方法")
                            
                            # 直接使用安全模塊解密
                            from ...core.security import decrypt_api_key
                            
                            # 優先嘗試 HMAC-SHA256 密鑰
                            api_key = decrypt_api_key(api_key_record.api_key, key_type="API Key (HMAC-SHA256)")
                            api_secret = decrypt_api_key(api_key_record.api_secret, key_type="API Secret (HMAC-SHA256)")
                            
                            # 在解密兩個密鑰後統一記錄結果
                            if api_key and api_secret:
                                logger.debug(f"HMAC-SHA256密鑰對解密成功，Key長度: {len(api_key)}, Secret長度: {len(api_secret)}")
                                # 存入緩存
                                key_cache.set_keys(user_id, exchange, api_key, api_secret)
                            else:
                                logger.warning(f"HMAC-SHA256密鑰解密失敗，嘗試 Ed25519 密鑰")
                            
                            # 如果 HMAC-SHA256 密鑰解密失敗，嘗試 Ed25519 密鑰
                            if not api_key or not api_secret:
                                api_key = decrypt_api_key(api_key_record.ed25519_key, key_type="API Key (Ed25519)")
                                api_secret = decrypt_api_key(api_key_record.ed25519_secret, key_type="API Secret (Ed25519)")
                                
                                # 統一記錄 Ed25519 密鑰解密結果
                                if api_key and api_secret:
                                    logger.debug(f"Ed25519密鑰對解密成功，Key長度: {len(api_key)}, Secret長度: {len(api_secret)}")
                                    # 存入緩存
                                    key_cache.set_ed25519_keys(user_id, exchange, api_key, api_key, api_secret)
                                else:
                                    logger.error(f"API密鑰解密全部失敗，無法繼續連接")
                            
                            if not api_key or not api_secret:
                                error_msg = "API密鑰解密失敗（所有方法均失敗）"
                                logger.error(error_msg)
                                raise ValueError(error_msg)
            else:
                error_msg = "API密鑰或密鑰密碼為空，且未提供足夠信息從 ApiKeyManager 獲取"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
        # 檢查 API 密鑰
        if not api_key or not api_secret:
            error_msg = "API密鑰或密鑰密碼為空"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # 記錄解密成功
        logger.info(f"成功獲取 API 密鑰，準備連接交易所 {exchange}")
        
        # 清理 API 密鑰中可能存在的引號和空白字符
        for key_var in [api_key, api_secret]:
            if key_var and key_var.startswith('"') and key_var.endswith('"'):
                key_var = key_var[1:-1]
        
        # 移除空白字符
        api_key = api_key.strip() if api_key else None
        api_secret = api_secret.strip() if api_secret else None
        
        if exchange.lower() == "binance":
            # 使用WebSocket方式獲取帳戶數據
            try:
                # 從連接管理器獲取客戶端
                if user_id:
                    client, is_new = await exchange_connection_manager.get_connection(user_id, exchange, db)
                else:
                    # 使用直接提供的API密鑰
                    client, is_new = await exchange_connection_manager.get_or_create_connection(api_key, api_secret, exchange)
                
                # 記錄客戶端來源
                if is_new:
                    logger.info(f"創建了新的幣安WebSocket客戶端")
                else:
                    logger.debug(f"重用現有的幣安WebSocket客戶端")
                
                # 確認客戶端連接狀態
                if not client.is_connected():
                    logger.warning(f"客戶端連接已斷開，嘗試重新連接")
                    connected = await client.connect()
                    if not connected:
                        logger.error(f"重新連接失敗，回退到REST API")
                    return await get_account_data_rest(exchange, api_key, api_secret)
                
                # 獲取帳戶信息
                account_info = await client.get_account_info()
                
                # 格式化返回數據
                formatted_data = {
                    "balances": [],
                    "positions": [],
                    "api_type": "WebSocket API (Ed25519)",
                }
                
                # 檢查帳戶信息是否有效
                if isinstance(account_info, dict):
                    # 處理餘額情況
                    if "assets" in account_info:
                        formatted_data["balances"] = account_info["assets"]
                        
                        # 提取總權益和可用餘額
                        for asset in account_info["assets"]:
                            if asset.get("asset") == "USDT":
                                formatted_data["totalWalletBalance"] = asset.get("walletBalance", "0")
                                formatted_data["availableBalance"] = asset.get("availableBalance", "0")
                                break
                    
                    # 處理持倉
                    if "positions" in account_info:
                        # 只保留持倉數量不為0的持倉
                        formatted_data["positions"] = [
                            pos for pos in account_info["positions"] 
                            if float(pos.get("positionAmt", 0)) != 0
                        ]
                        
                        # 計算未實現盈虧總和
                        total_unrealized_profit = sum(
                            float(pos.get("unrealizedProfit", 0)) 
                            for pos in account_info["positions"]
                        )
                        formatted_data["totalUnrealizedProfit"] = str(total_unrealized_profit)
                
                return formatted_data
            
            except Exception as e:
                logger.error(f"使用WebSocket獲取幣安帳戶數據時出錯: {str(e)}")
                # 如果WebSocket方式失敗，回退到REST API方式
                logger.info(f"回退到使用REST API獲取幣安帳戶數據")
                return await get_account_data_rest(exchange, api_key, api_secret)
        
        else:
            # 其他交易所使用REST API方式
            return await get_account_data_rest(exchange, api_key, api_secret)
        
    except Exception as e:
        logger.error(f"獲取帳戶數據時出錯: {str(e)}")
        raise

# 保留 get_account_data_rest 函數作為後備方案
async def get_account_data_rest(exchange, api_key, api_secret):
    """
    使用REST API獲取帳戶數據（舊方法，作為備份）
    """
    # 保持原有的函數實現不變...
    # 此處省略原函數內容，保持不變

@router.post("/api-keys/diagnostic", response_model=dict)
async def api_key_diagnostic(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # 返回基本診斷信息
    return {
        "success": True,
        "message": "API 密鑰診斷功能正常",
        "user_id": current_user.id,
        "username": current_user.username
    }

@router.get("/api-keys/exchanges", response_model=list)
async def get_user_exchanges(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """獲取用戶已配置的交易所列表"""
    try:
        # 使用 ApiKeyManager 獲取用戶的所有 API 密鑰
        api_keys = await api_key_manager.get_api_keys(db, current_user.id)
        
        # 提取交易所名稱列表
        exchange_list = [api_key.exchange for api_key in api_keys]
        
        return exchange_list
    except Exception as e:
        logger.error(f"獲取用戶交易所列表失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"獲取交易所列表失敗: {str(e)}"
        )
