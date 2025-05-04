import logging
from typing import Dict, Any, List, Optional
from app.core.exchanges.base import ExchangeBase
from app.core.exchanges.binance import BinanceExchange

# 初始化日誌記錄器，用於記錄市場數據服務的運行情況
logger = logging.getLogger(__name__)

class MarketDataService:
    """
    市場數據服務
    
    負責管理和協調所有交易所的市場數據，提供統一的數據存取介面。
    該服務作為系統與各交易所之間的中介層，簡化了多交易所數據的處理流程。
    支援即時行情訂閱、市場數據查詢等功能。
    """
    
    def __init__(self):
        """
        初始化市場數據服務
        
        建立交易所字典，用於存儲和管理各個交易所的實例。
        呼叫初始化方法設置支援的交易所。
        """
        self.exchanges: Dict[str, ExchangeBase] = {}  # 交易所字典，鍵為交易所名稱，值為交易所實例
        self._initialize_exchanges()  # 初始化支援的交易所
        
    def _initialize_exchanges(self):
        """
        初始化支援的交易所
        
        目前支援的交易所包括：
        1. 幣安（Binance）- 全球領先的加密貨幣交易所
        
        此方法在服務實例化時自動呼叫，也可手動呼叫以重新初始化交易所連接。
        異常處理機制確保單個交易所初始化失敗不會影響整個服務。
        """
        try:
            # 創建並添加幣安交易所實例
            binance = BinanceExchange()
            self.exchanges["binance"] = binance
            logger.info("已初始化支持的交易所")
        except Exception as e:
            # 記錄初始化過程中的錯誤
            logger.error(f"初始化交易所時出錯: {str(e)}")
            
    async def start(self):
        """
        啟動所有交易所的數據服務
        
        為每個已初始化的交易所建立WebSocket連接，開始接收市場數據。
        此方法應在應用程式啟動時呼叫，通常在FastAPI的啟動事件中執行。
        
        注意：
            連接過程是非同步的，需要使用await關鍵字調用。
            連接後會自動訂閱市場數據流，無需額外訂閱操作。
        """
        for name, exchange in self.exchanges.items():
            try:
                # 建立WebSocket連接 - BinanceExchange的connect方法已包含市場類型的訂閱邏輯
                await exchange.connect()
                # 不需要在此重複訂閱市場類型
                # for market_type in ["spot", "futures"]:
                #     await exchange.subscribe_market_type(market_type)
                logger.info(f"已啟動{name}交易所的數據服務")
            except Exception as e:
                # 記錄啟動過程中的錯誤
                logger.error(f"啟動{name}交易所數據服務時出錯: {str(e)}")
                
    async def stop(self):
        """
        停止所有交易所的數據服務
        
        關閉所有活動的WebSocket連接，釋放相關資源。
        此方法應在應用程式關閉時呼叫，通常在FastAPI的關閉事件中執行。
        
        注意：
            關閉過程是非同步的，需要使用await關鍵字調用。
            確保在應用終止前正確關閉連接，避免資源洩漏。
        """
        for name, exchange in self.exchanges.items():
            try:
                # 斷開WebSocket連接
                await exchange.disconnect()
                logger.info(f"已停止{name}交易所的數據服務")
            except Exception as e:
                # 記錄停止過程中的錯誤
                logger.error(f"停止{name}交易所數據服務時出錯: {str(e)}")
                
    def get_all_tickers(self, exchange: str = "binance", market_type: str = "spot") -> Dict[str, Any]:
        """
        獲取指定交易所的所有交易對行情
        
        從指定交易所獲取指定市場類型的所有交易對最新行情數據。
        
        參數:
            exchange: 交易所名稱，預設為 "binance"
            market_type: 市場類型，可選 "spot"（現貨）或 "futures"（期貨），預設為 "spot"
            
        返回:
            包含所有交易對行情的字典，格式為 {交易對: 行情數據}
            若交易所不存在或發生錯誤，則返回空字典
        """
        try:
            if exchange in self.exchanges:
                return self.exchanges[exchange].get_all_tickers(market_type)
            return {}
        except Exception as e:
            # 記錄獲取行情時的錯誤
            logger.error(f"獲取{exchange}交易所{market_type}市場全部行情時出錯: {str(e)}")
            return {}
            
    def get_ticker(self, symbol: str, exchange: str = "binance", market_type: str = "spot") -> Optional[Dict[str, Any]]:
        """
        獲取指定交易對的行情
        
        從指定交易所獲取特定交易對的最新行情數據。
        
        參數:
            symbol: 交易對名稱，例如 "BTCUSDT"
            exchange: 交易所名稱，預設為 "binance"
            market_type: 市場類型，可選 "spot"（現貨）或 "futures"（期貨），預設為 "spot"
            
        返回:
            交易對行情數據的字典
            若交易所不存在、交易對不存在或發生錯誤，則返回None
        """
        try:
            if exchange in self.exchanges:
                return self.exchanges[exchange].get_ticker(symbol, market_type)
            return None
        except Exception as e:
            # 記錄獲取行情時的錯誤
            logger.error(f"獲取{exchange}交易所{market_type}市場{symbol}行情時出錯: {str(e)}")
            return None
            
    def get_24h_ticker(self, symbol: str, exchange: str = "binance", market_type: str = "spot") -> Optional[Dict[str, Any]]:
        """
        獲取指定交易對的24小時行情數據
        
        從指定交易所獲取特定交易對的24小時統計數據，包括成交量、價格變化等。
        
        參數:
            symbol: 交易對名稱，例如 "BTCUSDT"
            exchange: 交易所名稱，預設為 "binance"
            market_type: 市場類型，可選 "spot"（現貨）或 "futures"（期貨），預設為 "spot"
            
        返回:
            交易對24小時行情數據的字典
            若交易所不存在、交易對不存在或發生錯誤，則返回None
        """
        try:
            if exchange in self.exchanges:
                return self.exchanges[exchange].get_24h_ticker(symbol, market_type)
            return None
        except Exception as e:
            # 記錄獲取行情時的錯誤
            logger.error(f"獲取{exchange}交易所{market_type}市場{symbol} 24小時行情時出錯: {str(e)}")
            return None
            
    async def subscribe_symbols(self, symbols: List[str], exchange: str = "binance", market_type: str = "spot") -> bool:
        """
        訂閱特定交易對的即時行情
        
        向指定交易所訂閱一組交易對的即時行情數據流。
        
        參數:
            symbols: 要訂閱的交易對列表，例如 ["BTCUSDT", "ETHUSDT"]
            exchange: 交易所名稱，預設為 "binance"
            market_type: 市場類型，可選 "spot"（現貨）或 "futures"（期貨），預設為 "spot"
            
        返回:
            訂閱成功返回True，失敗返回False
            若交易所不存在或發生錯誤，則返回False
        """
        try:
            if exchange in self.exchanges:
                return await self.exchanges[exchange].subscribe_symbols(symbols, market_type)
            return False
        except Exception as e:
            # 記錄訂閱時的錯誤
            logger.error(f"訂閱{exchange}交易所{market_type}市場交易對時出錯: {str(e)}")
            return False
            
    async def unsubscribe_symbols(self, symbols: List[str], exchange: str = "binance", market_type: str = "spot") -> bool:
        """
        取消訂閱特定交易對的即時行情
        
        取消向指定交易所訂閱的一組交易對即時行情數據流。
        
        參數:
            symbols: 要取消訂閱的交易對列表，例如 ["BTCUSDT", "ETHUSDT"]
            exchange: 交易所名稱，預設為 "binance"
            market_type: 市場類型，可選 "spot"（現貨）或 "futures"（期貨），預設為 "spot"
            
        返回:
            取消訂閱成功返回True，失敗返回False
            若交易所不存在或發生錯誤，則返回False
        """
        try:
            if exchange in self.exchanges:
                return await self.exchanges[exchange].unsubscribe_symbols(symbols, market_type)
            return False
        except Exception as e:
            # 記錄取消訂閱時的錯誤
            logger.error(f"取消訂閱{exchange}交易所{market_type}市場交易對時出錯: {str(e)}")
            return False
            
    def get_exchange(self, exchange: str) -> Optional[ExchangeBase]:
        """
        獲取指定交易所實例
        
        根據交易所名稱獲取對應的交易所實例。
        
        參數:
            exchange: 交易所名稱，例如 "binance"
            
        返回:
            交易所實例，若交易所不存在則返回None
        """
        return self.exchanges.get(exchange)
        
    def get_supported_exchanges(self) -> List[str]:
        """
        獲取支援的交易所列表
        
        返回當前服務支援的所有交易所名稱列表。
        
        返回:
            交易所名稱列表，例如 ["binance"]
        """
        return list(self.exchanges.keys())

# 創建全局市場數據服務實例
# 該實例可被應用中的其他模組導入和使用，作為市場數據的中央存取點
market_data_service = MarketDataService() 