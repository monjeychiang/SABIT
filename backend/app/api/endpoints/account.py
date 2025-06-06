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
from ...core.security import get_current_user, get_current_active_user, decrypt_api_key
# 導入連接管理器
from backend.utils.exchange_connection_manager import exchange_connection_manager, initialize_connection_manager

router = APIRouter()
logger = logging.getLogger(__name__)

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
    # 先接受連接，以避免HTTP 403錯誤
    await websocket.accept()
    logger.info(f"[AccountWS] 已接受來自 {exchange} 的WebSocket連接請求")
    
    try:
        # 如果未通過查詢參數傳遞token，等待客戶端發送token
        user_id = None
        api_key_data = None
        direct_api_mode = False
        
        if not token:
            logger.info(f"[AccountWS] 沒有通過查詢參數接收到token，等待客戶端發送")
            try:
                # 等待客戶端發送token
                token_from_client = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
                token = token_from_client
                logger.info(f"[AccountWS] 從WebSocket消息接收到token，長度: {len(token)}")
            except asyncio.TimeoutError:
                await websocket.send_json({"success": False, "message": "未能接收到認證信息"})
                logger.warning("[AccountWS] 等待token超時")
                return
        else:
            logger.info(f"[AccountWS] 通過查詢參數接收到token，長度: {len(token)}")
            
        # 手動創建數據庫會話，而不是通過依賴注入
        from ...db.database import SessionLocal
        db = SessionLocal()
        
        try:
            # 使用 verify_token_ws 函數驗證token
            from ...core.security import verify_token_ws
            user = await verify_token_ws(token, db)
            
            if not user:
                await websocket.send_json({"success": False, "message": "用戶驗證失敗"})
                logger.warning("[AccountWS] 用戶驗證失敗")
                return
            
            user_id = user.id
            logger.info(f"[AccountWS] 用戶 {user.username}(ID:{user_id}) 認證成功")
            
            # 檢查是否有直接API密鑰請求
            try:
                # 嘗試接收一條消息，看是否為直接API請求
                direct_api_request = await asyncio.wait_for(websocket.receive_text(), timeout=3.0)
                try:
                    direct_data = json.loads(direct_api_request)
                    if direct_data.get("direct_api") and "api_key" in direct_data and "api_secret" in direct_data:
                        logger.info(f"[AccountWS] 收到直接API密鑰請求")
                        api_key_data = {
                            "api_key": direct_data["api_key"].strip(),
                            "api_secret": direct_data["api_secret"].strip()
                        }
                        direct_api_mode = True
                except json.JSONDecodeError:
                    # 不是JSON格式，可能是其他消息
                    logger.debug(f"[AccountWS] 收到非JSON格式消息，長度: {len(direct_api_request)}")
                    pass
            except asyncio.TimeoutError:
                # 沒有收到額外消息，繼續標準流程
                logger.debug(f"[AccountWS] 沒有收到直接API密鑰請求，使用標準流程")
                pass
            
            # 如果沒有直接API模式，從數據庫獲取API密鑰
            if not direct_api_mode:
                # 獲取API密鑰
                api_key = db.query(ExchangeAPI).filter(
                    ExchangeAPI.user_id == user_id, 
                    ExchangeAPI.exchange == exchange
                ).first()
        
                if not api_key:
                    await websocket.send_json({"success": False, "message": f"未找到{exchange}的API密鑰"})
                    logger.warning(f"[AccountWS] 用戶 {user_id} 沒有 {exchange} 的API密鑰")
                    return
                
                logger.info(f"[AccountWS] 從數據庫獲取到用戶 {user_id} 的 {exchange} API密鑰，開始解密")
                
                # 解密API密鑰
                from ...core.security import decrypt_api_key, clean_api_key
                
                # 記錄加密API密鑰的長度（不記錄實際內容以保護安全）
                encrypted_key_length = len(api_key.ed25519_key) if api_key.ed25519_key else 0
                encrypted_secret_length = len(api_key.ed25519_secret) if api_key.ed25519_secret else 0
                logger.debug(f"[AccountWS] 加密的Ed25519 API密鑰長度: {encrypted_key_length}, 加密的Ed25519 API密鑰密碼長度: {encrypted_secret_length}")
                
                # 解密Ed25519 API密鑰
                decrypted_key = decrypt_api_key(api_key.ed25519_key)
                decrypted_secret = decrypt_api_key(api_key.ed25519_secret)
                
                # 檢查解密結果
                if not decrypted_key or not decrypted_secret:
                    error_msg = "Ed25519 API密鑰解密失敗"
                    logger.error(f"[AccountWS] {error_msg}")
                    
                    # 嘗試使用HMAC作為後備方案
                    logger.info(f"[AccountWS] 嘗試使用HMAC-SHA256 API密鑰作為後備")
                    decrypted_key = decrypt_api_key(api_key.api_key)
                    decrypted_secret = decrypt_api_key(api_key.api_secret)
                    
                    if not decrypted_key or not decrypted_secret:
                        error_msg = "API密鑰解密失敗（Ed25519和HMAC均失敗）"
                        logger.error(f"[AccountWS] {error_msg}")
                        await websocket.send_json({"success": False, "message": error_msg})
                        return
                    
                    logger.info(f"[AccountWS] 成功使用HMAC-SHA256 API密鑰作為後備方案")
                
                # 確保API密鑰格式正確
                api_key_data = {
                    "api_key": decrypted_key,
                    "api_secret": decrypted_secret
                }
                
                logger.info(f"[AccountWS] 成功獲取並解密用戶 {user_id} 的 {exchange} API密鑰")
            else:
                logger.info(f"[AccountWS] 使用直接提供的API密鑰，繞過數據庫加密/解密")
            
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
                
                # 顯示 API 密鑰長度以進行診斷
                key_length = len(api_key_data['api_key']) if api_key_data['api_key'] else 0
                secret_length = len(api_key_data['api_secret']) if api_key_data['api_secret'] else 0
                logger.debug(f"[AccountWS] 最終使用的API密鑰長度: {key_length}, API密鑰密碼長度: {secret_length}")
                
                # 檢查API密鑰格式，提供更多診斷信息
                if key_length < 10 or secret_length < 10:
                    logger.warning(f"[AccountWS] API密鑰長度異常，可能解密有問題: key={key_length}, secret={secret_length}")
                
                # 檢查是否包含控制字符或不可打印字符
                if api_key_data['api_key'] and any(c not in string.printable for c in api_key_data['api_key']):
                    logger.warning("[AccountWS] API密鑰包含不可打印字符，可能解密有問題")
                if api_key_data['api_secret'] and any(c not in string.printable for c in api_key_data['api_secret']):
                    logger.warning("[AccountWS] API密鑰密碼包含不可打印字符，可能解密有問題")
            
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
                    logger.info(f"[AccountWS] 從連接管理器獲取連接 - 用戶ID:{user_id}, 是新連接:{is_new}")
                else:
                    # 直接API模式下，創建新連接
                    binance_client, is_new = await exchange_connection_manager.get_or_create_connection(
                        api_key_data["api_key"], 
                        api_key_data["api_secret"], 
                        exchange, 
                        user_id=user_id
                    )
                    logger.info(f"[AccountWS] 直接API模式：從連接管理器創建連接 - 用戶ID:{user_id}, 是新連接:{is_new}")
                
                # 確認連接有效
                if not binance_client.is_connected():
                    logger.warning(f"[AccountWS] 連接管理器提供的連接已斷開，嘗試重新連接")
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
                logger.info(f"[AccountWS] 發送初始帳戶數據成功 - 用戶:{user_id}")
                
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
                                logger.info(f"[AccountWS] 收到刷新請求 - 用戶:{user_id}")
                                
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
                                logger.info(f"[AccountWS] 發送刷新帳戶數據成功 - 用戶:{user_id}")
                            
                            elif message_type == "place_order":
                                # 下單請求
                                logger.info(f"[AccountWS] 收到下單請求 - 用戶:{user_id}")
                                
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
                                    logger.info(f"[AccountWS] 下單成功 - 用戶:{user_id}, 訂單ID:{result.get('orderId')}")
                                    
                                except Exception as e:
                                    # 下單失敗，返回錯誤信息
                                    await websocket.send_json({
                                        "type": "order_response",
                                        "success": False,
                                        "message": str(e),
                                        "request_id": msg.get("request_id")
                                    })
                                    logger.error(f"[AccountWS] 下單失敗 - 用戶:{user_id}, 錯誤:{str(e)}")
                            
                            elif message_type == "cancel_order":
                                # 取消訂單請求
                                logger.info(f"[AccountWS] 收到取消訂單請求 - 用戶:{user_id}")
                                
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
                                    logger.info(f"[AccountWS] 取消訂單成功 - 用戶:{user_id}, 訂單ID:{order_id}")
                                    
                                except Exception as e:
                                    # 取消訂單失敗，返回錯誤信息
                                    await websocket.send_json({
                                        "type": "cancel_response",
                                        "success": False,
                                        "message": str(e),
                                        "request_id": msg.get("request_id")
                                    })
                                    logger.error(f"[AccountWS] 取消訂單失敗 - 用戶:{user_id}, 錯誤:{str(e)}")
                            
                            elif message_type == "ping":
                                # 客戶端發送的ping請求
                                logger.debug(f"[AccountWS] 收到ping請求 - 用戶:{user_id}")
                                await websocket.send_json({"type": "pong"})
                            
                            else:
                                # 未知消息類型
                                logger.warning(f"[AccountWS] 收到未知類型的消息 - 用戶:{user_id}, 類型:{message_type}")
                        
                        except json.JSONDecodeError:
                            # 非JSON格式消息
                            logger.warning(f"[AccountWS] 收到非JSON格式消息 - 用戶:{user_id}")
                    
                    except asyncio.TimeoutError:
                        # 沒有收到新消息，這是正常的，可以繼續其他操作
                        pass
                    except WebSocketDisconnect:
                        # 客戶端斷開連接
                        logger.info(f"[AccountWS] 客戶端斷開連接 - 用戶:{user_id}")
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
                                logger.debug(f"[AccountWS] 發現帳戶數據變化，已發送更新 - 用戶:{user_id}")
                            
                            last_data_refresh_time = current_time
                        
                        except Exception as e:
                            logger.error(f"[AccountWS] 刷新帳戶數據時出錯 - 用戶:{user_id}, 錯誤:{str(e)}")
                    
                    # 定期發送心跳
                    if current_time - last_heartbeat_time > heartbeat_interval:
                        await websocket.send_json({"type": "heartbeat"})
                        last_heartbeat_time = current_time
                        logger.debug(f"[AccountWS] 發送心跳 - 用戶:{user_id}")
            
            except Exception as e:
                logger.error(f"[AccountWS] 處理WebSocket連接時出錯 - 用戶:{user_id}, 錯誤:{str(e)}")
                await websocket.send_json({
                    "success": False,
                    "message": f"處理連接時出錯: {str(e)}"
                })
        
        finally:
            # 關閉數據庫會話
            db.close()
    
    except WebSocketDisconnect:
        logger.info("[AccountWS] 客戶端斷開連接")
    except Exception as e:
        logger.error(f"[AccountWS] WebSocket處理時出錯: {str(e)}")
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

async def get_account_data(exchange, api_key, api_secret, user_id=None):
    """
    使用API密鑰獲取帳戶數據
    
    Args:
        exchange: 交易所名稱
        api_key: API密鑰
        api_secret: API密鑰密碼
        user_id: 用戶ID（用於連接緩存）
        
    Returns:
        帳戶數據
    """
    logger.info(f"[AccountWS] 開始獲取帳戶數據: {exchange}")
    
    try:
        # 檢查API密鑰
        if not api_key or not api_secret:
            error_msg = "API密鑰或密鑰密碼為空"
            logger.error(f"[AccountWS] {error_msg}")
            raise ValueError(error_msg)
        
        if exchange.lower() == "binance":
            try:
                # 使用連接管理器獲取連接
                client, is_new = await exchange_connection_manager.get_or_create_connection(
                    api_key, api_secret, exchange, user_id=user_id
                )
                
                # 記錄客戶端來源
                if is_new:
                    logger.info(f"[AccountWS] 創建了新的幣安WebSocket客戶端")
                else:
                    logger.debug(f"[AccountWS] 重用現有的幣安WebSocket客戶端")
                
                # 確認客戶端連接狀態
                if not client.is_connected():
                    logger.warning(f"[AccountWS] 客戶端連接已斷開，嘗試重新連接")
                    connected = await client.connect()
                    if not connected:
                        logger.error(f"[AccountWS] 重新連接失敗，回退到REST API")
                    return await get_account_data_rest(exchange, api_key, api_secret)
                
                # 獲取帳戶資訊 - 使用現有連接
                account_info = await client.get_account_info()
                
                # 記錄收到的原始數據結構 (僅在日誌中記錄摘要信息，不記錄完整數據)
                logger.debug(f"[AccountWS] 已從幣安獲取帳戶數據，包含 {len(account_info.get('assets', []))} 個資產和 {len(account_info.get('positions', []))} 個持倉")
                
                # 格式化返回數據
                formatted_data = {
                    "balances": [],
                    "positions": [],
                    "api_type": "WebSocket API (Ed25519)", # 添加API類型標記
                    "raw_data": account_info  # 添加原始數據以便前端可以直接使用
                }
                
                # 處理賬戶資訊
                if isinstance(account_info, dict):
                    # 記錄數據結構中的關鍵字段，但不顯示具體值
                    top_level_keys = list(account_info.keys())
                    logger.debug(f"[AccountWS] 帳戶數據包含以下頂層字段: {', '.join(top_level_keys)}")
                    
                    # 處理餘額情況
                    if "assets" in account_info:
                        formatted_data["balances"] = account_info["assets"]
                        
                        # 提取總權益和可用餘額
                        for asset in account_info["assets"]:
                            if asset.get("asset") == "USDT":
                                formatted_data["totalWalletBalance"] = asset.get("walletBalance", "0")
                                formatted_data["availableBalance"] = asset.get("availableBalance", "0")
                                break
                    # 對現貨帳戶的處理
                    elif "balances" in account_info:
                        formatted_data["balances"] = [
                            {
                                "asset": balance.get("asset", ""),
                                "walletBalance": balance.get("free", "0"),
                                "availableBalance": balance.get("free", "0"),
                                "locked": balance.get("locked", "0")
                            }
                            for balance in account_info["balances"]
                            if float(balance.get("free", 0)) > 0 or float(balance.get("locked", 0)) > 0
                        ]
                        
                    # 處理持倉
                    if "positions" in account_info:
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
                logger.error(f"[AccountWS] 使用WebSocket獲取幣安帳戶數據時出錯: {str(e)}")
                import traceback
                logger.error(f"[AccountWS] 詳細錯誤: {traceback.format_exc()}")
                # 如果WebSocket方式失敗，回退到REST API方式
                logger.info(f"[AccountWS] 回退到使用REST API獲取幣安帳戶數據")
                return await get_account_data_rest(exchange, api_key, api_secret)
                
        elif exchange.lower() == "bitget" or exchange.lower() == "okx":
            # 這些交易所仍使用原始的REST API方式
            return await get_account_data_rest(exchange, api_key, api_secret)
        else:
            raise Exception(f"不支持的交易所: {exchange}")
            
    except Exception as e:
        logger.error(f"[AccountWS] 獲取帳戶數據時出錯: {str(e)}")
        import traceback
        trace = traceback.format_exc()
        logger.error(trace)
        raise Exception(f"獲取帳戶數據時出錯: {str(e)}")

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
    # 查詢當前用戶的交易所 API 密鑰
    exchanges = db.query(ExchangeAPI.exchange).filter(
        ExchangeAPI.user_id == current_user.id
    ).distinct().all()
    
    # 將查詢結果轉換為列表
    exchange_list = [item[0] for item in exchanges]
    
    return exchange_list
