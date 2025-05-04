from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime

class ExchangeBase(ABC):
    """
    交易所基類，定義所有交易所必須實現的介面
    
    此抽象基類提供了所有加密貨幣交易所共同功能的統一介面，
    包括市場數據獲取、WebSocket連接管理和交易對訂閱等功能。
    任何新增的交易所實現都應繼承此類並實現所有抽象方法。
    """
    
    def __init__(self, name: str):
        """
        初始化交易所基類
        
        參數:
            name: 交易所名稱，如 'binance', 'okx' 等
        """
        self.name = name
        self.ws_endpoints = {
            "spot": "",      # 現貨市場WebSocket端點
            "futures": ""    # 期貨市場WebSocket端點
        }
        self.rest_endpoints = {
            "spot": "",      # 現貨市場REST API端點
            "futures": ""    # 期貨市場REST API端點
        }
        
    @abstractmethod
    async def connect(self) -> bool:
        """
        建立WebSocket連接
        
        連接到交易所的WebSocket服務，用於接收實時市場數據。
        
        返回:
            連接成功返回True，否則返回False
        """
        pass
        
    @abstractmethod
    async def disconnect(self) -> bool:
        """
        斷開WebSocket連接
        
        安全地關閉與交易所的WebSocket連接，釋放相關資源。
        
        返回:
            斷開連接成功返回True，否則返回False
        """
        pass
        
    @abstractmethod
    async def subscribe_market_type(self, market_type: str) -> bool:
        """
        訂閱特定市場類型的所有交易對
        
        一次性訂閱指定市場類型（現貨或期貨）的所有交易對行情數據。
        
        參數:
            market_type: 市場類型，'spot'（現貨）或'futures'（期貨）
            
        返回:
            訂閱成功返回True，否則返回False
        """
        pass
        
    @abstractmethod
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
        pass
        
    @abstractmethod
    async def unsubscribe_symbols(self, symbols: List[str], market_type: str) -> bool:
        """
        取消訂閱特定交易對
        
        停止接收指定交易對的實時行情數據。
        
        參數:
            symbols: 要取消訂閱的交易對列表
            market_type: 市場類型，'spot'（現貨）或'futures'（期貨）
            
        返回:
            取消訂閱成功返回True，否則返回False
        """
        pass
        
    @abstractmethod
    def get_all_tickers(self, market_type: str) -> Dict[str, Any]:
        """
        獲取所有交易對的最新行情
        
        返回指定市場類型下所有交易對的最新價格和其他行情數據。
        
        參數:
            market_type: 市場類型，'spot'（現貨）或'futures'（期貨）
            
        返回:
            包含所有交易對行情數據的字典，格式為 {交易對: 行情數據}
        """
        pass
        
    @abstractmethod
    def get_ticker(self, symbol: str, market_type: str) -> Optional[Dict[str, Any]]:
        """
        獲取單個交易對的最新行情
        
        返回指定交易對的最新價格和其他行情數據。
        
        參數:
            symbol: 交易對名稱，如 'BTCUSDT'
            market_type: 市場類型，'spot'（現貨）或'futures'（期貨）
            
        返回:
            交易對行情數據字典，若交易對不存在則返回None
        """
        pass
        
    @abstractmethod
    def get_24h_ticker(self, symbol: str, market_type: str) -> Optional[Dict[str, Any]]:
        """
        獲取24小時行情數據
        
        返回指定交易對的24小時統計數據，包括成交量、價格變化等。
        
        參數:
            symbol: 交易對名稱，如 'BTCUSDT'
            market_type: 市場類型，'spot'（現貨）或'futures'（期貨）
            
        返回:
            交易對24小時行情數據字典，若交易對不存在則返回None
        """
        pass
        
    @abstractmethod
    def format_ticker_data(self, raw_data: Dict[str, Any], market_type: str) -> Dict[str, Any]:
        """
        格式化行情數據為統一格式
        
        將各交易所的原始行情數據轉換為系統內部統一的數據格式，
        確保不同交易所的數據在系統內部有一致的結構。
        
        參數:
            raw_data: 原始行情數據
            market_type: 市場類型，'spot'（現貨）或'futures'（期貨）
            
        返回:
            標準化格式的行情數據字典
        """
        pass
        
    def get_endpoint(self, market_type: str, endpoint_type: str = "ws") -> str:
        """
        獲取指定類型的端點
        
        根據市場類型和端點類型返回相應的API端點URL。
        
        參數:
            market_type: 市場類型，'spot'（現貨）或'futures'（期貨）
            endpoint_type: 端點類型，'ws'（WebSocket）或'rest'（REST API）
            
        返回:
            端點URL字符串
        """
        if endpoint_type == "ws":
            return self.ws_endpoints.get(market_type, "")
        return self.rest_endpoints.get(market_type, "")
        
    def normalize_symbol(self, symbol: str) -> str:
        """
        標準化交易對格式
        
        將交易對轉換為大寫格式，確保系統內部處理的一致性。
        
        參數:
            symbol: 原始交易對名稱
            
        返回:
            標準化後的交易對名稱
        """
        return symbol.upper()
        
    def get_timestamp(self) -> str:
        """
        獲取當前時間戳
        
        返回ISO格式的當前時間字符串，用於日誌記錄和數據標記。
        
        返回:
            ISO格式的當前時間字符串
        """
        return datetime.now().isoformat() 