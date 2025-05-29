import json
import logging
import asyncio
from typing import Dict, Any, Optional, List, Set
from datetime import datetime
import websockets  # 恢復使用 websockets 庫
import ssl  # 引入 SSL 模組以處理 SSL 上下文
from .base import ExchangeBase
import os
from dotenv import load_dotenv
from urllib.parse import urlparse
import threading

# 配置日誌記錄器，用於幣安交易所模組的日誌記錄
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)  # 將日誌級別從INFO改為WARNING，減少輸出量

# 設置websockets庫的日誌級別為ERROR，進一步減少DEBUG信息的數量
logging.getLogger('websockets').setLevel(logging.ERROR)
logging.getLogger('websockets.client').setLevel(logging.ERROR)
logging.getLogger('websockets.protocol').setLevel(logging.ERROR)

class BinanceExchange(ExchangeBase):
    """
    幣安交易所實現 - 直接從Binance WebSocket獲取數據
    
    此類實現了與幣安交易所的通信接口，包括WebSocket連接管理、
    行情數據訂閱和處理等功能。支持現貨和期貨市場的實時價格訂閱。
    """
    
    def __init__(self):
        """
        初始化幣安交易所連接
        
        設置API端點、連接管理、市場數據緩存等資源。
        支持從環境變數中讀取端點配置。
        """
        super().__init__("binance")
        
        # 從環境變數中讀取WebSocket端點配置，如果沒有則使用預設值
        load_dotenv()
        
        # 修改WebSocket終端直接使用流URL格式，支持自訂配置
        self.ws_endpoints = {
            "spot": os.getenv("BINANCE_SPOT_WS", "wss://stream.binance.com:9443/ws/!ticker@arr"),     # 現貨市場全部交易對行情流
            "futures": os.getenv("BINANCE_FUTURES_WS", "wss://fstream.binance.com/ws/!ticker@arr")    # 期貨市場全部交易對行情流
        }
        
        # REST API端點也支持自訂配置
        self.rest_endpoints = {
            "spot": os.getenv("BINANCE_SPOT_API", "https://api.binance.com/api/v3"),                    # 現貨市場REST API
            "futures": os.getenv("BINANCE_FUTURES_API", "https://fapi.binance.com/fapi/v1")             # 期貨市場REST API
        }
        
        self.ws_connections = {
            "spot": None,                                                # 現貨WebSocket連接對象
            "futures": None                                              # 期貨WebSocket連接對象
        }
        self.subscribed_channels = {
            "spot": set(),                                               # 已訂閱的現貨頻道集合
            "futures": set()                                             # 已訂閱的期貨頻道集合
        }
        self.market_data = {
            "spot": {},                                                  # 現貨市場數據緩存
            "futures": {}                                                # 期貨市場數據緩存
        }
        self.is_running = False                                          # 運行狀態標誌
        self.is_shutting_down = False                                    # 應用關閉標誌，用於防止在關閉時嘗試重新連接
        self.tasks = []                                                  # 異步任務列表
        # 設置檢查點，記錄各市場類型的數據更新情況
        self.update_checkpoints = {
            "spot": {"count": 0, "last_time": datetime.now()},           # 現貨數據更新檢查點
            "futures": {"count": 0, "last_time": datetime.now()}         # 期貨數據更新檢查點
        }
        # 連接嘗試計數
        self.connection_attempts = {
            "spot": 0,                                                   # 現貨連接嘗試次數
            "futures": 0                                                 # 期貨連接嘗試次數
        }
        # 最大重試次數
        self.max_retry_attempts = int(os.getenv("BINANCE_MAX_RETRY", "5"))  # 連接失敗後的最大重試次數
        
        # 簡化初始化日誌，只記錄一條摘要信息
        logger.info(f"幣安交易所初始化完成，端點: spot={self.ws_endpoints['spot'].split('/')[2]}, futures={self.ws_endpoints['futures'].split('/')[2]}")
        
        # 增加消息隊列，用於在非同步環境中處理WebSocket消息
        self.message_queues = {
            "spot": asyncio.Queue(),
            "futures": asyncio.Queue()
        }
        
    async def connect(self) -> bool:
        """
        建立WebSocket連接到幣安交易所
        
        使用優化的連接參數和SSL設置，嘗試解決測試腳本能連接但服務無法連接的問題。
        包含增強的重試機制和連接診斷。
        
        返回:
            連接成功返回True，否則返回False
        """
        # 簡化開始連接日誌
        logger.info("開始連接幣安交易所WebSocket")
        try:
            # 首先設置運行標誌，確保任務能正常運行
            self.is_running = True
            
            # 檢查代理設置
            # 讀取代理配置
            http_proxy = os.getenv("HTTP_PROXY", "")
            https_proxy = os.getenv("HTTPS_PROXY", "")
            wss_proxy = os.getenv("WSS_PROXY", https_proxy)  # 如未設置WSS代理，則使用HTTPS代理
            
            # 簡化代理日誌，只在有代理時記錄
            if http_proxy or https_proxy or wss_proxy:
                logger.info(f"使用代理設置: HTTP={http_proxy}, HTTPS={https_proxy}, WSS={wss_proxy}")
                if wss_proxy:
                    os.environ["HTTPS_PROXY"] = wss_proxy
                    os.environ["HTTP_PROXY"] = http_proxy if http_proxy else wss_proxy
                    os.environ["WSS_PROXY"] = wss_proxy
                    
            # 創建一個自定義的SSL上下文，針對可能的SSL問題進行調整
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE  # 在故障排除過程中禁用證書驗證
            
            connected_markets = []
            
            for market_type in ["spot", "futures"]:
                if not self.ws_connections[market_type]:
                    logger.info(f"連接幣安{market_type}市場WebSocket...")
                    
                    # 使用重試邏輯
                    max_retries = 5  # 增加重試次數
                    retry_count = 0
                    last_error = None
                    
                    while retry_count < max_retries and self.is_running:
                        try:
                            # 減少連接嘗試日誌，只在重試時記錄
                            if retry_count > 0:
                                logger.info(f"嘗試第 {retry_count + 1} 次連接到 {market_type} 市場...")
                            
                            # 配置連接選項，使用更寬松的超時設定
                            connect_kwargs = {
                                "ping_interval": 30,  # 增加ping間隔
                                "ping_timeout": 20,   # 增加ping超時
                                "close_timeout": 20,  # 增加關閉超時
                                "max_size": 10 * 1024 * 1024,  # 增加最大消息大小至10MB
                                "ssl": ssl_context    # 使用自定義的SSL上下文
                            }
                            
                            # 連接到WebSocket，使用更長的超時時間
                            self.ws_connections[market_type] = await asyncio.wait_for(
                                websockets.connect(
                                    self.ws_endpoints[market_type],
                                    **connect_kwargs
                                ),
                                timeout=60.0  # 增加至60秒連接超時
                            )
                            
                            # 驗證連接是否建立
                            if self.ws_connections[market_type].open:
                                logger.info(f"幣安{market_type}市場WebSocket連接成功")
                                
                                # 立即訂閱所有市場數據 - 以確保數據流開始
                                try:
                                    await asyncio.wait_for(
                                        self.subscribe_market_type(market_type),
                                        timeout=10.0  # 10秒訂閱超時
                                    )
                                except asyncio.TimeoutError:
                                    logger.warning(f"{market_type}市場訂閱超時，但連接已建立")
                                    # 忽略訂閱超時，繼續處理
                                
                                # 啟動消息處理任務
                                task = asyncio.create_task(
                                    self._handle_messages(market_type)
                                )
                                self.tasks.append(task)
                                
                                connected_markets.append(market_type)
                                break  # 連接成功，跳出重試循環
                            else:
                                logger.error(f"幣安{market_type}市場WebSocket連接未打開")
                                retry_count += 1
                                last_error = "連接已創建但未打開"
                                
                        except asyncio.TimeoutError as e:
                            retry_count += 1
                            last_error = f"連接超時: {str(e)}"
                            logger.warning(f"連接到 {market_type} 市場超時，第 {retry_count} 次重試")
                            await asyncio.sleep(2 * retry_count)  # 指數退避延遲
                            
                        except Exception as e:
                            retry_count += 1
                            last_error = str(e)
                            logger.warning(f"連接到 {market_type} 市場失敗: {str(e)}，第 {retry_count} 次重試")
                            await asyncio.sleep(2 * retry_count)  # 指數退避延遲
                    
                    # 如果所有重試都失敗了
                    if retry_count >= max_retries:
                        logger.error(f"連接幣安{market_type}市場WebSocket失敗，已重試 {max_retries} 次，最後錯誤: {last_error}")
                else:
                    logger.info(f"幣安{market_type}市場WebSocket已連接")
                    connected_markets.append(market_type)
                    
            # 檢查至少有一個市場連接成功
            if connected_markets:
                logger.info(f"幣安交易所連接完成，已連接: {', '.join(connected_markets)}")
                return True
            else:
                logger.error("幣安交易所連接失敗，所有市場都無法連接")
                self.is_running = False  # 重置運行標誌
                return False
        except Exception as e:
            logger.error(f"連接幣安WebSocket時出錯: {str(e)}")
            # 添加詳細的異常信息
            import traceback
            logger.error(f"異常追踪: {traceback.format_exc()}")
            self.is_running = False  # 重置運行標誌
            return False
    
    async def _handle_messages(self, market_type: str):
        """
        處理WebSocket消息，解析幣安推送的數據
        
        增強的錯誤處理和重連機制，添加更多診斷資訊
        """
        ws = self.ws_connections[market_type]
        if not ws:
            logger.error(f"無法處理{market_type}市場數據：WebSocket連接不存在")
            return
            
        logger.info(f"開始處理幣安{market_type}市場數據")
        message_count = 0
        update_count = 0
        last_log_time = datetime.now()
        log_interval = 600  # 延長日誌間隔至10分鐘
        start_time = datetime.now()  # 記錄開始時間
        last_message_time = datetime.now()  # 最後收到消息的時間
        
        try:
            # 簡化循環開始前的狀態日誌
            while self.is_running and ws.open:
                try:
                    # 接收消息，設置超時防止永久阻塞
                    message = await asyncio.wait_for(ws.recv(), timeout=30.0)
                    current_time = datetime.now()
                    time_since_last = (current_time - last_message_time).total_seconds()
                    last_message_time = current_time  # 更新最後消息時間
                    
                    if not message:
                        continue
                        
                    message_count += 1
                    
                    # 只記錄第一條消息，減少日誌量
                    if message_count == 1:
                        logger.info(f"幣安{market_type}市場收到首條數據")
                    
                    # 解析數據
                    try:
                        data = json.loads(message)
                    except json.JSONDecodeError:
                        if message_count < 5:  # 僅在前幾條消息出現問題時記錄
                            logger.warning(f"幣安{market_type}市場收到無效數據")
                        continue
                    
                    # 如果收到的是ping/pong消息，直接忽略
                    if isinstance(data, dict) and (data.get("ping") is not None or data.get("pong") is not None):
                        continue
                    
                    # 處理數據
                    if self._process_ticker_data(data, market_type):
                        update_count += 1
                        
                        # 減少更新日誌頻率，每10000次更新記錄一次進度
                        if update_count == 1 or update_count % 10000 == 0:
                            current_time = datetime.now()
                            runtime = (current_time - start_time).total_seconds()
                            logger.info(f"幣安{market_type}市場更新: {update_count}次，當前有{len(self.market_data[market_type])}個交易對")
                    
                    # 每10分鐘記錄一次統計信息，減少日誌量
                    current_time = datetime.now()
                    if (current_time - last_log_time).total_seconds() >= log_interval:
                        runtime = (current_time - start_time).total_seconds()
                        logger.info(f"{market_type}市場統計: 已處理{message_count}條消息，更新{update_count}次，運行{int(runtime)}秒")
                        last_log_time = current_time
                        
                except asyncio.TimeoutError:
                    # 檢測心跳超時 - 如果30秒未收到消息，記錄警告
                    current_time = datetime.now()
                    time_since_last = (current_time - last_message_time).total_seconds()
                    
                    if time_since_last > 60:  # 超過60秒未收到消息
                        logger.warning(f"幣安{market_type}市場已 {time_since_last:.1f} 秒未收到消息，可能存在連接問題")
                        
                        # 檢查連接是否仍然開放
                        if not ws.open:
                            logger.error(f"幣安{market_type}市場WebSocket連接已關閉，正在重連")
                            raise websockets.exceptions.ConnectionClosed(1000, "Connection timeout, no messages received")
                    
                    # 否則靜默繼續
                    continue
                        
                except websockets.exceptions.ConnectionClosed as e:
                    # 檢查是否是應用關閉導致的連接斷開
                    # 當代碼為1000時表示正常關閉，或者當應用處於關閉狀態時，不應嘗試重新連接
                    if self.is_shutting_down or e.code == 1000:
                        logger.info(f"幣安{market_type}市場WebSocket連接已正常關閉，不嘗試重連")
                        break
                    
                    logger.warning(f"幣安{market_type}市場WebSocket連接意外關閉，嘗試重連")
                    
                    # 檢查是否超過最大重試次數
                    if self.connection_attempts[market_type] >= self.max_retry_attempts:
                        logger.error(f"幣安{market_type}市場連接重試已達上限({self.max_retry_attempts})")
                        break
                    
                    # 應用未關閉時才嘗試重新連接
                    if not self.is_shutting_down:
                        self.connection_attempts[market_type] += 1
                        retry_delay = min(2 ** self.connection_attempts[market_type], 60)
                        
                        logger.info(f"幣安{market_type}市場將在{retry_delay}秒後重連 (嘗試 {self.connection_attempts[market_type]}/{self.max_retry_attempts})")
                        await asyncio.sleep(retry_delay)
                        
                        # 嘗試重新連接，使用優化的連接參數
                        logger.info(f"重新連接到幣安{market_type}市場")
                        
                        # 創建一個自定義的SSL上下文
                        ssl_context = ssl.create_default_context()
                        ssl_context.check_hostname = False
                        ssl_context.verify_mode = ssl.CERT_NONE  # 禁用證書驗證
                        
                        self.ws_connections[market_type] = await asyncio.wait_for(
                            websockets.connect(
                                self.ws_endpoints[market_type],
                                ping_interval=30,
                                ping_timeout=20,
                                close_timeout=20,
                                max_size=10 * 1024 * 1024,
                                ssl=ssl_context
                            ),
                            timeout=60.0
                        )
                        
                        if self.ws_connections[market_type].open:
                            logger.info(f"幣安{market_type}市場重連成功")
                            ws = self.ws_connections[market_type]  # 更新ws引用
                            self.connection_attempts[market_type] = 0
                            
                            # 重新訂閱
                            await self.subscribe_market_type(market_type)
                            logger.info(f"幣安{market_type}市場數據流已重新訂閱")
                            
                            # 重置計數器和時間
                            last_message_time = datetime.now()
                            continue
                        else:
                            logger.error(f"幣安{market_type}市場重連失敗")
                            break
                    else:
                        logger.info(f"應用正在關閉，不再嘗試重連幣安{market_type}市場")
                        break
                    
                except asyncio.CancelledError:
                    logger.info(f"幣安{market_type}市場數據處理任務被取消")
                    raise
                    
                except Exception as e:
                    logger.error(f"處理{market_type}市場數據出錯: {str(e)}")
                    await asyncio.sleep(1)
                    continue
                    
        except asyncio.CancelledError:
            logger.info(f"幣安{market_type}市場數據處理任務已取消")
        except Exception as e:
            logger.error(f"幣安{market_type}市場數據處理異常: {str(e)}")
        finally:
            runtime = datetime.now() - start_time
            logger.info(f"幣安{market_type}市場數據處理結束，運行{int(runtime.total_seconds())}秒，處理{message_count}條消息，更新{update_count}次")

    async def disconnect(self) -> bool:
        """
        斷開WebSocket連接
        
        安全地關閉所有WebSocket連接和相關的異步任務。
        設置 is_shutting_down 標誌以防止在關閉過程中嘗試重新連接。
        
        返回:
            斷開成功返回True，否則返回False
        """
        try:
            # 設置關閉標誌，防止在連接斷開時嘗試重連
            self.is_shutting_down = True
            logger.info("設置關閉標誌，防止重新連接嘗試")
            
            # 設置運行標誌為False，停止所有處理循環
            self.is_running = False
            
            # 關閉所有WebSocket連接
            for market_type, ws in self.ws_connections.items():
                if ws:
                    try:
                        await ws.close(code=1000, reason="Application shutdown")
                        logger.info(f"已關閉幣安{market_type}市場WebSocket連接")
                    except Exception as e:
                        logger.error(f"關閉幣安{market_type}市場WebSocket連接時出錯: {str(e)}")
                
            # 取消所有異步任務
            for task in self.tasks:
                if not task.done() and not task.cancelled():
                    task.cancel()
                    try:
                        await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
                    except asyncio.TimeoutError:
                        logger.warning("等待任務取消超時")
                    except asyncio.CancelledError:
                        logger.info("任務已成功取消")
                    except Exception as e:
                        logger.error(f"取消任務時出錯: {str(e)}")
                        
            # 清空任務列表
            self.tasks = []
            
            logger.info("幣安交易所WebSocket連接已完全斷開")
            return True
        except Exception as e:
            logger.error(f"斷開幣安交易所WebSocket連接時出錯: {str(e)}")
            import traceback
            logger.error(f"異常追踪: {traceback.format_exc()}")
            return False
            
    async def subscribe_market_type(self, market_type: str) -> bool:
        """
        訂閱特定市場類型的所有交易對
        
        使用端點與URL參數，不需要額外訂閱操作。
        當使用 stream.binance.com:9443/ws/!ticker@arr 這類直接帶有訂閱參數的URL時，
        連接後Binance自動發送數據，不需要明確訂閱。
        
        參數:
            market_type: 市場類型，可選 "spot"（現貨）或 "futures"（期貨）
            
        返回:
            訂閱成功返回True，否則返回False
        """
        try:
            if market_type not in ["spot", "futures"]:
                logger.error(f"不支持的市場類型: {market_type}")
                return False
                
            if not self.ws_connections[market_type]:
                logger.error(f"無法訂閱{market_type}市場: WebSocket未連接")
                return False
            
            # 使用端點URL自動訂閱模式，記錄日誌但不發送額外命令
            logger.info(f"幣安{market_type}市場使用URL參數方式訂閱: {self.ws_endpoints[market_type]}")
            self.subscribed_channels[market_type].add("!ticker@arr")
            return True
            
        except Exception as e:
            logger.error(f"訂閱幣安{market_type}市場時出錯: {str(e)}")
            return False
        
    async def subscribe_symbols(self, symbols: List[str], market_type: str) -> bool:
        """
        訂閱特定交易對的行情
        
        我們使用全局行情流，所以此方法主要是保留兼容性。
        如果需要單獨訂閱特定交易對，也可以發送訂閱消息。
        
        參數:
            symbols: 要訂閱的交易對列表，例如 ["BTCUSDT", "ETHUSDT"]
            market_type: 市場類型，可選 "spot"（現貨）或 "futures"（期貨）
            
        返回:
            訂閱成功返回True，否則返回False
        """
        logger.info(f"幣安{market_type}市場已通過全局行情流訂閱所有交易對，包括: {', '.join(symbols)}")
        return True
            
    async def unsubscribe_symbols(self, symbols: List[str], market_type: str) -> bool:
        """取消訂閱特定交易對"""
        # 不需要實際取消訂閱，因為我們使用全局流
        logger.info(f"幣安{market_type}市場使用全局行情流，不支持取消單個交易對訂閱")
        return True
            
    def get_all_tickers(self, market_type: str) -> Dict[str, Any]:
        """獲取所有交易對的最新行情"""
        return self.market_data.get(market_type, {})
        
    def get_ticker(self, symbol: str, market_type: str) -> Optional[Dict[str, Any]]:
        """獲取單個交易對的最新行情"""
        symbol = self.normalize_symbol(symbol)
        return self.market_data.get(market_type, {}).get(symbol)
        
    def get_24h_ticker(self, symbol: str, market_type: str) -> Optional[Dict[str, Any]]:
        """獲取24小時行情數據 - 直接返回ticker數據，已包含24小時信息"""
        return self.get_ticker(symbol, market_type)
        
    def format_ticker_data(self, raw_data: Dict[str, Any], market_type: str) -> Dict[str, Any]:
        """格式化Binance的24小時ticker數據為統一格式"""
        try:
            if not isinstance(raw_data, dict):
                # 簡化日誌
                return {}
                
            if "s" not in raw_data:
                # 簡化日誌
                return {}
            
            # 提取基本數據
            symbol = raw_data["s"]
            
            # Binance 24h ticker數據包含這些字段
            required_fields = ["c", "o", "h", "l", "v", "q", "p", "P"]
            missing_fields = [field for field in required_fields if field not in raw_data]
            
            # 檢查必要字段
            if "c" not in raw_data:
                # 只在調試級別記錄
                return {}
                
            # 非關鍵字段缺失時僅在DEBUG級別記錄
            # if missing_fields and missing_fields != ["p", "P"] and logger.level <= logging.DEBUG:
            #     logger.debug(f"{market_type}市場 {symbol}: 缺少字段: {', '.join(missing_fields)}")
            
            try:
                # 構建基本數據結構，使用safe_float處理可能缺失或無效的字段
                formatted_data = {
                    "symbol": symbol,
                    "price": self._safe_float(raw_data, "c", 0),  # 最新價格
                    "price_change_24h": self._safe_float(raw_data, "P", 0),  # 24小時漲跌幅
                    "price_change": self._safe_float(raw_data, "p", 0),  # 24小時價格變化
                    "volume_24h": self._safe_float(raw_data, "v", 0),  # 24小時成交量
                    "quote_volume_24h": self._safe_float(raw_data, "q", 0),  # 24小時成交額
                    "high_24h": self._safe_float(raw_data, "h", 0),  # 24小時最高價
                    "low_24h": self._safe_float(raw_data, "l", 0),  # 24小時最低價
                    "open_24h": self._safe_float(raw_data, "o", 0),  # 24小時開盤價
                    "count": int(self._safe_float(raw_data, "n", 0)),  # 成交筆數
                    "bid_price": self._safe_float(raw_data, "b", 0),  # 最佳買入價
                    "ask_price": self._safe_float(raw_data, "a", 0),  # 最佳賣出價
                    "bid_qty": self._safe_float(raw_data, "B", 0),  # 最佳買入量
                    "ask_qty": self._safe_float(raw_data, "A", 0),  # 最佳賣出量
                    "last_update": self.get_timestamp(),
                    "market_type": market_type,
                    "exchange": "binance"  # 添加交易所標識
                }
                return formatted_data
            except (ValueError, TypeError) as e:
                # 簡化錯誤日誌
                return {}
                
        except Exception as e:
            # 簡化錯誤日誌
            return {}

    def _safe_float(self, data: Dict[str, Any], key: str, default: float = 0.0) -> float:
        """安全地從字典中提取浮點數值"""
        try:
            if key not in data:
                return default
                
            value = data[key]
            if value is None:
                return default
                
            return float(value)
        except (ValueError, TypeError):
            return default

    def _process_ticker_data(self, data, market_type):
        """處理ticker數據，返回是否成功處理"""
        try:
            updates_count = 0
            temp_symbols = set()
            
            # 首先檢查數據類型
            if data is None:
                return False
                
            # 處理數組類型數據
            if isinstance(data, list):
                # 記錄過濾前的交易對數量
                initial_count = len(data)
                
                # 如果是空列表，直接返回
                if initial_count == 0:
                    return False
                
                for item in data:
                    if not isinstance(item, dict):
                        continue  # 跳過非字典類型數據
                        
                    if not item.get("s"):
                        continue  # 跳過沒有交易對標識的數據
                        
                    symbol = item["s"]
                    temp_symbols.add(symbol)
                        
                    # 根據市場類型過濾
                    if market_type == "spot":
                        # 現貨市場篩選 - 只接受以USDT結尾的交易對，排除含有PERP的期貨符號
                        if not symbol.endswith("USDT") or "PERP" in symbol or symbol.endswith("_PERP"):
                            continue
                    elif market_type == "futures":
                        # 期貨市場通常以USDT結尾
                        if not symbol.endswith("USDT"):
                            continue
                    
                    try:
                        formatted_data = self.format_ticker_data(item, market_type)
                        if formatted_data:
                            self.market_data[market_type][symbol] = formatted_data
                            updates_count += 1
                    except Exception:
                        continue  # 單個交易對出錯不影響其他交易對處理
                
                # 只在更新數量大于0時記錄日誌
                if updates_count > 0:
                    self.update_checkpoints[market_type]["count"] += 1
                    self.update_checkpoints[market_type]["last_time"] = datetime.now()
                    # 每1000次更新才記錄一次統計信息
                    if self.update_checkpoints[market_type]["count"] % 1000 == 0:
                        logger.info(f"{market_type}市場數據更新: {len(self.market_data[market_type])}個交易對")
                
                return updates_count > 0
            
            # 處理單個字典類型數據
            elif isinstance(data, dict):
                # 檢查是否有交易對標識
                if "s" not in data:
                    # 控制消息不記錄日誌
                    return False
                
                symbol = data["s"]
                temp_symbols.add(symbol)
                
                # 根據市場類型過濾
                valid_for_market = True
                if market_type == "spot":
                    if not symbol.endswith("USDT") or "PERP" in symbol or symbol.endswith("_PERP"):
                        valid_for_market = False
                elif market_type == "futures":
                    if not symbol.endswith("USDT"):
                        valid_for_market = False
                
                if valid_for_market:
                    try:
                        formatted_data = self.format_ticker_data(data, market_type)
                        if formatted_data:
                            self.market_data[market_type][symbol] = formatted_data
                            updates_count += 1
                            self.update_checkpoints[market_type]["count"] += 1
                            self.update_checkpoints[market_type]["last_time"] = datetime.now()
                    except Exception:
                        return False
                
                return updates_count > 0
            
            # 處理其他類型的數據
            else:
                return False
        
        except Exception as e:
            # 簡化錯誤日誌
            logger.error(f"處理{market_type}市場數據錯誤: {str(e)}")
            return False 