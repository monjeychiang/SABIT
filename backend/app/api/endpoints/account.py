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

from ...db.database import get_db
from ...schemas.trading import ExchangeEnum
from ...db.models import User, ExchangeAPI
from ...core.security import get_current_user, get_current_active_user, decrypt_api_key

router = APIRouter()
logger = logging.getLogger(__name__)

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
            account_data = await get_account_data(exchange, api_key_data["api_key"], api_key_data["api_secret"])
        
            # 發送帳戶數據
            await websocket.send_json({
                "success": True,
                "data": account_data,
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
                    current_time = time.time()
                    last_activity_time = current_time
                    
                    try:
                        message_data = json.loads(data)
                        msg_type = message_data.get("type")
                        
                        # 處理心跳
                        if msg_type == "ping":
                            logger.debug(f"[AccountWS] 收到PING - user:{user_id}")
                            await websocket.send_json({
                                "type": "pong", 
                                "timestamp": datetime.now().isoformat()
                            })
                            continue
                        
                        # 處理手動刷新請求
                        if msg_type == "refresh":
                            logger.info(f"[AccountWS] 收到刷新請求 - user:{user_id}")
                            # 獲取最新帳戶數據
                            account_data = await get_account_data(exchange, api_key_data["api_key"], api_key_data["api_secret"])
                            
                            # 發送最新帳戶數據
                            await websocket.send_json({
                                "type": "account_data",
                                "success": True,
                                "data": account_data,
                                "timestamp": datetime.now().isoformat()
                            })
                            
                            last_data_update = current_time
                            continue
                    except json.JSONDecodeError:
                        logger.warning(f"[AccountWS] 收到無效的JSON數據: {data[:100]}...")
                        continue
                        
                except asyncio.TimeoutError:
                    # 檢查是否需要定期更新數據
                    current_time = time.time()
                    
                    # 如果超過設定的間隔時間，自動更新帳戶數據
                    if current_time - last_data_update > update_interval:
                        logger.info(f"[AccountWS] 定期更新 {exchange} 帳戶數據 - user:{user_id}")
                        try:
                            # 獲取最新帳戶數據
                            account_data = await get_account_data(exchange, api_key_data["api_key"], api_key_data["api_secret"])
                            
                            # 發送最新帳戶數據
                            await websocket.send_json({
                                "type": "account_data",
                                "success": True,
                                "data": account_data,
                                "timestamp": datetime.now().isoformat()
                            })
                            
                            last_data_update = current_time
                        except Exception as e:
                            logger.error(f"[AccountWS] 定期更新數據時發生錯誤: {str(e)}")
                            # 繼續運行，不中斷連接
                    
                    # 如果很長時間沒有活動，發送心跳檢查連接是否仍然活躍
                    if current_time - last_activity_time > 30:  # 30秒無活動
                        logger.debug(f"[AccountWS] 發送心跳檢查 - user:{user_id}")
                        try:
                            await websocket.send_json({
                                "type": "ping",
                                "timestamp": datetime.now().isoformat()
                            })
                        except Exception as e:
                            logger.error(f"[AccountWS] 發送心跳檢查失敗: {str(e)}")
                            break  # 如果無法發送心跳，退出循環
                    
                    continue
                    
                except WebSocketDisconnect:
                    logger.info(f"[AccountWS] WebSocket連接被客戶端主動關閉 - user:{user_id}")
                    break
                
                except Exception as e:
                    logger.error(f"[AccountWS] 處理WebSocket消息時發生錯誤: {str(e)}")
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
    使用API密鑰連接到交易所API獲取帳戶數據
    """
    logger.info(f"[AccountWS] 開始獲取 {exchange} 帳戶數據")
    
    try:
        # 確保 API 密鑰格式正確
        if not api_key or not api_secret:
            error_msg = "API密鑰或密鑰密碼為空"
            logger.error(f"[AccountWS] {error_msg}")
            return {
                "error": error_msg,
                "balances": [],
                "positions": []
            }
            
        if api_key:
            api_key = api_key.strip()
            # 診斷日誌 - 只顯示密鑰開頭幾個字符，避免泄露完整密鑰
            masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "***masked***"
            logger.debug(f"[AccountWS] API密鑰格式: {masked_key}, 長度: {len(api_key)}")
        
        if api_secret:
            api_secret = api_secret.strip()
            logger.debug(f"[AccountWS] API密鑰密碼長度: {len(api_secret)}")
        
        if exchange.lower() == "binance":
            # 使用幣安API獲取帳戶信息
            import hmac
            import hashlib
            import time
            
            try:
                # 生成簽名
                timestamp = int(time.time() * 1000)
                query_string = f"timestamp={timestamp}"
                
                # 檢查API密鑰密碼的編碼
                if isinstance(api_secret, str):
                    api_secret_bytes = api_secret.encode('utf-8')
                else:
                    api_secret_bytes = api_secret
                    
                # 檢查query_string的編碼
                if isinstance(query_string, str):
                    query_string_bytes = query_string.encode('utf-8')
                else:
                    query_string_bytes = query_string
                
                # 生成簽名
                try:
                    signature = hmac.new(
                        api_secret_bytes,
                        query_string_bytes,
                        hashlib.sha256
                    ).hexdigest()
                    logger.debug(f"[AccountWS] 成功生成API請求簽名")
                except Exception as sig_err:
                    logger.error(f"[AccountWS] 生成簽名時發生錯誤: {str(sig_err)}")
                    if isinstance(sig_err, TypeError):
                        logger.error(f"[AccountWS] 這可能是API密鑰格式問題，API密鑰密碼長度: {len(api_secret)}")
                    raise
            
                # 構建API請求
                url = f"https://fapi.binance.com/fapi/v2/account?{query_string}&signature={signature}"
                headers = {"X-MBX-APIKEY": api_key}
                
                logger.debug(f"[AccountWS] 請求URL: {url.split('?')[0]}")
                logger.debug(f"[AccountWS] 請求頭部: X-MBX-APIKEY={masked_key}")
                
                # 使用 aiohttp 發送請求
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    logger.debug(f"[AccountWS] 開始發送API請求")
                    async with session.get(url, headers=headers) as response:
                        response_status = response.status
                        logger.debug(f"[AccountWS] 收到API響應: HTTP {response_status}")
                        
                        if response_status == 200:
                            account_data = await response.json()
                            # 處理返回數據
                            logger.info(f"[AccountWS] 成功獲取帳戶數據")
                            
                            # 檢查關鍵字段是否存在
                            if "assets" not in account_data or "positions" not in account_data:
                                logger.warning(f"[AccountWS] 獲取的帳戶數據缺少關鍵字段: assets或positions")
                                if "code" in account_data or "msg" in account_data:
                                    logger.warning(f"[AccountWS] 交易所返回錯誤: {account_data.get('code')} - {account_data.get('msg')}")
                            
                            return {
                                "balances": account_data.get("assets", []),
                                "positions": account_data.get("positions", []),
                                "availableBalance": account_data.get("availableBalance", "0"),
                                "totalWalletBalance": account_data.get("totalWalletBalance", "0"),
                                "totalUnrealizedProfit": account_data.get("totalUnrealizedProfit", "0"),
                                "totalMarginBalance": account_data.get("totalMarginBalance", "0")
                            }
                        else:
                            error_text = await response.text()
                            logger.error(f"[AccountWS] 獲取帳戶數據失敗: HTTP {response.status}, {error_text}")
                            
                            # 嘗試解析詳細錯誤
                            try:
                                error_json = await response.json()
                                error_code = error_json.get("code", "未知")
                                error_msg = error_json.get("msg", error_text)
                                logger.error(f"[AccountWS] 交易所API錯誤: 代碼 {error_code}, 信息: {error_msg}")
                                
                                # 針對特定錯誤代碼提供更詳細的診斷
                                if error_code == -2014 or error_code == -2015:  # 無效的API密鑰或簽名
                                    logger.error(f"[AccountWS] 這可能是API密鑰格式或加密/解密問題")
                            except:
                                # 無法解析JSON
                                pass
                                
                            raise Exception(f"獲取帳戶數據失敗: HTTP {response.status}, {error_text}")
            
            except aiohttp.ClientError as client_err:
                logger.error(f"[AccountWS] HTTP請求錯誤: {str(client_err)}")
                raise Exception(f"連接交易所API時發生錯誤: {str(client_err)}")
                
        else:
            # 其他交易所實現...
            raise Exception(f"不支持的交易所: {exchange}")
    
    except Exception as e:
        logger.error(f"[AccountWS] 獲取帳戶數據時發生錯誤: {str(e)}")
        import traceback
        trace = traceback.format_exc()
        logger.error(trace)
        # 返回一個錯誤信息
        return {
            "error": str(e),
            "trace": trace if len(trace) < 500 else trace[:500] + "...",  # 限制跟踪信息長度
            "balances": [],
            "positions": []
        }

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