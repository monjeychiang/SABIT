import logging
from typing import Dict, Any, List, Optional
from app.core.exchanges.base import ExchangeBase
from app.core.exchanges.binance import BinanceExchange

# 导入Cython优化模块
try:
    from ..cython_modules import calculate_indicators, CYTHON_ENABLED
    import logging
    logging.info("使用Cython加速版技術指標計算函數")
except ImportError:
    # 如果导入失败，使用原生Python版本
    CYTHON_ENABLED = False
    logging.warning("Cython模块导入失败，使用Python原生实现")
    import numpy as np

# 初始化日誌記錄器，用於記錄市場數據服務的運行情況
logger = logging.getLogger(__name__)
# 設置日誌級別為INFO，保留重要訊息
logger.setLevel(logging.INFO)

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
        # 簡化的開始日誌記錄
        logger.info("市場數據服務啟動中")
        logger.info(f"已初始化的交易所數量: {len(self.exchanges)}")
        
        # 檢查是否有初始化的交易所
        if not self.exchanges:
            logger.warning("沒有初始化任何交易所，市場數據服務啟動完成但無可用數據源")
            return
            
        # 單獨處理每個交易所，防止一個錯誤影響其他交易所
        active_exchanges = []
        for name, exchange in self.exchanges.items():
            try:
                # 簡化日誌輸出
                logger.info(f"正在啟動 {name} 交易所連接")
                
                # 嘗試連接交易所
                connect_result = await exchange.connect()
                
                if connect_result:
                    logger.info(f"{name} 交易所連接成功")
                    active_exchanges.append(name)
                else:
                    logger.error(f"{name} 交易所連接失敗")
            except Exception as e:
                # 記錄啟動過程中的錯誤，但不輸出完整堆疊跟踪，減少日誌量
                logger.error(f"啟動 {name} 交易所數據服務時出錯: {str(e)}")
        
        # 簡化完成日誌
        logger.info(f"市場數據服務啟動完成，活躍交易所: {', '.join(active_exchanges) if active_exchanges else '無'}")
        return active_exchanges
        
    async def stop(self):
        """
        停止所有交易所的數據服務
        
        關閉所有活動的WebSocket連接，釋放相關資源。
        此方法應在應用程式關閉時呼叫，通常在FastAPI的關閉事件中執行。
        
        注意：
            關閉過程是非同步的，需要使用await關鍵字調用。
            確保在應用終止前正確關閉連接，避免資源洩漏。
        """
        logger.info("正在停止市場數據服務")
        for name, exchange in self.exchanges.items():
            try:
                # 斷開WebSocket連接
                await exchange.disconnect()
                logger.info(f"{name}交易所連接已關閉")
            except Exception as e:
                # 記錄停止過程中的錯誤
                logger.error(f"停止{name}交易所數據服務時出錯: {str(e)}")
        logger.info("市場數據服務已停止")
                
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
            
    def calculate_technical_indicators(self, 
                                     ohlcv_data: Dict[str, List[float]], 
                                     indicators: List[str] = None) -> Dict[str, Any]:
        """
        计算技术指标
        
        计算给定OHLCV数据的各种技术指标，包括均线、RSI、布林带等
        
        参数:
            ohlcv_data: 包含OHLCV数据的字典
            indicators: 要计算的指标列表
            
        返回:
            Dict[str, Any]: 包含各指标计算结果的字典
        """
        # 如果没有指定指标，默认计算常用指标
        if indicators is None:
            indicators = ['sma', 'ema', 'rsi', 'bollinger', 'macd']
            
        # 使用Cython加速版本（如果可用）
        if CYTHON_ENABLED:
            return calculate_indicators(ohlcv_data, indicators)
            
        # 否则使用原生Python实现
        result = {}
        
        # 确保数据正确转换为NumPy数组
        closes = np.array(ohlcv_data.get('close', []), dtype=np.float64)
        
        # 计算所需指标
        for indicator in indicators:
            if indicator.lower() == 'sma':
                result['sma'] = {
                    '5': self._calculate_sma(closes, 5),
                    '10': self._calculate_sma(closes, 10),
                    '20': self._calculate_sma(closes, 20),
                    '50': self._calculate_sma(closes, 50),
                    '200': self._calculate_sma(closes, 200)
                }
            elif indicator.lower() == 'ema':
                result['ema'] = {
                    '5': self._calculate_ema(closes, 5),
                    '10': self._calculate_ema(closes, 10),
                    '20': self._calculate_ema(closes, 20),
                    '50': self._calculate_ema(closes, 50),
                    '200': self._calculate_ema(closes, 200)
                }
            elif indicator.lower() == 'rsi':
                result['rsi'] = {
                    '14': self._calculate_rsi(closes, 14)
                }
            elif indicator.lower() == 'bollinger':
                upper, middle, lower = self._calculate_bollinger_bands(closes, 20, 2.0)
                result['bollinger'] = {
                    'upper': upper,
                    'middle': middle,
                    'lower': lower
                }
            elif indicator.lower() == 'macd':
                macd_line, signal_line, histogram = self._calculate_macd(closes, 12, 26, 9)
                result['macd'] = {
                    'macd': macd_line,
                    'signal': signal_line,
                    'histogram': histogram
                }
        
        return result
    
    def _calculate_sma(self, data, period):
        """简单移动平均线计算"""
        n = len(data)
        result = np.zeros(n)
        result[:period-1] = np.nan
        
        # 使用滑动窗口计算
        for i in range(period-1, n):
            result[i] = np.mean(data[i-period+1:i+1])
            
        return result
    
    def _calculate_ema(self, data, period):
        """指数移动平均线计算"""
        n = len(data)
        result = np.zeros(n)
        alpha = 2.0 / (period + 1.0)
        
        # 前period-1个点设为NaN
        result[:period-1] = np.nan
        
        # 计算第一个EMA值
        result[period-1] = np.mean(data[:period])
        
        # 计算其余EMA值
        for i in range(period, n):
            result[i] = data[i] * alpha + result[i-1] * (1.0 - alpha)
            
        return result
    
    def _calculate_rsi(self, data, period):
        """相对强弱指标计算"""
        n = len(data)
        result = np.zeros(n)
        delta = np.zeros(n)
        
        # 计算价格变化
        for i in range(1, n):
            delta[i] = data[i] - data[i-1]
        
        # 分离涨跌
        gain = np.zeros(n)
        loss = np.zeros(n)
        
        for i in range(1, n):
            if delta[i] > 0:
                gain[i] = delta[i]
            elif delta[i] < 0:
                loss[i] = -delta[i]
        
        # 计算平均涨幅和跌幅
        avg_gain = np.zeros(n)
        avg_loss = np.zeros(n)
        
        # 计算第一个值
        avg_gain[period] = np.sum(gain[1:period+1]) / period
        avg_loss[period] = np.sum(loss[1:period+1]) / period
        
        # 计算其余值
        for i in range(period+1, n):
            avg_gain[i] = (avg_gain[i-1] * (period-1) + gain[i]) / period
            avg_loss[i] = (avg_loss[i-1] * (period-1) + loss[i]) / period
        
        # 计算相对强度
        rs = np.zeros(n)
        for i in range(period, n):
            if avg_loss[i] == 0:
                result[i] = 100
            else:
                rs[i] = avg_gain[i] / avg_loss[i]
                result[i] = 100 - (100 / (1 + rs[i]))
        
        # 前期值设为NaN
        result[:period] = np.nan
        
        return result
    
    def _calculate_bollinger_bands(self, data, period=20, deviation=2.0):
        """布林带计算"""
        # 计算中轨(SMA)
        middle = self._calculate_sma(data, period)
        
        # 计算标准差
        std = np.zeros(len(data))
        for i in range(period-1, len(data)):
            window = data[i-period+1:i+1]
            std[i] = np.std(window)
        
        # 计算上轨和下轨
        upper = middle + deviation * std
        lower = middle - deviation * std
        
        return upper, middle, lower
    
    def _calculate_macd(self, data, fast_period=12, slow_period=26, signal_period=9):
        """MACD计算"""
        # 计算快线和慢线
        fast_ema = self._calculate_ema(data, fast_period)
        slow_ema = self._calculate_ema(data, slow_period)
        
        # 计算MACD线
        macd_line = fast_ema - slow_ema
        
        # 计算信号线
        signal_line = self._calculate_ema(macd_line, signal_period)
        
        # 计算直方图
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    def get_exchange(self, exchange: str) -> Optional[ExchangeBase]:
        """
        獲取指定交易所實例
        
        參數:
            exchange: 交易所名稱
            
        返回:
            ExchangeBase: 交易所實例，若不存在則返回None
        """
        return self.exchanges.get(exchange.lower())
    
    def get_supported_exchanges(self) -> List[str]:
        """
        獲取所有支援的交易所列表
        
        返回:
            List[str]: 交易所名稱列表
        """
        return list(self.exchanges.keys())

# 創建全局市場數據服務實例
# 該實例可被應用中的其他模組導入和使用，作為市場數據的中央存取點
market_data_service = MarketDataService() 