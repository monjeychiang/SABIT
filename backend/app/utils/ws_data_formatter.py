"""
WebSocket数据格式化工具

用于将交易所推送的WebSocket账户数据转换为更易读和理解的格式
支持多种交易所的数据格式化，提供统一的数据结构
"""

from typing import Dict, Any, List, Optional
from decimal import Decimal
import json
from datetime import datetime
import logging
from enum import Enum

from ..schemas.trading import ExchangeEnum, Balance

logger = logging.getLogger(__name__)

class AccountUpdateType(str, Enum):
    """账户更新类型枚举"""
    BALANCE = "BALANCE"           # 资产余额更新
    POSITION = "POSITION"         # 持仓信息更新
    MARGIN_CALL = "MARGIN_CALL"   # 保证金预警
    ORDER = "ORDER"               # 订单更新
    FUNDING = "FUNDING"           # 资金费率结算
    UNKNOWN = "UNKNOWN"           # 未知类型

class WebSocketDataFormatter:
    """WebSocket数据格式化类"""
    
    @staticmethod
    def format_account_update(exchange: ExchangeEnum, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        格式化账户更新数据
        
        将原始WebSocket数据转换为统一、易读的格式
        
        Args:
            exchange: 交易所枚举
            data: 原始WebSocket数据
            
        Returns:
            Dict[str, Any]: 格式化后的数据
        """
        # 标准化的数据结构
        formatted_data = {
            "exchange": exchange.value,
            "event_type": "UNKNOWN",
            "timestamp": datetime.now().isoformat(),
            "formatted_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data": {},
            "raw_data": data  # 保留原始数据以供参考
        }
        
        try:
            # 根据不同交易所处理数据
            if exchange == ExchangeEnum.BINANCE:
                return WebSocketDataFormatter._format_binance_data(data, formatted_data)
            elif exchange == ExchangeEnum.BYBIT:
                return WebSocketDataFormatter._format_bybit_data(data, formatted_data)
            elif exchange == ExchangeEnum.okx:
                return WebSocketDataFormatter._format_okx_data(data, formatted_data)
            else:
                formatted_data["event_type"] = "UNKNOWN"
                formatted_data["data"] = {
                    "message": f"未知交易所数据格式: {exchange.value}"
                }
                return formatted_data
        except Exception as e:
            logger.error(f"格式化WebSocket数据异常: {str(e)}")
            formatted_data["event_type"] = "ERROR"
            formatted_data["data"] = {
                "error": str(e),
                "message": "数据格式化过程中出现错误"
            }
            return formatted_data
    
    @staticmethod
    def _format_binance_data(data: Dict[str, Any], formatted_data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化币安WebSocket数据"""
        # 提取事件类型和时间戳
        event_type = data.get("e", "UNKNOWN")
        timestamp = data.get("E", 0)
        
        if timestamp > 0:
            dt = datetime.fromtimestamp(timestamp / 1000)
            formatted_data["timestamp"] = dt.isoformat()
            formatted_data["formatted_time"] = dt.strftime("%Y-%m-%d %H:%M:%S")
        
        # 根据不同事件类型处理
        if event_type == "ACCOUNT_UPDATE":
            formatted_data["event_type"] = "ACCOUNT_UPDATE"
            
            # 提取账户变动数据
            account_data = data.get("a", {})
            
            # 处理余额更新
            balances = []
            for b in account_data.get("B", []):
                asset = b.get("a", "")
                wallet_balance = WebSocketDataFormatter._format_decimal(b.get("wb", "0"))
                cross_balance = WebSocketDataFormatter._format_decimal(b.get("cw", "0"))
                available = WebSocketDataFormatter._format_decimal(b.get("ab", wallet_balance))
                
                balances.append({
                    "asset": asset,
                    "wallet_balance": wallet_balance,
                    "cross_wallet_balance": cross_balance,
                    "available_balance": available,
                    "locked": WebSocketDataFormatter._format_decimal(
                        float(wallet_balance) - float(available)
                    )
                })
            
            # 处理持仓更新
            positions = []
            for p in account_data.get("P", []):
                symbol = p.get("s", "")
                entry_price = WebSocketDataFormatter._format_decimal(p.get("ep", "0"))
                position_amount = WebSocketDataFormatter._format_decimal(p.get("pa", "0"))
                unrealized_pnl = WebSocketDataFormatter._format_decimal(p.get("up", "0"))
                margin_type = p.get("mt", "")
                isolated_margin = WebSocketDataFormatter._format_decimal(p.get("iw", "0"))
                
                # 计算方向
                position_side = "LONG" if float(position_amount) > 0 else "SHORT" if float(position_amount) < 0 else "FLAT"
                
                positions.append({
                    "symbol": symbol,
                    "position_amount": position_amount,
                    "entry_price": entry_price,
                    "unrealized_pnl": unrealized_pnl,
                    "position_side": position_side,
                    "margin_type": margin_type,
                    "isolated_wallet": isolated_margin
                })
            
            formatted_data["data"] = {
                "reason": account_data.get("m", ""),  # 触发原因
                "balances": balances,
                "positions": positions,
                "balances_count": len(balances),
                "positions_count": len(positions),
                "update_type": "BALANCE_AND_POSITION" if balances and positions else 
                               "BALANCE_ONLY" if balances else 
                               "POSITION_ONLY" if positions else "UNKNOWN"
            }
        
        elif event_type == "MARGIN_CALL":
            formatted_data["event_type"] = "MARGIN_CALL"
            
            margin_calls = []
            for mc in data.get("mc", []):
                margin_calls.append({
                    "symbol": mc.get("s", ""),
                    "position_side": mc.get("ps", ""),
                    "position_amount": WebSocketDataFormatter._format_decimal(mc.get("pa", "0")),
                    "margin_type": mc.get("mt", ""),
                    "isolated_wallet": WebSocketDataFormatter._format_decimal(mc.get("iw", "0")),
                    "mark_price": WebSocketDataFormatter._format_decimal(mc.get("mp", "0")),
                    "maintenance_margin": WebSocketDataFormatter._format_decimal(mc.get("mm", "0")),
                    "required_margin": WebSocketDataFormatter._format_decimal(mc.get("mm", "0")),
                    "current_margin": WebSocketDataFormatter._format_decimal(mc.get("mm", "0")),
                    "margin_ratio": WebSocketDataFormatter._format_decimal(mc.get("mr", "0"))
                })
            
            formatted_data["data"] = {
                "margin_calls": margin_calls,
                "count": len(margin_calls),
                "explanation": "保证金不足警告，请及时增加保证金或减少仓位，避免被强制平仓"
            }
        
        elif event_type == "ORDER_TRADE_UPDATE":
            formatted_data["event_type"] = "ORDER_UPDATE"
            
            order_data = data.get("o", {})
            formatted_data["data"] = {
                "symbol": order_data.get("s", ""),
                "client_order_id": order_data.get("c", ""),
                "side": order_data.get("S", ""),
                "order_type": order_data.get("o", ""),
                "time_in_force": order_data.get("f", ""),
                "original_quantity": WebSocketDataFormatter._format_decimal(order_data.get("q", "0")),
                "original_price": WebSocketDataFormatter._format_decimal(order_data.get("p", "0")),
                "average_price": WebSocketDataFormatter._format_decimal(order_data.get("ap", "0")),
                "stop_price": WebSocketDataFormatter._format_decimal(order_data.get("sp", "0")),
                "execution_type": order_data.get("x", ""),
                "order_status": order_data.get("X", ""),
                "order_id": order_data.get("i", 0),
                "last_filled_quantity": WebSocketDataFormatter._format_decimal(order_data.get("l", "0")),
                "filled_accumulated_quantity": WebSocketDataFormatter._format_decimal(order_data.get("z", "0")),
                "last_filled_price": WebSocketDataFormatter._format_decimal(order_data.get("L", "0")),
                "commission_asset": order_data.get("N", None),
                "commission_amount": WebSocketDataFormatter._format_decimal(order_data.get("n", "0")),
                "trade_time": datetime.fromtimestamp(order_data.get("T", 0) / 1000).strftime("%Y-%m-%d %H:%M:%S"),
                "trade_id": order_data.get("t", 0),
                "in_position": order_data.get("ps", ""),
                "is_maker": order_data.get("m", False),
                "reduce_only": order_data.get("R", False),
                "realized_profit": WebSocketDataFormatter._format_decimal(order_data.get("rp", "0"))
            }
        
        # 添加其他事件类型的处理...
        else:
            formatted_data["event_type"] = f"UNKNOWN_{event_type}"
            formatted_data["data"] = {
                "message": f"未知事件类型: {event_type}"
            }
        
        return formatted_data
    
    @staticmethod
    def _format_bybit_data(data: Dict[str, Any], formatted_data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化Bybit WebSocket数据"""
        # Bybit格式处理逻辑，根据具体数据结构实现
        # 示例格式化逻辑
        topic = data.get("topic", "")
        
        if "wallet" in topic:
            formatted_data["event_type"] = "ACCOUNT_UPDATE"
            wallet_data = data.get("data", [])
            
            balances = []
            for item in wallet_data:
                asset = item.get("coin", "")
                wallet_balance = WebSocketDataFormatter._format_decimal(item.get("wallet_balance", "0"))
                available = WebSocketDataFormatter._format_decimal(item.get("available_balance", "0"))
                
                balances.append({
                    "asset": asset,
                    "wallet_balance": wallet_balance,
                    "available_balance": available,
                    "locked": WebSocketDataFormatter._format_decimal(
                        float(wallet_balance) - float(available)
                    )
                })
            
            formatted_data["data"] = {
                "balances": balances,
                "balances_count": len(balances),
                "update_type": "BALANCE_ONLY"
            }
        
        elif "position" in topic:
            formatted_data["event_type"] = "POSITION_UPDATE"
            position_data = data.get("data", [])
            
            positions = []
            for pos in position_data:
                symbol = pos.get("symbol", "")
                position_value = WebSocketDataFormatter._format_decimal(pos.get("position_value", "0"))
                entry_price = WebSocketDataFormatter._format_decimal(pos.get("entry_price", "0"))
                
                positions.append({
                    "symbol": symbol,
                    "position_value": position_value,
                    "entry_price": entry_price,
                    "leverage": pos.get("leverage", "0"),
                    "position_side": "LONG" if pos.get("side", "") == "Buy" else "SHORT",
                    "unrealized_pnl": WebSocketDataFormatter._format_decimal(pos.get("unrealised_pnl", "0"))
                })
            
            formatted_data["data"] = {
                "positions": positions,
                "positions_count": len(positions),
                "update_type": "POSITION_ONLY"
            }
        
        # 添加其他主题的处理...
        else:
            formatted_data["event_type"] = f"UNKNOWN_TOPIC"
            formatted_data["data"] = {
                "topic": topic,
                "message": "未知主题类型"
            }
        
        return formatted_data
    
    @staticmethod
    def _format_okx_data(data: Dict[str, Any], formatted_data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化OKX WebSocket数据"""
        # OKX格式处理逻辑，根据具体数据结构实现
        # 示例格式化逻辑
        
        # 添加OKX特定的格式化逻辑
        arg = data.get("arg", {})
        channel = arg.get("channel", "")
        
        if channel == "account":
            formatted_data["event_type"] = "ACCOUNT_UPDATE"
            
            account_data = data.get("data", [])
            if account_data:
                balances = []
                for item in account_data[0].get("details", []):
                    asset = item.get("ccy", "")
                    equity = WebSocketDataFormatter._format_decimal(item.get("eq", "0"))
                    available = WebSocketDataFormatter._format_decimal(item.get("availEq", "0"))
                    
                    balances.append({
                        "asset": asset,
                        "equity": equity,
                        "available": available,
                        "frozen": WebSocketDataFormatter._format_decimal(
                            float(equity) - float(available)
                        )
                    })
                
                formatted_data["data"] = {
                    "balances": balances,
                    "balances_count": len(balances),
                    "update_type": "BALANCE_ONLY",
                    "total_equity": account_data[0].get("totalEq", "0")
                }
        
        elif channel == "positions":
            formatted_data["event_type"] = "POSITION_UPDATE"
            
            positions_data = data.get("data", [])
            positions = []
            
            for pos in positions_data:
                positions.append({
                    "symbol": pos.get("instId", ""),
                    "position_side": "LONG" if pos.get("posSide", "") == "long" else "SHORT",
                    "position_size": WebSocketDataFormatter._format_decimal(pos.get("pos", "0")),
                    "entry_price": WebSocketDataFormatter._format_decimal(pos.get("avgPx", "0")),
                    "mark_price": WebSocketDataFormatter._format_decimal(pos.get("markPx", "0")),
                    "unrealized_pnl": WebSocketDataFormatter._format_decimal(pos.get("upl", "0")),
                    "margin_mode": pos.get("mgnMode", ""),
                    "leverage": pos.get("lever", "0")
                })
            
            formatted_data["data"] = {
                "positions": positions,
                "positions_count": len(positions),
                "update_type": "POSITION_ONLY"
            }
        
        # 添加其他通道的处理...
        else:
            formatted_data["event_type"] = f"UNKNOWN_CHANNEL"
            formatted_data["data"] = {
                "channel": channel,
                "message": "未知通道类型"
            }
        
        return formatted_data
    
    @staticmethod
    def _format_decimal(value: Any) -> str:
        """
        格式化数字为易读字符串
        
        Args:
            value: 需要格式化的数值
            
        Returns:
            str: 格式化后的字符串
        """
        if value is None:
            return "0"
            
        try:
            # 转换为Decimal确保精度
            decimal_value = Decimal(str(value))
            
            # 如果是整数，去除小数点后的零
            if decimal_value == decimal_value.to_integral_value():
                return str(decimal_value.quantize(Decimal("1")))
                
            # 否则格式化为最多8位小数
            return str(decimal_value.quantize(Decimal("0.00000001")).normalize())
        except:
            # 转换失败返回原值的字符串
            return str(value)
    
    @staticmethod
    def get_human_readable_summary(exchange: ExchangeEnum, data: Dict[str, Any]) -> str:
        """
        生成人类可读的WebSocket数据摘要
        
        Args:
            exchange: 交易所枚举
            data: 原始WebSocket数据
            
        Returns:
            str: 人类可读的摘要
        """
        try:
            # 先格式化数据
            formatted = WebSocketDataFormatter.format_account_update(exchange, data)
            
            # 构建摘要
            summary = []
            summary.append(f"交易所: {formatted['exchange']}")
            summary.append(f"事件类型: {formatted['event_type']}")
            summary.append(f"时间: {formatted['formatted_time']}")
            
            event_data = formatted["data"]
            
            # 根据事件类型生成不同的摘要
            if formatted["event_type"] == "ACCOUNT_UPDATE":
                balances = event_data.get("balances", [])
                positions = event_data.get("positions", [])
                
                if balances:
                    summary.append(f"\n资产更新 ({len(balances)}个):")
                    for i, balance in enumerate(balances[:3]):  # 只显示前3个
                        summary.append(f"  {i+1}. {balance['asset']}: 余额={balance['wallet_balance']}, 可用={balance['available_balance'] if 'available_balance' in balance else '未知'}")
                    if len(balances) > 3:
                        summary.append(f"  ... 还有 {len(balances)-3} 个资产 ...")
                
                if positions:
                    summary.append(f"\n持仓更新 ({len(positions)}个):")
                    for i, position in enumerate(positions[:3]):  # 只显示前3个
                        direction = position.get('position_side', '')
                        size = position.get('position_amount', position.get('position_value', '0'))
                        entry = position.get('entry_price', '0')
                        pnl = position.get('unrealized_pnl', '0')
                        summary.append(f"  {i+1}. {position['symbol']}: 方向={direction}, 数量={size}, 入场价={entry}, 盈亏={pnl}")
                    if len(positions) > 3:
                        summary.append(f"  ... 还有 {len(positions)-3} 个持仓 ...")
            
            elif formatted["event_type"] == "MARGIN_CALL":
                margin_calls = event_data.get("margin_calls", [])
                summary.append(f"\n保证金预警 ({len(margin_calls)}个):")
                for i, mc in enumerate(margin_calls[:3]):
                    summary.append(f"  {i+1}. {mc['symbol']}: 方向={mc['position_side']}, 保证金率={mc['margin_ratio']}")
                if len(margin_calls) > 3:
                    summary.append(f"  ... 还有 {len(margin_calls)-3} 个保证金预警 ...")
                
                summary.append(f"\n警告: {event_data.get('explanation', '保证金不足，请及时处理')}")
            
            elif formatted["event_type"] == "ORDER_UPDATE":
                order = event_data
                summary.append(f"\n订单更新:")
                summary.append(f"  交易对: {order.get('symbol', '未知')}")
                summary.append(f"  订单ID: {order.get('order_id', '未知')}")
                summary.append(f"  方向: {order.get('side', '未知')}")
                summary.append(f"  类型: {order.get('order_type', '未知')}")
                summary.append(f"  价格: {order.get('original_price', '未知')}")
                summary.append(f"  数量: {order.get('original_quantity', '未知')}")
                summary.append(f"  状态: {order.get('order_status', '未知')}")
                summary.append(f"  成交量: {order.get('filled_accumulated_quantity', '0')}")
                summary.append(f"  平均成交价: {order.get('average_price', '0')}")
            
            elif "UNKNOWN" in formatted["event_type"]:
                # 处理未知事件类型
                summary.append("\n未知事件数据:")
                for key, value in event_data.items():
                    if isinstance(value, (str, int, float, bool)):
                        summary.append(f"  {key}: {value}")
            
            # 返回拼接的摘要
            return "\n".join(summary)
            
        except Exception as e:
            return f"生成摘要出错: {str(e)}\n原始数据: {json.dumps(data, indent=2)[:500]}" 