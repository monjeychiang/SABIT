"""
Cython优化模块
包含对计算密集型操作的优化实现
"""

# 导入Cython加速的函数
try:
    from .ws_data_formatter_cy import format_decimal, format_binance_data
    from .trading_cy import calculate_position_value, calculate_margin_requirement
    from .market_data_cy import calculate_indicators
    
    # 标记功能可用状态
    CYTHON_ENABLED = True
except ImportError:
    # 如果Cython模块加载失败，降级使用Python实现
    CYTHON_ENABLED = False
    
    def format_decimal(value):
        """兼容函数，如果Cython模块未编译，则回退到Python实现"""
        from ..utils.ws_data_formatter import WebSocketDataFormatter
        return WebSocketDataFormatter._format_decimal(value)
    
    # 其他兼容函数...
    def format_binance_data(data, formatted_data):
        """兼容函数，如果Cython模块未编译，则回退到Python实现"""
        from ..utils.ws_data_formatter import WebSocketDataFormatter
        return WebSocketDataFormatter._format_binance_data(data, formatted_data)
    
    def calculate_position_value(*args, **kwargs):
        """兼容函数，如果Cython模块未编译，则回退到Python实现"""
        # 默认实现
        return None
    
    def calculate_margin_requirement(*args, **kwargs):
        """兼容函数，如果Cython模块未编译，则回退到Python实现"""
        # 默认实现
        return None
    
    def calculate_indicators(*args, **kwargs):
        """兼容函数，如果Cython模块未编译，则回退到Python实现"""
        # 默认实现
        return None 