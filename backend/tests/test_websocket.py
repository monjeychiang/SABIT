import asyncio
import websockets
import json
from datetime import datetime
import logging
from collections import defaultdict

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def format_value(value):
    """格式化数值以便於显示"""
    if isinstance(value, float):
        # 根据数值大小调整小数位数
        if abs(value) < 0.001:
            return f"{value:.8f}"
        elif abs(value) < 1:
            return f"{value:.6f}"
        elif abs(value) < 10:
            return f"{value:.4f}"
        else:
            return f"{value:.2f}"
    return str(value)

def print_market_data(data, prefix=""):
    """格式化打印市場數據"""
    if isinstance(data, list):
        logger.info(f"{prefix}收到 Binance 直接數據，{len(data)} 個交易對:")
        for item in data[:5]:  # 只打印前5個作為示例
            symbol = item.get('s', 'unknown')
            price = format_value(float(item.get('c', 0))) if item.get('c') else 'N/A'
            change = format_value(float(item.get('P', 0))) if item.get('P') else 'N/A'
            volume = format_value(float(item.get('v', 0))) if item.get('v') else 'N/A'
            high = format_value(float(item.get('h', 0))) if item.get('h') else 'N/A'
            low = format_value(float(item.get('l', 0))) if item.get('l') else 'N/A'
            logger.info(f"{prefix}  {symbol}: 價格={price}, 漲跌幅={change}%, 最高={high}, 最低={low}, 成交量={volume}")
        if len(data) > 5:
            logger.info(f"{prefix}  ... 還有 {len(data)-5} 個交易對")
        
        # 市场统计
        spot_count = 0
        futures_count = 0
        
        for item in data:
            symbol = item.get('s', '')
            if 'PERP' in symbol or symbol.endswith('_PERP'):
                futures_count += 1
            elif symbol.endswith('USDT'):
                spot_count += 1
                
        logger.info(f"{prefix}  估计现货：{spot_count}个交易对，期货：{futures_count}个交易对")
    
    elif isinstance(data, dict):
        if data.get('type') == 'update' and data.get('markets'):
            markets = data['markets']
            if 'spot' in markets:
                spot_data = markets['spot']
                logger.info(f"{prefix}現貨市場更新，{len(spot_data)} 個交易對:")
                for symbol, details in list(spot_data.items())[:5]:
                    price = format_value(details.get('price', 0)) if details.get('price') else 'N/A'
                    change = format_value(details.get('price_change_24h', 0)) if details.get('price_change_24h') else 'N/A'
                    volume = format_value(details.get('volume_24h', 0)) if details.get('volume_24h') else 'N/A'
                    high = format_value(details.get('high_24h', 0)) if details.get('high_24h') else 'N/A'
                    low = format_value(details.get('low_24h', 0)) if details.get('low_24h') else 'N/A'
                    logger.info(f"{prefix}  {symbol}: 價格={price}, 漲跌幅={change}%, 最高={high}, 最低={low}, 成交量={volume}")
                if len(spot_data) > 5:
                    logger.info(f"{prefix}  ... 還有 {len(spot_data)-5} 個交易對")
            
            if 'futures' in markets:
                futures_data = markets['futures']
                logger.info(f"{prefix}合約市場更新，{len(futures_data)} 個交易對:")
                for symbol, details in list(futures_data.items())[:5]:
                    price = format_value(details.get('price', 0)) if details.get('price') else 'N/A'
                    change = format_value(details.get('price_change_24h', 0)) if details.get('price_change_24h') else 'N/A'
                    volume = format_value(details.get('volume_24h', 0)) if details.get('volume_24h') else 'N/A'
                    high = format_value(details.get('high_24h', 0)) if details.get('high_24h') else 'N/A'
                    low = format_value(details.get('low_24h', 0)) if details.get('low_24h') else 'N/A'
                    logger.info(f"{prefix}  {symbol}: 價格={price}, 漲跌幅={change}%, 最高={high}, 最低={low}, 成交量={volume}")
                if len(futures_data) > 5:
                    logger.info(f"{prefix}  ... 還有 {len(futures_data)-5} 個交易對")
        
        elif data.get('type') == 'connection':
            logger.info(f"{prefix}收到连接确认: {data}")
            
        elif data.get('type') in ['pong', 'heartbeat']:
            logger.info(f"{prefix}收到心跳消息: {data}")
        
        elif data.get('id') is not None and data.get('result') is not None:
            logger.info(f"{prefix}收到订阅确认: {data}")
            
        else:
            logger.info(f"{prefix}收到其他類型消息: {json.dumps(data, indent=2)}")
            
    else:
        # 处理其他类型数据
        logger.info(f"{prefix}收到未知类型数据: {type(data)}")
        try:
            logger.info(f"{prefix}数据内容: {data}")
        except:
            logger.info(f"{prefix}无法打印数据内容")

async def test_websocket():
    # 統計數據
    message_count = 0
    message_types = defaultdict(int)
    market_updates = defaultdict(int)
    start_time = None
    
    try:
        uri = "ws://localhost:8000/api/v1/markets/ws/all"
        logger.info(f"正在连接 WebSocket: {uri}")
        
        async with websockets.connect(uri) as websocket:
            logger.info("已連接到 WebSocket")
            start_time = datetime.now()
            
            # 發送訂閱請求
            subscribe_message = {
                "type": "subscribe",
                "market_type": "all"
            }
            await websocket.send(json.dumps(subscribe_message))
            logger.info("已發送訂閱請求")
            
            # 收集20秒數據
            test_duration = 20  # 增加测试时间到20秒
            logger.info(f"开始收集数据，持续 {test_duration} 秒...")
            
            while (datetime.now() - start_time).total_seconds() < test_duration:
                try:
                    # 设置较短的超时，以便能够定期更新状态
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    message_count += 1
                    
                    # 解析並分析消息
                    data = json.loads(message)
                    
                    # 打印接收到的數據
                    logger.info(f"\n--- 消息 #{message_count} ---")
                    print_market_data(data, "  ")
                    
                    if isinstance(data, list):
                        # Binance 直接數據
                        message_types['binance_direct'] += 1
                        market_updates['symbols'] += len(data)
                    elif isinstance(data, dict):
                        message_types[data.get('type', 'unknown')] += 1
                        
                        if data.get('type') == 'update' and data.get('markets'):
                            markets = data['markets']
                            if 'spot' in markets:
                                market_updates['spot'] += len(markets['spot'])
                            if 'futures' in markets:
                                market_updates['futures'] += len(markets['futures'])
                    
                    # 每5秒输出中间统计
                    elapsed = (datetime.now() - start_time).total_seconds()
                    if int(elapsed) % 5 == 0 and int(elapsed) > 0:
                        logger.info(f"\n--- 阶段性统计 ---")
                        logger.info(f"已运行 {int(elapsed)} 秒，接收 {message_count} 条消息，频率: {message_count/elapsed:.2f}条/秒")
                        
                except asyncio.TimeoutError:
                    # 超时但未收到消息，输出当前状态
                    elapsed = (datetime.now() - start_time).total_seconds()
                    remaining = test_duration - elapsed
                    if int(elapsed) % 5 == 0:
                        logger.info(f"等待消息中... 已运行 {int(elapsed)} 秒，还剩 {int(remaining)} 秒，已收到 {message_count} 条消息")
                    continue
                except json.JSONDecodeError as e:
                    logger.error(f"無法解析消息: {e}")
                    continue
                except Exception as e:
                    logger.error(f"处理消息时出错: {e}")
                    continue
                
    except Exception as e:
        logger.error(f"連接錯誤: {e}")
        return
    
    # 輸出統計結果
    duration = (datetime.now() - start_time).total_seconds() if start_time else 0
    logger.info("\n=== 測試結果 ===")
    logger.info(f"運行時間: {duration:.2f} 秒")
    logger.info(f"總消息數: {message_count}")
    logger.info(f"消息頻率: {message_count/duration:.2f} 條/秒") if duration > 0 else logger.info("无法计算消息频率")
    
    logger.info("\n消息類型統計:")
    for msg_type, count in message_types.items():
        logger.info(f"- {msg_type}: {count} 條")
    
    logger.info("\n市場更新統計:")
    for market, count in market_updates.items():
        logger.info(f"- {market}: {count} 個交易對")
    
    spot_count = market_updates.get('spot', 0)
    futures_count = market_updates.get('futures', 0)
    if spot_count or futures_count:
        total_updates = spot_count + futures_count
        logger.info(f"\n交易对统计:")
        logger.info(f"- 总计: {total_updates} 个交易对")
        logger.info(f"- 现货: {spot_count} 个交易对 ({spot_count/total_updates*100:.1f}%)" if total_updates else "- 现货: 0 个交易对")
        logger.info(f"- 期货: {futures_count} 个交易对 ({futures_count/total_updates*100:.1f}%)" if total_updates else "- 期货: 0 个交易对")

if __name__ == "__main__":
    logger.info("启动 WebSocket 测试...")
    asyncio.run(test_websocket())
    logger.info("WebSocket 测试完成。") 