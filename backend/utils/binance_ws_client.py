import asyncio
import json
import logging
import time
import random
import websockets
from typing import Dict, Any, Optional, Callable, List, Tuple
from backend.utils.ed25519_util import Ed25519KeyManager
import uuid

logger = logging.getLogger(__name__)

class BinanceWebSocketClient:
    """
    幣安WebSocket API客戶端
    處理與幣安WebSocket API的連接、認證和請求
    
    注意：幣安WebSocket API需要使用Ed25519密鑰，而非HMAC-SHA256密鑰
    用戶需要在幣安API管理界面創建專用的WebSocket API密鑰
    """

    def __init__(self, api_key: str, api_secret: str) -> None:
        """
        初始化WebSocket客戶端
        
        幣安API認證使用兩個組件：
        1. API Key: 公開識別符，相當於「用戶名」
        2. API Secret: 私鑰，用於生成簽名，相當於「密碼」
        
        Args:
            api_key: 幣安 API Key (公開識別符)
            api_secret: 幣安 API Secret (Ed25519 私鑰)，支持以下格式:
                1. 自行生成的私鑰 (通常是 Base64 格式，包含 +, /, = 等字符)
                   - 可以是 PKCS#8 格式 (解碼後為 48 字節)
                2. 幣安提供的十六進制格式 (64字符的十六進制字符)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        
        # 記錄關鍵信息以幫助診斷
        self.logger = logger
        logger.info(f"API Key 長度: {len(api_key)}, Secret 長度: {len(api_secret)}")
        
        # 檢查 API Secret 格式
        contains_base64_chars = '+' in api_secret or '/' in api_secret or '=' in api_secret
        is_hex_format = len(api_secret) == 64 and all(c in '0123456789abcdefABCDEF' for c in api_secret)
        
        if contains_base64_chars:
            logger.info("檢測到 Base64 格式的 Ed25519 私鑰")
        elif is_hex_format:
            logger.info("檢測到十六進制格式 Ed25519 私鑰 (64字符)")
        else:
            logger.warning("API Secret 格式無法識別")
        
        # 初始化Ed25519密鑰管理器
        try:
            from backend.utils.ed25519_util import Ed25519KeyManager
            self.key_manager = Ed25519KeyManager(generate_key_pair=False)
            logger.debug("密鑰管理器初始化成功")
        except Exception as e:
            logger.error(f"初始化密鑰管理器失敗: {str(e)}")
            raise ValueError(f"初始化密鑰管理器失敗: {str(e)}")
        
        # WebSocket終端點 - U本位合約的端點
        self.endpoint = "wss://ws-fapi.binance.com/ws-fapi/v1"  # U本位合約正式網端點
        
        # 記錄使用的端點
        logger.info(f"使用 WebSocket 端點: {self.endpoint}")
        
        # WebSocket連接
        self.ws = None
        self.connected = False
        self.authenticated = False
        
        # 響應追踪
        self.response_futures = {}
        
        # 後台任務
        self.tasks = []
        self.closed = False
        self.request_id = 1
        self.recv_lock = None
        self.ping_task = None
        self.response_handler_task = None
        
        # 添加連接管理和健康狀態相關屬性
        self.consecutive_errors = 0
        self.max_consecutive_errors = 5  # 連續錯誤閾值，超過此值將重新連接
        self.connection_start_time = None  # 記錄連接建立時間
        self.max_connection_age = 12 * 3600  # 連接最大存活時間（12小時）
        self.last_health_check = 0  # 上次健康檢查時間

    def sign_parameters(self, params: Dict[str, Any]) -> str:
        """
        使用Ed25519簽名生成請求參數的簽名
        
        使用 API Secret (私鑰) 對參數進行簽名
        支持以下格式的 API Secret:
        1. PEM 格式的 Ed25519 私鑰 (帶有 -----BEGIN PRIVATE KEY----- 標記)
        2. 自行生成的 Base64 格式私鑰 (含有 +, /, = 等字符)
           - 特別處理 PKCS#8 格式 (解碼後通常為 48 字節)
        3. 幣安提供的十六進制格式 (64字符)
        
        Args:
            params: 需要簽名的參數
            
        Returns:
            生成的簽名
        """
        # 將參數轉換為查詢字符串格式
        query_string = '&'.join([f"{key}={params[key]}" for key in params])
        logger.debug(f"待簽名參數: {query_string}")
        
        try:
            # 檢查 API Secret 是否為 PEM 格式 (帶頭尾標記)
            is_pem_format = self.api_secret.strip().startswith("-----BEGIN") and self.api_secret.strip().endswith("-----")
            
            if is_pem_format:
                logger.info("檢測到 PEM 格式的 Ed25519 私鑰")
                
                # 檢測並處理單行PEM格式
                if "\n" not in self.api_secret:
                    try:
                        # 提取密鑰類型 (例如 "PRIVATE KEY")
                        key_type = self.api_secret.split("-----BEGIN ")[1].split("-----")[0].strip()
                        
                        # 提取Base64內容
                        base64_content = self.api_secret.split(f"-----BEGIN {key_type}-----")[1]
                        base64_content = base64_content.split(f"-----END {key_type}-----")[0].strip()
                        
                        # 重新格式化為標準PEM格式
                        formatted_key = f"-----BEGIN {key_type}-----\n{base64_content}\n-----END {key_type}-----"
                        
                        # 使用格式化後的密鑰進行簽名
                        signature = self.key_manager.sign_message(query_string, private_key=formatted_key)
                        return signature
                    except Exception as e:
                        logger.warning(f"單行PEM格式處理失敗: {str(e)}")
                
                try:
                    # 直接使用密鑰管理器處理 PEM 格式
                    signature = self.key_manager.sign_message(query_string, private_key=self.api_secret)
                    return signature
                except Exception as e:
                    logger.error(f"使用 PEM 格式私鑰生成簽名失敗: {str(e)}")
            
            # 嘗試使用密鑰管理器的通用簽名方法
            try:
                signature = self.key_manager.sign_message(query_string, private_key=self.api_secret)
                return signature
            except Exception as e:
                logger.warning(f"使用密鑰管理器簽名失敗: {str(e)}")
            
            # 檢查 API Secret 是否為自行生成的 Base64 格式
            contains_base64_chars = '+' in self.api_secret or '/' in self.api_secret or '=' in self.api_secret
            
            if contains_base64_chars:
                logger.debug("嘗試處理 Base64 格式的 Ed25519 私鑰")
                
                # 檢查是否為 PKCS#8 格式的 Ed25519 私鑰
                is_pkcs8_format = False
                try:
                    import base64
                    decoded_key = base64.b64decode(self.api_secret)
                    if len(decoded_key) == 48:
                        is_pkcs8_format = True
                        
                        # 提取私鑰部分(後32字節)
                        actual_key = decoded_key[16:]
                        
                        # 直接使用 PyNaCl 簽名
                        import nacl.signing
                        signing_key = nacl.signing.SigningKey(actual_key)
                        signed_message = signing_key.sign(query_string.encode())
                        signature = base64.b64encode(signed_message.signature).decode('utf-8')
                        return signature
                except Exception as e:
                    logger.error(f"處理 PKCS#8 格式私鑰失敗: {str(e)}")
                
                try:
                    # 使用密鑰管理器處理 API Secret 簽名
                    signature = self.key_manager.sign_message(query_string, private_key=self.api_secret)
                    return signature
                except Exception as e:
                    logger.error(f"使用 Base64 格式簽名失敗: {str(e)}")
            
            # 檢查 API Secret 是否為幣安提供的十六進制格式 (64字符, 0-9a-fA-F)
            is_hex_format = len(self.api_secret) == 64 and all(c in '0123456789abcdefABCDEF' for c in self.api_secret)
            
            if is_hex_format:
                logger.debug("嘗試處理十六進制格式的 Ed25519 私鑰")
                try:
                    # 將十六進制轉換為字節
                    key_bytes = bytes.fromhex(self.api_secret)
                    
                    # 直接使用 PyNaCl 簽名
                    import nacl.signing
                    import base64
                    
                    # 創建簽名密鑰
                    signing_key = nacl.signing.SigningKey(key_bytes)
                    
                    # 生成簽名
                    signed_message = signing_key.sign(query_string.encode())
                    signature = base64.b64encode(signed_message.signature).decode('utf-8')
                    return signature
                except Exception as e:
                    logger.error(f"使用十六進制格式簽名失敗: {str(e)}")
            
            # 最後嘗試直接簽名
            try:
                import nacl.signing
                import base64
                
                # 嘗試使用原始字符串
                key_bytes = self.api_secret.encode('utf-8')
                logger.warning(f"嘗試使用原始字符串作為私鑰")
                
                if len(key_bytes) == 32:
                    signing_key = nacl.signing.SigningKey(key_bytes)
                elif len(key_bytes) > 32:
                    signing_key = nacl.signing.SigningKey(key_bytes[:32])
                    logger.warning("截斷私鑰至前32字節")
                else:
                    # 如果不夠32字節，填充
                    padded_key = key_bytes.ljust(32, b'\0')
                    signing_key = nacl.signing.SigningKey(padded_key)
                    logger.warning("私鑰不足32字節，已填充")
                
                signed_message = signing_key.sign(query_string.encode())
                signature = base64.b64encode(signed_message.signature).decode('utf-8')
                return signature
            except Exception as final_e:
                logger.error("所有簽名方法都失敗")
                raise ValueError(f"無法生成有效的 Ed25519 簽名: {str(final_e)}")
        except Exception as e:
            logger.error(f"簽名生成失敗: {str(e)}")
            raise ValueError(f"簽名生成失敗: {str(e)}")

    async def connect(self) -> bool:
        """
        連接到幣安 WebSocket API 並進行認證
        
        支持的私鑰格式:
        1. PEM 格式 (帶有 -----BEGIN PRIVATE KEY----- 標記)
        2. Base64 格式 (包含 +, /, = 等特殊字符)
        3. PKCS#8 格式 (解碼後為 48 字節)
        4. 十六進制格式 (64 字符)
        
        Returns:
            連接是否成功
        """
        if self.ws is not None and self.connected:
            logger.info("WebSocket 已連接")
            return True
            
        self.closed = False
        logger.info(f"連接到幣安 WebSocket API: {self.endpoint}")
        
        try:
            # 建立 WebSocket 連接
            self.ws = await websockets.connect(
                self.endpoint,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )
            
            self.connected = True
            # 記錄連接建立時間
            self.connection_start_time = time.time()
            self.consecutive_errors = 0  # 重置錯誤計數
            logger.info("WebSocket 連接成功")
            
            # 初始化同步鎖，用於防止多個協程同時接收消息
            self.recv_lock = asyncio.Lock()
            
            # 認證
            try:
                logger.info("開始進行認證流程")
                auth_success = await self._authenticate()
                if not auth_success:
                    logger.error("認證失敗，WebSocket API 功能不可用")
                    await self.disconnect()
                    return False
            except Exception as e:
                logger.error(f"認證過程中出錯: {str(e)}")
                await self.disconnect()
                return False
            
            # 啟動響應處理器和ping任務
            self._start_background_tasks()
            return True
        except Exception as e:
            logger.error(f"WebSocket 連接失敗: {str(e)}")
            self.connected = False
            if self.ws:
                await self.ws.close()
                self.ws = None
            return False
    
    async def disconnect(self) -> None:
        """斷開與幣安WebSocket API的連接"""
        try:
            # 先標記為已關閉，避免響應處理器繼續處理
            self.closed = True
            
            # 取消並等待 ping 任務結束
            if self.ping_task and not self.ping_task.done():
                self.ping_task.cancel()
                try:
                    await asyncio.wait_for(asyncio.shield(self.ping_task), timeout=2.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass
                self.ping_task = None
            
            # 取消並等待響應處理器任務結束
            if self.response_handler_task and not self.response_handler_task.done():
                self.response_handler_task.cancel()
                try:
                    await asyncio.wait_for(asyncio.shield(self.response_handler_task), timeout=2.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass
                self.response_handler_task = None
            
            # 清理其他任務
            for task in self.tasks:
                if task and not task.done() and task != self.ping_task and task != self.response_handler_task:
                    task.cancel()
                    try:
                        await asyncio.wait_for(asyncio.shield(task), timeout=1.0)
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        pass
            
            self.tasks = []
            
            # 關閉 WebSocket 連接
            if self.ws:
                try:
                    await asyncio.wait_for(self.ws.close(code=1000, reason="正常關閉"), timeout=3.0)
                except (asyncio.TimeoutError, Exception) as e:
                    logger.warning(f"關閉WebSocket連接時超時或發生錯誤: {str(e)}")
                self.ws = None
                
            # 更新狀態
            self.connected = False
            self.authenticated = False
            
            # 清理響應 future
            for future in self.response_futures.values():
                if not future.done():
                    future.set_exception(ConnectionError("WebSocket連接已關閉"))
            self.response_futures.clear()
            
            logger.info("已正常斷開與幣安WebSocket API的連接")
            
        except Exception as e:
            logger.error(f"斷開WebSocket連接時出錯: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def _authenticate(self) -> bool:
        """
        使用 Ed25519 簽名認證 WebSocket 連接
        幣安的 WebSocket API 需要使用 Ed25519 密鑰，而不是 HMAC-SHA256 密鑰
        
        Returns:
            認證是否成功
        """
        if not self.api_key or not self.api_secret:
            logger.error("API Key 或 Secret 為空")
            return False
            
        if not self.authenticated:
            # 構建認證請求參數
            params = {
                "apiKey": self.api_key,
                "timestamp": str(int(time.time() * 1000)),
                "recvWindow": "15000"  # 增加接收窗口時間到15秒，避免時間同步問題
            }
            
            # 按參數名稱排序
            sorted_params = {key: params[key] for key in sorted(params.keys())}
            
            try:
                # 生成簽名
                logger.debug("正在生成認證簽名")
                signature = self.sign_parameters(sorted_params)
                sorted_params["signature"] = signature
                
                # 構建認證請求
                auth_request = {
                    "id": str(uuid.uuid4()),
                    "method": "session.logon",
                    "params": sorted_params
                }
                
                # 發送認證請求
                await self.ws.send(json.dumps(auth_request))
                
                # 等待認證響應
                try:
                    # 使用鎖確保只有一個協程在等待消息
                    response = None
                    async with self.recv_lock:
                        response = await asyncio.wait_for(self.ws.recv(), timeout=15)
                    
                    if not response:
                        logger.error("未收到認證響應")
                        self.authenticated = False
                        return False
                    
                    response_data = json.loads(response)
                    
                    # 檢查認證是否成功
                    if 'error' in response_data:
                        error_code = response_data.get('error', {}).get('code', 'unknown')
                        error_msg = response_data.get('error', {}).get('msg', 'Unknown error')
                        logger.error(f"認證失敗: 錯誤碼 {error_code}, 錯誤信息: {error_msg}")
                        
                        if error_code == -4056:
                            logger.error("HMAC_SHA256 API 密鑰不支持 WebSocket API，請在幣安 API 管理界面創建 Ed25519 密鑰")
                        elif error_code == -1022 or "signature" in error_msg.lower():
                            logger.error("簽名無效，請檢查 API Secret 格式和正確性")
                        elif error_code == -1099:
                            logger.error("API密鑰無權限或未找到，請檢查 API Key 和權限設置")
                            
                        self.authenticated = False
                        return False
                    elif 'result' in response_data and response_data.get('result', None) is not None:
                        logger.info("認證成功")
                        self.authenticated = True
                        return True
                    else:
                        logger.error("認證響應格式異常")
                        self.authenticated = False
                        return False
                except asyncio.TimeoutError:
                    logger.error("認證響應超時")
                    self.authenticated = False
                    return False
                except Exception as e:
                    logger.error(f"認證過程中發生錯誤: {str(e)}")
                    self.authenticated = False
                    return False
            except Exception as e:
                logger.error(f"生成認證簽名時出錯: {str(e)}")
                self.authenticated = False
                return False
                
        return self.authenticated
    
    async def _ping_loop(self) -> None:
        """
        維持WebSocket連接的ping/pong循環
        每3分鐘發送一次ping以保持連接活躍
        """
        try:
            while self.connected and self.ws:
                await asyncio.sleep(180)  # 3分鐘
                
                if not self.connected or not self.ws:
                    break
                    
                try:
                    # 發送空的pong幀
                    await self.ws.pong()
                    logger.debug("發送pong幀以保持連接")
                except Exception as e:
                    logger.error(f"發送ping/pong時出錯: {str(e)}")
                    # 嘗試重新連接
                    break
        except asyncio.CancelledError:
            logger.debug("Ping循環已取消")
        except Exception as e:
            logger.error(f"Ping循環中出錯: {str(e)}")
    
    async def _response_handler(self) -> None:
        """
        處理從 WebSocket 接收到的響應
        """
        try:
            logger.debug("響應處理器已啟動")
            
            while not self.closed and self.ws is not None:
                try:
                    # 檢查連接是否需要預防性重建
                    await self._check_connection_health()
                    
                    # 使用鎖確保只有一個協程在等待消息
                    async with self.recv_lock:
                        message = await self.ws.recv()
                    
                    # 成功接收消息，重置連續錯誤計數
                    self.consecutive_errors = 0
                    
                    # 解析消息
                    try:
                        response = json.loads(message)
                        logger.debug(f"收到響應摘要: {_log_response_summary(response)}")
                    except json.JSONDecodeError:
                        logger.error(f"無法解析 WebSocket 響應: {message}")
                        continue
                    
                    # 處理响應
                    if "id" in response:
                        request_id = response["id"]
                        future = self.response_futures.pop(request_id, None)
                        
                        if future:
                            # 直接設置結果
                            future.set_result(response)
                        else:
                            logger.warning(f"未找到請求ID的處理器: {request_id}")
                    elif "error" in response:
                        # 處理全局錯誤響應
                        error = response.get("error", {})
                        logger.error(f"收到錯誤響應: 代碼 {error.get('code')}, 信息: {error.get('msg')}")
                    elif "result" in response:
                        # 處理無ID的結果響應
                        logger.info(f"收到無ID的結果響應: {response.get('result')}")
                    else:
                        # 處理其他響應
                        logger.debug(f"收到其他響應: {response}")
                except asyncio.CancelledError:
                    logger.info("響應處理器被取消")
                    break
                except Exception as e:
                    if self.closed:
                        break
                        
                    error_msg = str(e)
                    logger.error(f"處理 WebSocket 響應時出錯: {error_msg}")
                    
                    # 增加連續錯誤計數
                    self.consecutive_errors += 1
                    
                    # 識別連接問題的特定錯誤
                    connection_error = False
                    if "no close frame received or sent" in error_msg:
                        logger.warning(f"檢測到無關閉幀錯誤 (第 {self.consecutive_errors} 次)")
                        connection_error = True
                    elif "connection is closed" in error_msg.lower() or "not connected" in error_msg.lower():
                        logger.warning(f"檢測到連接已關閉錯誤 (第 {self.consecutive_errors} 次)")
                        connection_error = True
                    elif "cancelled" in error_msg.lower() or "timeout" in error_msg.lower():
                        logger.warning(f"檢測到取消或超時錯誤 (第 {self.consecutive_errors} 次)")
                        connection_error = True
                    
                    # 連續錯誤超過閾值或連接問題，嘗試主動重連
                    if (self.consecutive_errors >= self.max_consecutive_errors) or connection_error:
                        logger.warning(f"連續錯誤達到閾值 ({self.consecutive_errors}/{self.max_consecutive_errors}) 或檢測到連接錯誤，觸發重新連接")
                        
                        # 如果自己不在重連過程中，發信號通知需要重新連接
                        if self.connected and self.ws is not None:
                            logger.info("主動關閉問題連接並嘗試重新連接")
                            self.connected = False
                            try:
                                # 使用指數退避等待時間
                                wait_time = min(2 ** (self.consecutive_errors - 1), 30)
                                logger.info(f"等待 {wait_time} 秒後重新連接")
                                await asyncio.sleep(wait_time)
                                
                                # 關閉當前問題連接
                                try:
                                    await self.ws.close(code=1006, reason="檢測到連接錯誤，主動關閉")
                                except:
                                    pass  # 忽略關閉時的錯誤
                                
                                self.ws = None
                                
                                # 嘗試重新連接
                                connected = await self.connect()
                                if connected:
                                    logger.info("成功重新連接")
                                    self.consecutive_errors = 0
                                else:
                                    logger.error("重新連接失敗")
                            except Exception as reconnect_error:
                                logger.error(f"嘗試重新連接時出錯: {str(reconnect_error)}")
                        break  # 跳出循環，響應處理器將終止並由_start_background_tasks重新啟動
                    
                    # 普通錯誤，等待後繼續嘗試
                    wait_time = min(1 * self.consecutive_errors, 5)  # 隨著連續錯誤增加等待時間，但最多5秒
                    logger.debug(f"等待 {wait_time} 秒後繼續")
                    await asyncio.sleep(wait_time)
        except asyncio.CancelledError:
            logger.info("響應處理器被取消")
        except Exception as e:
            logger.error(f"響應處理器出錯: {str(e)}")
        finally:
            logger.debug("響應處理器已停止")
    
    async def _check_connection_health(self) -> None:
        """
        檢查連接健康狀態並實施預防性連接重建
        
        當連接存活時間超過預設閾值（默認12小時）時，主動重建連接，
        以避免接近幣安的連接時間限制，並減少非正常斷開的風險。
        
        為了優化資源使用，此函數僅每5分鐘執行一次檢查。
        """
        current_time = time.time()
        # 每5分鐘執行一次健康檢查，避免頻繁檢查
        if current_time - self.last_health_check < 300:  # 300秒 = 5分鐘
            return
            
        self.last_health_check = current_time
        
        # 如果連接時間未記錄，則記錄當前時間
        if not self.connection_start_time:
            self.connection_start_time = current_time
            return
            
        # 計算連接已存活的時間
        connection_age = current_time - self.connection_start_time
        
        # 減少日誌輸出 - 只在關鍵時刻記錄健康檢查信息
        is_debug_mode = logger.getEffectiveLevel() <= logging.DEBUG
        
        # 如果連接存活時間超過預設閾值，主動重建連接
        if connection_age > self.max_connection_age:
            logger.info(f"連接已存活 {connection_age/3600:.2f} 小時，超過預設閾值 {self.max_connection_age/3600} 小時，開始預防性重建")
            
            try:
                # 先嘗試正常斷開當前連接
                old_connection = self.ws
                self.connected = False
                self.ws = None
                
                if old_connection:
                    try:
                        await old_connection.close(code=1000, reason="預防性連接重建")
                    except Exception as close_error:
                        logger.warning(f"關閉舊連接時出錯: {str(close_error)}")
                
                # 等待一小段時間確保連接完全關閉
                await asyncio.sleep(2)
                
                # 建立新連接
                connected = await self.connect()
                if connected:
                    logger.info("預防性連接重建成功")
                    # 確保其他響應處理器和ping任務已關閉
                    self._start_background_tasks()
                else:
                    logger.error("預防性連接重建失敗")
            except Exception as rebuild_error:
                logger.error(f"預防性連接重建時出錯: {str(rebuild_error)}")
        else:
            # 定期記錄連接狀態但頻率更低（只有連接時間超過1小時且在調試模式下）
            if is_debug_mode and connection_age > 3600:  # 1小時以上才記錄
                # 計算距離需要重建的時間
                hours_until_rebuild = (self.max_connection_age - connection_age) / 3600
                if hours_until_rebuild < 1:  # 距離重建不到1小時
                    logger.debug(f"連接健康狀態良好，已存活 {connection_age/3600:.2f} 小時，將在 {hours_until_rebuild:.2f} 小時後進行預防性重建")
                elif connection_age > 3600 * 6:  # 存活超過6小時才記錄
                    # 每隔6小時記錄一次長時間連接的狀態
                    if int(connection_age / 3600) % 6 == 0:
                        logger.debug(f"連接長時間保持活躍，已存活 {connection_age/3600:.2f} 小時，運行正常")

    async def get_account_info(self) -> Dict[str, Any]:
        """
        通過 WebSocket 獲取U本位合約賬戶信息
        
        使用 'account.status' 方法查詢U本位合約賬戶狀態信息
        
        此方法會保持 WebSocket 連接，不會在獲取完資訊後斷開，
        以支持多次調用和長連接模式。
        
        Returns:
            U本位合約賬戶信息，包含餘額、持倉等資料
        """
        # 確保連接已建立
        if not self.connected or self.ws is None:
            logger.info("WebSocket 未連接，嘗試建立連接")
            connected = await self.connect()
            if not connected:
                raise ConnectionError("無法建立 WebSocket 連接")
        
        # 基本參數
        params = {
            "timestamp": int(time.time() * 1000),
            "recvWindow": 60000  # 延長接收窗口，避免時間同步問題
        }
        
        # 格式化參數
        formatted_params = self._format_params(params)
        
        # 生成請求ID
        request_id = str(uuid.uuid4())
        
        # 構建請求 - 使用正確的API方法
        request = {
            "id": request_id,
            "method": "account.status",  # 使用正確的合約賬戶狀態查詢方法
            "params": formatted_params
        }
        
        # 設置響應Future
        future = asyncio.get_event_loop().create_future()
        self.response_futures[request_id] = future
        
        # 發送請求
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # 檢查連接狀態
                if not self.connected or self.ws is None:
                    logger.warning("連接已關閉，嘗試重新連接...")
                    connected = await self.connect()
                    if not connected:
                        raise ConnectionError("重新連接失敗")
                
                try:
                    await self.ws.send(json.dumps(request))
                except Exception as e:
                    logger.error(f"發送WebSocket請求失敗: {str(e)}")
                    retry_count += 1
                    continue
                
                # 等待響應
                try:
                    response = await asyncio.wait_for(future, 10)  # 10秒超時
                    
                    # 檢查錯誤
                    if 'error' in response:
                        error_code = response['error']['code']
                        error_message = response['error']['msg']
                        
                        # 檢查是否需要重試
                        if error_code in [-1021, -1022]:  # 時間同步錯誤或簽名錯誤
                            logger.warning(f"時間同步或簽名錯誤: {error_message}，重試中...")
                            retry_count += 1
                            # 更新時間戳
                            formatted_params['timestamp'] = str(int(time.time() * 1000))
                            request['params'] = formatted_params
                            
                            # 清理舊的 future
                            if request_id in self.response_futures:
                                del self.response_futures[request_id]
                                
                            # 建立新的 future
                            request_id = str(uuid.uuid4())
                            request['id'] = request_id
                            future = asyncio.get_event_loop().create_future()
                            self.response_futures[request_id] = future
                            
                            continue
                        else:
                            # 其他錯誤，直接返回
                            raise ApiError(f"獲取U本位合約賬戶信息錯誤: {error_code} - {error_message}")
                    
                    # 如果沒有錯誤，則返回結果
                    result = response.get('result', {})
                    
                    # 添加 API 類型標記
                    if isinstance(result, dict):
                        result['api_type'] = 'FUTURES_WEBSOCKET'  # 標記為U本位合約WebSocket
                    
                    # 增加額外處理：如果是空響應或只有基本字段，標記為潛在問題
                    if isinstance(result, dict) and len(result.keys()) <= 2:
                        logger.warning(f"收到可能不完整的U本位合約賬戶信息，字段數量: {len(result.keys())}")
                        logger.debug(f"響應結果字段: {list(result.keys())}")
                    
                    return result
                    
                except asyncio.TimeoutError:
                    # 超時，重試
                    logger.warning("獲取U本位合約賬戶信息請求超時，重試中...")
                    retry_count += 1
                    
                    # 清理舊的 future
                    if request_id in self.response_futures:
                        del self.response_futures[request_id]
                        
                    # 建立新的 future
                    request_id = str(uuid.uuid4())
                    request['id'] = request_id
                    future = asyncio.get_event_loop().create_future()
                    self.response_futures[request_id] = future
                    
                    # 檢查連接狀態
                    if not self.connected or self.ws is None:
                        logger.warning("連接已關閉，嘗試重新連接...")
                        try:
                            connected = await self.connect()
                            if not connected:
                                logger.error("重新連接失敗")
                        except Exception as conn_err:
                            logger.error(f"重新連接過程中出錯: {str(conn_err)}")
                    
                    continue
                
            except Exception as e:
                # 其他錯誤，重試
                logger.error(f"獲取U本位合約賬戶信息過程中發生錯誤: {str(e)}")
                retry_count += 1
                
                # 清理舊的 future
                if request_id in self.response_futures:
                    del self.response_futures[request_id]
                
                # 檢查連接狀態
                if not self.connected or self.ws is None:
                    logger.warning("連接已關閉，嘗試重新連接...")
                    try:
                        connected = await self.connect()
                        if not connected:
                            logger.error("重新連接失敗")
                    except Exception as conn_err:
                        logger.error(f"重新連接過程中出錯: {str(conn_err)}")
                
                # 重新建立 future 和請求 ID
                if retry_count < max_retries:
                    request_id = str(uuid.uuid4())
                    request['id'] = request_id
                    future = asyncio.get_event_loop().create_future()
                    self.response_futures[request_id] = future
                
                continue
        
        # 超過最大重試次數
        raise ApiError("獲取U本位合約賬戶信息失敗: 超過最大重試次數")
    
    async def place_order(self, symbol: str, side: str, order_type: str, 
                          quantity: float = None, quote_quantity: float = None, price: float = None, 
                          time_in_force: str = None, stop_price: float = None, **kwargs) -> Dict:
        """
        通過 WebSocket 下單
        
        Args:
            symbol: 交易對
            side: 訂單方向 (BUY 或 SELL)
            order_type: 訂單類型 (LIMIT, MARKET, STOP_LOSS, 等)
            quantity: 訂單數量
            quote_quantity: 報價資產數量 (僅適用於部分訂單類型)
            price: 訂單價格 (對於 LIMIT 訂單是必需的)
            time_in_force: 訂單的生效時間 (GTC, IOC, FOK)
            stop_price: 觸發價格 (僅適用於部分訂單類型)
            **kwargs: 其他參數
            
        Returns:
            API 響應
        """
        # 基本參數
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
            "quoteOrderQty": quote_quantity,
            "price": price,
            "timeInForce": time_in_force,
            "stopPrice": stop_price,
            "timestamp": int(time.time() * 1000),
            "recvWindow": 60000  # 延長接收窗口，避免時間同步問題
        }
        
        # 如果沒有提供 positionSide，則根據 side 自動添加
        if "positionSide" not in kwargs:
            if side == "BUY":
                params["positionSide"] = "LONG"
            elif side == "SELL":
                params["positionSide"] = "SHORT"
        
        # 添加其他參數
        params.update(kwargs)
        
        # 格式化參數，移除 None 值，轉換布爾值等
        formatted_params = self._format_params(params)
        
        # 生成請求ID
        request_id = str(uuid.uuid4())
        
        # 構建請求
        request = {
            "id": request_id,
            "method": "order.place",
            "params": formatted_params
        }
        
        # 記錄請求
        logger.debug(f"下單請求: {json.dumps(request, ensure_ascii=False)}")
        
        # 設置響應Future
        future = asyncio.get_event_loop().create_future()
        self.response_futures[request_id] = future
        
        # 發送請求
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # 檢查連接狀態
                if not self.connected or self.ws is None:
                    logger.warning("連接已關閉，嘗試重新連接...")
                    connected = await self.connect()
                    if not connected:
                        raise ConnectionError("重新連接失敗")
                
                await self.ws.send(json.dumps(request))
                
                # 等待響應
                try:
                    response = await asyncio.wait_for(future, 10)  # 10秒超時
                    logger.debug(f"下單響應摘要: {_log_response_summary(response)}")
                    
                    # 檢查錯誤
                    if 'error' in response:
                        error_code = response['error']['code']
                        error_message = response['error']['msg']
                        
                        # 檢查是否需要重試
                        if error_code in [-1021, -1022]:  # 時間同步錯誤或簽名錯誤
                            logger.warning(f"時間同步或簽名錯誤: {error_message}，重試中...")
                            retry_count += 1
                            # 更新時間戳
                            formatted_params['timestamp'] = str(int(time.time() * 1000))
                            request['params'] = formatted_params
                            continue
                        else:
                            # 其他錯誤，直接返回
                            raise ApiError(f"下單錯誤: {error_code} - {error_message}")
                    
                    # 如果沒有錯誤，則返回結果
                    return response.get('result', response)
                    
                except asyncio.TimeoutError:
                    # 超時，重試
                    logger.warning("下單請求超時，重試中...")
                    retry_count += 1
                    continue
                    
            except Exception as e:
                # 其他錯誤，重試
                logger.error(f"下單過程中發生錯誤: {str(e)}")
                retry_count += 1
                
                continue
        
        # 超過最大重試次數
        raise ApiError("下單失敗: 超過最大重試次數")
    
    async def cancel_order(self, symbol: str, order_id: str = None, orig_client_order_id: str = None, **kwargs) -> Dict:
        """
        通過 WebSocket 取消訂單
        
        Args:
            symbol: 交易對
            order_id: 幣安訂單ID (與 orig_client_order_id 二選一)
            orig_client_order_id: 原始客戶端訂單ID (與 order_id 二選一)
            **kwargs: 其他參數
            
        Returns:
            API 響應
        """
        # 基本參數
        params = {
            "symbol": symbol,
            "orderId": order_id,
            "origClientOrderId": orig_client_order_id,
            "timestamp": int(time.time() * 1000),
            "recvWindow": 60000  # 延長接收窗口，避免時間同步問題
        }
        
        # 添加其他參數
        params.update(kwargs)
        
        # 格式化參數，移除 None 值，轉換布爾值等
        formatted_params = self._format_params(params)
        
        # 生成請求ID
        request_id = str(uuid.uuid4())
        
        # 構建請求
        request = {
            "id": request_id,
            "method": "order.cancel",
            "params": formatted_params
        }
        
        # 記錄請求
        logger.debug(f"取消訂單請求: {json.dumps(request, ensure_ascii=False)}")
        
        # 設置響應Future
        future = asyncio.get_event_loop().create_future()
        self.response_futures[request_id] = future
        
        # 發送請求
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # 檢查連接狀態
                if not self.connected or self.ws is None:
                    logger.warning("連接已關閉，嘗試重新連接...")
                    connected = await self.connect()
                    if not connected:
                        raise ConnectionError("重新連接失敗")
                
                await self.ws.send(json.dumps(request))
                
                # 等待響應
                try:
                    response = await asyncio.wait_for(future, 10)  # 10秒超時
                    logger.debug(f"取消訂單響應摘要: {_log_response_summary(response)}")
                    
                    # 檢查錯誤
                    if 'error' in response:
                        error_code = response['error']['code']
                        error_message = response['error']['msg']
                        
                        # 檢查是否需要重試
                        if error_code in [-1021, -1022]:  # 時間同步錯誤或簽名錯誤
                            logger.warning(f"時間同步或簽名錯誤: {error_message}，重試中...")
                            retry_count += 1
                            # 更新時間戳
                            formatted_params['timestamp'] = str(int(time.time() * 1000))
                            request['params'] = formatted_params
                            continue
                        elif error_code == -2011:  # 未知訂單，不存在或已取消
                            logger.warning(f"訂單未找到: {error_message}")
                            return {"status": "CANCELED", "message": "Order not found or already canceled"}
                        else:
                            # 其他錯誤，直接返回
                            raise ApiError(f"取消訂單錯誤: {error_code} - {error_message}")
                    
                    # 如果沒有錯誤，則返回結果
                    return response.get('result', response)
                    
                except asyncio.TimeoutError:
                    # 超時，重試
                    logger.warning("取消訂單請求超時，重試中...")
                    retry_count += 1
                    continue
                    
            except Exception as e:
                # 其他錯誤，重試
                logger.error(f"取消訂單過程中發生錯誤: {str(e)}")
                retry_count += 1
                
                continue
        
        # 超過最大重試次數
        raise ApiError("取消訂單失敗: 超過最大重試次數")
    
    def is_connected(self) -> bool:
        """
        檢查WebSocket連接是否仍然連接
        """
        return self.ws and self.ws.open

    def _format_params(self, params: Dict[str, Any]) -> Dict[str, str]:
        """
        格式化參數為 WebSocket API 要求的格式
        
        Args:
            params: 原始參數
            
        Returns:
            格式化後的參數
        """
        formatted = {}
        
        for key, value in params.items():
            # 跳過 None 值
            if value is None:
                continue
                
            # 將布爾值轉換為 'true' 或 'false'
            if isinstance(value, bool):
                formatted[key] = 'true' if value else 'false'
            # 將列表轉換為逗號分隔的字符串
            elif isinstance(value, list):
                formatted[key] = ','.join([str(item) for item in value])
            # 其他值轉換為字符串
            else:
                formatted[key] = str(value)
                
        return formatted

    def _start_background_tasks(self):
        """
        啟動響應處理器和ping保持活躍任務
        """
        # 清理之前的任務
        for task in self.tasks:
            if not task.done():
                task.cancel()
        self.tasks = []
        
        # 啟動新任務
        self.response_handler_task = asyncio.create_task(self._response_handler())
        self.ping_task = asyncio.create_task(self._ping_loop())
        
        # 添加到任務列表
        self.tasks.extend([self.response_handler_task, self.ping_task])
        logger.info("已啟動後台任務: 響應處理器和ping保持活躍")

    async def get_account_balance(self) -> Dict[str, Any]:
        """
        通過 WebSocket 獲取U本位合約賬戶餘額信息
        
        使用 'v2/account.balance' 方法查詢U本位合約賬戶餘額
        
        此方法會保持 WebSocket 連接，不會在獲取完資訊後斷開，
        以支持多次調用和長連接模式。
        
        Returns:
            U本位合約賬戶餘額信息，包含各資產餘額
        """
        # 確保連接已建立
        if not self.connected or self.ws is None:
            logger.info("WebSocket 未連接，嘗試建立連接")
            connected = await self.connect()
            if not connected:
                raise ConnectionError("無法建立 WebSocket 連接")
        
        # 基本參數
        params = {
            "timestamp": int(time.time() * 1000),
            "recvWindow": 60000  # 延長接收窗口，避免時間同步問題
        }
        
        # 格式化參數
        formatted_params = self._format_params(params)
        
        # 生成請求ID
        request_id = str(uuid.uuid4())
        
        # 構建請求 - 使用正確的API方法
        request = {
            "id": request_id,
            "method": "v2/account.balance",  # 使用 v2 版本的賬戶餘額查詢方法
            "params": formatted_params
        }
        
        # 記錄請求
        logger.debug(f"獲取U本位合約賬戶餘額請求: {json.dumps(request, ensure_ascii=False)}")
        
        # 設置響應Future
        future = asyncio.get_event_loop().create_future()
        self.response_futures[request_id] = future
        
        # 發送請求
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # 檢查連接狀態
                if not self.connected or self.ws is None:
                    logger.warning("連接已關閉，嘗試重新連接...")
                    connected = await self.connect()
                    if not connected:
                        raise ConnectionError("重新連接失敗")
                
                try:
                    await self.ws.send(json.dumps(request))
                
                    # 等待響應
                    try:
                        response = await asyncio.wait_for(future, 10)  # 10秒超時
                        logger.debug(f"U本位合約賬戶餘額響應摘要: {_log_response_summary(response)}")
                        
                        # 檢查錯誤
                        if 'error' in response:
                            error_code = response['error']['code']
                            error_message = response['error']['msg']
                            
                            # 檢查是否需要重試
                            if error_code in [-1021, -1022]:  # 時間同步錯誤或簽名錯誤
                                logger.warning(f"時間同步或簽名錯誤: {error_message}，重試中...")
                                retry_count += 1
                                # 更新時間戳
                                formatted_params['timestamp'] = str(int(time.time() * 1000))
                                request['params'] = formatted_params
                                
                                # 清理舊的 future
                                if request_id in self.response_futures:
                                    del self.response_futures[request_id]
                                    
                                # 建立新的 future
                                request_id = str(uuid.uuid4())
                                request['id'] = request_id
                                future = asyncio.get_event_loop().create_future()
                                self.response_futures[request_id] = future
                                
                                continue
                            else:
                                # 其他錯誤，直接返回
                                raise ApiError(f"獲取U本位合約賬戶餘額錯誤: {error_code} - {error_message}")
                        
                        # 如果沒有錯誤，則返回結果
                        result = response.get('result', {})
                        
                        # 添加 API 類型標記
                        if isinstance(result, list):
                            for item in result:
                                if isinstance(item, dict):
                                    item['api_type'] = 'FUTURES_WEBSOCKET'  # 標記為U本位合約WebSocket
                        
                        # 增加額外處理：如果是空響應，標記為潛在問題
                        if isinstance(result, list) and len(result) == 0:
                            logger.warning("收到空的U本位合約賬戶餘額列表")
                        
                        return result
                        
                    except asyncio.TimeoutError:
                        # 超時，重試
                        logger.warning("獲取U本位合約賬戶餘額請求超時，重試中...")
                        retry_count += 1
                        
                        # 清理舊的 future
                        if request_id in self.response_futures:
                            del self.response_futures[request_id]
                            
                        # 建立新的 future
                        request_id = str(uuid.uuid4())
                        request['id'] = request_id
                        future = asyncio.get_event_loop().create_future()
                        self.response_futures[request_id] = future
                        
                        # 檢查連接狀態
                        if not self.connected or self.ws is None:
                            logger.warning("連接已關閉，嘗試重新連接...")
                            try:
                                connected = await self.connect()
                                if not connected:
                                    logger.error("重新連接失敗")
                            except Exception as conn_err:
                                logger.error(f"重新連接過程中出錯: {str(conn_err)}")
                    
                        continue
                except Exception as e:
                    logger.error(f"發送請求或處理響應時出錯: {str(e)}")
                    retry_count += 1
                    continue
                
            except Exception as e:
                # 其他錯誤，重試
                logger.error(f"獲取U本位合約賬戶餘額過程中發生錯誤: {str(e)}")
                retry_count += 1
                
                # 清理舊的 future
                if request_id in self.response_futures:
                    del self.response_futures[request_id]
                
                # 檢查連接狀態
                if not self.connected or self.ws is None:
                    logger.warning("連接已關閉，嘗試重新連接...")
                    try:
                        connected = await self.connect()
                        if not connected:
                            logger.error("重新連接失敗")
                    except Exception as conn_err:
                        logger.error(f"重新連接過程中出錯: {str(conn_err)}")
                
                # 重新建立 future 和請求 ID
                if retry_count < max_retries:
                    request_id = str(uuid.uuid4())
                    request['id'] = request_id
                    future = asyncio.get_event_loop().create_future()
                    self.response_futures[request_id] = future
                
                continue
        
        # 超過最大重試次數
        raise ApiError("獲取U本位合約賬戶餘額失敗: 超過最大重試次數")

    async def refresh_auth(self):
        """
        重新進行身份驗證
        
        當使用長期連接時，認證可能會過期
        此方法用於重新進行身份驗證，以確保 API 請求能夠正常處理
        
        Returns:
            bool: 重新認證是否成功
        """
        try:
            logger.info("開始重新進行身份驗證")
            
            # 構建認證請求參數
            params = {
                "apiKey": self.api_key,
                "timestamp": str(int(time.time() * 1000)),
                "recvWindow": "15000"  # 增加接收窗口時間到15秒，避免時間同步問題
            }
            
            # 按參數名稱排序
            sorted_params = {key: params[key] for key in sorted(params.keys())}
            
            try:
                # 生成簽名
                logger.debug("正在生成重新認證簽名")
                signature = self.sign_parameters(sorted_params)
                sorted_params["signature"] = signature
                
                # 構建認證請求
                request_id = str(uuid.uuid4())
                auth_request = {
                    "id": request_id,
                    "method": "session.logon",
                    "params": sorted_params
                }
                
                # 關鍵修改：創建一個Future對象並存儲在response_futures中
                future = asyncio.get_event_loop().create_future()
                self.response_futures[request_id] = future
                
                # 發送認證請求
                await self.ws.send(json.dumps(auth_request))
                
                # 等待認證響應
                try:
                    # 使用future等待響應，而不是直接等待接收消息
                    response_data = await asyncio.wait_for(future, timeout=15)
                    
                    # 檢查認證是否成功
                    if 'error' in response_data:
                        error_code = response_data.get('error', {}).get('code', 'unknown')
                        error_msg = response_data.get('error', {}).get('msg', 'Unknown error')
                        logger.error(f"重新認證失敗: 錯誤碼 {error_code}, 錯誤信息: {error_msg}")
                        
                        if error_code == -4056:
                            logger.error("HMAC_SHA256 API 密鑰不支持 WebSocket API，請在幣安 API 管理界面創建 Ed25519 密鑰")
                        elif error_code == -1022 or "signature" in error_msg.lower():
                            logger.error("簽名無效，請檢查 API Secret 格式和正確性")
                        elif error_code == -1099:
                            logger.error("API密鑰無權限或未找到，請檢查 API Key 和權限設置")
                            
                        self.authenticated = False
                        return False
                    elif 'result' in response_data and response_data.get('result', None) is not None:
                        logger.info("重新認證成功")
                        self.authenticated = True
                        return True
                    else:
                        logger.error("重新認證響應格式異常")
                        self.authenticated = False
                        return False
                except asyncio.TimeoutError:
                    logger.error("重新認證響應超時")
                    self.authenticated = False
                    return False
                except Exception as e:
                    logger.error(f"重新認證過程中發生錯誤: {str(e)}")
                    self.authenticated = False
                    return False
                finally:
                    # 清理：確保無論成功失敗都從response_futures中移除
                    if request_id in self.response_futures:
                        del self.response_futures[request_id]
            except Exception as e:
                logger.error(f"生成重新認證簽名時出錯: {str(e)}")
                self.authenticated = False
                return False
                
        except Exception as e:
            logger.error(f"重新認證過程中發生錯誤: {str(e)}")
            self.authenticated = False
            return False
            
        return self.authenticated


class ConnectionError(Exception):
    """WebSocket連接錯誤"""
    pass


class AuthenticationError(Exception):
    """WebSocket認證錯誤"""
    pass


class WebSocketAPIError(Exception):
    """WebSocket API 錯誤"""
    pass


class ApiError(Exception):
    """幣安API錯誤"""
    
    def __init__(self, message):
        super().__init__(message)
        self.message = message
        
    def __str__(self):
        return self.message 

def _log_response_summary(response):
    """
    記錄響應摘要而不是完整的JSON數據
    生成一個包含關鍵信息但排除大量數據的摘要
    """
    if not response:
        return "無響應數據"
    
    try:
        # 創建響應摘要
        summary = {}
        
        # 記錄基本信息
        if isinstance(response, dict):
            # 添加ID和狀態
            if 'id' in response:
                summary['id'] = response['id']
            if 'status' in response:
                summary['status'] = response['status']
            
            # 檢查result字段
            if 'result' in response and isinstance(response['result'], dict):
                result_summary = {}
                
                # 處理帳戶信息
                if 'assets' in response['result']:
                    result_summary['assets_count'] = len(response['result']['assets'])
                
                if 'positions' in response['result']:
                    result_summary['positions_count'] = len(response['result']['positions'])
                
                # 添加其他關鍵字段
                for key in ['totalWalletBalance', 'availableBalance', 'totalUnrealizedProfit']:
                    if key in response['result']:
                        result_summary[key] = response['result'][key]
                
                # 處理訂單結果
                if 'orderId' in response['result']:
                    result_summary['orderId'] = response['result']['orderId']
                if 'status' in response['result']:
                    result_summary['status'] = response['result']['status']
                if 'symbol' in response['result']:
                    result_summary['symbol'] = response['result']['symbol']
                
                summary['result'] = result_summary
            
            # 處理錯誤
            if 'error' in response and isinstance(response['error'], dict):
                summary['error'] = response['error']
        
        # 如果無法提取有用信息，則返回類型和大小信息
        if not summary:
            return f"響應類型: {type(response).__name__}, 大小: {len(str(response))}字節"
        
        import json
        return json.dumps(summary, ensure_ascii=False)
    except Exception as e:
        # 如果處理過程中出錯，返回簡單信息
        return f"響應類型: {type(response).__name__}, 大小: {len(str(response))}字節, 處理錯誤: {str(e)}"