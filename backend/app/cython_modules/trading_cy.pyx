# cython: language_level=3, boundscheck=False, wraparound=False, nonecheck=False
"""
交易服务相关功能的Cython优化版本

提供交易相关的计算密集型功能的高性能实现
主要优化持仓计算、保证金计算和订单匹配等功能
"""

import cython
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple, Union
import numpy as np

# 导入本地优化函数
from .ws_data_formatter_cy import format_decimal

# 使用C层面的数据类型提高性能
ctypedef dict dict_type
ctypedef list list_type
ctypedef str str_type
ctypedef double float_type

@cython.ccall
def calculate_position_value(dict position, float_type mark_price) -> float_type:
    """
    计算持仓价值的Cython优化版本
    
    Args:
        position: 持仓信息字典
        mark_price: 标记价格
            
    Returns:
        float_type: 持仓价值
    """
    cdef float_type position_amount = float(position.get("position_amount", 0))
    cdef float_type abs_position = abs(position_amount)
    
    # 计算持仓价值
    cdef float_type position_value = abs_position * mark_price
    
    return position_value

@cython.ccall
def calculate_margin_requirement(dict position, 
                                float_type mark_price, 
                                float_type maintenance_margin_rate, 
                                str margin_type="ISOLATED") -> Dict[str, float_type]:
    """
    计算保证金需求的Cython优化版本
    
    Args:
        position: 持仓信息字典
        mark_price: 标记价格
        maintenance_margin_rate: 维持保证金率
        margin_type: 保证金类型，可选 "ISOLATED" 或 "CROSS"
            
    Returns:
        Dict[str, float_type]: 包含保证金需求信息的字典
    """
    cdef float_type position_amount = float(position.get("position_amount", 0))
    cdef float_type entry_price = float(position.get("entry_price", 0))
    cdef float_type isolated_wallet = float(position.get("isolated_wallet", 0))
    cdef float_type abs_position = abs(position_amount)
    
    # 计算持仓价值
    cdef float_type position_value = abs_position * mark_price
    
    # 计算未实现盈亏
    cdef float_type unrealized_pnl = 0.0
    if position_amount > 0:  # 多头
        unrealized_pnl = abs_position * (mark_price - entry_price)
    elif position_amount < 0:  # 空头
        unrealized_pnl = abs_position * (entry_price - mark_price)
    
    # 计算维持保证金
    cdef float_type maintenance_margin = position_value * maintenance_margin_rate
    
    # 计算保证金率
    cdef float_type margin_ratio = 0.0
    if margin_type == "ISOLATED":
        # 对于逐仓，保证金率 = (钱包余额 + 未实现盈亏) / 维持保证金
        if maintenance_margin > 0:
            margin_ratio = (isolated_wallet + unrealized_pnl) / maintenance_margin
    else:  # CROSS
        # 对于全仓，需要考虑账户余额，这里简化处理
        # 实际应用中需要传入更多参数
        if maintenance_margin > 0:
            margin_ratio = (isolated_wallet + unrealized_pnl) / maintenance_margin
    
    # 返回计算结果
    return {
        "position_value": position_value,
        "maintenance_margin": maintenance_margin,
        "unrealized_pnl": unrealized_pnl,
        "margin_ratio": margin_ratio,
        "liquidation_price": calculate_liquidation_price(
            position_amount, entry_price, isolated_wallet, 
            maintenance_margin_rate, margin_type
        )
    }

@cython.ccall
def calculate_liquidation_price(float_type position_amount,
                               float_type entry_price,
                               float_type wallet_balance,
                               float_type maintenance_margin_rate,
                               str margin_type="ISOLATED") -> float_type:
    """
    计算清算价格的Cython优化版本
    
    Args:
        position_amount: 持仓数量
        entry_price: 开仓均价
        wallet_balance: 钱包余额
        maintenance_margin_rate: 维持保证金率
        margin_type: 保证金类型
            
    Returns:
        float_type: 清算价格
    """
    # 如果没有持仓，返回0
    if position_amount == 0:
        return 0.0
    
    cdef float_type abs_position = abs(position_amount)
    cdef float_type maintenance_amount = wallet_balance - abs_position * entry_price * maintenance_margin_rate
    cdef float_type liquidation_price = 0.0
    
    if position_amount > 0:  # 多头
        # 对于多头，清算价格 = (开仓价值 - 钱包余额) / ((1 - 维持保证金率) * 持仓数量)
        if abs_position * (1 - maintenance_margin_rate) == 0:
            return 0.0  # 避免除以零
        liquidation_price = (abs_position * entry_price - wallet_balance) / (abs_position * (1 - maintenance_margin_rate))
    else:  # 空头
        # 对于空头，清算价格 = (开仓价值 + 钱包余额) / ((1 + 维持保证金率) * 持仓数量)
        if abs_position * (1 + maintenance_margin_rate) == 0:
            return 0.0  # 避免除以零
        liquidation_price = (abs_position * entry_price + wallet_balance) / (abs_position * (1 + maintenance_margin_rate))
    
    # 确保清算价格为正数
    return max(0.0, liquidation_price)

@cython.ccall
def match_orders(dict[:] buy_orders, dict[:] sell_orders) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    订单匹配算法的Cython优化版本
    
    模拟交易所订单簿中的订单匹配过程
    
    Args:
        buy_orders: 买单列表
        sell_orders: 卖单列表
            
    Returns:
        Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]: 匹配结果和成交记录
    """
    # 按价格排序订单 - 避免使用lambda表达式
    cdef list sorted_buys = sorted_by_price(buy_orders, True)  # 买单降序
    cdef list sorted_sells = sorted_by_price(sell_orders, False)  # 卖单升序
    
    cdef list trades = []  # 成交记录
    cdef list updated_orders = []  # 更新后的订单
    
    cdef int i = 0
    cdef int j = 0
    cdef dict buy_order, sell_order
    cdef float_type buy_price, sell_price
    cdef float_type buy_quantity, sell_quantity
    cdef float_type match_quantity
    
    # 匹配过程
    while i < len(sorted_buys) and j < len(sorted_sells):
        buy_order = sorted_buys[i]
        sell_order = sorted_sells[j]
        
        buy_price = float(buy_order.get("price", 0))
        sell_price = float(sell_order.get("price", 0))
        
        # 价格不匹配条件
        if buy_price < sell_price:
            break
        
        buy_quantity = float(buy_order.get("quantity", 0)) - float(buy_order.get("filled", 0))
        sell_quantity = float(sell_order.get("quantity", 0)) - float(sell_order.get("filled", 0))
        
        # 确定成交数量
        match_quantity = min(buy_quantity, sell_quantity)
        
        if match_quantity > 0:
            # 创建成交记录
            trade = {
                "buy_order_id": buy_order.get("order_id"),
                "sell_order_id": sell_order.get("order_id"),
                "price": sell_price,  # 通常以卖单价格成交
                "quantity": match_quantity,
                "value": match_quantity * sell_price,
                "buyer_id": buy_order.get("user_id"),
                "seller_id": sell_order.get("user_id"),
                "symbol": buy_order.get("symbol")
            }
            trades.append(trade)
            
            # 更新订单已成交数量
            buy_order["filled"] = float(buy_order.get("filled", 0)) + match_quantity
            sell_order["filled"] = float(sell_order.get("filled", 0)) + match_quantity
            
            # 检查订单是否完全成交
            if buy_order.get("filled") >= buy_order.get("quantity"):
                buy_order["status"] = "FILLED"
                i += 1
            
            if sell_order.get("filled") >= sell_order.get("quantity"):
                sell_order["status"] = "FILLED"
                j += 1
            
            # 如果两个订单都未完全成交，则只移动一个
            if buy_order.get("status") != "FILLED" and sell_order.get("status") != "FILLED":
                if buy_quantity > sell_quantity:
                    j += 1
                else:
                    i += 1
        else:
            # 没有可匹配的数量，移动指针
            i += 1
            j += 1
    
    # 将未完全匹配的订单添加到结果
    for k in range(i, len(sorted_buys)):
        updated_orders.append(sorted_buys[k])
    
    for k in range(j, len(sorted_sells)):
        updated_orders.append(sorted_sells[k])
    
    return updated_orders, trades

# 添加辅助函数代替lambda表达式
@cython.ccall
def sorted_by_price(dict[:] orders, bint reverse) -> list:
    """按价格排序订单的辅助函数"""
    cdef list result = []
    cdef dict order
    cdef list price_order_pairs = []
    cdef int i
    
    # 创建(价格, 订单)对列表
    for i in range(len(orders)):
        order = orders[i]
        price = float(order.get("price", 0))
        price_order_pairs.append((price, order))
    
    # 排序
    price_order_pairs.sort(reverse=reverse)
    
    # 提取排序后的订单
    for price, order in price_order_pairs:
        result.append(order)
    
    return result 