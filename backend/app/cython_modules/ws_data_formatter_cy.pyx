# cython: language_level=3, boundscheck=False, wraparound=False, nonecheck=False
"""
WebSocket数据格式化工具的Cython优化版本

此模块提供对WebSocket数据处理的高性能实现
主要优化数值处理和大型JSON数据格式化
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from decimal import Decimal
import json
import cython

# 使用C层面的数据类型提高性能
ctypedef dict dict_type
ctypedef list list_type
ctypedef str str_type
ctypedef double float_type

@cython.ccall
def format_decimal(value) -> str:
    """
    格式化小数值为字符串的Cython优化版本
    
    将各种类型的值转换为标准格式的字符串，去除尾随零
    
    Args:
        value: 待格式化的值，可以是字符串、浮点数或None
            
    Returns:
        str: 格式化后的字符串
    """
    # 如果值为None或空字符串，返回"0"
    if value is None or value == "":
        return "0"
        
    # 尝试转换为Decimal进行精确处理
    cdef str result_str
    cdef double float_val
    
    try:
        # 对于字符串，先转换为Decimal再格式化
        if isinstance(value, str):
            # 替换逗号，避免解析错误
            value = value.replace(',', '')
            try:
                decimal_val = Decimal(value)
                result_str = str(decimal_val.normalize())
                # 如果结果等于零值的Decimal，返回"0"
                if result_str == "0E-8" or result_str == "0":
                    return "0"
                # 规范化输出，去除科学记数法
                if 'E' in result_str:
                    # 处理科学记数法
                    mantissa, exponent = result_str.split('E')
                    exponent = int(exponent)
                    if exponent > 0:
                        mantissa = mantissa.replace('.', '')
                        result_str = mantissa + '0' * (exponent - len(mantissa) + 1)
                    else:
                        mantissa = mantissa.replace('.', '')
                        result_str = '0.' + '0' * (-exponent - 1) + mantissa
                return result_str
            except:
                # 如果转换失败，尝试直接使用浮点数
                try:
                    float_val = float(value)
                    # 避免精度问题，使用字符串格式化
                    result_str = f"{float_val:.8f}".rstrip('0').rstrip('.')
                    return result_str if result_str != "" else "0"
                except:
                    # 如果仍然失败，返回原始值
                    return str(value)
                
        # 对于数值类型，直接格式化
        elif isinstance(value, (int, float)):
            # 避免精度问题，使用字符串格式化
            result_str = f"{float(value):.8f}".rstrip('0').rstrip('.')
            return result_str if result_str != "" else "0"
            
        # 默认情况，转换为字符串
        else:
            return str(value)
            
    except Exception as e:
        # 出现异常时，尝试简单地转换为字符串
        return str(value)

@cython.ccall
def format_binance_data(dict data, dict formatted_data) -> dict:
    """
    格式化币安WebSocket数据的Cython优化版本
    
    Args:
        data: 原始WebSocket数据
        formatted_data: 预格式化的基础数据结构
            
    Returns:
        dict: 格式化后的数据
    """
    # 提取事件类型和时间戳
    cdef str event_type = data.get("e", "UNKNOWN")
    cdef long long timestamp = data.get("E", 0)
    
    if timestamp > 0:
        dt = datetime.fromtimestamp(timestamp / 1000.0)
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
            wallet_balance = format_decimal(b.get("wb", "0"))
            cross_balance = format_decimal(b.get("cw", "0"))
            available = format_decimal(b.get("ab", wallet_balance))
            
            # 计算锁定金额
            locked = format_decimal(
                float(wallet_balance) - float(available)
            )
            
            balances.append({
                "asset": asset,
                "wallet_balance": wallet_balance,
                "cross_wallet_balance": cross_balance,
                "available_balance": available,
                "locked": locked
            })
        
        # 处理持仓更新
        positions = []
        for p in account_data.get("P", []):
            symbol = p.get("s", "")
            entry_price = format_decimal(p.get("ep", "0"))
            position_amount = format_decimal(p.get("pa", "0"))
            unrealized_pnl = format_decimal(p.get("up", "0"))
            margin_type = p.get("mt", "")
            isolated_margin = format_decimal(p.get("iw", "0"))
            
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
        
        # 整合数据
        update_type = "BALANCE_AND_POSITION" if balances and positions else \
                      "BALANCE_ONLY" if balances else \
                      "POSITION_ONLY" if positions else "UNKNOWN"
                      
        formatted_data["data"] = {
            "reason": account_data.get("m", ""),  # 触发原因
            "balances": balances,
            "positions": positions,
            "balances_count": len(balances),
            "positions_count": len(positions),
            "update_type": update_type
        }
    
    elif event_type == "MARGIN_CALL":
        formatted_data["event_type"] = "MARGIN_CALL"
        
        margin_calls = []
        for mc in data.get("mc", []):
            margin_calls.append({
                "symbol": mc.get("s", ""),
                "position_side": mc.get("ps", ""),
                "position_amount": format_decimal(mc.get("pa", "0")),
                "margin_type": mc.get("mt", ""),
                "isolated_wallet": format_decimal(mc.get("iw", "0")),
                "mark_price": format_decimal(mc.get("mp", "0")),
                "maintenance_margin": format_decimal(mc.get("mm", "0")),
                "required_margin": format_decimal(mc.get("mm", "0")),
                "current_margin": format_decimal(mc.get("mm", "0")),
                "margin_ratio": format_decimal(mc.get("mr", "0"))
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
            "original_quantity": format_decimal(order_data.get("q", "0")),
            "original_price": format_decimal(order_data.get("p", "0")),
            "average_price": format_decimal(order_data.get("ap", "0")),
            "stop_price": format_decimal(order_data.get("sp", "0")),
            "execution_type": order_data.get("x", ""),
            "order_status": order_data.get("X", ""),
            "order_id": order_data.get("i", 0),
            "last_filled_quantity": format_decimal(order_data.get("l", "0")),
            "filled_accumulated_quantity": format_decimal(order_data.get("z", "0")),
            "last_filled_price": format_decimal(order_data.get("L", "0")),
            "commission_asset": order_data.get("N", None),
            "commission_amount": format_decimal(order_data.get("n", "0")),
            "trade_time": datetime.fromtimestamp(order_data.get("T", 0) / 1000).strftime("%Y-%m-%d %H:%M:%S"),
            "trade_id": order_data.get("t", 0),
            "in_position": order_data.get("ps", ""),
            "is_maker": order_data.get("m", False),
            "reduce_only": order_data.get("R", False),
            "realized_profit": format_decimal(order_data.get("rp", "0"))
        }
    
    return formatted_data 