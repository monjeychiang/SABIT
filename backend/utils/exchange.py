from typing import Dict, Any
import ccxt.async_support as ccxt
from backend.app.schemas.trading import ExchangeEnum

async def get_exchange_client(exchange: ExchangeEnum, api_key: str, api_secret: str) -> ccxt.Exchange:
    """
    獲取交易所客戶端實例
    
    注意：CCXT 庫僅支持 HMAC-SHA256 密鑰格式，不支持 Ed25519 密鑰。
    請確保提供的 api_key 和 api_secret 是 HMAC-SHA256 格式的密鑰。
    
    Args:
        exchange: 交易所枚舉
        api_key: API Key (HMAC-SHA256 格式)
        api_secret: API Secret (HMAC-SHA256 格式)
    
    Returns:
        ccxt.Exchange: 交易所客戶端實例
    
    Raises:
        ValueError: 如果交易所不支持或使用了不兼容的密鑰格式
    """
    exchange_classes: Dict[ExchangeEnum, Any] = {
        ExchangeEnum.BINANCE: ccxt.binance,
        ExchangeEnum.okx: ccxt.okx,
        ExchangeEnum.BYBIT: ccxt.bybit,
        ExchangeEnum.GATE: ccxt.gateio,
        ExchangeEnum.MEXC: ccxt.mexc,
    }
    
    if exchange not in exchange_classes:
        raise ValueError(f"Exchange {exchange} is not supported")
    
    # 創建交易所實例
    exchange_class = exchange_classes[exchange]
    client = exchange_class({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,  # 啟用請求頻率限制
        'options': {
            'defaultType': 'future',  # 默認使用合約市場
            'adjustForTimeDifference': True,  # 調整時間差
        }
    })
    
    # 加載市場
    await client.load_markets()
    
    return client 