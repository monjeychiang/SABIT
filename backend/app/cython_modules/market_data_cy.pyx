# cython: language_level=3, boundscheck=False, wraparound=False, nonecheck=False
"""
市场数据处理和技术指标计算的Cython优化版本

提供技术分析指标的高性能实现，包括移动平均线、相对强弱指标、布林带等
"""

import cython
import numpy as np
from typing import Dict, Any, List, Optional, Tuple, Union
cimport numpy as np

# 定义C数据类型
ctypedef double float_type
# 移除全局作用域中的缓冲区类型定义
# ctypedef np.ndarray[float_type, ndim=1] float_array
# ctypedef np.ndarray[long, ndim=1] long_array

@cython.boundscheck(False)
@cython.wraparound(False)
def calculate_indicators(dict data, list indicators=None) -> Dict[str, Any]:
    """
    计算多种技术指标的Cython优化版本
    
    Args:
        data: 行情数据，包含OHLCV数据
        indicators: 要计算的指标列表
            
    Returns:
        Dict[str, Any]: 计算结果
    """
    if indicators is None:
        indicators = ['sma', 'ema', 'rsi', 'bollinger', 'macd']
    
    # 确保数据正确转换为NumPy数组
    cdef np.ndarray[double, ndim=1] closes 
    cdef np.ndarray[double, ndim=1] opens
    cdef np.ndarray[double, ndim=1] highs
    cdef np.ndarray[double, ndim=1] lows
    cdef np.ndarray[double, ndim=1] volumes
    
    # 从字典中提取数据并转换为NumPy数组
    closes = np.asarray(data.get('close', []), dtype=np.float64)
    opens = np.asarray(data.get('open', []), dtype=np.float64)
    highs = np.asarray(data.get('high', []), dtype=np.float64)
    lows = np.asarray(data.get('low', []), dtype=np.float64)
    volumes = np.asarray(data.get('volume', []), dtype=np.float64)
    
    result = {}
    
    # 计算所需指标
    for indicator in indicators:
        if indicator.lower() == 'sma':
            result['sma'] = {
                '5': calculate_sma(closes, 5),
                '10': calculate_sma(closes, 10),
                '20': calculate_sma(closes, 20),
                '50': calculate_sma(closes, 50),
                '200': calculate_sma(closes, 200)
            }
        elif indicator.lower() == 'ema':
            result['ema'] = {
                '5': calculate_ema(closes, 5),
                '10': calculate_ema(closes, 10),
                '20': calculate_ema(closes, 20),
                '50': calculate_ema(closes, 50),
                '200': calculate_ema(closes, 200)
            }
        elif indicator.lower() == 'rsi':
            result['rsi'] = {
                '14': calculate_rsi(closes, 14)
            }
        elif indicator.lower() == 'bollinger':
            upper, middle, lower = calculate_bollinger_bands(closes, 20, 2.0)
            result['bollinger'] = {
                'upper': upper,
                'middle': middle,
                'lower': lower
            }
        elif indicator.lower() == 'macd':
            macd_line, signal_line, histogram = calculate_macd(closes, 12, 26, 9)
            result['macd'] = {
                'macd': macd_line,
                'signal': signal_line,
                'histogram': histogram
            }
    
    return result

@cython.boundscheck(False)
@cython.wraparound(False)
def calculate_sma(np.ndarray[double, ndim=1] data, int period) -> np.ndarray:
    """
    计算简单移动平均线 (SMA) 的Cython优化版本
    
    Args:
        data: 价格数据数组
        period: 周期
            
    Returns:
        np.ndarray: SMA值数组
    """
    cdef int n = data.shape[0]
    cdef np.ndarray[double, ndim=1] result = np.zeros(n, dtype=np.float64)
    cdef double total
    cdef int i, j
    
    if n < period:
        return result  # 如果数据不足，返回全零数组
    
    # 首先为前period-1个元素计算结果
    for i in range(period-1):
        result[i] = np.nan
    
    # 计算第一个完整窗口的SMA
    total = 0.0
    for i in range(period):
        total += data[i]
    result[period-1] = total / period
    
    # 使用滑动窗口高效计算后续SMA
    for i in range(period, n):
        total = total - data[i-period] + data[i]
        result[i] = total / period
    
    return result

@cython.boundscheck(False)
@cython.wraparound(False)
def calculate_ema(np.ndarray[double, ndim=1] data, int period) -> np.ndarray:
    """
    计算指数移动平均线 (EMA) 的Cython优化版本
    
    Args:
        data: 价格数据数组
        period: 周期
            
    Returns:
        np.ndarray: EMA值数组
    """
    cdef int n = data.shape[0]
    cdef np.ndarray[double, ndim=1] result = np.zeros(n, dtype=np.float64)
    cdef double alpha = 2.0 / (period + 1.0)
    cdef double prev_ema
    cdef int i
    
    if n < period:
        return result  # 如果数据不足，返回全零数组
        
    # 为前period-1个元素填充NaN
    for i in range(period-1):
        result[i] = np.nan
    
    # 计算第一个EMA值（使用SMA作为起点）
    prev_ema = 0.0
    for i in range(period):
        prev_ema += data[i]
    prev_ema /= period
    result[period-1] = prev_ema
    
    # 计算后续EMA值
    for i in range(period, n):
        result[i] = data[i] * alpha + prev_ema * (1.0 - alpha)
        prev_ema = result[i]
    
    return result

@cython.boundscheck(False)
@cython.wraparound(False)
def calculate_rsi(np.ndarray[double, ndim=1] data, int period) -> np.ndarray:
    """
    计算相对强弱指标 (RSI) 的Cython优化版本
    
    Args:
        data: 价格数据数组
        period: 周期
            
    Returns:
        np.ndarray: RSI值数组（范围为0-100）
    """
    cdef int n = data.shape[0]
    cdef np.ndarray[double, ndim=1] result = np.zeros(n, dtype=np.float64)
    cdef np.ndarray[double, ndim=1] delta = np.zeros(n, dtype=np.float64)
    cdef np.ndarray[double, ndim=1] gain = np.zeros(n, dtype=np.float64)
    cdef np.ndarray[double, ndim=1] loss = np.zeros(n, dtype=np.float64)
    cdef double avg_gain, avg_loss, rs
    cdef int i
    
    if n <= period:
        return result  # 如果数据不足，返回全零数组
    
    # 计算价格变化
    for i in range(1, n):
        delta[i] = data[i] - data[i-1]
    
    # 分离涨跌
    for i in range(1, n):
        if delta[i] > 0:
            gain[i] = delta[i]
        elif delta[i] < 0:
            loss[i] = abs(delta[i])
    
    # 为前period个元素填充NaN
    for i in range(period):
        result[i] = np.nan
    
    # 计算初始平均涨跌幅
    avg_gain = sum(gain[1:period+1]) / period
    avg_loss = sum(loss[1:period+1]) / period
    
    # 避免除以零
    if avg_loss == 0:
        result[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100.0 - (100.0 / (1.0 + rs))
    
    # 计算后续RSI值
    for i in range(period+1, n):
        avg_gain = (avg_gain * (period-1) + gain[i]) / period
        avg_loss = (avg_loss * (period-1) + loss[i]) / period
        
        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100.0 - (100.0 / (1.0 + rs))
    
    return result

@cython.boundscheck(False)
@cython.wraparound(False)
def calculate_bollinger_bands(np.ndarray[double, ndim=1] data, int period=20, double deviation=2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    计算布林带的Cython优化版本
    
    Args:
        data: 价格数据数组
        period: 移动平均周期
        deviation: 标准差倍数
            
    Returns:
        Tuple[np.ndarray, np.ndarray, np.ndarray]: 上轨、中轨、下轨
    """
    cdef int n = data.shape[0]
    cdef np.ndarray[double, ndim=1] upper_band = np.zeros(n, dtype=np.float64)
    cdef np.ndarray[double, ndim=1] middle_band = np.zeros(n, dtype=np.float64)
    cdef np.ndarray[double, ndim=1] lower_band = np.zeros(n, dtype=np.float64)
    cdef np.ndarray[double, ndim=1] std = np.zeros(n, dtype=np.float64)
    cdef double window_sum, window_mean, window_var
    cdef int i, j
    
    if n < period:
        return upper_band, middle_band, lower_band  # 如果数据不足，返回全零数组
    
    # 计算SMA作为中轨
    middle_band = calculate_sma(data, period)
    
    # 计算移动标准差
    for i in range(period-1, n):
        window_sum = 0.0
        window_mean = middle_band[i]
        
        # 计算窗口内每个点与均值的平方差之和
        window_var = 0.0
        for j in range(i-period+1, i+1):
            window_var += (data[j] - window_mean) ** 2
        
        # 计算标准差
        std[i] = (window_var / period) ** 0.5
    
    # 计算布林带上下轨
    for i in range(n):
        if i >= period-1:
            upper_band[i] = middle_band[i] + deviation * std[i]
            lower_band[i] = middle_band[i] - deviation * std[i]
        else:
            upper_band[i] = np.nan
            middle_band[i] = np.nan
            lower_band[i] = np.nan
    
    return upper_band, middle_band, lower_band

@cython.boundscheck(False)
@cython.wraparound(False)
def calculate_macd(np.ndarray[double, ndim=1] data, int fast_period=12, int slow_period=26, int signal_period=9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    计算MACD指标的Cython优化版本
    
    Args:
        data: 价格数据数组
        fast_period: 快线周期
        slow_period: 慢线周期
        signal_period: 信号线周期
            
    Returns:
        Tuple[np.ndarray, np.ndarray, np.ndarray]: MACD线, 信号线, 柱状图
    """
    cdef int n = data.shape[0]
    cdef np.ndarray[double, ndim=1] macd_line = np.zeros(n, dtype=np.float64)
    cdef np.ndarray[double, ndim=1] signal_line = np.zeros(n, dtype=np.float64)
    cdef np.ndarray[double, ndim=1] histogram = np.zeros(n, dtype=np.float64)
    
    # 计算快线和慢线EMA
    cdef np.ndarray[double, ndim=1] fast_ema = calculate_ema(data, fast_period)
    cdef np.ndarray[double, ndim=1] slow_ema = calculate_ema(data, slow_period)
    
    # 计算MACD线（快线EMA - 慢线EMA）
    for i in range(n):
        if i >= slow_period-1:
            macd_line[i] = fast_ema[i] - slow_ema[i]
        else:
            macd_line[i] = np.nan
    
    # 计算信号线（MACD的EMA）
    signal_line = calculate_ema(macd_line[slow_period-1:], signal_period)
    
    # 补全信号线数组前面的NaN值
    cdef np.ndarray[double, ndim=1] full_signal_line = np.zeros(n, dtype=np.float64)
    full_signal_line[:slow_period-1+signal_period-1] = np.nan
    full_signal_line[slow_period-1+signal_period-1:] = signal_line[signal_period-1:]
    
    # 计算柱状图（MACD线 - 信号线）
    for i in range(n):
        if i >= slow_period-1+signal_period-1:
            histogram[i] = macd_line[i] - full_signal_line[i]
        else:
            histogram[i] = np.nan
    
    return macd_line, full_signal_line, histogram

@cython.boundscheck(False)
@cython.wraparound(False)
def calculate_volatility(np.ndarray[double, ndim=1] data, int period=14) -> np.ndarray:
    """
    计算价格波动率的Cython优化版本（使用标准差法）
    
    Args:
        data: 价格数据数组
        period: 周期
            
    Returns:
        np.ndarray: 波动率数组（百分比）
    """
    cdef int n = data.shape[0]
    cdef np.ndarray[double, ndim=1] result = np.zeros(n, dtype=np.float64)
    cdef double mean, sum_squared_diff
    cdef int i, j, start_idx
    
    if n < period:
        return result  # 如果数据不足，返回全零数组
    
    # 填充前period-1个位置为NaN
    for i in range(period-1):
        result[i] = np.nan
    
    # 计算每个窗口的波动率
    for i in range(period-1, n):
        start_idx = i - period + 1
        
        # 计算窗口内的平均价格
        mean = 0.0
        for j in range(start_idx, i+1):
            mean += data[j]
        mean /= period
        
        # 计算价格偏差的平方和
        sum_squared_diff = 0.0
        for j in range(start_idx, i+1):
            sum_squared_diff += (data[j] - mean) ** 2
        
        # 计算标准差并转换为百分比
        result[i] = 100.0 * (sum_squared_diff / period) ** 0.5 / mean
    
    return result 