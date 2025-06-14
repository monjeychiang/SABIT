"""
加密貨幣市場數據模組

本模組提供加密貨幣市場數據API端點，包括:
1. 現貨和期貨市場價格查詢
2. 24小時交易資訊
3. WebSocket即時行情推送
4. 自定義交易對訂閱

支援多家交易所，主要實現Binance交易所API。
"""

import logging  # 導入日誌記錄模組，用於記錄系統運行狀態和錯誤信息
from fastapi import APIRouter, HTTPException, Depends, WebSocket, status, WebSocketDisconnect, Query, BackgroundTasks  # 導入FastAPI相關組件
from typing import Dict, Any, List, Optional, Set  # 導入類型提示工具
import httpx  # 導入現代化的HTTP客戶端，支援異步請求
import json  # 導入JSON處理工具
import asyncio  # 導入異步IO處理庫
import time  # 導入時間處理函數
from datetime import datetime  # 導入日期時間處理類
from sqlalchemy.orm import Session  # 導入SQLAlchemy的ORM會話類
from ...db.database import get_db  # 導入資料庫連接函數
from fastapi.security import OAuth2PasswordBearer  # 導入OAuth2密碼授權機制
from fastapi.responses import JSONResponse  # 導入JSON響應類
from websockets.exceptions import ConnectionClosed, ConnectionClosedOK, ConnectionClosedError  # 導入WebSocket連接相關異常
from ...services.market_data import market_data_service  # 導入市場數據服務
import os  # 導入操作系統模組，用於環境變數
from bs4 import BeautifulSoup  # 導入BeautifulSoup，用於解析HTML
from dotenv import load_dotenv  # 導入dotenv以載入環境變數

# 載入環境變數
load_dotenv()

# 設置日誌記錄
logger = logging.getLogger("market_api")  # 建立專屬於市場API的日誌記錄器
logger.setLevel(logging.INFO)  # 設置日誌級別為INFO

# 降低外部庫的日誌級別，避免過多干擾性日誌
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# 創建API路由器
router = APIRouter()  # 建立FastAPI路由器，用於註冊各種API端點

# OAuth2 Bearer Token設置，用於API認證
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

# 交易所 API 端點列表，包含各大交易所的API端點配置
CRYPTO_EXCHANGES = {
    "binance": {  # 幣安交易所
        "spot": "https://api.binance.com/api/v3/ticker/price",  # 現貨市場價格API
        "futures": "https://fapi.binance.com/fapi/v1/ticker/price",  # 期貨市場價格API
        "24h_ticker": "https://api.binance.com/api/v3/ticker/24hr",  # 24小時交易統計API
        "futures_24h": "https://fapi.binance.com/fapi/v1/ticker/24hr",  # 期貨24小時交易統計API
        "ws_spot": "wss://stream.binance.com:9443/ws",  # 現貨WebSocket端點
        "ws_futures": "wss://fstream.binance.com/ws"  # 期貨WebSocket端點
    },
    
    # === 以下交易所配置暂时注释，后续可根据需要启用 ===
    
    # OKX (前 okx)
    # "okx": {
    #     "spot": "https://www.okx.com/api/v5/market/tickers?instType=SPOT",
    #     "futures": "https://www.okx.com/api/v5/market/tickers?instType=SWAP",
    #     "24h_ticker": "https://www.okx.com/api/v5/market/ticker?instId=",  # 需要加上交易对
    #     "ws_public": "wss://ws.okx.com:8443/ws/v5/public",
    #     "ws_private": "wss://ws.okx.com:8443/ws/v5/private"  # 需要验证
    # },
    
    # Bybit
    # "bybit": {
    #     "spot": "https://api.bybit.com/v5/market/tickers?category=spot",
    #     "futures": "https://api.bybit.com/v5/market/tickers?category=linear",
    #     "24h_ticker": "https://api.bybit.com/v5/market/tickers?category=spot&symbol=",  # 需要加上交易对
    #     "ws_public": "wss://stream.bybit.com/v5/public",
    #     "ws_private": "wss://stream.bybit.com/v5/private"  # 需要验证
    # },
    
    # KuCoin
    # "kucoin": {
    #     "spot": "https://api.kucoin.com/api/v1/market/allTickers",
    #     "futures": "https://api-futures.kucoin.com/api/v1/contracts/active",
    #     "24h_ticker": "https://api.kucoin.com/api/v1/market/stats?symbol=",  # 需要加上交易对
    #     "ws_public": "wss://push1.kucoin.com/endpoint",  # 需要先获取token
    #     "ws_private": "wss://push1.kucoin.com/endpoint"  # 需要验证
    # },
    
    # Gate.io
    # "gate": {
    #     "spot": "https://api.gateio.ws/api/v4/spot/tickers",
    #     "futures": "https://api.gateio.ws/api/v4/futures/usdt/tickers",
    #     "24h_ticker": "https://api.gateio.ws/api/v4/spot/tickers?currency_pair=",  # 需要加上交易对
    #     "ws_spot": "wss://api.gateio.ws/ws/v4/",
    #     "ws_futures": "wss://fx-ws.gateio.ws/v4/ws/usdt"
    # },
    
    # Huobi Global
    # "huobi": {
    #     "spot": "https://api.huobi.pro/market/tickers",
    #     "futures": "https://api.hbdm.com/linear-swap-ex/market/detail/merged_all",
    #     "24h_ticker": "https://api.huobi.pro/market/detail/merged?symbol=",  # 需要加上交易对
    #     "ws_spot": "wss://api.huobi.pro/ws",
    #     "ws_futures": "wss://api.hbdm.com/linear-swap-ws"
    # },
    
    # Bitget
    # "bitget": {
    #     "spot": "https://api.bitget.com/api/spot/v1/market/tickers",
    #     "futures": "https://api.bitget.com/api/mix/v1/market/tickers?productType=USDT-FUTURES",
    #     "24h_ticker": "https://api.bitget.com/api/spot/v1/market/ticker?symbol=",  # 需要加上交易对
    #     "ws_spot": "wss://ws.bitget.com/spot/v1/stream",
    #     "ws_futures": "wss://ws.bitget.com/mix/v1/stream"
    # },
    
    # Mexc (前 MXC)
    # "mexc": {
    #     "spot": "https://api.mexc.com/api/v3/ticker/24hr",
    #     "futures": "https://contract.mexc.com/api/v1/contract/ticker",
    #     "24h_ticker": "https://api.mexc.com/api/v3/ticker/24hr?symbol=",  # 需要加上交易对
    #     "ws_spot": "wss://wbs.mexc.com/ws",
    #     "ws_futures": "wss://contract.mexc.com/ws"
    # }
}

# 價格緩存
class PriceCache:
    """
    價格資料緩存類
    
    用於緩存各交易所、各市場類型的價格數據，減少對外部API的請求頻率。
    包含智能更新機制、並發控制和數據統計功能。
    
    主要特點:
    - 支援多交易所數據緩存 (Binance、Bybit、OKX等)
    - 區分現貨和期貨市場
    - 異步更新機制
    - 防止短時間內頻繁請求
    - 自動日誌記錄和統計
    """
    def __init__(self):
        """
        初始化價格緩存類
        
        設置數據結構來存儲各交易所、各市場類型的價格數據，
        並初始化相關計數器、時間記錄和鎖。
        """
        # 主數據存儲，按交易所和市場類型組織
        self.data = {
            "binance": {"spot": {}, "futures": {}, "24h": {}},  # 幣安的現貨、期貨和24小時數據
            "bybit": {"spot": {}, "futures": {}},  # Bybit的現貨和期貨數據
            "okx": {"spot": {}, "futures": {}}  # OKX的現貨和期貨數據
        }
        # 最後更新時間記錄
        self.last_update = {
            "binance": {"spot": None, "futures": None, "24h": None},
            "bybit": {"spot": None, "futures": None},
            "okx": {"spot": None, "futures": None}
        }
        self.update_interval = 1.0  # 更新間隔（秒），控制API請求頻率
        self.last_fetch_time = 0  # 上次獲取數據的時間戳
        self.lock = asyncio.Lock()  # 異步鎖，確保並發環境下的數據一致性
        # 更新計數器，用於統計和監控
        self.update_counts = {
            "binance": {"spot": 0, "futures": 0, "24h": 0},
            "bybit": {"spot": 0, "futures": 0},
            "okx": {"spot": 0, "futures": 0}
        }
        self.log_interval = 3600  # 日誌記錄間隔（秒），每小時記錄一次統計信息
        self.last_log_time = datetime.now()  # 上次記錄日誌的時間
        
    async def get_prices(self, exchange="binance", market_type="spot", force_update=False):
        """
        獲取指定交易所和市場類型的價格數據
        
        智能判斷是否需要更新數據，若數據較新則直接返回緩存，
        否則通過API獲取最新數據。
        
        參數:
            exchange (str): 交易所名稱，默認為"binance"
            market_type (str): 市場類型，如"spot"或"futures"，默認為"spot"
            force_update (bool): 是否強制更新數據，忽略時間間隔限制，默認為False
            
        返回:
            dict: 包含價格數據的字典，格式為 {交易對: {價格信息}}
        """
        current_time = time.time()
        
        # 如果请求间隔太短且不强制更新，直接返回缓存
        if not force_update and (current_time - self.last_fetch_time < self.update_interval):
            return self.data[exchange][market_type]
            
        # 使用锁确保同一时间只有一个更新操作
        async with self.lock:
            # 再次检查，避免在等待锁期间其他请求已经更新了数据
            if force_update or (current_time - self.last_fetch_time >= self.update_interval):
                await self._update_prices(exchange, market_type)
                self.last_fetch_time = time.time()
                
        return self.data[exchange][market_type]
    
    async def _update_prices(self, exchange, market_type):
        """
        更新指定交易所和市場類型的價格數據
        
        內部方法，通過API請求獲取最新價格數據，
        並根據不同交易所的數據格式進行解析和存儲。
        
        參數:
            exchange (str): 交易所名稱
            market_type (str): 市場類型，如"spot"或"futures"
            
        返回:
            dict或None: 成功時返回更新後的數據，失敗時返回None
        """
        if exchange not in CRYPTO_EXCHANGES or market_type not in CRYPTO_EXCHANGES[exchange]:
            logger.warning(f"不支持的交易所: {exchange}")
            return
            
        try:
            url = CRYPTO_EXCHANGES[exchange][market_type]
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                
                result = {}
                
                # 根据不同交易所处理返回数据
                if exchange == "binance":
                    if isinstance(data, list):
                        for item in data:
                            symbol = item.get("symbol")
                            price = item.get("price")
                            if symbol and price:
                                result[symbol] = {
                                    "price": float(price),
                                    "lastUpdate": datetime.now().isoformat()
                                }
                elif exchange == "bybit":
                    if "result" in data and "list" in data["result"]:
                        for item in data["result"]["list"]:
                            symbol = item.get("symbol")
                            price = item.get("lastPrice")
                            if symbol and price:
                                result[symbol] = {
                                    "price": float(price),
                                    "lastUpdate": datetime.now().isoformat()
                                }
                elif exchange == "okx":
                    if "data" in data:
                        for item in data["data"]:
                            symbol = item.get("instId")
                            price = item.get("last")
                            if symbol and price:
                                result[symbol] = {
                                    "price": float(price),
                                    "lastUpdate": datetime.now().isoformat()
                                }
                
                # 更新缓存
                self.data[exchange][market_type] = result
                self.last_update[exchange][market_type] = datetime.now().isoformat()
                self.update_counts[exchange][market_type] += 1
                
                # 每10分鐘記錄一次統計信息
                current_time = datetime.now()
                if (current_time - self.last_log_time).total_seconds() >= self.log_interval:
                    logger.info(f"更新統計: {exchange} - 總更新次數 {self.update_counts[exchange][market_type]}")
                    self.last_log_time = current_time
                
                return result
                
        except Exception as e:
            logger.error(f"更新失敗: {exchange}")
            return None
            
    async def get_24h_data(self, exchange="binance", symbols=None):
        """
        獲取24小時行情數據
        
        通過API獲取指定交易對的24小時交易統計數據，
        包括最高價、最低價、交易量、價格變化百分比等信息。
        
        參數:
            exchange (str): 交易所名稱，目前僅支持 "binance"
            symbols (list): 交易對列表，如 ["BTCUSDT", "ETHUSDT"]
            
        返回:
            dict: 包含24小時行情數據的字典，格式為 {交易對: {行情數據}}
        """
        if exchange != "binance":
            logger.warning(f"僅支持Binance")
            return {}
            
        if not symbols:
            return {}
            
        try:
            results = {}
            async with httpx.AsyncClient(timeout=15.0) as client:
                for symbol in symbols:
                    try:
                        url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
                        response = await client.get(url)
                        if response.status_code == 200:
                            data = response.json()
                            results[symbol] = {
                                "price": float(data.get("lastPrice", 0)),
                                "priceChange": float(data.get("priceChangePercent", 0)),
                                "high": float(data.get("highPrice", 0)),
                                "low": float(data.get("lowPrice", 0)),
                                "volume": float(data.get("volume", 0)),
                                "quoteVolume": float(data.get("quoteVolume", 0)),
                                "lastUpdate": datetime.now().isoformat()
                            }
                        else:
                            logger.warning(f"請求失敗: {symbol}")
                    except Exception as e:
                        logger.error(f"處理失敗: {symbol}")
                        continue
                        
            # 更新缓存
            self.data[exchange]["24h"] = results
            self.last_update[exchange]["24h"] = datetime.now().isoformat()
            self.update_counts[exchange]["24h"] += 1
            
            # 每10分鐘記錄一次統計信息
            current_time = datetime.now()
            if (current_time - self.last_log_time).total_seconds() >= self.log_interval:
                logger.info(f"24h更新統計: 總更新次數 {self.update_counts[exchange]['24h']}")
                self.last_log_time = current_time
                
            return results
            
        except Exception as e:
            logger.error("24h數據更新失敗")
            return {}

# 初始化價格緩存
price_cache = PriceCache()

# WebSocket 連接管理
class ConnectionManager:
    """
    WebSocket連接管理器
    
    負責管理所有WebSocket連接，包括連接建立、關閉、分組和廣播消息。
    支援不同類型的連接分組管理，如全部價格、現貨價格、期貨價格和自定義交易對訂閱。
    
    主要功能:
    - 建立和關閉WebSocket連接
    - 管理連接分組
    - 向特定分組廣播消息
    - 統計連接數量和廣播次數
    """
    def __init__(self):
        """
        初始化WebSocket連接管理器
        
        設置連接存儲結構、計數器和日誌記錄間隔。
        """
        # 活躍連接字典，按連接類型分組存儲
        self.active_connections: Dict[str, List[WebSocket]] = {
            "all_prices": [],  # 訂閱所有價格的連接
            "binance_spot": [],  # 訂閱幣安現貨的連接
            "binance_futures": [],  # 訂閱幣安期貨的連接
            "custom_symbols": {}  # 自定義交易對訂閱，格式為 {交易對字符串: [連接列表]}
        }
        self.background_tasks = set()  # 追蹤背景任務
        # 廣播計數器，用於統計
        self.broadcast_counts = {
            "all_prices": 0,
            "binance_spot": 0,
            "binance_futures": 0,
            "custom": {}
        }
        # 日誌記錄參數
        self.log_interval = 600  # 每10分鐘記錄一次統計信息
        self.last_log_time = datetime.now()  # 上次記錄日誌的時間

    async def connect(self, websocket: WebSocket, connection_type: str, symbols=None):
        """
        建立WebSocket連接
        
        接受WebSocket連接請求，並將連接添加到適當的分組中。
        根據連接類型和訂閱的交易對進行不同處理。
        
        參數:
            websocket (WebSocket): 待連接的WebSocket對象
            connection_type (str): 連接類型，如 "all_prices", "binance_spot", "custom" 等
            symbols (list, 可選): 若為自定義交易對訂閱，需提供交易對列表
            
        返回:
            str: 客戶端ID，用於日誌記錄和調試
            
        異常:
            可能引發連接相關的異常
        """
        try:
            await websocket.accept()
            
            # 根据连接类型添加到不同的连接组
            if connection_type == "custom" and symbols:
                formatted_symbols = [s.upper() for s in symbols]
                key = ",".join(sorted(formatted_symbols))
                
                if key not in self.active_connections["custom_symbols"]:
                    self.active_connections["custom_symbols"][key] = []
                    self.broadcast_counts["custom"][key] = 0
                
                self.active_connections["custom_symbols"][key].append(websocket)
            else:
                self.active_connections[connection_type].append(websocket)
                
            client_id = f"{connection_type}_{id(websocket)}"
            
            # 每10分鐘記錄一次統計信息
            current_time = datetime.now()
            if (current_time - self.last_log_time).total_seconds() >= self.log_interval:
                logger.info(f"連接統計: {self.get_total_connections()}個")
                self.last_log_time = current_time
                
            return client_id
            
        except Exception as e:
            logger.error("連接失敗")
            raise

    def disconnect(self, websocket: WebSocket, connection_type: str, symbols=None):
        """
        關閉WebSocket連接
        
        從連接管理器中移除已關閉的連接，並清理相關資源。
        若某分組的連接數變為零，會清理該分組的相關數據。
        
        參數:
            websocket (WebSocket): 要斷開的WebSocket連接
            connection_type (str): 連接類型
            symbols (list, 可選): 若為自定義交易對訂閱，需提供交易對列表
        """
        try:
            if connection_type == "custom" and symbols:
                formatted_symbols = [s.upper() for s in symbols]
                key = ",".join(sorted(formatted_symbols))
                
                if key in self.active_connections["custom_symbols"]:
                    if websocket in self.active_connections["custom_symbols"][key]:
                        self.active_connections["custom_symbols"][key].remove(websocket)
                    
                    if not self.active_connections["custom_symbols"][key]:
                        del self.active_connections["custom_symbols"][key]
                        if key in self.broadcast_counts["custom"]:
                            del self.broadcast_counts["custom"][key]
            else:
                if websocket in self.active_connections[connection_type]:
                    self.active_connections[connection_type].remove(websocket)
                    
            # 每10分鐘記錄一次統計信息
            current_time = datetime.now()
            if (current_time - self.last_log_time).total_seconds() >= self.log_interval:
                logger.info(f"連接統計: {self.get_total_connections()}個")
                self.last_log_time = current_time
            
        except ValueError:
            pass
        except Exception as e:
            logger.error("斷開連接失敗")

    async def broadcast_to_group(self, group: str, message: Dict[str, Any]):
        """
        向指定分組廣播消息
        
        將消息發送給某個分組中的所有連接，同時處理已斷開的連接。
        包含統計功能，記錄廣播次數並定期記錄日誌。
        
        參數:
            group (str): 要廣播的目標分組，如 "all_prices", "binance_spot" 等
            message (dict): 要發送的消息內容，將被轉換為JSON
        """
        if group not in self.active_connections:
            return
        
        self.broadcast_counts[group] += 1
        
        # 每10分鐘記錄一次統計信息
        current_time = datetime.now()
        if (current_time - self.last_log_time).total_seconds() >= self.log_interval:
            active_connections = len(self.active_connections[group])
            if active_connections > 0:
                logger.info(f"廣播統計: {group} - {self.broadcast_counts[group]}次")
            self.last_log_time = current_time
            
        disconnected = []
        for connection in self.active_connections[group]:
            try:
                await connection.send_json(message)
            except Exception as e:
                disconnected.append((connection, group, None))
        
        for conn, group, _ in disconnected:
            self.disconnect(conn, group)

    async def broadcast_to_custom(self, symbols: List[str], message: Dict[str, Any]):
        """
        向訂閱特定交易對的客戶端廣播消息
        
        將消息發送給訂閱了特定交易對的WebSocket連接。
        自動處理已斷開的連接，並包含廣播統計功能。
        
        參數:
            symbols (list): 交易對列表，如 ["BTCUSDT", "ETHUSDT"]
            message (dict): 要發送的消息內容，將被轉換為JSON
        """
        if not symbols:
            return
            
        formatted_symbols = [s.upper() for s in symbols]
        key = ",".join(sorted(formatted_symbols))
        
        if key not in self.active_connections["custom_symbols"]:
            return
        
        if key not in self.broadcast_counts["custom"]:
            self.broadcast_counts["custom"][key] = 0
        self.broadcast_counts["custom"][key] += 1
        
        # 每10分鐘記錄一次統計信息
        current_time = datetime.now()
        if (current_time - self.last_log_time).total_seconds() >= self.log_interval:
            active_connections = len(self.active_connections["custom_symbols"][key])
            if active_connections > 0:
                logger.info(f"自定義廣播統計: {self.broadcast_counts['custom'][key]}次")
            self.last_log_time = current_time
            
        disconnected = []
        for connection in self.active_connections["custom_symbols"][key]:
            try:
                await connection.send_json(message)
            except Exception as e:
                disconnected.append((connection, "custom", formatted_symbols))
        
        for conn, group, symbols in disconnected:
            self.disconnect(conn, group, symbols)

    def get_total_connections(self):
        """
        獲取當前總連接數
        
        計算所有類型連接的總數，包括標準分組和自定義交易對訂閱。
        
        返回:
            int: 當前活躍的WebSocket連接總數
        """
        total = sum(len(conns) for key, conns in self.active_connections.items() 
                   if key != "custom_symbols")
                   
        # 添加自定义符号连接
        for key, conns in self.active_connections["custom_symbols"].items():
            total += len(conns)
            
        return total

    def add_background_task(self, task):
        """
        添加背景任務並追蹤
        
        將背景任務添加到集合中進行追蹤，任務完成後自動從集合中移除。
        
        參數:
            task: 要追蹤的異步任務對象
        """
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

# 初始化连接管理器
manager = ConnectionManager()

# 后台任务：更新所有价格并广播
async def background_price_updater():
    """
    後台價格更新任務
    
    持續運行的後台任務，負責定期更新價格數據並廣播給訂閱的用戶。
    功能包括：
    1. 獲取最新的現貨和期貨價格數據
    2. 將數據廣播給相應分組的WebSocket連接
    3. 更新自定義交易對訂閱
    4. 定期記錄統計信息
    5. 錯誤處理和恢復機制
    
    該任務在服務啟動時自動開始，並持續運行直到服務關閉。
    """
    logger.info("服務啟動")
    last_log_time = datetime.now()
    log_interval = 600  # 每10分鐘記錄一次統計
    
    while True:
        try:
            connection_count = manager.get_total_connections()
            current_time = datetime.now()
            
            # 每10分鐘記錄一次統計
            if (current_time - last_log_time).total_seconds() >= log_interval:
                logger.info(f"服務統計: {connection_count}個連接")
                last_log_time = current_time
            
            if connection_count > 0:
                # 更新Binance现货价格
                binance_spot = await price_cache.get_prices("binance", "spot", force_update=True)
                if binance_spot:
                    spot_message = {
                        "type": "update",
                        "exchange": "binance",
                        "market": "spot",
                        "timestamp": datetime.now().isoformat(),
                        "data": binance_spot
                    }
                    await manager.broadcast_to_group("all_prices", spot_message)
                    await manager.broadcast_to_group("binance_spot", spot_message)
                
                # 更新Binance期货价格
                binance_futures = await price_cache.get_prices("binance", "futures", force_update=True)
                if binance_futures:
                    futures_message = {
                        "type": "update",
                        "exchange": "binance",
                        "market": "futures",
                        "timestamp": datetime.now().isoformat(),
                        "data": binance_futures
                    }
                    await manager.broadcast_to_group("all_prices", futures_message)
                    await manager.broadcast_to_group("binance_futures", futures_message)
                
                # 更新自定义交易对订阅
                for symbols_key in list(manager.active_connections["custom_symbols"].keys()):
                    if not manager.active_connections["custom_symbols"][symbols_key]:
                        continue
                        
                    symbols = symbols_key.split(",")
                    data = await price_cache.get_24h_data("binance", symbols)
                    if data:
                        custom_message = {
                            "type": "update",
                            "exchange": "binance",
                            "market": "custom",
                            "timestamp": datetime.now().isoformat(),
                            "data": data
                        }
                        await manager.broadcast_to_custom(symbols, custom_message)
            
            await asyncio.sleep(1.0)
            
        except Exception as e:
            logger.error("服務異常")
            await asyncio.sleep(5)

# 启动后台更新任务
async def initialize_market_services():
    """
    市場數據服務初始化函數
    
    注意：此函數不再使用 router.on_event 裝飾器，而是作為普通函數，
    以便在 main.py 的應用啟動流程中被呼叫，避免重複初始化。
    
    功能：
    1. 初始化價格緩存，預先載入幣安的現貨和期貨價格
    2. 啟動後台價格更新任務，持續獲取和廣播最新市場數據
    
    這確保了服務一啟動就能提供有效的市場數據。
    """
    logger.info("初始化市場數據服務...")
    await price_cache.get_prices("binance", "spot")
    await price_cache.get_prices("binance", "futures")
    
    task = asyncio.create_task(background_price_updater())
    manager.add_background_task(task)
    logger.info("市場數據價格緩存和後台更新任務初始化完成")

@router.get("/prices", response_model=Dict[str, Any])
async def get_all_prices(
    exchange: str = Query("binance", description="交易所名稱"),
    market_type: str = Query("spot", description="市場類型 (spot/futures)")
):
    """
    獲取指定交易所和市場類型的所有價格
    
    此端點返回指定交易所和市場類型的所有交易對的最新價格。
    支援多種交易所和市場類型組合，如幣安的現貨和期貨市場。
    
    參數:
        exchange: 交易所名稱，默認為 "binance"
        market_type: 市場類型，可選 "spot"(現貨) 或 "futures"(期貨)，默認為 "spot"
    
    返回:
        包含交易所、市場類型、時間戳、最後更新時間和價格數據的JSON物件
        
    錯誤:
        400: 不支持的交易所或市場類型
        500: 獲取價格數據時出錯
    """
    if exchange not in CRYPTO_EXCHANGES or market_type not in CRYPTO_EXCHANGES[exchange]:
        raise HTTPException(status_code=400, detail=f"不支持的交易所或市場類型: {exchange} - {market_type}")
    
    prices = await price_cache.get_prices(exchange, market_type)
    
    if not prices:
        raise HTTPException(status_code=500, detail=f"獲取 {exchange} {market_type} 價格時出錯")
    
    return {
        "exchange": exchange,
        "market": market_type,
        "timestamp": datetime.now().isoformat(),
        "last_update": price_cache.last_update[exchange][market_type],
        "data": prices
    }

@router.get("/symbols", response_model=Dict[str, Any])
async def get_symbols(
    exchange: str = Query("binance", description="交易所名稱"),
    market_type: str = Query("spot", description="市場類型 (spot/futures)"),
    filter: Optional[str] = Query(None, description="過濾條件，例如 'BTC' 或 'USDT'")
):
    """
    獲取指定交易所和市場類型的所有交易對
    
    返回特定交易所和市場類型的所有可用交易對列表。
    支援按關鍵字過濾交易對，例如只返回包含 "BTC" 或 "USDT" 的交易對。
    
    參數:
        exchange: 交易所名稱，默認為 "binance"
        market_type: 市場類型，可選 "spot"(現貨) 或 "futures"(期貨)，默認為 "spot"
        filter: 過濾條件，篩選包含此字符串的交易對，選填
        
    返回:
        包含交易所、市場類型、交易對數量和交易對列表的JSON物件
    """
    prices = await price_cache.get_prices(exchange, market_type)
    
    if not prices:
        raise HTTPException(status_code=500, detail=f"獲取 {exchange} {market_type} 交易對時出錯")
    
    # 过滤交易对
    symbols = list(prices.keys())
    if filter:
        symbols = [s for s in symbols if filter.upper() in s]
    
    return {
        "exchange": exchange,
        "market": market_type,
        "count": len(symbols),
        "symbols": symbols
    }

@router.get("/tickers/24h", response_model=Dict[str, Any])
async def get_multiple_24h_tickers(
    symbols: List[str] = Query([], description="交易對列表，例如 ['BTCUSDT', 'ETHUSDT']"),
    exchange: str = Query("binance", description="交易所名稱")
):
    """
    獲取指定交易對的24小時行情數據
    
    返回指定交易對的24小時交易統計數據，包括價格變化百分比、最高價、最低價、
    交易量等信息。可同時請求多個交易對的數據。
    
    參數:
        symbols: 要查詢的交易對列表，例如 ["BTCUSDT", "ETHUSDT"]，可選，默認為空列表
        exchange: 交易所名稱，目前僅支持 "binance"，默認為 "binance"
        
    返回:
        包含交易所名稱、交易對數量、時間戳和24小時行情數據的JSON物件
        
    錯誤:
        500: 獲取行情數據失敗
    """
    data = await price_cache.get_24h_data(exchange, symbols)
    
    if not data:
        raise HTTPException(status_code=500, detail=f"獲取24小時行情數據時出錯")
    
    return {
        "exchange": exchange,
        "count": len(data),
        "timestamp": datetime.now().isoformat(),
        "data": data
    }

# WebSocket 端點 - 允許訪客模式
@router.websocket("/ws/all")
async def websocket_all_prices(
    websocket: WebSocket,
    exchange: str = Query("binance", description="交易所名称")
):
    """
    WebSocket連接獲取所有市場的價格更新
    
    建立WebSocket長連接，實時接收指定交易所的現貨和期貨市場價格更新。
    支援心跳機制、連接超時檢測和錯誤處理。
    
    連接參數:
        exchange: 交易所名稱，默認為 "binance"
    
    消息類型:
    - connection_established: 連接建立確認
    - update: 價格更新數據
    - heartbeat: 心跳消息
    - error: 錯誤信息
    - timeout_warning: 連接超時警告
    - connection_closing: 連接關閉通知
    
    客戶端可發送ping消息保持連接活躍。
    """
    await websocket.accept()
    connection_id = id(websocket)
    last_heartbeat = datetime.now()
    heartbeat_interval = 10  # 每10秒发送一次心跳
    is_closed = False
    last_client_message = datetime.now()
    connection_timeout = 60  # 60秒无消息则断开
    
    logger.info(f"新的市场数据WebSocket连接已建立 [ID: {connection_id}]")
    
    try:
        # 发送连接确认
        await websocket.send_json({
            "type": "connection_established",
            "connection_id": connection_id,
            "timestamp": datetime.now().isoformat(),
            "message": "已连接到市场数据服务"
        })
    except Exception as e:
        logger.error(f"发送连接确认失败 [ID: {connection_id}]: {str(e)}")
        return
    
    try:
        while not is_closed:
            try:
                # 尝试接收客户端消息（非阻塞）
                try:
                    text = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=0.1  # 使用非常短的超时时间，不会阻塞太久
                    )
                    # 记录收到客户端消息的时间
                    last_client_message = datetime.now()
                    
                    # 处理客户端消息
                    try:
                        data = json.loads(text)
                        if data.get("type") == "ping":
                            # 记录 ping 消息
                            logger.debug(f"PING - conn:{connection_id}")
                            await websocket.send_json({
                                "type": "pong",
                                "timestamp": datetime.now().isoformat()
                            })
                            continue
                    except:
                        # 忽略无效的JSON
                        pass
                except asyncio.TimeoutError:
                    # 超时是正常的，继续执行
                    pass
                except WebSocketDisconnect:
                    logger.info(f"客户端断开连接 [ID: {connection_id}]")
                    is_closed = True
                    break
                except ConnectionClosedOK:
                    logger.info(f"客户端正常断开连接 [ID: {connection_id}]")
                    is_closed = True
                    break
                except ConnectionClosedError:
                    logger.warning(f"客户端异常断开连接 [ID: {connection_id}]")
                    is_closed = True
                    break
                except ConnectionClosed:
                    logger.warning(f"客户端连接关闭 [ID: {connection_id}]")
                    is_closed = True
                    break
                
                # 检查连接是否超时
                current_time = datetime.now()
                if (current_time - last_client_message).total_seconds() > connection_timeout:
                    logger.warning(f"连接超时 [ID: {connection_id}]: {connection_timeout}秒内无响应")
                    try:
                        await websocket.send_json({
                            "type": "timeout_warning",
                            "timestamp": current_time.isoformat(),
                            "message": "连接即将关闭，请发送ping消息保持活跃"
                        })
                    except:
                        is_closed = True
                        break
                
                # 获取市场数据
                spot_tickers = market_data_service.get_all_tickers(exchange, "spot")
                futures_tickers = market_data_service.get_all_tickers(exchange, "futures")
                
                # 检查数据是否有效
                if not spot_tickers and not futures_tickers:
                    # 数据无效，等待一段时间再尝试
                    await asyncio.sleep(1)
                    continue
                
                # 构建市场数据
                market_data = {
                    "type": "update",
                    "timestamp": current_time.isoformat(),
                    "exchange": exchange,
                    "markets": {
                        "spot": spot_tickers,
                        "futures": futures_tickers
                    },
                    "stats": {
                        "spot_count": len(spot_tickers),
                        "futures_count": len(futures_tickers),
                        "total_count": len(spot_tickers) + len(futures_tickers)
                    }
                }
                
                # 发送市场数据
                if not is_closed:
                    try:
                        await websocket.send_json(market_data)
                    except Exception as e:
                        logger.error(f"发送市场数据失败 [ID: {connection_id}]: {str(e)}")
                        is_closed = True
                        break
                
                # 检查是否需要发送心跳
                if (current_time - last_heartbeat).total_seconds() >= heartbeat_interval:
                    if not is_closed:
                        try:
                            await websocket.send_json({
                                "type": "heartbeat",
                                "timestamp": current_time.isoformat()
                            })
                            last_heartbeat = current_time
                        except Exception as e:
                            logger.error(f"发送心跳失败 [ID: {connection_id}]: {str(e)}")
                            is_closed = True
                            break
                    
                # 等待下一次更新
                await asyncio.sleep(0.5)
                
            except WebSocketDisconnect:
                logger.info(f"客户端断开连接 [ID: {connection_id}]")
                is_closed = True
                break
            except ConnectionClosedOK:
                logger.info(f"客户端正常断开连接 [ID: {connection_id}]")
                is_closed = True
                break
            except ConnectionClosedError as e:
                logger.warning(f"客户端异常断开连接 [ID: {connection_id}]: {str(e)}")
                is_closed = True
                break
            except Exception as e:
                logger.error(f"处理市场数据失败 [ID: {connection_id}]: {str(e)}")
                if not is_closed:
                    try:
                        await websocket.send_json({
                            "type": "error",
                            "timestamp": datetime.now().isoformat(),
                            "message": "获取市场数据失败，稍后重试"
                        })
                    except:
                        is_closed = True
                        break
                # 出错后稍等一段时间再继续
                await asyncio.sleep(2)
                
    except Exception as e:
        logger.error(f"WebSocket连接出现异常 [ID: {connection_id}]: {str(e)}")
    finally:
        logger.info(f"WebSocket连接已关闭 [ID: {connection_id}]")
        if not is_closed:
            try:
                # 发送关闭通知
                await websocket.send_json({
                    "type": "connection_closing",
                    "timestamp": datetime.now().isoformat(),
                    "message": "服务器正在关闭连接"
                })
                await websocket.close()
            except:
                pass

@router.websocket("/ws/spot")
async def websocket_spot_prices(
    websocket: WebSocket,
    exchange: str = Query("binance", description="交易所名称")
):
    """
    WebSocket連接獲取現貨市場的價格更新
    
    建立WebSocket長連接，專門接收指定交易所的現貨市場實時價格數據。
    每秒更新一次數據，並自動處理連接異常。
    
    連接參數:
        exchange: 交易所名稱，默認為 "binance"
        
    消息格式:
        {
            "type": "update",
            "timestamp": "ISO時間戳",
            "exchange": "交易所名稱",
            "market_type": "spot",
            "data": {交易對價格數據}
        }
    """
    await websocket.accept()
    connection_id = id(websocket)
    logger.info(f"新的现货WebSocket连接已建立 [ID: {connection_id}]")
    
    try:
        while True:
            try:
                # 获取现货数据
                spot_tickers = market_data_service.get_all_tickers(exchange, "spot")
                
                # 构建数据
                market_data = {
                    "type": "update",
                    "timestamp": datetime.now().isoformat(),
                    "exchange": exchange,
                    "market_type": "spot",
                    "data": spot_tickers
                }
                
                # 发送数据
                await websocket.send_json(market_data)
                await asyncio.sleep(1)
                
            except WebSocketDisconnect:
                logger.info(f"现货WebSocket客户端断开连接 [ID: {connection_id}]")
                break
            except Exception as e:
                logger.error(f"处理现货WebSocket数据时出错 [ID: {connection_id}]: {str(e)}")
                await asyncio.sleep(5)
                
    except Exception as e:
        logger.error(f"现货WebSocket连接错误 [ID: {connection_id}]: {str(e)}")
    finally:
        logger.info(f"现货WebSocket连接已关闭 [ID: {connection_id}]")
        await websocket.close()

@router.websocket("/ws/futures")
async def websocket_futures_prices(
    websocket: WebSocket,
    exchange: str = Query("binance", description="交易所名称")
):
    """
    WebSocket連接獲取期貨市場的價格更新
    
    建立WebSocket長連接，專門接收指定交易所的期貨市場實時價格數據。
    每秒更新一次數據，自動處理連接中斷和錯誤恢復。
    
    連接參數:
        exchange: 交易所名稱，默認為 "binance"
        
    消息格式:
        {
            "type": "update",
            "timestamp": "ISO時間戳",
            "exchange": "交易所名稱",
            "market_type": "futures",
            "data": {期貨交易對價格數據}
        }
    """
    await websocket.accept()
    connection_id = id(websocket)
    logger.info(f"新的合约WebSocket连接已建立 [ID: {connection_id}]")
    
    try:
        while True:
            try:
                # 获取合约数据
                futures_tickers = market_data_service.get_all_tickers(exchange, "futures")
                
                # 构建数据
                market_data = {
                    "type": "update",
                    "timestamp": datetime.now().isoformat(),
                    "exchange": exchange,
                    "market_type": "futures",
                    "data": futures_tickers
                }
                
                # 发送数据
                await websocket.send_json(market_data)
                await asyncio.sleep(1)
                
            except WebSocketDisconnect:
                logger.info(f"合约WebSocket客户端断开连接 [ID: {connection_id}]")
                return
            except Exception as e:
                logger.error(f"处理合约WebSocket数据时出错 [ID: {connection_id}]: {str(e)}")
                await asyncio.sleep(5)
                continue
                
    except Exception as e:
        logger.error(f"合约WebSocket连接错误 [ID: {connection_id}]: {str(e)}")
    finally:
        logger.info(f"合约WebSocket连接已关闭 [ID: {connection_id}]")
        await websocket.close()

@router.websocket("/ws/binance/spot")
async def websocket_binance_spot(websocket: WebSocket):
    """
    WebSocket連接獲取幣安現貨實時價格
    
    使用連接管理器建立WebSocket連接，實時接收幣安現貨市場所有交易對的價格數據。
    提供初始數據載入和定期心跳機制，確保連接穩定性。
    
    消息類型:
    - initial: 連接建立後發送的初始數據
    - heartbeat: 每30秒發送一次的心跳消息
    
    初始數據包含幣安現貨市場所有交易對的最新價格，之後的更新通過廣播方式推送。
    """
    client_id = None
    send_counter = 0
    
    try:
        # 接受連接
        client_id = await manager.connect(websocket, "binance_spot")
        logger.info(f"Binance現貨WebSocket連接已建立：{client_id}")
        
        # 立即發送初始價格數據
        initial_data = {
            "type": "initial",
            "exchange": "binance",
            "market": "spot",
            "timestamp": datetime.now().isoformat(),
            "data": await price_cache.get_prices("binance", "spot")
        }
        await websocket.send_json(initial_data)
        logger.info(f"已發送初始Binance現貨價格數據到客戶端：{client_id}")
        send_counter += 1
        
        # 保持连接，等待客户端消息
        while True:
            await asyncio.sleep(30)  # 使用简单的心跳保持连接
            await websocket.send_json({"type": "heartbeat"})
            # 不再記錄每次心跳
            
    except WebSocketDisconnect:
        logger.info(f"Binance現貨客戶端主動斷開連接：{client_id}")
    except Exception as e:
        logger.error(f"Binance現貨WebSocket連接中斷：{client_id}，錯誤：{str(e)}")
    finally:
        # 連接關閉時清理
        if client_id:
            manager.disconnect(websocket, "binance_spot")
            logger.info(f"Binance現貨WebSocket連接已清理：{client_id}，共發送 {send_counter} 次數據")

@router.websocket("/ws/binance/futures")
async def websocket_binance_futures(websocket: WebSocket):
    """
    WebSocket連接獲取幣安期貨實時價格
    
    使用連接管理器建立WebSocket連接，專門接收幣安期貨市場的實時價格數據。
    提供完整的連接生命週期管理，包括連接建立、數據初始化、定期更新和連接關閉。
    
    消息類型:
    - connection_success: 連接成功確認
    - initial: 初始價格數據
    - update: 每3秒更新一次的價格數據
    - heartbeat: 心跳消息（當無數據更新時發送）
    - error: 錯誤信息
    
    數據結構採用嵌套格式，便於客戶端處理多交易所、多市場類型的情況。
    """
    client_id = None
    connection_type = "binance_futures"
    update_counter = 0
    
    try:
        client_id = await manager.connect(websocket, connection_type)
        logger.info(f"Binance期貨WebSocket連接已建立：{client_id}")
        
        # 發送初始數據
        initial_data = await price_cache.get_prices("binance", "futures", force_update=True)
        if initial_data:
            # 发送连接成功消息
            await websocket.send_json({
                "type": "connection_success",
                "message": "已連接到合約市場"
            })
            
            # 发送初始数据
            await websocket.send_json({
            "type": "initial",
                "data": {
                    "binance": {
                        "futures": initial_data
                    }
                }
            })
            
            logger.info(f"已向客戶端 {client_id} 發送合約市場初始數據")
        else:
            await websocket.send_json({
                "type": "error",
                "message": "獲取合約市場數據失敗"
            })
            logger.error(f"向客戶端 {client_id} 發送合約市場初始數據失敗")
            
        # 持續發送更新數據
        while True:
            # 每3秒從緩存獲取一次最新數據
            await asyncio.sleep(3)
            
            # 檢查連接是否仍然活躍
            try:
                # 嘗試獲取最新數據
                updated_data = await price_cache.get_prices("binance", "futures")
                
                if updated_data:
                    # 發送更新數據
                    await websocket.send_json({
                        "type": "update",
                        "data": {
                            "binance": {
                                "futures": updated_data
                            }
                        }
                    })
                    update_counter += 1
                    # 不再每次更新都記錄日誌
                else:
                    # 發送心跳保持連接
                    await websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": datetime.now().isoformat()
                    })
            except Exception as e:
                logger.error(f"發送合約市場更新數據時出錯: {str(e)}")
                break
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket客戶端 {client_id} 斷開連接 (合約市場)，共發送 {update_counter} 次數據更新")
    except Exception as e:
        logger.error(f"處理WebSocket連接時出錯 (合約市場): {str(e)}")
    finally:
        if client_id:
            manager.disconnect(websocket, connection_type)
            logger.info(f"Binance期貨WebSocket連接已清理：{client_id}")

@router.websocket("/ws/futures/prices")
async def websocket_futures_prices(websocket: WebSocket):
    """
    WebSocket連接獲取包含價格變化的期貨行情
    
    建立WebSocket連接，提供帶有24小時價格變化數據的期貨行情信息。
    除了基本價格數據外，還包含每個交易對的漲跌幅百分比。
    
    特點:
    - 包含24小時價格變化百分比（priceChange字段）
    - 每5次更新重新獲取一次24小時變化數據
    - 數據更新頻率為2秒一次
    - 支持自動重連和錯誤處理
    
    消息類型:
    - connection_success: 連接成功確認
    - initial: 初始數據（包含價格和漲跌幅）
    - update: 更新數據
    - heartbeat: 心跳消息
    - error: 錯誤信息
    """
    client_id = None
    update_counter = 0
    
    try:
        client_id = await manager.connect(websocket, "binance_futures")
        logger.info(f"期貨價格WebSocket連接已建立：{client_id}")
        
        # 發送初始數據
        initial_data = await price_cache.get_prices("binance", "futures", force_update=True)
        if initial_data:
            # 计算并添加24小时涨跌幅
            try:
                # 獲取24小時行情數據以添加漲跌幅
                futures_24h_data = await update_futures_price_changes()
                
                # 合併價格和漲跌幅數據
                for symbol, info in futures_24h_data.items():
                    if symbol in initial_data:
                        initial_data[symbol]["priceChange"] = info.get("priceChange", 0)
            except Exception as e:
                logger.error(f"獲取合約市場24小時數據時出錯: {str(e)}")
            
            # 发送连接成功消息
            await websocket.send_json({
                "type": "connection_success",
                "message": "已連接到合約市場價格推送"
            })
            
            # 发送初始数据，确保数据格式一致且只包含futures数据
            await websocket.send_json({
            "type": "initial",
                "data": {
                    "binance": {
                        "futures": initial_data  # 确保标记为futures数据
                    }
                }
            })
            
            logger.info(f"已向客戶端 {client_id} 發送合約市場初始數據")
        else:
            await websocket.send_json({
                "type": "error",
                "message": "獲取合約市場初始數據失敗"
            })
            logger.error(f"向客戶端 {client_id} 發送合約市場初始數據失敗")
            
        # 持續發送更新數據
        futures_24h_data = {}
        while True:
            # 每2秒更新一次
            await asyncio.sleep(2)
            
            try:
                # 每5次更新獲取一次24小時數據
                if update_counter % 5 == 0:
                    futures_24h_data = await update_futures_price_changes()
                
                # 獲取最新價格數據
                updated_data = await price_cache.get_prices("binance", "futures")
                
                if updated_data:
                    # 合併價格和漲跌幅數據
                    for symbol, info in futures_24h_data.items():
                        if symbol in updated_data:
                            updated_data[symbol]["priceChange"] = info.get("priceChange", 0)
                    
                    # 發送更新數據，明确标识为期货数据
                    await websocket.send_json({
                        "type": "update",
                        "data": {
                            "binance": {
                                "futures": updated_data  # 明确标识为futures数据
                            }
                        }
                    })
                    # 不再每次更新都記錄日誌
                    update_counter += 1
                else:
                    # 發送心跳包
                    await websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": datetime.now().isoformat()
                    })
            except Exception as e:
                logger.error(f"發送合約市場更新數據時出錯: {str(e)}")
                break
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket客戶端 {client_id} 斷開連接 (期貨價格)，共發送 {update_counter} 次數據更新")
    except Exception as e:
        logger.error(f"處理WebSocket連接時出錯 (期貨價格): {str(e)}")
    finally:
        if client_id:
            manager.disconnect(websocket, "binance_futures")
            logger.info(f"期貨價格WebSocket連接已清理：{client_id}")

async def update_futures_price_changes():
    """獲取期貨24小時價格變化數據"""
    try:
        url = CRYPTO_EXCHANGES["binance"]["futures_24h"]
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            result = {}
            if isinstance(data, list):
                for item in data:
                    symbol = item.get("symbol")
                    price_change = item.get("priceChangePercent")
                    
                    if symbol and price_change is not None:
                        result[symbol] = {
                            "priceChange": float(price_change) / 100,  # 轉換為小數
                            "high": float(item.get("highPrice", 0)),
                            "low": float(item.get("lowPrice", 0)),
                            "volume": float(item.get("volume", 0)),
                            "quoteVolume": float(item.get("quoteVolume", 0)),
                            "lastUpdate": datetime.now().isoformat()
                        }
            
            return result
    except Exception as e:
        logger.error(f"獲取期貨24小時數據時出錯: {str(e)}")
        return {}

@router.get("/futures/prices", response_model=Dict[str, Any])
async def get_futures_prices(
    exchange: str = Query("binance", description="交易所名稱")
):
    """獲取期貨市場價格數據"""
    try:
        # 獲取期貨價格
        futures_data = await price_cache.get_prices(exchange, "futures", force_update=True)
        
        if not futures_data:
            return {"success": False, "message": "獲取期貨價格數據失敗", "data": {}}
        
        # 獲取24小時變化數據
        futures_24h_data = await update_futures_price_changes()
        
        # 合併數據
        for symbol, info in futures_24h_data.items():
            if symbol in futures_data:
                futures_data[symbol]["priceChange"] = info.get("priceChange", 0)
                futures_data[symbol]["high"] = info.get("high", 0)
                futures_data[symbol]["low"] = info.get("low", 0)
                futures_data[symbol]["volume"] = info.get("volume", 0)
        
        return {
            "success": True,
            "message": "獲取期貨價格數據成功",
            "data": futures_data
        }
    except Exception as e:
        logger.error(f"獲取期貨價格時出錯: {str(e)}")
        return {"success": False, "message": f"獲取期貨價格出錯: {str(e)}", "data": {}}



@router.websocket("/ws/custom")
async def websocket_custom_symbols(
    websocket: WebSocket,
    symbols: str = Query(..., description="逗號分隔的交易對列表，例如 'BTCUSDT,ETHUSDT'")
):
    """
    WebSocket 連接，用於訂閱特定交易對的價格更新
    """
    client_id = None
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    update_counter = 0
    
    if not symbol_list:
        await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA, reason="未提供有效的交易對")
        return
    
    try:
        # 接受連接
        client_id = await manager.connect(websocket, "custom", symbol_list)
        logger.info(f"自定義WebSocket連接已建立：{client_id}，訂閱交易對: {symbols}")
        
        # 获取并发送初始数据
        initial_data = await price_cache.get_24h_data("binance", symbol_list)
        
        await websocket.send_json({
            "type": "initial",
            "exchange": "binance",
            "symbols": symbol_list,
            "timestamp": datetime.now().isoformat(),
            "data": initial_data
        })
        logger.info(f"已發送初始自定義交易對數據到客戶端：{client_id}")
        update_counter += 1
        
        # 保持连接，等待客户端消息
        while True:
            await asyncio.sleep(30)  # 使用简单的心跳保持连接
            await websocket.send_json({"type": "heartbeat"})
            # 不記錄心跳
            
    except WebSocketDisconnect:
        logger.info(f"自定義客戶端主動斷開連接：{client_id}，共發送 {update_counter} 次數據更新")
    except Exception as e:
        logger.error(f"自定義WebSocket連接中斷：{client_id}，錯誤：{str(e)}")
    finally:
        # 連接關閉時清理
        if client_id:
            manager.disconnect(websocket, "custom", symbol_list)
            logger.info(f"自定義WebSocket連接已清理：{client_id}") 

# 改為普通的清理函數，由 main.py 調用
# @router.on_event("shutdown")
async def cleanup_market_services():
    """關閉市場數據服務資源
    
    注意：此函數不再使用 router.on_event 裝飾器，而是作為普通函數，
    以便在 main.py 的應用關閉流程中被呼叫，確保資源正確釋放。
    
    功能：
    - 停止市場數據服務
    - 關閉所有活躍的WebSocket連接
    - 取消後台任務
    """
    await market_data_service.stop()
    logger.info("市場數據服務已停止")

@router.get("/prices/all")
async def get_all_prices(
    exchange: str = Query("binance", description="交易所名称"),
    market_type: str = Query("spot", description="市场类型 (spot/futures)")
):
    """获取所有交易对的价格"""
    tickers = market_data_service.get_all_tickers(exchange, market_type)
    if not tickers:
        raise HTTPException(status_code=404, detail="未找到价格数据")
    return tickers

@router.get("/prices/spot")
async def get_spot_prices(
    exchange: str = Query("binance", description="交易所名称")
):
    """获取所有现货交易对的价格"""
    return await get_all_prices(exchange, "spot")

@router.get("/prices/futures")
async def get_futures_prices(
    exchange: str = Query("binance", description="交易所名称")
):
    """获取所有合约交易对的价格"""
    return await get_all_prices(exchange, "futures")

@router.get("/ticker")
async def get_ticker(
    symbol: str = Query(..., description="交易对名称"),
    exchange: str = Query("binance", description="交易所名称"),
    market_type: str = Query("spot", description="市场类型 (spot/futures)")
):
    """获取单个交易对的价格"""
    ticker = market_data_service.get_ticker(symbol, exchange, market_type)
    if not ticker:
        raise HTTPException(status_code=404, detail="未找到该交易对的价格数据")
    return ticker

@router.get("/ticker/24h")
async def get_24h_ticker(
    symbol: str = Query(..., description="交易对名称"),
    exchange: str = Query("binance", description="交易所名称"),
    market_type: str = Query("spot", description="市场类型 (spot/futures)")
):
    """获取单个交易对的24小时行情数据"""
    ticker = market_data_service.get_24h_ticker(symbol, exchange, market_type)
    if not ticker:
        raise HTTPException(status_code=404, detail="未找到该交易对的24小时行情数据")
    return ticker

@router.websocket("/ws/symbols")
async def websocket_symbol_prices(
    websocket: WebSocket,
    symbols: str = Query(..., description="交易对列表，用逗号分隔"),
    exchange: str = Query("binance", description="交易所名称"),
    market_type: str = Query("spot", description="市场类型 (spot/futures)")
):
    """WebSocket连接获取特定交易对的价格更新"""
    await websocket.accept()
    symbol_list = [s.strip() for s in symbols.split(",")]
    try:
        await market_data_service.subscribe_symbols(symbol_list, exchange, market_type)
        while True:
            tickers = {
                symbol: market_data_service.get_ticker(symbol, exchange, market_type)
                for symbol in symbol_list
            }
            await websocket.send_json(tickers)
            await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"WebSocket连接错误: {str(e)}")
    finally:
        await market_data_service.unsubscribe_symbols(symbol_list, exchange, market_type)
        await websocket.close()

@router.get("/prices/usdt", response_model=Dict[str, Any])
async def get_usdt_pairs(
    exchange: str = Query("binance", description="交易所名称"),
    market_type: str = Query("spot", description="市场类型 (spot/futures)")
):
    """获取所有USDT交易对的价格"""
    try:
        # 获取所有价格
        all_tickers = market_data_service.get_all_tickers(exchange, market_type)
        
        # 筛选USDT交易对
        usdt_tickers = {
            symbol: data for symbol, data in all_tickers.items()
            if symbol.endswith('USDT')
        }
        
        return {
            "exchange": exchange,
            "market_type": market_type,
            "timestamp": datetime.now().isoformat(),
            "count": len(usdt_tickers),
            "data": usdt_tickers
        }
    except Exception as e:
        logger.error(f"获取USDT交易对价格时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/ws/usdt")
async def websocket_usdt_pairs(
    websocket: WebSocket,
    exchange: str = Query("binance", description="交易所名称"),
    market_type: str = Query("spot", description="市場類型 (spot/futures)")
):
    """WebSocket連接獲取USDT交易對的價格更新"""
    await websocket.accept()
    last_heartbeat = datetime.now()
    connection_id = id(websocket)
    is_closed = False
    is_subscribed = False
    logger.info(f"新的USDT交易對WebSocket連接已建立 [ID: {connection_id}]")
    
    try:
        while not is_closed:
            try:
                # 檢查心跳超時
                current_time = datetime.now()
                if (current_time - last_heartbeat).total_seconds() > 60:  # 60秒無響應則斷開
                    logger.warning(f"WebSocket心跳超時 [ID: {connection_id}]")
                    break
                
                # 等待客戶端消息或超時
                try:
                    message = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                    data = json.loads(message)
                    
                    if data.get("type") == "pong":
                        last_heartbeat = current_time
                        continue
                    
                    if data.get("type") == "subscribe":
                        is_subscribed = True
                        await websocket.send_json({
                            "type": "subscribed",
                            "timestamp": current_time.isoformat(),
                            "market_type": market_type
                        })
                        logger.info(f"客戶端訂閱了 {market_type} 市場數據 [ID: {connection_id}]")
                        continue
                        
                except asyncio.TimeoutError:
                    # 發送心跳
                    if not is_closed:
                        await websocket.send_json({
                            "type": "heartbeat",
                            "timestamp": current_time.isoformat()
                        })
                    continue
                except WebSocketDisconnect:
                    logger.info(f"客戶端斷開連接 [ID: {connection_id}]")
                    is_closed = True
                    break
                except Exception as e:
                    logger.error(f"處理客戶端消息時出錯 [ID: {connection_id}]: {str(e)}")
                    continue
                
                # 如果客戶端未訂閱，則不發送數據
                if not is_subscribed:
                    continue
                
                # 獲取所有價格
                all_tickers = market_data_service.get_all_tickers(exchange, market_type)
                
                # 篩選USDT交易對
                usdt_tickers = {
                    symbol: data for symbol, data in all_tickers.items()
                    if symbol.endswith('USDT')
                }
                
                # 構建市場數據
                market_data = {
                    "type": "update",
                    "timestamp": current_time.isoformat(),
                    "exchange": exchange,
                    "market_type": market_type,
                    "count": len(usdt_tickers),
                    "data": usdt_tickers
                }
                
                # 發送數據
                if not is_closed:
                    await websocket.send_json(market_data)
                
                # 等待下一次更新
                await asyncio.sleep(1)
                
            except WebSocketDisconnect:
                logger.info(f"USDT交易對WebSocket客戶端斷開連接 [ID: {connection_id}]")
                is_closed = True
                break
            except Exception as e:
                logger.error(f"處理USDT交易對WebSocket數據時出錯 [ID: {connection_id}]: {str(e)}")
                if not is_closed:
                    try:
                        await websocket.send_json({
                            "type": "error",
                            "timestamp": datetime.now().isoformat(),
                            "message": "獲取USDT交易對數據時出錯"
                        })
                    except:
                        is_closed = True
                        break
                await asyncio.sleep(5)  # 出錯後等待較長時間再重試
                
    except Exception as e:
        logger.error(f"USDT交易對WebSocket連接錯誤 [ID: {connection_id}]: {str(e)}")
    finally:
        logger.info(f"USDT交易對WebSocket連接已關閉 [ID: {connection_id}]")
        if not is_closed:
            try:
                await websocket.close()
            except:
                pass 

@router.websocket("/ws/ticker/{symbol}")
async def websocket_ticker(websocket: WebSocket, symbol: str):
    """为单个交易对提供实时行情数据
    
    Args:
        websocket: WebSocket连接
        symbol: 交易对符号，如BTCUSDT
    """
    await websocket.accept()
    
    # 发送连接确认消息
    await websocket.send_json({
        "type": "connection_established",
        "message": f"已连接到{symbol}行情数据",
        "timestamp": datetime.now().isoformat()
    })
    
    # 定义异步生成数据的函数
    async def send_ticker_data():
        try:
            while True:
                try:
                    # 获取所有市场数据
                    spot_tickers = market_data_service.get_all_tickers(exchange="binance", market_type="spot")
                    futures_tickers = market_data_service.get_all_tickers(exchange="binance", market_type="futures")
                    
                    all_tickers = {
                        "spot": spot_tickers,
                        "futures": futures_tickers
                    }
                    
                    # 确定交易对所在的市场类型
                    ticker_data = None
                    market_type = None
                    
                    if symbol in all_tickers.get("spot", {}):
                        ticker_data = all_tickers["spot"][symbol]
                        market_type = "spot"
                    elif symbol in all_tickers.get("futures", {}):
                        ticker_data = all_tickers["futures"][symbol]
                        market_type = "futures"
                    
                    # 如果找到数据，发送给客户端
                    if ticker_data:
                        # 添加市场类型和时间戳
                        ticker_data["market_type"] = market_type
                        ticker_data["timestamp"] = datetime.now().isoformat()
                        ticker_data["symbol"] = symbol  # 确保包含交易对信息
                        
                        await websocket.send_json(ticker_data)
                    else:
                        # 如果未找到数据，发送一个提示信息
                        await websocket.send_json({
                            "type": "error",
                            "message": f"未找到交易对 {symbol} 的行情数据",
                            "timestamp": datetime.now().isoformat()
                        })
                        
                except Exception as e:
                    logger.error(f"处理交易对 {symbol} 行情数据时出错: {str(e)}")
                    # 发送错误消息到客户端
                    await websocket.send_json({
                        "type": "error",
                        "message": f"获取行情数据时出错: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    })
                
                # 休眠一段时间
                await asyncio.sleep(3)
        except WebSocketDisconnect:
            # 用户断开连接
            return
        except Exception as e:
            # 发生错误，记录日志
            logger.error(f"交易对行情WebSocket错误: {str(e)}")
    
    # 启动数据发送任务
    data_task = asyncio.create_task(send_ticker_data())
    
    try:
        # 保持连接直到客户端断开
        await websocket.wait_for_disconnect()
    finally:
        # 取消数据发送任务
        data_task.cancel()
        try:
            await data_task
        except asyncio.CancelledError:
            pass 

# 新增CoinMarketCap API配置
COINMARKETCAP_API_KEY = os.getenv("COINMARKETCAP_API_KEY", "")
COINMARKETCAP_API_URL = "https://pro-api.coinmarketcap.com"

# 新增獲取全球加密貨幣市場數據端點
@router.get("/global-metrics", response_model=Dict[str, Any])
async def get_global_metrics(force_refresh: bool = Query(False, description="強制刷新數據，忽略緩存")):
    """
    獲取全球加密貨幣市場指標數據
    
    此端點從緩存中獲取全球加密貨幣市場指標數據，包括:
    - 總市值
    - 24小時交易量
    - 比特幣佔比
    - 以太坊佔比
    - 活躍加密貨幣數量
    - 活躍市場數量
    - 恐懼與貪婪指數
    
    為了減少API請求次數，數據會被緩存:
    - 全球市場數據每小時更新一次
    - 恐懼與貪婪指數每3小時更新一次
    
    參數:
        force_refresh (bool): 是否強制刷新數據，忽略緩存
    
    返回:
        包含全球市場指標、恐懼與貪婪指數和緩存信息的JSON物件
    """
    try:
        # 從緩存獲取數據
        global_metrics = await global_market_cache.get_global_metrics(force_update=force_refresh)
        fear_greed_data = await global_market_cache.get_fear_greed_index(force_update=force_refresh)
        
        # 合併數據
        result = {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "global_metrics": global_metrics,
            "fear_greed_index": fear_greed_data,
            "cache_info": {
                "was_cached": not force_refresh,
                "last_forced_refresh": datetime.now().isoformat() if force_refresh else None
            }
        }
        
        return result
    except Exception as e:
        logger.error(f"獲取全球市場數據失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=f"獲取全球市場數據失敗: {str(e)}")

async def get_coinmarketcap_global_metrics() -> Dict[str, Any]:
    """
    從CoinMarketCap API獲取全球加密貨幣市場指標
    
    調用CoinMarketCap的v1/global-metrics/quotes/latest端點，獲取全球加密貨幣市場指標數據
    
    返回:
        Dict[str, Any]: 包含全球加密貨幣市場指標數據的字典
    """
    # 直接從環境變數中獲取API金鑰
    api_key = os.getenv("COINMARKETCAP_API_KEY", "")
    
    # 記錄API金鑰是否成功載入的日誌
    if api_key:
        logger.info(f"已成功讀取 CoinMarketCap API 金鑰 (前4字元: {api_key[:4]}...)")
    else:
        logger.warning("未找到 CoinMarketCap API 金鑰環境變數，將使用模擬數據")
    
    # 如果API密鑰為空，使用模擬數據
    if not api_key:
        logger.warning("缺少CoinMarketCap API密鑰，使用模擬數據")
        # 返回模擬數據，如果未設置API密鑰
        return {
            "total_market_cap_usd": 2500000000000,
            "total_volume_24h_usd": 150000000000,
            "bitcoin_dominance": 48.5,
            "ethereum_dominance": 18.7,
            "active_cryptocurrencies": 10000,
            "active_exchanges": 500,
            "last_updated": datetime.now().isoformat(),
            "note": "模擬數據 - 未配置CoinMarketCap API密鑰"
        }
    
    url = f"{COINMARKETCAP_API_URL}/v1/global-metrics/quotes/latest"
    headers = {
        "X-CMC_PRO_API_KEY": api_key,
        "Accept": "application/json"
    }
    
    try:
        logger.info(f"正在發送請求到 CoinMarketCap API: {url}")
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # 檢查API響應是否成功
            if "data" not in data:
                error_message = data.get("status", {}).get("error_message", "Unknown error")
                logger.error(f"CoinMarketCap API返回錯誤: {error_message}")
                raise HTTPException(
                    status_code=500,
                    detail=f"獲取CoinMarketCap數據失敗: {error_message}"
                )
            
            # 處理並格式化數據
            quotes = data["data"]["quote"]["USD"]
            result = {
                "total_market_cap_usd": quotes["total_market_cap"],
                "total_volume_24h_usd": quotes["total_volume_24h"],
                "bitcoin_dominance": data["data"]["btc_dominance"],
                "ethereum_dominance": data["data"]["eth_dominance"],
                "active_cryptocurrencies": data["data"]["active_cryptocurrencies"],
                "active_exchanges": data["data"]["active_exchanges"],
                "last_updated": data["data"]["last_updated"],
            }
            
            logger.info("成功獲取CoinMarketCap全球市場數據")
            return result
    
    except httpx.HTTPError as e:
        logger.error(f"獲取CoinMarketCap全球指標數據時HTTP錯誤: {str(e)}")
        raise HTTPException(status_code=500, detail=f"獲取CoinMarketCap數據時發生HTTP錯誤: {str(e)}")
    except Exception as e:
        logger.error(f"獲取CoinMarketCap全球指標數據時發生錯誤: {str(e)}")
        raise HTTPException(status_code=500, detail=f"獲取CoinMarketCap數據時發生錯誤: {str(e)}")

async def get_fear_greed_index() -> Dict[str, Any]:
    """
    從Alternative.me獲取加密貨幣恐懼與貪婪指數
    
    優先使用官方API獲取數據，如果失敗則嘗試網頁抓取和備用來源
    
    返回:
        Dict[str, Any]: 包含恐懼與貪婪指數數據的字典
    """
    try:
        # 定義多個可能的數據源
        sources = [
            # 優先使用Alternative.me官方API
            {
                "type": "api",
                "name": "Alternative.me API",
                "url": "https://api.alternative.me/fng/",
                "headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "application/json"
                }
            },
            # 備用: Alternative.me網頁抓取
            {
                "type": "scrape",
                "name": "Alternative.me Website",
                "url": "https://alternative.me/crypto/fear-and-greed-index/",
                "headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Referer": "https://google.com",
                }
            },
            # 備用: CNN資料
            {
                "type": "api",
                "name": "CNN Fear & Greed",
                "url": "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
                "headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                }
            }
        ]
        
        # 結果值，如果爬取失敗則提供預設值
        fear_greed_value = 0
        classification = "unknown"
        historical_data = {}
        success = False
        error_messages = []
        
        # 1. 嘗試使用Alternative.me官方API
        logger.info("正在使用Alternative.me官方API獲取恐懼與貪婪指數...")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(sources[0]["url"], headers=sources[0]["headers"], params={"limit": "3"})
                response.raise_for_status()
                data = response.json()
                
                # 檢查API響應是否成功
                if "data" in data and len(data["data"]) > 0:
                    # 獲取最新數據
                    current_data = data["data"][0]
                    
                    fear_greed_value = int(current_data.get("value", 0))
                    classification = current_data.get("value_classification", "").lower().replace(" ", "-")
                    logger.info(f"從官方API成功獲取恐懼與貪婪指數: {fear_greed_value} ({classification})")
                    
                    # 獲取歷史數據
                    if len(data["data"]) > 1:
                        historical_data["yesterday"] = int(data["data"][1].get("value", 0))
                    
                    if len(data["data"]) > 2:
                        historical_data["last_week"] = int(data["data"][2].get("value", 0))
                        
                    # 額外請求獲取月度數據 (如果沒有在前面獲取到)
                    if "last_month" not in historical_data:
                        try:
                            month_response = await client.get(sources[0]["url"], headers=sources[0]["headers"], params={"limit": "30"})
                            month_response.raise_for_status()
                            month_data = month_response.json()
                            
                            if "data" in month_data and len(month_data["data"]) >= 30:
                                historical_data["last_month"] = int(month_data["data"][29].get("value", 0))
                        except Exception as e:
                            logger.warning(f"獲取月度歷史數據時出錯: {str(e)}")
                    
                    success = True
                else:
                    error_messages.append("API回應未包含預期的數據結構")
                    logger.warning("Alternative.me API回應未包含預期的數據結構")
        except Exception as e:
            error_messages.append(f"Alternative.me API 獲取失敗: {str(e)}")
            logger.error(f"從Alternative.me API獲取恐懼與貪婪指數失敗: {str(e)}")
        
        # 2. 如果API失敗，嘗試網頁抓取方法
        if not success:
            logger.info("API方法失敗，嘗試從Alternative.me網頁抓取恐懼與貪婪指數...")
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(sources[1]["url"], headers=sources[1]["headers"], follow_redirects=True)
                    response.raise_for_status()
                    html = response.text
                    
                    # 使用BeautifulSoup解析HTML
                    soup = BeautifulSoup(html, 'html.parser')
                    logger.debug(f"成功獲取Alternative.me頁面，HTML長度: {len(html)}字元")
                    
                    # 檢查新網頁結構
                    now_section = soup.find("div", string="Now")
                    if now_section:
                        # 尋找 Now 後面的值
                        greed_section = now_section.find_next("div")
                        if greed_section and greed_section.text.strip():
                            # 找到分類和值
                            classification = greed_section.text.strip().lower()
                            value_section = greed_section.find_next("div")
                            if value_section and value_section.text.strip().isdigit():
                                fear_greed_value = int(value_section.text.strip())
                                success = True
                                logger.info(f"成功從網頁新結構獲取恐懼與貪婪指數值: {fear_greed_value} ({classification})")
                                
                                # 獲取歷史數據
                                historical_sections = {
                                    "Yesterday": "yesterday",
                                    "Last week": "last_week",
                                    "Last month": "last_month"
                                }
                                
                                for label, key in historical_sections.items():
                                    section = soup.find("div", string=label)
                                    if section:
                                        # 跳過分類，直接獲取值
                                        value_div = section.find_next("div")
                                        if value_div:
                                            value_div = value_div.find_next("div")
                                            if value_div and value_div.text.strip().isdigit():
                                                historical_data[key] = int(value_div.text.strip())
                    
                    # 如果新方法失敗，嘗試舊的選擇器
                    if not success:
                        # 嘗試各種選擇器
                        selectors = [
                            '.fng-circle .fng-value',
                            '.fng-value',
                            'div[class*="fng-circle"] div[class*="fng-value"]',
                            'div.fng-circle',
                        ]
                        
                        for selector in selectors:
                            try:
                                fear_greed_element = soup.select_one(selector)
                                if fear_greed_element and fear_greed_element.text:
                                    value_text = fear_greed_element.text.strip()
                                    import re
                                    number_match = re.search(r'\d+', value_text)
                                    if number_match:
                                        fear_greed_value = int(number_match.group())
                                        logger.info(f"成功獲取恐懼與貪婪指數值: {fear_greed_value} (選擇器: {selector})")
                                        success = True
                                        break
                            except Exception as e:
                                logger.warning(f"使用選擇器 {selector} 提取數值時失敗: {str(e)}")
                        
                        # 嘗試從JavaScript變量提取
                        if not success:
                            try:
                                logger.debug("嘗試從JavaScript變量中提取數據...")
                                js_pattern = r'var\s+fng_value\s*=\s*(\d+)'
                                js_match = re.search(js_pattern, html)
                                if js_match:
                                    fear_greed_value = int(js_match.group(1))
                                    logger.info(f"從JavaScript變量成功獲取恐懼與貪婪指數: {fear_greed_value}")
                                    success = True
                            except Exception as e:
                                logger.warning(f"從JavaScript提取恐懼與貪婪指數失敗: {str(e)}")
                        
                        # 如果成功獲取值，嘗試提取分類
                        if success:
                            try:
                                classification_element = soup.select_one('.fng-circle')
                                if classification_element:
                                    classes = classification_element.get('class', [])
                                    classification = next((cls for cls in classes if cls.startswith('fng-') and cls != 'fng-circle' and cls != 'fng-value'), 'unknown')
                                    classification = classification.replace('fng-', '')
                                
                                # 根據值推斷分類
                                if classification == 'unknown':
                                    if fear_greed_value >= 90:
                                        classification = "extreme-greed"
                                    elif fear_greed_value >= 75:
                                        classification = "greed"
                                    elif fear_greed_value >= 55:
                                        classification = "neutral-greed"
                                    elif fear_greed_value >= 45:
                                        classification = "neutral"
                                    elif fear_greed_value >= 25:
                                        classification = "neutral-fear"
                                    elif fear_greed_value >= 10:
                                        classification = "fear"
                                    else:
                                        classification = "extreme-fear"
                            except Exception as e:
                                logger.warning(f"提取恐懼與貪婪指數分類時出錯: {str(e)}")
                            
                            # 嘗試獲取歷史數據 (舊方法)
                            if not historical_data:
                                try:
                                    timeframes = soup.select('.fng-verbiage')
                                    for timeframe in timeframes:
                                        period_text = timeframe.select_one('.gray')
                                        if not period_text:
                                            continue
                                            
                                        period_text_lower = period_text.text.lower()
                                        value_element = timeframe.select_one('.fng-value')
                                        if not value_element:
                                            continue
                                            
                                        try:
                                            value = int(value_element.text.strip())
                                            
                                            if "yesterday" in period_text_lower or "day" in period_text_lower:
                                                historical_data["yesterday"] = value
                                            elif "week" in period_text_lower:
                                                historical_data["last_week"] = value
                                            elif "month" in period_text_lower:
                                                historical_data["last_month"] = value
                                        except (ValueError, AttributeError):
                                            continue
                                except Exception as e:
                                    logger.warning(f"提取恐懼與貪婪指數歷史數據時出錯: {str(e)}")
            
            except Exception as e:
                error_messages.append(f"Alternative.me 網頁抓取失敗: {str(e)}")
                logger.error(f"從Alternative.me網頁抓取恐懼與貪婪指數失敗: {str(e)}")
        
        # 3. 如果前兩個來源都失敗，嘗試CNN的備用資料源
        if not success:
            logger.info("嘗試從CNN獲取恐懼與貪婪指數...")
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(sources[2]["url"], headers=sources[2]["headers"])
                    response.raise_for_status()
                    data = response.json()
                    
                    # 檢查CNN數據格式
                    if data and "fear_and_greed" in data and len(data["fear_and_greed"]) > 0 and "score" in data["fear_and_greed"][-1]:
                        fear_greed_value = int(data["fear_and_greed"][-1]["score"])
                        logger.info(f"從CNN API成功獲取恐懼與貪婪指數值: {fear_greed_value}")
                        
                        # 根據值推斷分類
                        if fear_greed_value >= 80:
                            classification = "extreme-greed"
                        elif fear_greed_value >= 65:
                            classification = "greed"
                        elif fear_greed_value >= 50:
                            classification = "neutral-greed"
                        elif fear_greed_value >= 35:
                            classification = "neutral"
                        elif fear_greed_value >= 20:
                            classification = "neutral-fear"
                        elif fear_greed_value >= 10:
                            classification = "fear"
                        else:
                            classification = "extreme-fear"
                        
                        success = True
                        
                        # 提取歷史數據
                        if len(data["fear_and_greed"]) > 1:
                            historical_data["yesterday"] = int(data["fear_and_greed"][-2]["score"])
                        
                        if len(data["fear_and_greed"]) > 7:
                            historical_data["last_week"] = int(data["fear_and_greed"][-8]["score"])
                            
                        if len(data["fear_and_greed"]) > 30:
                            historical_data["last_month"] = int(data["fear_and_greed"][-31]["score"])
                    else:
                        error_messages.append("CNN API回應未包含預期的數據結構")
                        logger.warning("CNN API回應未包含預期的數據結構")
            except Exception as e:
                error_messages.append(f"CNN 數據提取失敗: {str(e)}")
                logger.error(f"從CNN獲取恐懼與貪婪指數失敗: {str(e)}")
        
        # 4. 如果所有來源都失敗，使用模擬數據
        if not success:
            logger.warning(f"所有來源均獲取恐懼與貪婪指數失敗，使用模擬數據。錯誤: {error_messages}")
            fear_greed_value = 45  # 假設中性值
            classification = "neutral"
            historical_data = {
                "yesterday": 47,
                "last_week": 50,
                "last_month": 40
            }
        
        # 格式化為易讀的分類
        classification_map = {
            "extreme-fear": "極度恐懼",
            "fear": "恐懼",
            "neutral-fear": "偏向恐懼",
            "neutral": "中性",
            "neutral-greed": "偏向貪婪",
            "greed": "貪婪",
            "extreme-greed": "極度貪婪",
            "unknown": "未知"
        }
        readable_classification = classification_map.get(classification, "未知")
        
        # 構建結果
        result = {
            "value": fear_greed_value,
            "classification": classification,
            "readable_classification": readable_classification,
            "timestamp": datetime.now().isoformat(),
            "historical_data": historical_data,
            "source": "alternative.me api" if success and not error_messages else "alternative.me web" if success and "API" in error_messages[0] else "cnn" if success else "simulation"
        }
        
        return result
    
    except Exception as e:
        logger.error(f"獲取恐懼與貪婪指數時發生未捕獲的錯誤: {str(e)}")
        # 返回默認值
        return {
            "value": 50,
            "classification": "neutral",
            "readable_classification": "中性",
            "timestamp": datetime.now().isoformat(),
            "historical_data": {},
            "source": "simulation",
            "error": str(e)
        }

@router.get("/fear-greed-index", response_model=Dict[str, Any])
async def get_fear_and_greed():
    """
    獲取加密貨幣恐懼與貪婪指數
    
    返回當前加密貨幣市場的恐懼與貪婪指數，這是一個市場情緒指標，
    範圍從0（極度恐懼）到100（極度貪婪）。
    
    該指數通過爬取Alternative.me網站獲取，包含當前值、分類和最近的歷史數據。
    
    返回:
        包含恐懼與貪婪指數數據的JSON物件
    """
    try:
        fear_greed_data = await get_fear_greed_index()
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "data": fear_greed_data
        }
    except Exception as e:
        logger.error(f"獲取恐懼與貪婪指數失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=f"獲取恐懼與貪婪指數失敗: {str(e)}")

# 在 PriceCache 類後添加一個新的緩存類
class GlobalMarketDataCache:
    """
    全球市場數據緩存類
    
    用於緩存全球市場數據和恐懼與貪婪指數，減少對外部API的請求頻率。
    提供智能更新機制和緩存時效管理。
    
    主要特點:
    - 支援全球市場數據緩存
    - 支援恐懼與貪婪指數緩存
    - 可設置不同數據類型的緩存時間
    - 提供強制更新機制
    - 自動數據過期檢查
    """
    def __init__(self):
        """初始化全球市場數據緩存"""
        # 主數據存儲
        self.data = {
            "global_metrics": None,
            "fear_greed_index": None
        }
        # 緩存時間設置（秒）
        self.cache_times = {
            "global_metrics": 3600,  # 1小時更新一次全球指標
            "fear_greed_index": 3600 * 3  # 3小時更新一次恐懼貪婪指數
        }
        # 最後更新時間
        self.last_update = {
            "global_metrics": None,
            "fear_greed_index": None
        }
        # 數據更新鎖，防止並發更新
        self.locks = {
            "global_metrics": asyncio.Lock(),
            "fear_greed_index": asyncio.Lock()
        }
        # 更新計數器
        self.update_counts = {
            "global_metrics": 0,
            "fear_greed_index": 0
        }
        # 日誌記錄時間
        self.last_log_time = datetime.now()
        self.log_interval = 3600  # 每小時記錄一次統計
        
    async def get_global_metrics(self, force_update=False) -> Dict[str, Any]:
        """
        獲取全球市場指標數據，如果數據過期或強制更新則重新獲取
        
        參數:
            force_update (bool): 是否強制更新數據，忽略緩存
            
        返回:
            Dict[str, Any]: 全球市場指標數據
        """
        current_time = datetime.now()
        data_type = "global_metrics"
        
        # 檢查是否需要更新數據
        if (force_update or 
            self.data[data_type] is None or 
            self.last_update[data_type] is None or
            (current_time - self.last_update[data_type]).total_seconds() > self.cache_times[data_type]):
            
            # 使用鎖確保同一時間只有一個更新操作
            async with self.locks[data_type]:
                # 再次檢查，避免在等待鎖期間已被其他請求更新
                if (force_update or 
                    self.data[data_type] is None or 
                    self.last_update[data_type] is None or
                    (current_time - self.last_update[data_type]).total_seconds() > self.cache_times[data_type]):
                    
                    try:
                        logger.info("緩存過期或強制更新，正在獲取新的全球市場數據")
                        new_data = await get_coinmarketcap_global_metrics()
                        
                        # 更新緩存
                        self.data[data_type] = new_data
                        self.last_update[data_type] = datetime.now()
                        self.update_counts[data_type] += 1
                        
                        # 記錄統計信息
                        current_time = datetime.now()
                        if (current_time - self.last_log_time).total_seconds() >= self.log_interval:
                            logger.info(f"全球市場數據更新統計: 總更新次數 {self.update_counts[data_type]}")
                            self.last_log_time = current_time
                    
                    except Exception as e:
                        logger.error(f"更新全球市場數據失敗: {str(e)}")
                        # 如果更新失敗但有舊數據，繼續使用舊數據
                        if self.data[data_type] is None:
                            # 如果沒有舊數據，創建一個模擬數據
                            self.data[data_type] = {
                                "total_market_cap_usd": 2500000000000,
                                "total_volume_24h_usd": 150000000000,
                                "bitcoin_dominance": 48.5,
                                "ethereum_dominance": 18.7,
                                "active_cryptocurrencies": 10000,
                                "active_exchanges": 500,
                                "last_updated": datetime.now().isoformat(),
                                "note": "模擬數據 - 更新失敗"
                            }
        
        # 添加緩存信息
        result = self.data[data_type].copy()
        result["cache_info"] = {
            "is_cached": True,
            "last_update": self.last_update[data_type].isoformat() if self.last_update[data_type] else None,
            "cache_time_seconds": self.cache_times[data_type],
            "next_update_in_seconds": max(0, self.cache_times[data_type] - 
                                         (datetime.now() - self.last_update[data_type]).total_seconds()) 
                                     if self.last_update[data_type] else 0
        }
        return result
            
    async def get_fear_greed_index(self, force_update=False) -> Dict[str, Any]:
        """
        獲取恐懼與貪婪指數數據，如果數據過期或強制更新則重新獲取
        
        參數:
            force_update (bool): 是否強制更新數據，忽略緩存
            
        返回:
            Dict[str, Any]: 恐懼與貪婪指數數據
        """
        current_time = datetime.now()
        data_type = "fear_greed_index"
        
        # 檢查是否需要更新數據
        if (force_update or 
            self.data[data_type] is None or 
            self.last_update[data_type] is None or
            (current_time - self.last_update[data_type]).total_seconds() > self.cache_times[data_type]):
            
            # 使用鎖確保同一時間只有一個更新操作
            async with self.locks[data_type]:
                # 再次檢查，避免在等待鎖期間已被其他請求更新
                if (force_update or 
                    self.data[data_type] is None or 
                    self.last_update[data_type] is None or
                    (current_time - self.last_update[data_type]).total_seconds() > self.cache_times[data_type]):
                    
                    try:
                        logger.info("緩存過期或強制更新，正在獲取新的恐懼與貪婪指數")
                        new_data = await get_fear_greed_index()
                        
                        # 更新緩存
                        self.data[data_type] = new_data
                        self.last_update[data_type] = datetime.now()
                        self.update_counts[data_type] += 1
                        
                        # 記錄統計信息
                        current_time = datetime.now()
                        if (current_time - self.last_log_time).total_seconds() >= self.log_interval:
                            logger.info(f"恐懼與貪婪指數更新統計: 總更新次數 {self.update_counts[data_type]}")
                            self.last_log_time = current_time
                    
                    except Exception as e:
                        logger.error(f"更新恐懼與貪婪指數失敗: {str(e)}")
                        # 如果更新失敗但有舊數據，繼續使用舊數據
                        if self.data[data_type] is None:
                            # 如果沒有舊數據，創建一個模擬數據
                            self.data[data_type] = {
                                "value": 50,
                                "classification": "neutral",
                                "readable_classification": "中性",
                                "timestamp": datetime.now().isoformat(),
                                "source": "simulation",
                                "note": "模擬數據 - 更新失敗"
                            }
        
        # 添加緩存信息
        result = self.data[data_type].copy()
        result["cache_info"] = {
            "is_cached": True,
            "last_update": self.last_update[data_type].isoformat() if self.last_update[data_type] else None,
            "cache_time_seconds": self.cache_times[data_type],
            "next_update_in_seconds": max(0, self.cache_times[data_type] - 
                                         (datetime.now() - self.last_update[data_type]).total_seconds())
                                     if self.last_update[data_type] else 0
        }
        return result

# 初始化全球市場數據緩存
global_market_cache = GlobalMarketDataCache()

@router.get("/diagnostic", response_model=Dict[str, Any])
async def diagnostic_check(
    exchange: str = Query("binance", description="交易所名稱")
):
    """
    診斷檢查交易所連接和數據流
    
    此端點執行詳細的連接診斷，包括:
    1. DNS 解析檢查
    2. WebSocket 連接測試
    3. REST API 連接測試
    
    結果包含每一步的成功/失敗狀態和診斷建議。
    """
    logger.info(f"執行診斷檢查: {exchange}")
    results = {
        "timestamp": datetime.now().isoformat(),
        "exchange": exchange,
        "tests": {},
        "market_data_service": {},
        "direct_connection": {},
        "suggestions": []
    }
    
    # 1. 檢查 market_data_service 狀態
    try:
        from app.services.market_data import market_data_service
        results["market_data_service"] = {
            "initialized": exchange in market_data_service.exchanges,
            "exchange_count": len(market_data_service.exchanges)
        }
        
        if exchange in market_data_service.exchanges:
            exchange_obj = market_data_service.exchanges[exchange]
            # 檢查連接狀態
            ws_connections = {
                market_type: (ws is not None and hasattr(ws, 'open') and ws.open) 
                for market_type, ws in exchange_obj.ws_connections.items()
            }
            results["market_data_service"]["ws_connections"] = ws_connections
            results["market_data_service"]["is_running"] = exchange_obj.is_running
            
            # 檢查數據
            data_counts = {
                market_type: len(data)
                for market_type, data in exchange_obj.market_data.items()
            }
            results["market_data_service"]["data_counts"] = data_counts
            
            # 如果沒有連接，則嘗試啟動
            if not any(ws_connections.values()):
                logger.info(f"診斷檢測到 {exchange} 未連接，嘗試啟動連接...")
                try:
                    connection_result = await market_data_service.start()
                    results["market_data_service"]["connection_attempt"] = {
                        "success": bool(connection_result),
                        "active_exchanges": connection_result
                    }
                except Exception as e:
                    results["market_data_service"]["connection_attempt"] = {
                        "success": False,
                        "error": str(e)
                    }
    except Exception as e:
        results["market_data_service"] = {
            "error": str(e)
        }
        results["suggestions"].append("市場數據服務導入或初始化存在問題")
    
    # 2. 嘗試直接連接測試
    try:
        from app.core.exchanges.binance import BinanceExchange
        logger.info("診斷: 創建新的 BinanceExchange 實例進行測試")
        
        # 創建新實例
        test_exchange = BinanceExchange()
        results["direct_connection"]["instance_created"] = True
        
        # 嘗試連接
        logger.info("診斷: 嘗試直接連接到交易所")
        try:
            connect_result = await test_exchange.connect()
            results["direct_connection"]["connection_success"] = connect_result
            
            if connect_result:
                # 等待短時間以接收一些數據
                logger.info("診斷: 連接成功，等待3秒接收數據")
                await asyncio.sleep(3)
                
                # 檢查是否有活躍連接
                ws_connections = {
                    market_type: (ws is not None and hasattr(ws, 'open') and ws.open) 
                    for market_type, ws in test_exchange.ws_connections.items()
                }
                results["direct_connection"]["ws_connections"] = ws_connections
                
                # 檢查是否有數據
                data_counts = {
                    market_type: len(data)
                    for market_type, data in test_exchange.market_data.items()
                }
                results["direct_connection"]["data_counts"] = data_counts
                
                # 取得樣本數據
                sample_data = {}
                for market_type, data in test_exchange.market_data.items():
                    if data:
                        symbols = list(data.keys())[:3]  # 取前3個交易對
                        sample_data[market_type] = {
                            symbol: {"price": data[symbol].get("price", "N/A")}
                            for symbol in symbols
                        }
                results["direct_connection"]["sample_data"] = sample_data
                
                # 關閉測試連接
                logger.info("診斷: 測試完成，關閉連接")
                await test_exchange.disconnect()
                results["direct_connection"]["disconnected"] = True
            else:
                results["suggestions"].append("直接連接失敗，可能是網絡問題或API端點不可用")
        except Exception as e:
            results["direct_connection"]["connection_error"] = str(e)
            results["suggestions"].append(f"連接過程發生錯誤: {str(e)}")
    except Exception as e:
        results["direct_connection"]["error"] = str(e)
        results["suggestions"].append("無法創建交易所實例")
    
    # 3. DNS 解析檢查
    try:
        import socket
        for ws_type in ["spot", "futures"]:
            try:
                if exchange == "binance":
                    if ws_type == "spot":
                        host = "stream.binance.com"
                    else:
                        host = "fstream.binance.com"
                    
                    ip = socket.gethostbyname(host)
                    results["tests"][f"dns_{ws_type}"] = {
                        "success": True,
                        "host": host,
                        "ip": ip
                    }
                    logger.info(f"DNS解析成功: {host} -> {ip}")
            except Exception as e:
                results["tests"][f"dns_{ws_type}"] = {
                    "success": False,
                    "error": str(e)
                }
                results["suggestions"].append(f"DNS解析 {ws_type} 失敗，檢查網絡連接")
    except Exception as e:
        results["tests"]["dns"] = {
            "success": False,
            "error": str(e)
        }
    
    # 4. HTTP連接檢查
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if exchange == "binance":
                url = "https://api.binance.com/api/v3/ping"
                response = await client.get(url)
                results["tests"]["http"] = {
                    "success": response.status_code == 200,
                    "status_code": response.status_code,
                    "url": url
                }
                logger.info(f"HTTP連接測試: {url} -> {response.status_code}")
    except Exception as e:
        results["tests"]["http"] = {
            "success": False,
            "error": str(e)
        }
        results["suggestions"].append("HTTP連接失敗，可能是網絡問題")
    
    # 添加總結建議
    if not results["suggestions"]:
        if results.get("direct_connection", {}).get("connection_success"):
            results["suggestions"].append("診斷顯示直接連接成功，但應用啟動時可能有問題。檢查啟動事件處理函數。")
        else:
            results["suggestions"].append("未檢測到明確問題，但連接仍然失敗。可能是網絡環境或代理設置問題。")
    
    logger.info(f"診斷檢查完成: {exchange}, 結果: {json.dumps(results, default=str)}")
    return results