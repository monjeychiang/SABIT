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
import string  # 新增：用於字符處理
import random

from ...db.database import get_db
from ...schemas.trading import ExchangeEnum
from ...db.models import User, ExchangeAPI
from ...core.security import get_current_user, get_current_active_user, decrypt_api_key

router = APIRouter()
logger = logging.getLogger(__name__)

# WebSocket客戶端緩存，以用戶ID為鍵
ws_clients = {}

# 新增函數：獲取或創建WebSocket客戶端
async def get_or_create_ws_client(api_key, api_secret, exchange="binance", testnet=False, user_id=None):
    """
    獲取或創建WebSocket客戶端，實現客戶端重用
    
    Args:
        api_key: API密鑰
        api_secret: API密鑰密碼
        exchange: 交易所名稱
        testnet: 是否使用測試網
        user_id: 用戶ID，用於緩存鍵
        
    Returns:
        client: WebSocket客戶端實例
        is_new: 是否為新創建的客戶端
    """
    # 如果沒有提供用戶ID，使用api_key的哈希作為緩存鍵
    cache_key = user_id if user_id else f"{exchange}_{api_key[:8]}_{testnet}"
    
    # 檢查緩存中是否有可用的客戶端
    if cache_key in ws_clients:
        client = ws_clients[cache_key]
        
        # 檢查客戶端是否仍然連接
        if await client.is_connected():
            logger.debug(f"[AccountWS] 使用已有的WebSocket客戶端 - key:{cache_key}")
            
            # 更新最後活動時間，確保客戶端不會被閒置回收
            client.last_activity_time = time.time()
            
            # 發送一個ping來確保連接活躍
            try:
                await client.ping()
                logger.debug(f"[AccountWS] 發送ping以保持連接活躍 - key:{cache_key}")
            except Exception as e:
                logger.warning(f"[AccountWS] 無法發送ping，嘗試重新連接 - key:{cache_key}, error:{str(e)}")
                # 如果ping失敗，關閉舊連接並建立新連接
                try:
                    await client.disconnect()
                except:
                    pass
                del ws_clients[cache_key]
                # 後續代碼會創建新連接
            else:
                return client, False
        else:
            # 如果連接已斷開，從緩存中移除
            logger.debug(f"[AccountWS] 客戶端連接已斷開，將創建新連接 - key:{cache_key}")
            try:
                await client.disconnect()
            except:
                pass
            del ws_clients[cache_key]
    
    # 創建新的客戶端
    logger.info(f"[AccountWS] 創建新的WebSocket客戶端 - exchange:{exchange}, testnet:{testnet}")
    
    if exchange.lower() == "binance":
        from backend.utils.binance_ws_client import BinanceWebSocketClient
        # 調整配置參數以確保長連接
        client = BinanceWebSocketClient(
            api_key, 
            api_secret, 
            testnet=testnet,
            # 配置參數，根據幣安文檔設置
            # 不需主動ping，而是響應服務器的ping
            # 服務器每3分鐘發送一次ping，10分鐘內需要回應pong
            ping_interval=None,  # 不主動發送ping，只響應服務器的ping
            ping_timeout=None,   # 不使用主動ping機制
            close_timeout=30,    # 關閉超時時間30秒
            max_queue_size=1000,  # 增加消息隊列大小
            max_reconnect_attempts=10  # 增加最大重連嘗試次數
        )
        
        # 添加額外的連接時間戳屬性
        client.last_activity_time = time.time()
    else:
        raise ValueError(f"不支持的交易所: {exchange}")
    
    # 連接到WebSocket API
    connected = await client.connect()
    
    if not connected:
        raise Exception(f"連接到{exchange} WebSocket API失敗")
    
    # 儲存到緩存中
    ws_clients[cache_key] = client
    
    # 啟動心跳任務，確保連接不會因為長時間閒置而斷開
    asyncio.create_task(_maintain_client_heartbeat(client, cache_key))
    
    logger.info(f"[AccountWS] 成功創建並連接WebSocket客戶端 - key:{cache_key}")
    
    # 清理過期的客戶端 (如果緩存過大)
    if len(ws_clients) > 100:  # 設置一個合理的上限
        # 按上次活動時間排序，移除最久未活動的客戶端
        inactive_clients = sorted(
            [(k, c.last_activity_time) for k, c in ws_clients.items() if k != cache_key],
            key=lambda x: x[1]
        )
        
        # 移除最早的10個
        for key, _ in inactive_clients[:10]:
            try:
                await ws_clients[key].disconnect()
                logger.debug(f"[AccountWS] 移除閒置的WebSocket客戶端 - key:{key}")
            except:
                pass
            del ws_clients[key]
    
    return client, True

# 新增心跳維護函數，用於長連接保持
async def _maintain_client_heartbeat(client, cache_key, heartbeat_interval=30):
    """
    維護客戶端心跳，確保長連接不斷開
    
    根據幣安文檔，服務器會每3分鐘發送一次ping frame，客戶端只需回應pong即可。
    本函數不再主動發送ping，而是監控連接狀態，確保WebSocket連接保持活躍。
    
    Args:
        client: WebSocket客戶端
        cache_key: 緩存鍵
        heartbeat_interval: 心跳檢查間隔（秒）
    """
    try:
        while cache_key in ws_clients:
            # 檢查客戶端是否已從緩存中移除
            if cache_key not in ws_clients:
                logger.debug(f"[AccountWS] 客戶端已從緩存中移除，停止心跳監控 - key:{cache_key}")
                break
                
            # 定期檢查連接狀態，但不發送ping (幣安服務器會自動每3分鐘發送ping)
            current_time = time.time()
            if hasattr(client, 'last_activity_time'):
                # 檢查上次活動時間，如果超過一定時間沒有活動，檢查連接狀態
                if current_time - client.last_activity_time > heartbeat_interval:
                    # 只檢查連接狀態，不發送ping
                    try:
                        if not await client.is_connected():
                            logger.info(f"[AccountWS] 檢測到連接已斷開，嘗試重新連接 - key:{cache_key}")
                            reconnected = await client.reconnect()
                            if reconnected:
                                logger.info(f"[AccountWS] 重新連接成功 - key:{cache_key}")
                                client.last_activity_time = time.time()
                            else:
                                logger.error(f"[AccountWS] 重新連接失敗，將從緩存中移除 - key:{cache_key}")
                                if cache_key in ws_clients:
                                    del ws_clients[cache_key]
                                break
                        else:
                            # 連接正常，更新最後活動時間
                            logger.debug(f"[AccountWS] 連接狀態正常 - key:{cache_key}")
                            client.last_activity_time = time.time()
                    except Exception as e:
                        logger.error(f"[AccountWS] 檢查連接狀態出錯 - key:{cache_key}, error:{str(e)}")
                        # 如果檢查過程中出錯，嘗試重新連接
                        try:
                            logger.info(f"[AccountWS] 嘗試重新連接 - key:{cache_key}")
                            reconnected = await client.reconnect()
                            if reconnected:
                                logger.info(f"[AccountWS] 重新連接成功 - key:{cache_key}")
                                client.last_activity_time = time.time()
                            else:
                                logger.error(f"[AccountWS] 重新連接失敗，將從緩存中移除 - key:{cache_key}")
                                if cache_key in ws_clients:
                                    del ws_clients[cache_key]
                                break
                        except Exception as re:
                            logger.error(f"[AccountWS] 重新連接過程中出錯 - key:{cache_key}, error:{str(re)}")
                            if cache_key in ws_clients:
                                del ws_clients[cache_key]
                            break
            
            # 等待下一次檢查
            await asyncio.sleep(heartbeat_interval)
    except Exception as e:
        # 捕獲並記錄任何未處理的異常
        logger.error(f"[AccountWS] 心跳維護任務發生未預期錯誤: {str(e)}")
    finally:
        # 無論如何確保在任務結束時記錄
        logger.info(f"[AccountWS] 心跳維護任務結束 - key:{cache_key}")
        # 如果客戶端仍在緩存中但任務結束，標記為可能不活躍
        if cache_key in ws_clients:
            logger.warning(f"[AccountWS] 心跳任務結束但客戶端仍在緩存中 - key:{cache_key}")
            # 不要在這裡移除，讓其他機制處理斷線

# 新增函數：釋放WebSocket客戶端資源
async def release_ws_client(client, force_disconnect=False, cache_key=None):
    """
    釋放WebSocket客戶端資源
    
    Args:
        client: WebSocket客戶端實例
        force_disconnect: 是否強制斷開連接
        cache_key: 緩存鍵，如果提供則從緩存中移除
    """
    if force_disconnect:
        try:
            await client.disconnect()
            logger.debug("[AccountWS] 已強制斷開WebSocket連接")
        except Exception as e:
            logger.error(f"[AccountWS] 斷開WebSocket連接時出錯: {str(e)}")
    
    # 如果提供了緩存鍵，從緩存中移除
    if cache_key and cache_key in ws_clients:
        del ws_clients[cache_key]
        logger.debug(f"[AccountWS] 從緩存中移除WebSocket客戶端 - key:{cache_key}")

# WebSocket端點獲取合約賬戶信息
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
                encrypted_key_length = len(api_key.api_key) if api_key.api_key else 0
                encrypted_secret_length = len(api_key.api_secret) if api_key.api_secret else 0
                logger.debug(f"[AccountWS] 加密的API密鑰長度: {encrypted_key_length}, 加密的API密鑰密碼長度: {encrypted_secret_length}")
                
                # 解密API密鑰
                decrypted_key = decrypt_api_key(api_key.api_key)
                decrypted_secret = decrypt_api_key(api_key.api_secret)
                
                # 檢查解密結果
                if not decrypted_key or not decrypted_secret:
                    error_msg = "API密鑰解密失敗"
                    logger.error(f"[AccountWS] {error_msg}")
                    await websocket.send_json({"success": False, "message": error_msg})
                    return
                
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
            
            # 首次獲取帳戶數據
            account_data = await get_account_data(exchange, api_key_data["api_key"], api_key_data["api_secret"])
            
            # 更新緩存
            last_account_data = account_data
        
            # 發送帳戶數據
            await websocket.send_json({
                "success": True,
                "data": account_data,
                "update_type": "full",  # 標記為完整更新
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(f"[AccountWS] 已成功發送 {exchange} 帳戶數據給用戶 {user_id}")
            
            # 使用無限循環保持連接（長期連接）
            # 追蹤最後活動時間
            last_activity_time = time.time()
            last_data_update = time.time()
            update_interval = 60  # 每60秒更新一次數據
            
            while True:
                try:
                    # 使用 wait_for 設定超時，避免無限等待
                    # 如果在3秒內沒有消息，則繼續循環檢查是否需要更新數據
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=3.0)
                    
                    # 更新最後活動時間
                    last_activity_time = time.time()
                    
                    # 處理來自前端的消息
                    try:
                        message = json.loads(data)
                        # 不記錄可能包含敏感信息的完整消息內容
                        logger.debug(f"[AccountWS] 收到消息類型: {message.get('type')} - user:{user_id}")
                        
                        # 處理 ping 消息
                        if message.get("type") == "ping":
                            logger.debug(f"[AccountWS] 收到PING - user:{user_id}")
                            await websocket.send_json({"type": "pong", "timestamp": time.time()})
                        
                        # 處理刷新請求
                        elif message.get("type") == "refresh":
                            logger.info(f"[AccountWS] 收到刷新請求 - user:{user_id}")
                            
                            # 獲取更新模式，默認為 "diff"
                            update_mode = message.get("update_mode", "diff")
                            
                            # 如果是強制刷新，則忽略緩存
                            force_refresh = message.get("force_refresh", False)
                            
                            # 重新獲取帳戶數據
                            try:
                                # 重用之前的連接或創建新連接
                                new_account_data = await get_account_data(exchange, api_key_data["api_key"], api_key_data["api_secret"])
                                last_data_update = time.time()
                                
                                # 檢查數據是否有變化
                                has_changes = force_refresh or not last_account_data or _has_account_data_changed(new_account_data, last_account_data)
                                
                                if has_changes:
                                    if update_mode == "diff" and last_account_data:
                                        # 計算差異
                                        diff_data = _compute_account_data_diff(new_account_data, last_account_data)
                                        
                                        # 發送差異數據
                                        await websocket.send_json({
                                            "success": True,
                                            "data": diff_data,
                                            "update_type": "diff",  # 標記為差異更新
                                            "timestamp": datetime.now().isoformat()
                                        })
                                        logger.info(f"[AccountWS] 已發送差異更新的帳戶數據 - user:{user_id}")
                                    else:
                                        # 發送完整數據
                                        await websocket.send_json({
                                            "success": True,
                                            "data": new_account_data,
                                            "update_type": "full",  # 標記為完整更新
                                            "timestamp": datetime.now().isoformat()
                                        })
                                        logger.info(f"[AccountWS] 已發送完整更新的帳戶數據 - user:{user_id}")
                                    
                                    # 更新緩存
                                    last_account_data = new_account_data
                                else:
                                    # 沒有變化時，只發送狀態訊息
                                    await websocket.send_json({
                                        "success": True,
                                        "message": "資料未發生變化",
                                        "update_type": "none",
                                        "timestamp": datetime.now().isoformat()
                                    })
                                    logger.info(f"[AccountWS] 資料未發生變化，無需更新 - user:{user_id}")
                            except Exception as e:
                                logger.error(f"[AccountWS] 刷新數據時出錯: {str(e)}")
                                await websocket.send_json({
                                    "success": False,
                                    "error": f"刷新數據時出錯: {str(e)}",
                                    "timestamp": datetime.now().isoformat()
                                })
                        
                        # 處理下單請求
                        elif message.get("type") == "place_order":
                            logger.info(f"[AccountWS] 收到下單請求 - user:{user_id}")
                            
                            # 獲取訂單參數
                            order_params = message.get("order_params", {})
                            
                            # 記錄簡化的訂單參數，僅包含關鍵信息
                            if order_params:
                                log_params = {
                                    "symbol": order_params.get("symbol"),
                                    "side": order_params.get("side"),
                                    "type": order_params.get("type"),
                                    "quantity": order_params.get("quantity"),
                                    "price": order_params.get("price") if order_params.get("type") == "LIMIT" else None
                                }
                                logger.debug(f"[AccountWS] 訂單參數: {log_params}")
                            else:
                                logger.warning(f"[AccountWS] 收到空的訂單參數 - user:{user_id}")
                            
                            # 驗證必要的訂單參數
                            required_params = ["symbol", "side", "type"]  # 最基本的必要參數
                            missing_params = [param for param in required_params if param not in order_params]
                            
                            if not order_params or missing_params:
                                error_msg = f"缺少必要的訂單參數: {', '.join(missing_params) if missing_params else '未知參數'}"
                                logger.warning(f"[AccountWS] {error_msg} - user:{user_id}")
                                await websocket.send_json({
                                    "type": "order_response",
                                    "success": False,
                                    "error": error_msg
                                })
                                continue
                            
                            # 下單
                            try:
                                # 使用合適的方法處理下單請求
                                if exchange.lower() == "binance":
                                    # 優先使用 WebSocket API 下單，傳入用戶ID用於客戶端緩存
                                    order_result = await place_order_via_websocket(
                                        exchange, api_key_data["api_key"], api_key_data["api_secret"], order_params, user_id
                                    )
                                else:
                                    # 其他交易所使用 REST API
                                    order_result = await place_order_via_rest(
                                        exchange, api_key_data["api_key"], api_key_data["api_secret"], order_params
                                    )
                                
                                # 記錄下單結果摘要，不記錄完整回應
                                order_id = order_result.get("orderId", "無")
                                status = order_result.get("status", "未知")
                                logger.info(f"[AccountWS] 下單成功 - user:{user_id}, orderId:{order_id}, status:{status}")
                                
                                # 發送下單結果
                                await websocket.send_json({
                                    "success": True,
                                    "type": "order_result",
                                    "data": order_result,
                                    "timestamp": datetime.now().isoformat()
                                })
                                
                                # 下單後重新獲取最新帳戶數據
                                try:
                                    new_account_data = await get_account_data(exchange, api_key_data["api_key"], api_key_data["api_secret"])
                                    last_data_update = time.time()
                                    
                                    # 檢查數據是否有變化
                                    has_changes = not last_account_data or _has_account_data_changed(new_account_data, last_account_data)
                                    
                                    if has_changes:
                                        # 計算差異並發送
                                        diff_data = _compute_account_data_diff(new_account_data, last_account_data)
                                        
                                        # 發送最新帳戶數據
                                        await websocket.send_json({
                                            "success": True,
                                            "type": "account_update",
                                            "data": diff_data,
                                            "update_type": "diff",  # 標記為差異更新
                                            "timestamp": datetime.now().isoformat()
                                        })
                                        logger.info(f"[AccountWS] 下單後已更新帳戶數據 - user:{user_id}")
                                        
                                        # 更新緩存
                                        last_account_data = new_account_data
                                except Exception as e:
                                    logger.error(f"[AccountWS] 下單後更新帳戶數據時出錯: {str(e)}")
                            except Exception as e:
                                error_msg = f"下單時出錯: {str(e)}"
                                logger.error(f"[AccountWS] {error_msg} - user:{user_id}")
                                await websocket.send_json({
                                    "success": False,
                                    "type": "order_result",
                                    "error": error_msg,
                                    "timestamp": datetime.now().isoformat()
                                })
                        
                        # 處理取消訂單請求
                        elif message.get("type") == "cancel_order":
                            logger.info(f"[AccountWS] 收到取消訂單請求 - user:{user_id}")
                            
                            # 獲取取消訂單參數
                            cancel_params = message.get("params", {})
                            
                            # 記錄簡化的取消訂單參數
                            if cancel_params:
                                log_params = {
                                    "symbol": cancel_params.get("symbol"),
                                    "orderId": cancel_params.get("orderId", "無"),
                                    "clientOrderId": cancel_params.get("origClientOrderId", "無")
                                }
                                logger.debug(f"[AccountWS] 取消訂單參數: {log_params}")
                            else:
                                logger.warning(f"[AccountWS] 收到空的取消訂單參數 - user:{user_id}")
                            
                            # 檢查必要參數
                            if "symbol" not in cancel_params or ("orderId" not in cancel_params and "clientOrderId" not in cancel_params):
                                error_msg = "缺少必要的取消訂單參數"
                                logger.warning(f"[AccountWS] {error_msg} - user:{user_id}")
                                await websocket.send_json({
                                    "success": False,
                                    "error": error_msg,
                                    "timestamp": datetime.now().isoformat()
                                })
                                continue
                            
                            # 取消訂單
                            try:
                                # 使用合適的方法處理取消訂單請求
                                if exchange.lower() == "binance":
                                    # 優先使用 WebSocket API 取消訂單，傳入用戶ID用於客戶端緩存
                                    cancel_result = await cancel_order_via_websocket(
                                        exchange, api_key_data["api_key"], api_key_data["api_secret"], cancel_params, user_id
                                    )
                                else:
                                    # 其他交易所使用 REST API
                                    cancel_result = await cancel_order_via_rest(
                                        exchange, api_key_data["api_key"], api_key_data["api_secret"], cancel_params
                                    )
                                
                                # 記錄取消訂單結果摘要
                                order_id = cancel_result.get("orderId", "無")
                                status = cancel_result.get("status", "未知")
                                logger.info(f"[AccountWS] 取消訂單成功 - user:{user_id}, orderId:{order_id}, status:{status}")
                                
                                # 發送取消訂單結果
                                await websocket.send_json({
                                    "success": True,
                                    "type": "cancel_result",
                                    "data": cancel_result,
                                    "timestamp": datetime.now().isoformat()
                                })
                                
                                # 取消訂單後重新獲取最新帳戶數據
                                try:
                                    new_account_data = await get_account_data(exchange, api_key_data["api_key"], api_key_data["api_secret"])
                                    last_data_update = time.time()
                                    
                                    # 檢查數據是否有變化
                                    has_changes = not last_account_data or _has_account_data_changed(new_account_data, last_account_data)
                                    
                                    if has_changes:
                                        # 計算差異並發送
                                        diff_data = _compute_account_data_diff(new_account_data, last_account_data)
                                        
                                        # 發送最新帳戶數據
                                        await websocket.send_json({
                                            "success": True,
                                            "type": "account_update",
                                            "data": diff_data,
                                            "update_type": "diff",  # 標記為差異更新
                                            "timestamp": datetime.now().isoformat()
                                        })
                                        logger.info(f"[AccountWS] 取消訂單後已更新帳戶數據 - user:{user_id}")
                                        
                                        # 更新緩存
                                        last_account_data = new_account_data
                                except Exception as e:
                                    logger.error(f"[AccountWS] 取消訂單後更新帳戶數據時出錯: {str(e)}")
                            except Exception as e:
                                error_msg = f"取消訂單時出錯: {str(e)}"
                                logger.error(f"[AccountWS] {error_msg} - user:{user_id}")
                                await websocket.send_json({
                                    "success": False,
                                    "type": "cancel_result",
                                    "error": error_msg,
                                    "timestamp": datetime.now().isoformat()
                                })
                        
                        # 其他消息類型
                        else:
                            logger.warning(f"[AccountWS] 收到未知類型的消息: {message.get('type')} - user:{user_id}")
                    except json.JSONDecodeError:
                        logger.warning(f"[AccountWS] 收到非JSON格式消息: {data[:30]}... - user:{user_id}")
                    
                except asyncio.TimeoutError:
                    # 超時，檢查是否應該主動更新數據
                    current_time = time.time()
                    
                    # 如果超過更新間隔，主動更新數據
                    if current_time - last_data_update > update_interval:
                        try:
                            logger.info(f"[AccountWS] 定期更新帳戶數據 - user:{user_id}")
                            new_account_data = await get_account_data(exchange, api_key_data["api_key"], api_key_data["api_secret"])
                            last_data_update = current_time
                            
                            # 檢查數據是否有變化
                            has_changes = not last_account_data or _has_account_data_changed(new_account_data, last_account_data)
                            
                            if has_changes:
                                # 計算差異並發送
                                diff_data = _compute_account_data_diff(new_account_data, last_account_data)
                                
                                # 發送最新數據
                                await websocket.send_json({
                                    "success": True,
                                    "type": "account_update",
                                    "data": diff_data,
                                    "update_type": "diff",  # 標記為差異更新
                                    "timestamp": datetime.now().isoformat()
                                })
                                logger.info(f"[AccountWS] 已發送定期更新的帳戶數據 - user:{user_id}")
                                
                                # 更新緩存
                                last_account_data = new_account_data
                            else:
                                logger.debug(f"[AccountWS] 定期檢查：資料無變化 - user:{user_id}")
                        except Exception as e:
                            logger.error(f"[AccountWS] 定期更新數據時出錯: {str(e)}")
                    
                    # 檢查是否長時間無活動，應該發送ping來檢查連接
                    if current_time - last_activity_time > 30:  # 30秒無活動發送ping
                        try:
                            await websocket.send_json({"type": "ping"})
                            logger.debug(f"[AccountWS] 發送PING檢查 - user:{user_id}")
                        except Exception as e:
                            logger.error(f"[AccountWS] 發送PING時出錯，可能連接已斷開: {str(e)}")
                            break
                
                except WebSocketDisconnect:
                    logger.info(f"[AccountWS] WebSocket連接已斷開 - user:{user_id}")
                    break
                    
                except Exception as e:
                    logger.error(f"[AccountWS] 處理消息時發生錯誤: {str(e)}")
                    # 嘗試發送錯誤通知
                    try:
                        await websocket.send_json({
                            "success": False,
                            "error": f"處理消息時發生錯誤: {str(e)}",
                            "timestamp": datetime.now().isoformat()
                        })
                    except:
                        # 如果發送錯誤通知也失敗，可能連接已斷開
                        logger.error("[AccountWS] 無法發送錯誤通知，連接可能已斷開")
                        break
                    
        finally:
            # 確保數據庫會話被關閉
            db.close()
            
    except WebSocketDisconnect:
        logger.info(f"[AccountWS] WebSocket連接已被客戶端關閉")
    except Exception as e:
        logger.error(f"[AccountWS] 處理WebSocket時發生錯誤: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        try:
            await websocket.send_json({
                "success": False,
                "message": f"發生錯誤: {str(e)}",
                "error": traceback.format_exc()
            })
        except:
            pass
    finally:
        # 確保WebSocket連接被關閉
        try:
            await websocket.close()
            logger.info(f"[AccountWS] WebSocket連接已關閉")
        except:
            pass

@router.websocket("/test-websocket")
async def test_websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(None, description="用戶驗證token（可選）")
):
    """
    簡單的測試WebSocket端點，用於驗證WebSocket基本功能
    """
    # 先接受連接，然後再處理授權
    await websocket.accept()
    logger.info(f"[TestWS] 已接受WebSocket連接請求")
    
    try:
        # 如果提供了 token 進行簡單驗證（可選）
        if token:
            logger.info(f"[TestWS] 收到 token 參數，長度: {len(token)}")
            # 此處可以添加實際 token 驗證邏輯
            # 但為了簡單起見，不做實際驗證
        
        # 發送連接成功消息
        await websocket.send_text("連接成功")
        logger.info(f"[TestWS] 已發送成功連接消息")
        
        # 保持連接一段時間，以便客戶端可以接收到響應
        await asyncio.sleep(5)
    except Exception as e:
        logger.error(f"[TestWS] 測試WebSocket錯誤: {str(e)}")
    finally:
        logger.info(f"[TestWS] 關閉WebSocket連接")
        await websocket.close()

async def get_account_data(exchange, api_key, api_secret):
    """
    使用API密鑰獲取帳戶數據
    
    Args:
        exchange: 交易所名稱
        api_key: API密鑰
        api_secret: API密鑰密碼
        
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
                # 使用新的WebSocket客戶端獲取帳戶數據
                from backend.utils.binance_ws_client import BinanceWebSocketClient
                
                # 創建WebSocket客戶端
                # 檢查是否為測試環境
                test_mode = False  # 可以從配置或環境變量中獲取
                client = BinanceWebSocketClient(api_key, api_secret, testnet=test_mode)
                
                # 連接到WebSocket API
                connected = await client.connect()
                
                if not connected:
                    # 提供更具體的錯誤信息
                    error_reason = """
                    認證失敗，可能原因：
                    1. API密鑰不正確或過期
                    2. API密鑰沒有WebSocket權限
                    3. 使用了HMAC-SHA256密鑰而非Ed25519密鑰
                    
                    幣安WebSocket API需要使用Ed25519密鑰，您需要在幣安API管理界面專門創建WebSocket API密鑰。
                    
                    創建步驟：
                    1. 登錄幣安賬戶
                    2. 進入API管理頁面
                    3. 選擇創建API密鑰，確保選擇Ed25519密鑰類型
                    4. 勾選WebSocket API權限
                    5. 完成安全驗證
                    
                    參考文檔: https://developers.binance.com/docs/binance-trading-api/websocket-api
                    """
                    logger.error(f"[AccountWS] 連接到幣安WebSocket API失敗: {error_reason}")
                    
                    # 嘗試檢測API密鑰是否為Ed25519格式
                    try:
                        import base64
                        try:
                            decoded = base64.b64decode(api_secret)
                            key_length = len(decoded)
                            if key_length != 32:
                                logger.warning(f"[AccountWS] API密鑰長度 ({key_length}) 不是標準的Ed25519密鑰長度(32字節)")
                        except Exception:
                            logger.warning("[AccountWS] 無法將API密鑰解碼為Base64格式，可能不是Ed25519密鑰")
                    except Exception as e:
                        logger.error(f"[AccountWS] 檢測API密鑰格式時出錯: {e}")
                    
                    # 回退到REST API
                    logger.info(f"[AccountWS] 回退到使用REST API獲取幣安帳戶數據")
                    return await get_account_data_rest(exchange, api_key, api_secret)
                
                # 獲取帳戶資訊
                account_info = await client.get_account_info()
                
                # 不再立即斷開連線，讓 client 對象繼續運行
                # await client.disconnect()  # 移除此行，保持連接
                
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

# 原始的REST API方式獲取帳戶數據的函數
async def get_account_data_rest(exchange, api_key, api_secret):
    """
    使用REST API獲取帳戶數據（舊方法，作為備份）
    """
    logger.info(f"[AccountWS] 開始使用REST API獲取帳戶數據: {exchange}")
    
    try:
        # 檢查API密鑰
        if not api_key or not api_secret:
            error_msg = "API密鑰或密鑰密碼為空"
            logger.error(f"[AccountWS] {error_msg}")
            raise ValueError(error_msg)
        
        # 處理不同交易所
        if exchange.lower() == "binance":
            endpoint = "/fapi/v2/account"
            
            # 生成簽名
            timestamp = int(time.time() * 1000)
            query_string = f"timestamp={timestamp}"
            
            # 使用HMAC SHA256簽名
            signature = hmac.new(
                api_secret.encode('utf-8'),
                query_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # 構建URL
            base_url = "https://fapi.binance.com"
            
            # 檢查是否為測試環境
            test_mode = False  # 可以從配置或環境變量中獲取
            if test_mode:
                base_url = "https://testnet.binancefuture.com"
            
            url = f"{base_url}{endpoint}?{query_string}&signature={signature}"
            
            # 發送請求
            headers = {
                'X-MBX-APIKEY': api_key
            }
            
            # 使用aiohttp進行非阻塞HTTP請求
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # 只記錄返回數據的摘要信息，不記錄完整數據
                        logger.debug(f"[AccountWS] REST API返回數據: 資產數量={len(data.get('assets', []))}, 持倉數量={len(data.get('positions', []))}")
                        
                        # 格式化返回數據
                        formatted_data = {
                            "balances": [],
                            "positions": [],
                            "api_type": "REST API (HMAC-SHA256)"  # 添加API類型標記
                        }
                        
                        # 處理餘額
                        if "assets" in data:
                            formatted_data["balances"] = data["assets"]
                            
                            # 提取總權益和可用餘額
                            for asset in data["assets"]:
                                if asset.get("asset") == "USDT":
                                    formatted_data["totalWalletBalance"] = asset.get("walletBalance", "0")
                                    formatted_data["availableBalance"] = asset.get("availableBalance", "0")
                                    break
                        
                        # 處理持倉
                        if "positions" in data:
                            formatted_data["positions"] = [
                                pos for pos in data["positions"] 
                                if float(pos.get("positionAmt", 0)) != 0
                            ]
                            
                            # 計算未實現盈虧總和
                            total_unrealized_profit = sum(
                                float(pos.get("unrealizedProfit", 0)) 
                                for pos in data["positions"]
                            )
                            formatted_data["totalUnrealizedProfit"] = str(total_unrealized_profit)
                        
                        return formatted_data
                    else:
                        error_data = await response.text()
                        logger.error(f"[AccountWS] 幣安API返回錯誤: {response.status} - {error_data}")
                        raise Exception(f"獲取帳戶數據時API返回錯誤: {response.status} - {error_data}")
                        
        # 其他交易所實現...
        elif exchange.lower() == "bitget":
            # Bitget實現
            pass
        elif exchange.lower() == "okx":
            # OKX實現
            pass
        else:
            raise Exception(f"不支持的交易所: {exchange}")
    
    except Exception as e:
        logger.error(f"[AccountWS] 使用REST API獲取帳戶數據時出錯: {str(e)}")
        import traceback
        trace = traceback.format_exc()
        logger.error(trace)
        raise

@router.post("/api-keys/diagnostic", response_model=dict)
async def api_key_diagnostic(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    API密鑰加密/解密診斷工具
    
    用於診斷API密鑰加密和解密過程中的問題。
    此端點將接收明文API密鑰，執行加密和解密操作，然後返回各步驟的結果。
    僅供管理員或技術人員使用，幫助排查加密/解密相關問題。
    
    請求體示例:
    ```json
    {
        "api_key": "your_api_key",
        "api_secret": "your_api_secret"
    }
    ```
    """
    # 只允許管理員或開發環境使用
    import os
    env = os.getenv("ENVIRONMENT", "development")
    if not current_user.is_admin and env != "development":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="僅限管理員或開發環境使用此診斷工具"
        )
    
    # 解析請求數據
    try:
        data = await request.json()
        original_api_key = data.get("api_key", "")
        original_api_secret = data.get("api_secret", "")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"無法解析請求數據: {str(e)}"
        )
    
    # 導入加密/解密函數
    from ...core.security import encrypt_api_key, decrypt_api_key, clean_api_key, standardize_api_key
    
    # 記錄原始數據（不記錄實際值，只記錄長度）
    results = {
        "original": {
            "api_key_length": len(original_api_key),
            "api_secret_length": len(original_api_secret)
        },
        "cleaned": {},
        "standardized": {},
        "encrypted": {},
        "decrypted": {},
        "final": {}
    }
    
    # 第1步：基本清理
    cleaned_api_key = clean_api_key(original_api_key)
    cleaned_api_secret = clean_api_key(original_api_secret)
    results["cleaned"] = {
        "api_key_length": len(cleaned_api_key) if cleaned_api_key else 0,
        "api_secret_length": len(cleaned_api_secret) if cleaned_api_secret else 0,
        "api_key_changed": cleaned_api_key != original_api_key,
        "api_secret_changed": cleaned_api_secret != original_api_secret
    }
    
    # 第2步：標準化
    standardized_api_key = standardize_api_key(original_api_key)
    standardized_api_secret = standardize_api_key(original_api_secret)
    results["standardized"] = {
        "api_key_length": len(standardized_api_key) if standardized_api_key else 0,
        "api_secret_length": len(standardized_api_secret) if standardized_api_secret else 0,
        "api_key_changed": standardized_api_key != original_api_key,
        "api_secret_changed": standardized_api_secret != original_api_secret
    }
    
    # 第3步：加密
    encrypted_api_key = encrypt_api_key(original_api_key)
    encrypted_api_secret = encrypt_api_key(original_api_secret)
    results["encrypted"] = {
        "api_key_length": len(encrypted_api_key) if encrypted_api_key else 0,
        "api_secret_length": len(encrypted_api_secret) if encrypted_api_secret else 0,
        "api_key_success": encrypted_api_key is not None,
        "api_secret_success": encrypted_api_secret is not None
    }
    
    # 第4步：解密
    decrypted_api_key = decrypt_api_key(encrypted_api_key) if encrypted_api_key else None
    decrypted_api_secret = decrypt_api_key(encrypted_api_secret) if encrypted_api_secret else None
    results["decrypted"] = {
        "api_key_length": len(decrypted_api_key) if decrypted_api_key else 0,
        "api_secret_length": len(decrypted_api_secret) if decrypted_api_secret else 0,
        "api_key_success": decrypted_api_key is not None,
        "api_secret_success": decrypted_api_secret is not None,
        "api_key_matches_original": decrypted_api_key == original_api_key,
        "api_secret_matches_original": decrypted_api_secret == original_api_secret,
        "api_key_matches_standardized": decrypted_api_key == standardized_api_key,
        "api_secret_matches_standardized": decrypted_api_secret == standardized_api_secret
    }
    
    # 第5步：最終結果（用於API調用的格式）
    final_api_key = decrypted_api_key
    final_api_secret = decrypted_api_secret
    results["final"] = {
        "api_key_length": len(final_api_key) if final_api_key else 0,
        "api_secret_length": len(final_api_secret) if final_api_secret else 0,
        "contains_non_printable_api_key": final_api_key and any(c not in string.printable for c in final_api_key),
        "contains_non_printable_api_secret": final_api_secret and any(c not in string.printable for c in final_api_secret),
        "overall_success": (
            final_api_key is not None and
            final_api_secret is not None and
            len(final_api_key) > 10 and
            len(final_api_secret) > 10
        )
    }
    
    return results 

# 添加一個新的端點，用於檢查用戶擁有哪些交易所的API密鑰
@router.get("/api-keys/exchanges", response_model=list)
async def get_user_exchanges(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    獲取用戶已配置API密鑰的交易所列表
    
    返回一個交易所名稱的列表，用戶已為這些交易所配置了API密鑰。
    前端可以使用此端點來檢查用戶是否有特定交易所的API密鑰，
    避免不必要的WebSocket連接嘗試。
    """
    try:
        # 查詢用戶已經配置的所有交易所API密鑰
        user_exchanges = db.query(ExchangeAPI.exchange).filter(
            ExchangeAPI.user_id == current_user.id
        ).all()
        
        # 將結果轉換為簡單的交易所名稱列表
        exchange_list = [item[0] for item in user_exchanges]
        
        return exchange_list
    except Exception as e:
        logger.error(f"獲取用戶交易所列表時發生錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="獲取交易所列表失敗"
        ) 

# 修改下單函數，使用緩存的客戶端
async def place_order_via_websocket(exchange, api_key, api_secret, order_params, user_id=None):
    """
    使用API密鑰通過WebSocket API下單
    
    Args:
        exchange: 交易所名稱
        api_key: API密鑰
        api_secret: API密鑰密碼
        order_params: 訂單參數
        user_id: 用戶ID，用於客戶端緩存
            
    Returns:
        訂單結果
    """
    logger.info(f"[AccountWS] 開始下單操作(WebSocket): {exchange}")
    
    try:
        # 確保 API 密鑰格式正確
        if not api_key or not api_secret:
            error_msg = "API密鑰或密鑰密碼為空"
            logger.error(f"[AccountWS] {error_msg}")
            raise ValueError(error_msg)
        
        # 檢查必要參數
        required_params = ["symbol", "side", "type", "quantity"]
        
        # LIMIT訂單還需要price和timeInForce
        if order_params.get("type") == "LIMIT":
            if "price" not in order_params:
                raise ValueError("缺少必要參數: price (限價單需要價格)")
            if "timeInForce" not in order_params:
                # 設定預設的timeInForce為GTC
                order_params["timeInForce"] = "GTC"
            
        for param in required_params:
            if param not in order_params:
                raise ValueError(f"缺少必要參數: {param}")
        
        # 處理不同交易所
        if exchange.lower() == "binance":
            try:
                # 檢查是否需要使用測試網
                test_mode = False
                if "test" in order_params and (order_params["test"] == "true" or order_params["test"] is True or order_params["test"] == "TRUE"):
                    test_mode = True
                    logger.info(f"[AccountWS] 使用測試網模式下單")
                
                # 獲取或創建WebSocket客戶端
                client, is_new = await get_or_create_ws_client(
                    api_key, api_secret, exchange, test_mode, user_id
                )
                
                # 從order_params中提取必要的參數
                symbol = order_params["symbol"]
                side = order_params["side"]
                order_type = order_params["type"]  # 注意，這裡提取了type參數作為order_type
                
                # 下單
                result = await client.place_order(side, order_type, order_params)
                
                # 不再每次操作後斷開連接，保持連接以便重用
                
                logger.info(f"[AccountWS] 下單成功: {result.get('orderId')}")
                return result
                
            except Exception as e:
                logger.error(f"[AccountWS] 使用WebSocket下單時出錯: {str(e)}")
                # 如果WebSocket方式失敗，回退到REST API方式
                logger.info(f"[AccountWS] 回退到使用REST API下單")
                return await place_order_via_rest(exchange, api_key, api_secret, order_params)
        else:
            # 其他交易所實現...
            raise Exception(f"不支持的交易所: {exchange}")
    
    except Exception as e:
        logger.error(f"[AccountWS] 下單時發生錯誤: {str(e)}")
        import traceback
        trace = traceback.format_exc()
        logger.error(trace)
        raise

# 原始的REST API方式下單的函數
async def place_order_via_rest(exchange, api_key, api_secret, order_params):
    """
    使用REST API下單（舊方法，作為備份）
    """
    logger.info(f"[AccountWS] 開始使用REST API下單: {exchange}")
    
    try:
        # 確保 API 密鑰格式正確
        if not api_key or not api_secret:
            error_msg = "API密鑰或密鑰密碼為空"
            logger.error(f"[AccountWS] {error_msg}")
            raise ValueError(error_msg)
        
        # 處理不同交易所
        if exchange.lower() == "binance":
            # 複製參數以防止修改原始參數
            params = {}
            
            # 處理所有參數 - 遵循幣安的數據類型要求
            for key, value in order_params.items():
                # 處理布爾值 - 必須是字符串格式的"true"或"false"
                if isinstance(value, bool):
                    params[key] = str(value).lower()
                # 處理數值參數 - 價格、數量等必須是字符串
                elif key in ['price', 'quantity', 'stopPrice', 'activationPrice', 'callbackRate', 'trailingDelta']:
                    if value is not None:
                        params[key] = str(value)
                # 其他參數保持不變
                else:
                    params[key] = value
            
            # 添加時間參數
            params["timestamp"] = int(time.time() * 1000)  # 保證是整數
            params["recvWindow"] = 5000  # 給予足夠的接收窗口
            
            # 創建簽名 - 按照字母順序排序參數
            query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items()) if k != "signature"])
            
            # 記錄查詢字符串 (開發調試用)
            logger.debug(f"[AccountWS] 簽名查詢字符串: {query_string}")
            
            # 使用HMAC SHA256計算簽名
            signature = hmac.new(
                api_secret.encode('utf-8'),
                query_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # 添加簽名到參數中
            params["signature"] = signature
            
            # 確定API端點
            is_test_order = "test" in params and (params["test"] == "true" or params["test"] is True)
            endpoint = "/fapi/v1/order/test" if is_test_order else "/fapi/v1/order"
            
            # 構建URL
            base_url = "https://fapi.binance.com"
            
            # 檢查是否為測試網
            test_mode = False  # 可以從配置或環境變量中獲取
            if test_mode:
                base_url = "https://testnet.binancefuture.com"
                
            # 移除test參數，因為我們已經使用不同的端點處理測試訂單
            if "test" in params:
                del params["test"]
                
            # 構建完整URL
            url = f"{base_url}{endpoint}"
            
            # 發送請求
            headers = {
                'X-MBX-APIKEY': api_key,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            # 使用aiohttp進行非阻塞HTTP請求
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=params, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"[AccountWS] REST API下單成功: {result.get('orderId')}")
                        return result
                    else:
                        error_data = await response.text()
                        logger.error(f"[AccountWS] 幣安API返回錯誤: {response.status} - {error_data}")
                        raise Exception(f"下單時API返回錯誤: {response.status} - {error_data}")
        else:
            # 其他交易所實現...
            raise Exception(f"不支持的交易所: {exchange}")
            
    except Exception as e:
        logger.error(f"[AccountWS] 使用REST API下單時出錯: {str(e)}")
        import traceback
        trace = traceback.format_exc()
        logger.error(trace)
        raise

# 修改取消訂單函數，使用緩存的客戶端
async def cancel_order_via_websocket(exchange, api_key, api_secret, cancel_params, user_id=None):
    """
    使用API密鑰通過WebSocket API取消訂單
    
    Args:
        exchange: 交易所名稱
        api_key: API密鑰
        api_secret: API密鑰密碼
        cancel_params: 取消訂單參數
        user_id: 用戶ID，用於客戶端緩存
            
    Returns:
        取消訂單結果
    """
    logger.info(f"[AccountWS] 開始取消訂單操作(WebSocket): {exchange}")
    
    try:
        # 確保 API 密鑰格式正確
        if not api_key or not api_secret:
            error_msg = "API密鑰或密鑰密碼為空"
            logger.error(f"[AccountWS] {error_msg}")
            raise ValueError(error_msg)
        
        # 檢查必要參數
        if "symbol" not in cancel_params:
            raise ValueError("缺少必要參數: symbol")
            
        if "orderId" not in cancel_params and "origClientOrderId" not in cancel_params:
            raise ValueError("缺少必要參數: orderId 或 origClientOrderId")
        
        # 處理不同交易所
        if exchange.lower() == "binance":
            try:
                # 檢查是否需要使用測試網
                test_mode = False
                if "test" in cancel_params and (cancel_params["test"] == "true" or cancel_params["test"] is True or cancel_params["test"] == "TRUE"):
                    test_mode = True
                    logger.info(f"[AccountWS] 使用測試網模式取消訂單")
                
                # 獲取或創建WebSocket客戶端
                client, is_new = await get_or_create_ws_client(
                    api_key, api_secret, exchange, test_mode, user_id
                )
                
                # 獲取必要參數
                symbol = cancel_params["symbol"]
                
                # 提取訂單ID或客戶端訂單ID
                order_id = cancel_params.get("orderId")
                client_order_id = cancel_params.get("origClientOrderId")
                
                # 取消訂單 - 根據提供的參數決定如何調用
                if order_id:
                    result = await client.cancel_order(symbol, orderId=order_id, params=cancel_params)
                elif client_order_id:
                    result = await client.cancel_order(symbol, origClientOrderId=client_order_id, params=cancel_params)
                else:
                    # 這種情況在前面的檢查中應該已經被排除
                    raise ValueError("缺少必要參數: orderId 或 origClientOrderId")
                
                # 不再每次操作後斷開連接，保持連接以便重用
                
                logger.info(f"[AccountWS] 取消訂單成功: {result.get('orderId')}")
                return result
                
            except Exception as e:
                logger.error(f"[AccountWS] 使用WebSocket取消訂單時出錯: {str(e)}")
                # 如果WebSocket方式失敗，回退到REST API方式
                logger.info(f"[AccountWS] 回退到使用REST API取消訂單")
                return await cancel_order_via_rest(exchange, api_key, api_secret, cancel_params)
        else:
            # 其他交易所實現...
            raise Exception(f"不支持的交易所: {exchange}")
            
    except Exception as e:
        logger.error(f"[AccountWS] 取消訂單時發生錯誤: {str(e)}")
        import traceback
        trace = traceback.format_exc()
        logger.error(trace)
        raise
        
# 原始的REST API方式取消訂單的函數
async def cancel_order_via_rest(exchange, api_key, api_secret, cancel_params):
    """
    使用REST API取消訂單（舊方法，作為備份）
    """
    logger.info(f"[AccountWS] 開始使用REST API取消訂單: {exchange}")
    
    try:
        # 確保 API 密鑰格式正確
        if not api_key or not api_secret:
            error_msg = "API密鑰或密鑰密碼為空"
            logger.error(f"[AccountWS] {error_msg}")
            raise ValueError(error_msg)
        
        # 處理不同交易所
        if exchange.lower() == "binance":
            # 複製參數以防止修改原始參數
            params = {}
            
            # 處理取消訂單參數 - 遵循幣安的數據類型要求
            for key, value in cancel_params.items():
                # 處理布爾值
                if isinstance(value, bool):
                    params[key] = str(value).lower()
                # 確保orderId是字符串
                elif key == 'orderId' and value is not None:
                    params[key] = str(value)
                # 其他參數保持不變
                else:
                    params[key] = value
            
            # 添加時間參數
            params["timestamp"] = int(time.time() * 1000)
            params["recvWindow"] = 5000
            
            # 創建簽名 - 按照字母順序排序參數
            query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items()) if k != "signature"])
            
            # 記錄查詢字符串 (開發調試用)
            logger.debug(f"[AccountWS] 簽名查詢字符串: {query_string}")
            
            # 使用HMAC SHA256計算簽名
            signature = hmac.new(
                api_secret.encode('utf-8'),
                query_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # 添加簽名到參數中
            params["signature"] = signature
            
            # 構建URL
            base_url = "https://fapi.binance.com"
            endpoint = "/fapi/v1/order"
            
            # 檢查是否為測試網
            test_mode = False  # 可以從配置或環境變量中獲取
            if test_mode:
                base_url = "https://testnet.binancefuture.com"
                
            # 移除test參數
            if "test" in params:
                del params["test"]
                
            # 構建完整URL
            url = f"{base_url}{endpoint}"
            
            # 發送請求
            headers = {
                'X-MBX-APIKEY': api_key,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            # 使用aiohttp進行非阻塞HTTP請求
            async with aiohttp.ClientSession() as session:
                async with session.delete(url, data=params, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"[AccountWS] REST API取消訂單成功: {result.get('orderId')}")
                        return result
                    else:
                        error_data = await response.text()
                        logger.error(f"[AccountWS] 幣安API返回錯誤: {response.status} - {error_data}")
                        raise Exception(f"取消訂單時API返回錯誤: {response.status} - {error_data}")
        else:
            # 其他交易所實現...
            raise Exception(f"不支持的交易所: {exchange}")
            
    except Exception as e:
        logger.error(f"[AccountWS] 使用REST API取消訂單時出錯: {str(e)}")
        import traceback
        trace = traceback.format_exc()
        logger.error(trace)
        raise 

# 幫助函數：檢查帳戶數據是否有變化
def _has_account_data_changed(new_data, old_data):
    """
    檢查帳戶數據是否發生變化
    
    比較兩次獲取的帳戶數據，判斷是否有變化。比較關鍵字段：
    1. 餘額（資產、總額、可用額）
    2. 持倉（倉位大小、開倉價格、未實現盈虧）
    
    Args:
        new_data: 新獲取的帳戶數據
        old_data: 上次獲取的帳戶數據
        
    Returns:
        bool: 如有變化返回True，否則返回False
    """
    if not old_data or not new_data:
        return True
    
    # 比較總額和可用餘額
    if ("totalWalletBalance" in new_data and "totalWalletBalance" in old_data and 
            new_data["totalWalletBalance"] != old_data["totalWalletBalance"]):
        return True
    
    if ("availableBalance" in new_data and "availableBalance" in old_data and 
            new_data["availableBalance"] != old_data["availableBalance"]):
        return True
    
    if ("totalUnrealizedProfit" in new_data and "totalUnrealizedProfit" in old_data and 
            new_data["totalUnrealizedProfit"] != old_data["totalUnrealizedProfit"]):
        return True
    
    # 比較餘額
    new_balances = {b.get("asset"): b for b in new_data.get("balances", [])}
    old_balances = {b.get("asset"): b for b in old_data.get("balances", [])}
    
    # 檢查資產數量是否不同
    if len(new_balances) != len(old_balances):
        return True
    
    # 檢查每個資產的餘額
    for asset, new_balance in new_balances.items():
        old_balance = old_balances.get(asset)
        if not old_balance:
            return True  # 新增資產
        
        # 比較關鍵數據
        for key in ["walletBalance", "availableBalance", "locked"]:
            if key in new_balance and key in old_balance:
                if new_balance[key] != old_balance[key]:
                    return True
    
    # 比較持倉
    new_positions = {f"{p.get('symbol')}_{p.get('positionSide', 'BOTH')}": p for p in new_data.get("positions", [])}
    old_positions = {f"{p.get('symbol')}_{p.get('positionSide', 'BOTH')}": p for p in old_data.get("positions", [])}
    
    # 檢查持倉數量是否不同
    if len(new_positions) != len(old_positions):
        return True
    
    # 檢查每個持倉的詳情
    for key, new_position in new_positions.items():
        old_position = old_positions.get(key)
        if not old_position:
            return True  # 新增持倉
        
        # 比較關鍵數據
        for field in ["positionAmt", "entryPrice", "unrealizedProfit", "leverage"]:
            if field in new_position and field in old_position:
                if new_position[field] != old_position[field]:
                    return True
    
    # 沒有發現變化
    return False

# 幫助函數：計算帳戶數據差異
def _compute_account_data_diff(new_data, old_data):
    """
    計算帳戶數據的差異
    
    比較兩次獲取的帳戶數據，計算出有變化的部分。
    
    Args:
        new_data: 新獲取的帳戶數據
        old_data: 上次獲取的帳戶數據
        
    Returns:
        dict: 包含變化部分的數據對象
    """
    if not old_data:
        return new_data  # 首次獲取，返回完整數據
    
    diff = {"balances": [], "positions": []}
    
    # 複製不可變的頂層數據（例如API類型和時間戳）
    for key, value in new_data.items():
        if key not in ["balances", "positions"]:
            diff[key] = value
    
    # 處理餘額變化
    new_balances = {b.get("asset"): b for b in new_data.get("balances", [])}
    old_balances = {b.get("asset"): b for b in old_data.get("balances", [])}
    
    # 找出所有發生變化的餘額
    for asset, new_balance in new_balances.items():
        old_balance = old_balances.get(asset)
        if not old_balance:
            # 新增資產
            diff["balances"].append(new_balance)
            continue
        
        # 檢查是否有變化
        balance_changed = False
        for key in ["walletBalance", "availableBalance", "locked"]:
            if key in new_balance and key in old_balance and new_balance[key] != old_balance[key]:
                balance_changed = True
                break
        
        if balance_changed:
            diff["balances"].append(new_balance)
    
    # 處理持倉變化
    new_positions = {f"{p.get('symbol')}_{p.get('positionSide', 'BOTH')}": p for p in new_data.get("positions", [])}
    old_positions = {f"{p.get('symbol')}_{p.get('positionSide', 'BOTH')}": p for p in old_data.get("positions", [])}
    
    # 找出所有發生變化的持倉
    for key, new_position in new_positions.items():
        old_position = old_positions.get(key)
        if not old_position:
            # 新增持倉
            diff["positions"].append(new_position)
            continue
        
        # 檢查是否有變化
        position_changed = False
        for field in ["positionAmt", "entryPrice", "unrealizedProfit", "leverage", "markPrice"]:
            if field in new_position and field in old_position and new_position[field] != old_position[field]:
                position_changed = True
                break
        
        if position_changed:
            diff["positions"].append(new_position)
    
    # 添加已消失的持倉（倉位已平）
    for key, old_position in old_positions.items():
        if key not in new_positions:
            # 標記已關閉的持倉
            closed_position = old_position.copy()
            closed_position["positionAmt"] = "0"
            closed_position["unrealizedProfit"] = "0"
            closed_position["closed"] = True
            diff["positions"].append(closed_position)
    
    # 更新差異數據的狀態
    diff["has_changes"] = len(diff["balances"]) > 0 or len(diff["positions"]) > 0
    diff["balances_changed"] = len(diff["balances"]) > 0
    diff["positions_changed"] = len(diff["positions"]) > 0
    
    return diff 