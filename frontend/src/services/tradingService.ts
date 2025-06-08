import { api } from '@/utils/api';

/**
 * 交易服務 - 提供交易相關功能
 * 用於處理與交易所交互的操作
 */
export const tradingService = {
  /**
   * 預熱 CCXT 連接
   * 在用戶登入後調用此方法，預先初始化 CCXT 連接，以減少首次交易操作的延遲
   * @param {string} exchange 交易所名稱 (binance, okx, bybit, gate, mexc)
   * @returns {Promise<{success: boolean, message: string, data: any}>} 預熱結果
   */
  async preheatExchangeConnection(exchange: string = 'binance') {
    console.log(`[TradingService] 開始預熱 ${exchange} CCXT 連接`);
    
    try {
      // 嘗試不同的 API 路徑
      let response;
      try {
        // 首先嘗試原始路徑
        response = await api.post('/trading/preheat', {
          exchange: exchange.toLowerCase()
        });
      } catch (err: any) {
        if (err.response?.status === 404) {
          console.log(`[TradingService] 路徑 '/trading/preheat' 不存在，嘗試替代路徑`);
          
          // 嘗試其他可能的路徑
          try {
            response = await api.post('/api/trading/preheat', {
              exchange: exchange.toLowerCase()
            });
          } catch (err2: any) {
            if (err2.response?.status === 404) {
              console.log(`[TradingService] 路徑 '/api/trading/preheat' 不存在，嘗試最後一個路徑`);
              
              // 最後嘗試完整路徑
              response = await api.post('/api/v1/trading/preheat', {
                exchange: exchange.toLowerCase()
              });
            } else {
              throw err2;
            }
          }
        } else {
          throw err;
        }
      }
      
      console.log(`[TradingService] ${exchange} CCXT 預熱結果:`, response.data);
      
      return {
        success: true,
        message: `成功預熱 ${exchange} 連接`,
        data: response.data
      };
    } catch (error: any) {
      console.error(`[TradingService] 預熱 ${exchange} CCXT 連接失敗:`, error);
      return {
        success: false,
        message: `預熱 ${exchange} 連接失敗: ${error instanceof Error ? error.message : '未知錯誤'}`,
        data: null
      };
    }
  },
  
  /**
   * 預熱多個交易所的 CCXT 連接
   * @param {string[]} exchanges 交易所名稱列表
   * @returns {Promise<{success: boolean, message: string, results: Record<string, any>}>} 預熱結果
   */
  async preheatMultipleExchanges(exchanges: string[] = ['binance']) {
    console.log(`[TradingService] 開始預熱多個交易所 CCXT 連接: ${exchanges.join(', ')}`);
    
    const results: Record<string, any> = {};
    let allSuccess = true;
    
    for (const exchange of exchanges) {
      try {
        const result = await this.preheatExchangeConnection(exchange);
        results[exchange] = result;
        
        if (!result.success) {
          allSuccess = false;
        }
      } catch (error) {
        console.error(`[TradingService] 預熱 ${exchange} 連接時發生錯誤:`, error);
        results[exchange] = {
          success: false,
          message: `預熱失敗: ${error instanceof Error ? error.message : '未知錯誤'}`,
          data: null
        };
        allSuccess = false;
      }
    }
    
    return {
      success: allSuccess,
      message: allSuccess ? '所有交易所連接預熱成功' : '部分交易所連接預熱失敗',
      results
    };
  },
  
  /**
   * 獲取賬戶資產信息
   * @param {string} exchange 交易所名稱
   * @returns {Promise<any>} 賬戶資產信息
   */
  async getAccountInfo(exchange: string) {
    try {
      const response = await api.get(`/trading/account/${exchange}`);
      return response.data;
    } catch (error) {
      console.error(`[TradingService] 獲取 ${exchange} 賬戶資產信息失敗:`, error);
      throw error;
    }
  },
  
  /**
   * 獲取特定資產餘額
   * @param {string} exchange 交易所名稱
   * @param {string} asset 資產名稱 (例如: BTC, USDT)
   * @returns {Promise<any>} 資產餘額信息
   */
  async getAssetBalance(exchange: string, asset: string) {
    try {
      const response = await api.get(`/trading/balance/${exchange}/${asset}`);
      return response.data;
    } catch (error) {
      console.error(`[TradingService] 獲取 ${exchange} ${asset} 餘額失敗:`, error);
      throw error;
    }
  },
  
  /**
   * 獲取交易對信息
   * @param {string} exchange 交易所名稱
   * @param {string} [symbol] 交易對名稱 (可選)
   * @returns {Promise<any>} 交易對信息
   */
  async getSymbolInfo(exchange: string, symbol?: string) {
    try {
      const url = symbol 
        ? `/trading/symbols/${exchange}?symbol=${encodeURIComponent(symbol)}`
        : `/trading/symbols/${exchange}`;
      
      const response = await api.get(url);
      return response.data;
    } catch (error) {
      console.error(`[TradingService] 獲取 ${exchange} 交易對信息失敗:`, error);
      throw error;
    }
  }
}; 