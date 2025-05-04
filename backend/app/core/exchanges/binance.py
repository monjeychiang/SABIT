import json
import logging
import asyncio
from typing import Dict, Any, Optional, List, Set
from datetime import datetime
import websockets
from .base import ExchangeBase

# 配置日誌記錄器，用於幣安交易所模組的日誌記錄
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 設置websockets庫的日誌級別為WARNING，減少DEBUG信息的數量
logging.getLogger('websockets').setLevel(logging.WARNING)
logging.getLogger('websockets.client').setLevel(logging.WARNING)
logging.getLogger('websockets.protocol').setLevel(logging.WARNING)

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
        """
        super().__init__("binance")
        # 修改WebSocket終端直接使用流URL格式
        self.ws_endpoints = {
            "spot": "wss://stream.binance.com:9443/ws/!ticker@arr",     # 現貨市場全部交易對行情流
            "futures": "wss://fstream.binance.com/ws/!ticker@arr"        # 期貨市場全部交易對行情流
        }
        self.rest_endpoints = {
            "spot": "https://api.binance.com/api/v3",                    # 現貨市場REST API
            "futures": "https://fapi.binance.com/fapi/v1"                # 期貨市場REST API
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
        self.max_retry_attempts = 5                                      # 連接失敗後的最大重試次數
        
    async def connect(self) -> bool:
        """
        建立WebSocket連接到幣安交易所
        
        嘗試連接到幣安的現貨和期貨市場WebSocket服務，並為每個市場啟動消息處理任務。
        
        返回:
            連接成功返回True，否則返回False
        """
        try:
            # 首先設置運行標誌，確保任務能正常運行
            self.is_running = True
            
            # 簡化連接開始日誌
            logger.info("開始連接幣安交易所WebSocket")
            
            for market_type in ["spot", "futures"]:
                if not self.ws_connections[market_type]:
                    logger.info(f"連接幣安{market_type}市場WebSocket...")
                    
                    # 連接到WebSocket
                    try:
                        self.ws_connections[market_type] = await websockets.connect(
                            self.ws_endpoints[market_type],
                            ping_interval=20,                           # 20秒發送一次ping
                            ping_timeout=10,                            # ping超時時間為10秒
                            close_timeout=10                            # 關閉超時時間為10秒
                        )
                        
                        # 驗證連接是否建立
                        if self.ws_connections[market_type].open:
                            logger.info(f"幣安{market_type}市場WebSocket連接成功")
                            
                            # 立即訂閱所有市場數據
                            await self.subscribe_market_type(market_type)
                            
                            # 啟動消息處理任務
                            task = asyncio.create_task(
                                self._handle_messages(market_type)
                            )
                            self.tasks.append(task)
                        else:
                            logger.error(f"幣安{market_type}市場WebSocket連接失敗")
                            
                    except Exception as e:
                        logger.error(f"連接幣安{market_type}市場WebSocket時出錯: {str(e)}")
                else:
                    logger.info(f"幣安{market_type}市場WebSocket已連接")
                    
            # 檢查至少有一個市場連接成功
            connected_markets = [m for m, ws in self.ws_connections.items() if ws and ws.open]
            if connected_markets:
                logger.info(f"幣安交易所連接完成，已連接: {', '.join(connected_markets)}")
                return True
            else:
                logger.error("幣安交易所連接失敗")
                self.is_running = False  # 重置運行標誌
                return False
        except Exception as e:
            logger.error(f"連接幣安WebSocket時出錯: {str(e)}")
            self.is_running = False  # 重置運行標誌
            return False
            
    async def disconnect(self) -> bool:
        """
        斷開WebSocket連接
        
        安全地關閉所有WebSocket連接和相關的異步任務。
        
        返回:
            斷開成功返回True，否則返回False
        """
        try:
            self.is_running = False
            
            # 取消所有任務
            for task in self.tasks:
                task.cancel()
            self.tasks.clear()
            
            # 關閉所有連接
            for market_type, ws in self.ws_connections.items():
                if ws:
                    await ws.close()
                    self.ws_connections[market_type] = None
                    logger.info(f"已斷開幣安{market_type}市場WebSocket連接")
                    
            return True
        except Exception as e:
            logger.error(f"斷開幣安WebSocket連接時出錯: {str(e)}")
            return False
            
    async def subscribe_market_type(self, market_type: str) -> bool:
        """
        訂閱特定市場類型的所有交易對價格
        
        訂閱指定市場類型的行情數據流，獲取全部交易對的最新價格。
        
        參數:
            market_type: 市場類型，'spot'（現貨）或'futures'（期貨）
            
        返回:
            訂閱成功返回True，否則返回False
        """
        try:
            ws = self.ws_connections[market_type]
            if not ws:
                logger.error(f"未找到{market_type}市場的WebSocket連接")
                return False
            
            # 簡化訂閱日誌
            logger.info(f"訂閱幣安{market_type}市場數據流")
            self.subscribed_channels[market_type].add("!ticker@arr")
            return True
                
        except Exception as e:
            logger.error(f"訂閱幣安{market_type}市場數據時出錯: {str(e)}")
            return False
            
    async def subscribe_symbols(self, symbols: List[str], market_type: str) -> bool:
        """
        訂閱特定交易對
        
        針對性地訂閱指定的一組交易對，以獲取其實時行情數據。
        
        參數:
            symbols: 交易對列表，如 ['BTCUSDT', 'ETHUSDT']
            market_type: 市場類型，'spot'（現貨）或'futures'（期貨）
            
        返回:
            訂閱成功返回True，否則返回False
        """
        try:
            ws = self.ws_connections[market_type]
            if not ws:
                logger.error(f"未找到{market_type}市場的WebSocket連接")
                return False
                
            # 格式化交易對名稱並創建訂閱消息
            formatted_symbols = [self.normalize_symbol(s) for s in symbols]
            channels = [f"{s.lower()}@ticker" for s in formatted_symbols]
            
            subscribe_message = {
                "method": "SUBSCRIBE",
                "params": channels,
                "id": 2
            }
            
            await ws.send(json.dumps(subscribe_message))
            
            # 等待確認訂閱成功
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(response)
                
                if data.get("result") is None:
                    logger.info(f"幣安{market_type}市場特定交易對訂閱成功: {', '.join(formatted_symbols)}")
                    self.subscribed_channels[market_type].update(channels)
                    return True
                else:
                    logger.error(f"幣安{market_type}市場特定交易對訂閱失敗: {data}")
                    return False
                    
            except asyncio.TimeoutError:
                logger.error(f"等待幣安{market_type}市場特定交易對訂閱確認超時")
                return False
            except Exception as e:
                logger.error(f"處理幣安{market_type}市場特定交易對訂閱確認時出錯: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"訂閱幣安{market_type}市場特定交易對時出錯: {str(e)}")
            return False
            
    async def unsubscribe_symbols(self, symbols: List[str], market_type: str) -> bool:
        """取消訂閱特定交易對"""
        try:
            ws = self.ws_connections[market_type]
            if not ws:
                logger.error(f"未找到{market_type}市場的WebSocket連接")
                return False
                
            # 格式化交易對名稱並創建取消訂閱消息
            formatted_symbols = [self.normalize_symbol(s) for s in symbols]
            channels = [f"{s.lower()}@ticker" for s in formatted_symbols]
            
            unsubscribe_message = {
                "method": "UNSUBSCRIBE",
                "params": channels,
                "id": 3
            }
            
            await ws.send(json.dumps(unsubscribe_message))
            
            # 等待確認取消訂閱成功
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(response)
                
                if data.get("result") is None:
                    logger.info(f"幣安{market_type}市場特定交易對取消訂閱成功: {', '.join(formatted_symbols)}")
                    self.subscribed_channels[market_type].difference_update(channels)
                    
                    # 清除相關市場數據
                    for symbol in formatted_symbols:
                        self.market_data[market_type].pop(symbol, None)
                        
                    return True
                else:
                    logger.error(f"幣安{market_type}市場特定交易對取消訂閱失敗: {data}")
                    return False
                    
            except asyncio.TimeoutError:
                logger.error(f"等待幣安{market_type}市場特定交易對取消訂閱確認超時")
                return False
            except Exception as e:
                logger.error(f"處理幣安{market_type}市場特定交易對取消訂閱確認時出錯: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"取消訂閱幣安{market_type}市場特定交易對時出錯: {str(e)}")
            return False
            
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
                    "market_type": market_type
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

    async def _handle_messages(self, market_type: str):
        """處理WebSocket消息，解析幣安推送的數據"""
        ws = self.ws_connections[market_type]
        if not ws:
            logger.error(f"無法處理{market_type}市場數據：WebSocket連接不存在")
            return
            
        logger.info(f"開始處理幣安{market_type}市場數據")
        message_count = 0
        update_count = 0
        last_log_time = datetime.now()
        log_interval = 300  # 每5分鐘記錄一次統計
        start_time = datetime.now()  # 記錄開始時間
        
        try:
            # 簡化循環開始前的狀態日誌
            while self.is_running and ws.open:
                try:
                    # 接收消息，設置超時防止永久阻塞
                    message = await asyncio.wait_for(ws.recv(), timeout=30.0)
                    if not message:
                        continue
                        
                    message_count += 1
                    
                    # 僅記錄第一條消息
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
                        
                        # 每1000次更新記錄一次進度，減少日誌量
                        if update_count % 1000 == 0:
                            logger.info(f"幣安{market_type}市場更新: {update_count}次")
                            logger.info(f"币安{market_type}市场更新: {update_count}次")
                    
                    # 每5分钟记录一次统计信息
                    current_time = datetime.now()
                    if (current_time - last_log_time).total_seconds() >= log_interval:
                        logger.info(f"{market_type}市场统计: 已处理{message_count}条消息，更新{update_count}次，运行{int((current_time - start_time).total_seconds())}秒")
                        last_log_time = current_time
                        
                except asyncio.TimeoutError:
                    # 超时不记录警告，默默重试
                    continue
                        
                except websockets.exceptions.ConnectionClosed as e:
                    logger.warning(f"币安{market_type}市场WebSocket连接已关闭，尝试重连")
                    
                    # 检查是否超过最大重试次数
                    if self.connection_attempts[market_type] >= self.max_retry_attempts:
                        logger.error(f"币安{market_type}市场连接重试已达上限({self.max_retry_attempts})")
                        break
                        
                    # 尝试重新连接
                    try:
                        self.connection_attempts[market_type] += 1
                        retry_delay = min(2 ** self.connection_attempts[market_type], 60)
                        
                        logger.info(f"币安{market_type}市场将在{retry_delay}秒后重连")
                        await asyncio.sleep(retry_delay)
                        
                        self.ws_connections[market_type] = await websockets.connect(
                            self.ws_endpoints[market_type],
                            ping_interval=20,
                            ping_timeout=10,
                            close_timeout=10
                        )
                        
                        if self.ws_connections[market_type].open:
                            logger.info(f"币安{market_type}市场重连成功")
                            ws = self.ws_connections[market_type]  # 更新ws引用
                            self.connection_attempts[market_type] = 0
                            continue
                        else:
                            logger.error(f"币安{market_type}市场重连失败")
                            break
                    except Exception as e:
                        logger.error(f"币安{market_type}市场重连失败: {str(e)}")
                        break
                        
                except asyncio.CancelledError:
                    logger.info(f"币安{market_type}市场数据处理任务被取消")
                    raise
                    
                except Exception as e:
                    logger.error(f"处理{market_type}市场数据出错: {str(e)}")
                    await asyncio.sleep(1)
                    continue
                    
        except asyncio.CancelledError:
            logger.info(f"币安{market_type}市场数据处理任务已取消")
        except Exception as e:
            logger.error(f"币安{market_type}市场数据处理异常: {str(e)}")
        finally:
            runtime = datetime.now() - start_time
            logger.info(f"币安{market_type}市场数据处理结束，运行{int(runtime.total_seconds())}秒，处理{message_count}条消息，更新{update_count}次") 