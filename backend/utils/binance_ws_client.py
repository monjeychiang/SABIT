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

    def __init__(self, api_key: str, api_secret: str, testnet: bool = False) -> None:
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
            testnet: 是否使用測試網
            
        注意:
            幣安 WebSocket API 要求使用 Ed25519 密鑰進行簽名。
            您需要在幣安 API 管理界面生成一個專用的 WebSocket API 密鑰。
            
            兩種獲取 API 的方式:
            1. 讓幣安生成密鑰對 (推薦新手使用)
               - 在幣安API管理界面創建密鑰
               - 幣安會生成 API Key 和 API Secret
               - API Secret 通常是 64 字符的十六進制格式
               
            2. 自行生成密鑰對 (適合高級用戶)
               - 自行生成 Ed25519 密鑰對
               - 向幣安提供公鑰
               - 自行保管私鑰 (API Secret)
               - 私鑰通常是 Base64 格式，可能是 PKCS#8 結構
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        
        # 記錄關鍵信息以幫助診斷
        self.logger = logger
        self.logger.info(f"API Key (公開識別符) 長度: {len(api_key)}")
        self.logger.info(f"API Secret (私鑰) 長度: {len(api_secret)}")
        
        # 檢查 API Secret 格式
        contains_base64_chars = '+' in api_secret or '/' in api_secret or '=' in api_secret
        is_hex_format = len(api_secret) == 64 and all(c in '0123456789abcdefABCDEF' for c in api_secret)
        
        if contains_base64_chars:
            self.logger.info("檢測到 API Secret 可能是 Base64 格式的 Ed25519 私鑰 (包含特殊字符)")
            # 嘗試解碼看是否為 PKCS#8 格式 (48 字節)
            try:
                import base64
                decoded = base64.b64decode(api_secret)
                if len(decoded) == 48:
                    self.logger.info("檢測到 PKCS#8 格式的 Ed25519 私鑰 (48 字節) - 這是標準的私鑰格式")
            except Exception:
                pass
        elif is_hex_format:
            self.logger.info("檢測到標準的十六進制格式 Ed25519 私鑰 (64字符) - 這是幣安直接提供的格式")
        else:
            self.logger.warning("API Secret 格式無法識別，既不是 Base64 也不是標準十六進制格式")
            self.logger.warning("這可能導致認證問題")
        
        # 初始化Ed25519密鑰管理器 - 不生成新的密鑰對
        try:
            from backend.utils.ed25519_util import Ed25519KeyManager
            self.key_manager = Ed25519KeyManager(generate_key_pair=False)
            self.logger.debug("成功初始化 Ed25519 密鑰管理器")
        except Exception as e:
            self.logger.error(f"初始化 Ed25519 密鑰管理器時出錯: {str(e)}")
            raise ValueError(f"初始化密鑰管理器失敗: {str(e)}")
        
        # WebSocket終端點 - 修改為U本位合約的端點
        if testnet:
            self.endpoint = "wss://stream.binancefuture.com/ws-api/v3"  # U本位合約測試網端點
        else:
            self.endpoint = "wss://ws-fapi.binance.com/ws-fapi/v1"  # U本位合約正式網端點
        
        # 記錄使用的端點
        self.logger.info(f"使用的 WebSocket 端點: {self.endpoint}")
        
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
        self.logger.debug(f"待簽名參數: {query_string}")
        
        try:
            # 檢查 API Secret 中的特殊字符
            special_chars = []
            for char in ['+', '/', '=']:
                if char in self.api_secret:
                    special_chars.append(char)
            
            if special_chars:
                self.logger.debug(f"API Secret 中包含特殊字符: {special_chars}")
            
            # 1. 首先檢查 API Secret 是否為 PEM 格式 (帶頭尾標記)
            is_pem_format = self.api_secret.strip().startswith("-----BEGIN") and self.api_secret.strip().endswith("-----")
            
            if is_pem_format:
                self.logger.info("檢測到 PEM 格式的 Ed25519 私鑰 (帶標準頭尾標記)")
                
                # 檢測並處理單行PEM格式
                if "\n" not in self.api_secret:
                    self.logger.info("檢測到單行PEM格式，嘗試添加換行符")
                    try:
                        # 提取密鑰類型 (例如 "PRIVATE KEY")
                        key_type = self.api_secret.split("-----BEGIN ")[1].split("-----")[0].strip()
                        
                        # 提取Base64內容
                        base64_content = self.api_secret.split(f"-----BEGIN {key_type}-----")[1]
                        base64_content = base64_content.split(f"-----END {key_type}-----")[0].strip()
                        
                        # 重新格式化為標準PEM格式
                        formatted_key = f"-----BEGIN {key_type}-----\n{base64_content}\n-----END {key_type}-----"
                        
                        self.logger.info(f"已將單行PEM格式轉換為標準多行格式，用於簽名 (類型: {key_type})")
                        
                        # 使用格式化後的密鑰進行簽名
                        signature = self.key_manager.sign_message(query_string, private_key=formatted_key)
                        self.logger.debug(f"使用格式化後的PEM格式私鑰生成簽名成功: {signature[:10]}...")
                        return signature
                    except Exception as e:
                        self.logger.warning(f"單行PEM格式處理失敗: {str(e)}，將嘗試原始密鑰")
                
                try:
                    # 直接使用密鑰管理器處理 PEM 格式
                    signature = self.key_manager.sign_message(query_string, private_key=self.api_secret)
                    self.logger.debug(f"使用 PEM 格式私鑰生成簽名成功: {signature[:10]}...")
                    return signature
                except Exception as e:
                    self.logger.error(f"使用 PEM 格式私鑰生成簽名失敗: {str(e)}")
                    # 失敗後將嘗試後續方法
            
            # 2. 嘗試使用密鑰管理器的通用簽名方法
            try:
                self.logger.debug("嘗試使用密鑰管理器的 sign_message 方法")
                signature = self.key_manager.sign_message(query_string, private_key=self.api_secret)
                self.logger.debug(f"成功生成簽名: {signature[:10]}...")
                return signature
            except Exception as e:
                self.logger.warning(f"使用密鑰管理器簽名失敗: {str(e)}，嘗試其他方法")
            
            # 3. 檢查 API Secret 是否為自行生成的 Base64 格式
            contains_base64_chars = '+' in self.api_secret or '/' in self.api_secret or '=' in self.api_secret
            
            if contains_base64_chars:
                self.logger.debug("檢測到 API Secret 可能是 Base64 格式的 Ed25519 私鑰")
                
                # 檢查是否為 PKCS#8 格式的 Ed25519 私鑰
                is_pkcs8_format = False
                try:
                    import base64
                    decoded_key = base64.b64decode(self.api_secret)
                    if len(decoded_key) == 48:
                        self.logger.info("檢測到 API Secret 可能是 PKCS#8 格式的 Ed25519 私鑰 (48 字節)")
                        is_pkcs8_format = True
                        
                        # 提取私鑰部分(後32字節)
                        actual_key = decoded_key[16:]
                        self.logger.debug(f"從 PKCS#8 格式提取的私鑰長度: {len(actual_key)} 字節")
                        
                        # 直接使用 PyNaCl 簽名
                        import nacl.signing
                        signing_key = nacl.signing.SigningKey(actual_key)
                        signed_message = signing_key.sign(query_string.encode())
                        signature = base64.b64encode(signed_message.signature).decode('utf-8')
                        self.logger.debug(f"直接使用提取的私鑰生成簽名成功: {signature[:10]}...")
                        return signature
                except Exception as e:
                    self.logger.error(f"直接處理 PKCS#8 格式的 API Secret 失敗: {str(e)}")
                
                try:
                    # 使用密鑰管理器處理 API Secret 簽名
                    signature = self.key_manager.sign_message(query_string, private_key=self.api_secret)
                    if is_pkcs8_format:
                        self.logger.debug(f"使用 PKCS#8 格式 Ed25519 私鑰生成簽名成功: {signature[:10]}...")
                    else:
                        self.logger.debug(f"使用 Base64 格式 Ed25519 私鑰生成簽名成功: {signature[:10]}...")
                    return signature
                except Exception as e:
                    self.logger.error(f"使用 Base64 格式 API Secret 生成簽名時出錯: {str(e)}")
                    # 如果失敗，將嘗試後續方法
            
            # 4. 檢查 API Secret 是否為幣安提供的十六進制格式 (64字符, 0-9a-fA-F)
            is_hex_format = len(self.api_secret) == 64 and all(c in '0123456789abcdefABCDEF' for c in self.api_secret)
            
            if is_hex_format:
                self.logger.debug("檢測到 API Secret 為十六進制格式的 Ed25519 私鑰 (64字符)")
                try:
                    # 將十六進制轉換為字節
                    key_bytes = bytes.fromhex(self.api_secret)
                    self.logger.debug(f"十六進制密鑰解碼為 {len(key_bytes)} 字節")
                    
                    # 直接使用 PyNaCl 簽名
                    import nacl.signing
                    
                    # 創建簽名密鑰
                    signing_key = nacl.signing.SigningKey(key_bytes)
                    
                    # 生成簽名
                    signed_message = signing_key.sign(query_string.encode())
                    signature = base64.b64encode(signed_message.signature).decode('utf-8')
                    self.logger.debug(f"使用十六進制格式的 API Secret 生成簽名成功: {signature[:10]}...")
                    return signature
                except Exception as e:
                    self.logger.error(f"使用十六進制格式 API Secret 生成簽名時出錯: {str(e)}")
            
            # 5. 最後使用直接簽名
            try:
                import nacl.signing
                import base64
                
                # 嘗試使用原始字符串
                key_bytes = self.api_secret.encode('utf-8')
                self.logger.warning(f"嘗試使用原始 API Secret 字符串作為私鑰，長度: {len(key_bytes)} 字節")
                
                if len(key_bytes) == 32:
                    signing_key = nacl.signing.SigningKey(key_bytes)
                elif len(key_bytes) > 32:
                    signing_key = nacl.signing.SigningKey(key_bytes[:32])
                    self.logger.warning("截斷 API Secret 至前 32 字節")
                else:
                    # 如果不夠32字節，填充
                    padded_key = key_bytes.ljust(32, b'\0')
                    signing_key = nacl.signing.SigningKey(padded_key)
                    self.logger.warning("API Secret 不足 32 字節，已填充")
                
                signed_message = signing_key.sign(query_string.encode())
                signature = base64.b64encode(signed_message.signature).decode('utf-8')
                self.logger.debug(f"成功生成 Ed25519 簽名: {signature[:10]}...")
                return signature
            except Exception as final_e:
                self.logger.error(f"所有簽名方法都失敗: {str(final_e)}")
                raise ValueError(f"無法使用提供的 API Secret 生成有效的 Ed25519 簽名: {str(final_e)}")
        except Exception as e:
            self.logger.error(f"簽名生成過程中出錯: {str(e)}")
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
            self.logger.info("WebSocket 已連接")
            return True
            
        self.closed = False
        self.logger.info(f"連接到幣安 WebSocket API: {self.endpoint}")
        
        # 預先檢查認證密鑰格式
        is_pem_format = self.api_secret.strip().startswith("-----BEGIN") and self.api_secret.strip().endswith("-----")
        contains_base64_chars = '+' in self.api_secret or '/' in self.api_secret or '=' in self.api_secret
        is_hex_format = len(self.api_secret) == 64 and all(c in '0123456789abcdefABCDEF' for c in self.api_secret)
        
        # 添加基本的格式診斷
        if is_pem_format:
            self.logger.debug("使用 PEM 格式的 Ed25519 私鑰進行認證")
        elif contains_base64_chars:
            self.logger.debug("使用 Base64 格式的 Ed25519 私鑰進行認證")
        elif is_hex_format:
            self.logger.debug("使用十六進制格式的 Ed25519 私鑰進行認證")
        else:
            self.logger.warning("API Secret 格式無法識別，可能會導致認證失敗")
        
        try:
            # 建立 WebSocket 連接
            self.ws = await websockets.connect(
                self.endpoint,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10
            )
            
            self.connected = True
            self.logger.info("WebSocket 連接成功")
            
            # 初始化同步鎖，用於防止多個協程同時接收消息
            self.recv_lock = asyncio.Lock()
            
            # 認證
            try:
                self.logger.info("開始進行認證流程 (使用 session.logon 方法)")
                auth_success = await self._authenticate()
                if not auth_success:
                    self.logger.error("認證失敗，WebSocket API 功能可能不可用")
                    self.logger.info("請執行以下檢查:")
                    self.logger.info("1. 確認您的 API Key 和 API Secret 是否正確配對")
                    
                    # 針對不同密鑰格式提供具體建議
                    if is_pem_format:
                        self.logger.info("PEM 格式檢查:")
                        self.logger.info("- 確保 PEM 格式完整，包含標準頭尾標記和所有換行符")
                        self.logger.info("- 確認使用的是私鑰，而不是公鑰")
                        self.logger.info("- 確認提供給幣安的是對應的公鑰")
                    elif contains_base64_chars:
                        self.logger.info("Base64 格式檢查:")
                        self.logger.info("- 確保密鑰未被額外編碼或截斷")
                        self.logger.info("- 如果是 PKCS#8 格式，需要正確提取 32 字節的實際密鑰")
                    
                    self.logger.info("2. 確認您的 API Key 已啟用並具有 WebSocket API 權限")
                    self.logger.info("3. 檢查 API Key 是否有 IP 限制，確保您的 IP 在允許列表中")
                    self.logger.info("4. 如果您自行生成了密鑰對，確認向幣安註冊的是正確的公鑰")
                    self.logger.info("5. 嘗試在幣安 API 管理界面刪除並重新創建一個 API Key")
                    self.logger.info("6. 如果仍有問題，請聯繫幣安客戶支持")
                    
                    await self.disconnect()
                    return False
            except Exception as e:
                self.logger.error(f"認證過程中出錯: {str(e)}")
                self.logger.error("認證過程異常中止，請檢查您的網絡連接和 API 配置")
                await self.disconnect()
                return False
            
            # 啟動響應處理器和ping任務
            self._start_background_tasks()
            return True
        except Exception as e:
            self.logger.error(f"WebSocket 連接失敗: {str(e)}")
            self.logger.error("無法連接到幣安 WebSocket API，請檢查您的網絡連接")
            self.connected = False
            if self.ws:
                await self.ws.close()
                self.ws = None
            return False
    
    async def disconnect(self) -> None:
        """斷開與幣安WebSocket API的連接"""
        try:
            if self.ping_task:
                self.ping_task.cancel()
                self.ping_task = None
                
            if self.response_handler_task:
                self.response_handler_task.cancel()
                self.response_handler_task = None
            
            if self.ws:
                await self.ws.close()
                self.ws = None
                
            self.connected = False
            self.authenticated = False
            logger.info("已斷開與幣安WebSocket API的連接")
            
        except Exception as e:
            logger.error(f"斷開WebSocket連接時出錯: {str(e)}")
    
    async def _authenticate(self) -> bool:
        """
        使用 Ed25519 簽名認證 WebSocket 連接
        幣安的 WebSocket API 需要使用 Ed25519 密鑰，而不是 HMAC-SHA256 密鑰
        
        認證方法:
        正確的WebSocket認證方法是 'session.logon'，不是 'auth'
        參考: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-api-general-info#log-in-with-api-key-signed
        
        密鑰說明：
        1. API Key 是您的公開識別符，不需要解碼
        2. API Secret 是您的私鑰，用於生成簽名
           - 支持 PEM 格式 (帶有 -----BEGIN PRIVATE KEY----- 標記)
           - 支持 Base64 格式 (包含 +, /, = 等字符)
           - 支持 PKCS#8 格式 (解碼後為 48 字節)
           - 支持十六進制格式 (64字符)
        """
        self.logger.info("開始 WebSocket 認證...")
        
        # 檢查API密鑰格式和長度
        if not self.api_key or not self.api_secret:
            self.logger.error("API密鑰或密鑰密碼為空")
            return False
        
        # 詳細檢查並記錄API密鑰信息
        self.logger.info(f"API Key (公開識別符) 長度: {len(self.api_key)}")
        self.logger.info(f"API Secret (私鑰) 長度: {len(self.api_secret)}")
        
        # 更詳細檢查 API Key
        if len(self.api_key) != 64:
            self.logger.warning(f"API Key 長度 ({len(self.api_key)}) 不是標準的 64 字符長度，可能有問題")
        
        # 更詳細檢查 API Secret 內容
        special_chars = []
        for char in ['+', '/', '=']:
            if char in self.api_secret:
                special_chars.append(char)
                
        if special_chars:
            self.logger.warning(f"API Secret 中包含特殊字符: {special_chars}，這在幣安提供的十六進制格式中是不正常的")
        
        # 顯示 API Secret 的前 4 個和後 4 個字符（用於診斷但不泄露完整密鑰）
        prefix = self.api_secret[:4] if len(self.api_secret) >= 4 else self.api_secret
        suffix = self.api_secret[-4:] if len(self.api_secret) >= 4 else ""
        self.logger.info(f"API Secret 前綴: {prefix}... 後綴: ...{suffix}")
        
        # 檢查 API Secret 是否為 PEM 格式
        is_pem_format = self.api_secret.strip().startswith("-----BEGIN") and self.api_secret.strip().endswith("-----")
        
        if is_pem_format:
            self.logger.info("檢測到 PEM 格式的 Ed25519 私鑰 (帶有標準頭尾標記)")
            
            # 檢測是否為單行PEM格式，並進行處理
            if "\n" not in self.api_secret:
                self.logger.info("檢測到單行PEM格式，嘗試添加換行符")
                
                # 提取密鑰類型和內容部分
                try:
                    # 提取頭部類型 (例如 "PRIVATE KEY")
                    key_type = self.api_secret.split("-----BEGIN ")[1].split("-----")[0].strip()
                    
                    # 提取Base64內容
                    base64_content = self.api_secret.split(f"-----BEGIN {key_type}-----")[1]
                    base64_content = base64_content.split(f"-----END {key_type}-----")[0].strip()
                    
                    # 重新格式化為標準PEM格式
                    formatted_key = f"-----BEGIN {key_type}-----\n{base64_content}\n-----END {key_type}-----"
                    
                    self.logger.info(f"已將單行PEM格式轉換為標準多行格式 (類型: {key_type})")
                    
                    # 使用格式化後的密鑰替換原始密鑰
                    self.api_secret = formatted_key
                except Exception as e:
                    self.logger.warning(f"單行PEM格式處理失敗: {str(e)}，將嘗試其他方式處理")
            
            try:
                # 提取 Base64 內容 (去掉頭尾標記和換行符)
                lines = self.api_secret.strip().split('\n')
                if len(lines) < 3:
                    self.logger.warning("PEM 格式不完整，缺少必要的行")
                else:
                    base64_content = ''.join(lines[1:-1]).replace(' ', '')
                    self.logger.debug(f"從 PEM 格式提取的 Base64 內容長度: {len(base64_content)}")
                    
                    # 嘗試解碼
                    try:
                        import base64
                        decoded = base64.b64decode(base64_content)
                        self.logger.debug(f"PEM 內容解碼後的長度: {len(decoded)} 字節")
                        
                        # 根據長度提供診斷
                        if len(decoded) == 48:
                            self.logger.info("檢測到 PKCS#8 格式的 Ed25519 私鑰 (48 字節)")
                            self.logger.info("這是標準的私鑰存儲格式，將提取 32 字節的實際私鑰數據")
                        elif len(decoded) == 32:
                            self.logger.info("解碼後得到標準的 32 字節 Ed25519 私鑰")
                        else:
                            self.logger.warning(f"PEM 內容解碼後長度 ({len(decoded)} 字節) 不是標準的 32 或 48 字節")
                    except Exception as e:
                        self.logger.error(f"PEM 內容 Base64 解碼失敗: {str(e)}")
            except Exception as e:
                self.logger.error(f"處理 PEM 格式時出錯: {str(e)}")
        
        # 檢查私鑰(API Secret)是否為 Base64 格式
        contains_base64_chars = '+' in self.api_secret or '/' in self.api_secret or '=' in self.api_secret
        
        if contains_base64_chars and not is_pem_format:
            self.logger.info("檢測到 API Secret 可能是 Base64 格式的 Ed25519 私鑰 (包含特殊字符)")
            try:
                # 嘗試解碼以驗證有效性
                import base64
                decoded = base64.b64decode(self.api_secret)
                self.logger.debug(f"Base64 解碼後的私鑰長度: {len(decoded)} 字節")
                
                # 特殊處理 PKCS#8 格式 (48 字節)
                if len(decoded) == 48:
                    self.logger.info("檢測到 PKCS#8 格式的 Ed25519 私鑰 (48 字節)")
                    self.logger.info("這是標準的私鑰存儲格式，包含算法標識符和私鑰數據")
                    self.logger.info("系統將提取實際的 32 字節私鑰數據")
                elif len(decoded) > 32:
                    self.logger.warning(f"Base64 解碼後的私鑰長度 ({len(decoded)}) 大於標準的 32 字節")
                    self.logger.info("系統將使用適當部分，這應該包含有效的私鑰數據")
                elif len(decoded) < 32:
                    self.logger.warning(f"Base64 解碼後的私鑰長度 ({len(decoded)}) 小於標準的 32 字節")
                    self.logger.warning("這可能會導致認證失敗，但系統將嘗試處理")
                else:
                    self.logger.info("Base64 解碼後的私鑰長度正好是標準的 32 字節，應該能正常工作")
            except Exception as e:
                self.logger.warning(f"嘗試解碼 Base64 格式私鑰時出錯: {str(e)}")
                self.logger.warning("這可能不是有效的 Base64 格式，或包含額外字符")
        else:
            # 檢查私鑰(API Secret)是否為十六進制格式
            is_hex_format = len(self.api_secret) == 64 and all(c in '0123456789abcdefABCDEF' for c in self.api_secret)
            
            if is_hex_format and not is_pem_format:
                self.logger.info("檢測到標準的十六進制格式 Ed25519 私鑰 (64字符)，這是幣安常見格式")
                try:
                    # 嘗試將十六進制轉換為字節以驗證有效性
                    hex_bytes = bytes.fromhex(self.api_secret)
                    self.logger.debug(f"十六進制密鑰有效，轉換為 {len(hex_bytes)} 字節")
                except Exception as e:
                    self.logger.warning(f"十六進制密鑰可能包含無效字符: {str(e)}")
            elif not is_pem_format:
                self.logger.warning(f"API Secret 格式無法識別，既不是 PEM 格式、Base64 也不是標準十六進制格式")
                self.logger.warning("這可能導致認證失敗，請確保使用正確的格式")
        
        if not self.authenticated:
            # 構建認證請求參數
            params = {
                "apiKey": self.api_key,  # API Key 是公開識別符，保持原樣
                "timestamp": str(int(time.time() * 1000)),
                "recvWindow": "15000"  # 增加接收窗口時間到15秒，避免時間同步問題
            }
            
            # 按參數名稱排序
            sorted_params = {key: params[key] for key in sorted(params.keys())}
            
            try:
                # 生成簽名 (使用 API Secret)
                self.logger.debug("開始生成認證簽名")
                signature = self.sign_parameters(sorted_params)
                sorted_params["signature"] = signature
                
                # 構建認證請求
                auth_request = {
                    "id": str(uuid.uuid4()),
                    "method": "session.logon",
                    "params": sorted_params
                }
                
                self.logger.info(f"發送認證請求: {json.dumps(auth_request, ensure_ascii=False)}")
                
                # 發送認證請求
                await self.ws.send(json.dumps(auth_request))
                
                # 等待認證響應
                try:
                    # 使用鎖確保只有一個協程在等待消息
                    response = None
                    async with self.recv_lock:
                        response = await asyncio.wait_for(self.ws.recv(), timeout=15)
                    
                    if not response:
                        self.logger.error("未能接收到認證響應")
                        self.authenticated = False
                        return False
                    
                    response_data = json.loads(response)
                    self.logger.info(f"收到認證響應: {json.dumps(response_data, ensure_ascii=False)}")
                    
                    # 檢查認證是否成功
                    if 'error' in response_data:
                        error_code = response_data.get('error', {}).get('code', 'unknown')
                        error_msg = response_data.get('error', {}).get('msg', 'Unknown error')
                        self.logger.error(f"認證失敗: 錯誤碼 {error_code}, 錯誤信息: {error_msg}")
                        
                        if error_code == -4056:
                            self.logger.error("HMAC_SHA256 API 密鑰不支持 WebSocket API。請在幣安 API 管理界面創建 Ed25519 密鑰。")
                            self.logger.error("請參考幣安文檔: https://developers.binance.com/docs/binance-trading-api/websocket-api#generate-ed25519-key")
                        elif error_code == -1022 or "signature" in error_msg.lower():
                            self.logger.error("簽名無效。請檢查以下可能的問題:")
                            
                            if is_pem_format:
                                self.logger.error("您使用的是 PEM 格式的私鑰，請確認:")
                                self.logger.error("1. PEM 格式正確，包含完整的頭尾標記")
                                self.logger.error("2. PEM 內容是有效的私鑰數據")
                                self.logger.error("3. 您向幣安提供的是對應的公鑰")
                            elif contains_base64_chars:
                                self.logger.error("您使用的是 Base64 格式的私鑰，請確認:")
                                self.logger.error("1. 這是您生成密鑰對時得到的完整原始私鑰")
                                self.logger.error("2. 您向幣安提供的是對應的公鑰")
                                self.logger.error("3. 您沒有對私鑰進行任何格式轉換或修改")
                                
                                # PKCS#8 格式相關提示
                                try:
                                    if len(decoded) == 48:
                                        self.logger.error("您的私鑰為 PKCS#8 格式 (48 字節)，這是標準格式，但需要正確處理")
                                except Exception:
                                    pass
                            else:
                                self.logger.error("請確保您使用的是正確格式的 Ed25519 私鑰:")
                                self.logger.error("1. 幣安提供的十六進制格式 (64字符)")
                                self.logger.error("2. 或自行生成的 Base64 格式 (包含 +, /, = 等字符)")
                                self.logger.error("3. 或完整的 PEM 格式 (帶有 BEGIN/END 標記)")
                            
                            self.logger.error("請參考文檔: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-api-general-info")
                            
                        elif error_code == -1099:
                            self.logger.error("API密鑰無權限或未找到。請檢查:")
                            self.logger.error("1. API密鑰是否為Ed25519類型")
                            self.logger.error("2. API密鑰是否有WebSocket權限")
                            self.logger.error("3. API密鑰是否啟用")
                            self.logger.error("4. 是否已經在API管理頁面啟用了WebSocket API的使用") 
                            self.logger.error("5. 您是否需要調整IP訪問限制")
                            self.logger.error("6. API密鑰是否被刪除或重置")
                            self.logger.error("7. API Key 和 API Secret 是否配對正確")
                            self.logger.error("8. 使用幣安 API 管理界面重新生成一個全新的 API Key")
                            self.logger.error("9. 確認您使用的認證方法是 'session.logon'")
                            
                        self.authenticated = False
                        return False
                    elif 'result' in response_data and response_data.get('result', None) is not None:
                        self.logger.info("認證成功")
                        self.authenticated = True
                        return True
                    else:
                        self.logger.error(f"認證響應格式異常: {response_data}")
                        self.authenticated = False
                        return False
                except asyncio.TimeoutError:
                    self.logger.error("認證響應超時")
                    self.authenticated = False
                    return False
                except Exception as e:
                    self.logger.error(f"認證過程中發生錯誤: {str(e)}")
                    self.authenticated = False
                    return False
            except Exception as e:
                self.logger.error(f"生成認證簽名時出錯: {str(e)}")
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
            self.logger.debug("響應處理器已啟動")
            
            while not self.closed and self.ws is not None:
                try:
                    # 使用鎖確保只有一個協程在等待消息
                    async with self.recv_lock:
                        message = await self.ws.recv()
                    
                    # 解析消息
                    try:
                        response = json.loads(message)
                        self.logger.debug(f"收到響應摘要: {_log_response_summary(response)}")
                    except json.JSONDecodeError:
                        self.logger.error(f"無法解析 WebSocket 響應: {message}")
                        continue
                    
                    # 處理响應
                    if "id" in response:
                        request_id = response["id"]
                        future = self.response_futures.pop(request_id, None)
                        
                        if future:
                            # 直接設置結果
                            future.set_result(response)
                        else:
                            self.logger.warning(f"未找到請求ID的處理器: {request_id}")
                    elif "error" in response:
                        # 處理全局錯誤響應
                        error = response.get("error", {})
                        self.logger.error(f"收到錯誤響應: 代碼 {error.get('code')}, 信息: {error.get('msg')}")
                    elif "result" in response:
                        # 處理無ID的結果響應
                        self.logger.info(f"收到無ID的結果響應: {response.get('result')}")
                    else:
                        # 處理其他響應
                        self.logger.debug(f"收到其他響應: {response}")
                except asyncio.CancelledError:
                    self.logger.info("響應處理器被取消")
                    break
                except Exception as e:
                    if self.closed:
                        break
                    self.logger.error(f"處理 WebSocket 響應時出錯: {str(e)}")
                    # 等待一段時間再繼續
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            self.logger.info("響應處理器被取消")
        except Exception as e:
            self.logger.error(f"響應處理器出錯: {str(e)}")
        finally:
            self.logger.debug("響應處理器已停止")
    
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
            self.logger.info("WebSocket 未連接，嘗試建立連接")
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
        
        # 記錄請求
        #self.logger.debug(f"獲取U本位合約賬戶信息請求: {json.dumps(request, ensure_ascii=False)}")
        
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
                    self.logger.warning("連接已關閉，嘗試重新連接...")
                    connected = await self.connect()
                    if not connected:
                        raise ConnectionError("重新連接失敗")
                
                await self.ws.send(json.dumps(request))
                
                # 等待響應
                try:
                    response = await asyncio.wait_for(future, 10)  # 10秒超時
                    #self.logger.debug(f"U本位合約賬戶信息響應: {json.dumps(response, ensure_ascii=False)}")
                    
                    # 檢查錯誤
                    if 'error' in response:
                        error_code = response['error']['code']
                        error_message = response['error']['msg']
                        
                        # 檢查是否需要重試
                        if error_code in [-1021, -1022]:  # 時間同步錯誤或簽名錯誤
                            self.logger.warning(f"時間同步或簽名錯誤: {error_message}，重試中...")
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
                        self.logger.warning(f"收到可能不完整的U本位合約賬戶信息，字段數量: {len(result.keys())}")
                        self.logger.debug(f"響應結果字段: {list(result.keys())}")
                    
                    return result
                    
                except asyncio.TimeoutError:
                    # 超時，重試
                    self.logger.warning("獲取U本位合約賬戶信息請求超時，重試中...")
                    retry_count += 1
                    
                    # 清理舊的 future
                    if request_id in self.response_futures:
                        del self.response_futures[request_id]
                        
                    # 建立新的 future
                    request_id = str(uuid.uuid4())
                    request['id'] = request_id
                    future = asyncio.get_event_loop().create_future()
                    self.response_futures[request_id] = future
                    
                    # 檢查連接狀態，可能需要重連
                    if not self.connected or self.ws is None:
                        self.logger.warning("連接可能已關閉，嘗試重新連接...")
                        await self.connect()
                    
                    continue
                    
            except Exception as e:
                # 其他錯誤，重試
                self.logger.error(f"獲取U本位合約賬戶信息過程中發生錯誤: {str(e)}")
                retry_count += 1
                
                # 清理舊的 future
                if request_id in self.response_futures:
                    del self.response_futures[request_id]
                
                # 檢查連接狀態
                if not self.connected or self.ws is None:
                    self.logger.warning("連接已關閉，嘗試重新連接...")
                    try:
                        await self.connect()
                    except Exception as conn_err:
                        self.logger.error(f"重新連接失敗: {conn_err}")
                
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
        self.logger.debug(f"下單請求: {json.dumps(request, ensure_ascii=False)}")
        
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
                    self.logger.warning("連接已關閉，嘗試重新連接...")
                    connected = await self.connect()
                    if not connected:
                        raise ConnectionError("重新連接失敗")
                
                await self.ws.send(json.dumps(request))
                
                # 等待響應
                try:
                    response = await asyncio.wait_for(future, 10)  # 10秒超時
                    self.logger.debug(f"下單響應摘要: {_log_response_summary(response)}")
                    
                    # 檢查錯誤
                    if 'error' in response:
                        error_code = response['error']['code']
                        error_message = response['error']['msg']
                        
                        # 檢查是否需要重試
                        if error_code in [-1021, -1022]:  # 時間同步錯誤或簽名錯誤
                            self.logger.warning(f"時間同步或簽名錯誤: {error_message}，重試中...")
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
                    self.logger.warning("下單請求超時，重試中...")
                    retry_count += 1
                    continue
                    
            except Exception as e:
                # 其他錯誤，重試
                self.logger.error(f"下單過程中發生錯誤: {str(e)}")
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
        self.logger.debug(f"取消訂單請求: {json.dumps(request, ensure_ascii=False)}")
        
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
                    self.logger.warning("連接已關閉，嘗試重新連接...")
                    connected = await self.connect()
                    if not connected:
                        raise ConnectionError("重新連接失敗")
                
                await self.ws.send(json.dumps(request))
                
                # 等待響應
                try:
                    response = await asyncio.wait_for(future, 10)  # 10秒超時
                    self.logger.debug(f"取消訂單響應摘要: {_log_response_summary(response)}")
                    
                    # 檢查錯誤
                    if 'error' in response:
                        error_code = response['error']['code']
                        error_message = response['error']['msg']
                        
                        # 檢查是否需要重試
                        if error_code in [-1021, -1022]:  # 時間同步錯誤或簽名錯誤
                            self.logger.warning(f"時間同步或簽名錯誤: {error_message}，重試中...")
                            retry_count += 1
                            # 更新時間戳
                            formatted_params['timestamp'] = str(int(time.time() * 1000))
                            request['params'] = formatted_params
                            continue
                        elif error_code == -2011:  # 未知訂單，不存在或已取消
                            self.logger.warning(f"訂單未找到: {error_message}")
                            return {"status": "CANCELED", "message": "Order not found or already canceled"}
                        else:
                            # 其他錯誤，直接返回
                            raise ApiError(f"取消訂單錯誤: {error_code} - {error_message}")
                    
                    # 如果沒有錯誤，則返回結果
                    return response.get('result', response)
                    
                except asyncio.TimeoutError:
                    # 超時，重試
                    self.logger.warning("取消訂單請求超時，重試中...")
                    retry_count += 1
                    continue
                    
            except Exception as e:
                # 其他錯誤，重試
                self.logger.error(f"取消訂單過程中發生錯誤: {str(e)}")
                retry_count += 1
                
                continue
        
        # 超過最大重試次數
        raise ApiError("取消訂單失敗: 超過最大重試次數")
    
    def is_connected(self) -> bool:
        """
        檢查是否已連接到WebSocket
        
        Returns:
            是否已連接
        """
        return self.connected and self.ws is not None

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
                formatted[key] = 'TRUE' if value else 'FALSE'
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
        self.logger.info("已啟動後台任務: 響應處理器和ping保持活躍")

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
            self.logger.info("WebSocket 未連接，嘗試建立連接")
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
        self.logger.debug(f"獲取U本位合約賬戶餘額請求: {json.dumps(request, ensure_ascii=False)}")
        
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
                    self.logger.warning("連接已關閉，嘗試重新連接...")
                    connected = await self.connect()
                    if not connected:
                        raise ConnectionError("重新連接失敗")
                
                await self.ws.send(json.dumps(request))
                
                # 等待響應
                try:
                    response = await asyncio.wait_for(future, 10)  # 10秒超時
                    self.logger.debug(f"U本位合約賬戶餘額響應摘要: {_log_response_summary(response)}")
                    
                    # 檢查錯誤
                    if 'error' in response:
                        error_code = response['error']['code']
                        error_message = response['error']['msg']
                        
                        # 檢查是否需要重試
                        if error_code in [-1021, -1022]:  # 時間同步錯誤或簽名錯誤
                            self.logger.warning(f"時間同步或簽名錯誤: {error_message}，重試中...")
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
                        self.logger.warning("收到空的U本位合約賬戶餘額列表")
                    
                    return result
                    
                except asyncio.TimeoutError:
                    # 超時，重試
                    self.logger.warning("獲取U本位合約賬戶餘額請求超時，重試中...")
                    retry_count += 1
                    
                    # 清理舊的 future
                    if request_id in self.response_futures:
                        del self.response_futures[request_id]
                        
                    # 建立新的 future
                    request_id = str(uuid.uuid4())
                    request['id'] = request_id
                    future = asyncio.get_event_loop().create_future()
                    self.response_futures[request_id] = future
                    
                    # 檢查連接狀態，可能需要重連
                    if not self.connected or self.ws is None:
                        self.logger.warning("連接可能已關閉，嘗試重新連接...")
                        await self.connect()
                    
                    continue
                    
            except Exception as e:
                # 其他錯誤，重試
                self.logger.error(f"獲取U本位合約賬戶餘額過程中發生錯誤: {str(e)}")
                retry_count += 1
                
                # 清理舊的 future
                if request_id in self.response_futures:
                    del self.response_futures[request_id]
                
                # 檢查連接狀態
                if not self.connected or self.ws is None:
                    self.logger.warning("連接已關閉，嘗試重新連接...")
                    try:
                        await self.connect()
                    except Exception as conn_err:
                        self.logger.error(f"重新連接失敗: {conn_err}")
                
                # 重新建立 future 和請求 ID
                if retry_count < max_retries:
                    request_id = str(uuid.uuid4())
                    request['id'] = request_id
                    future = asyncio.get_event_loop().create_future()
                    self.response_futures[request_id] = future
                
                continue
        
        # 超過最大重試次數
        raise ApiError("獲取U本位合約賬戶餘額失敗: 超過最大重試次數")


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