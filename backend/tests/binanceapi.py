#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
币安API测试脚本
测试API密钥是否能正常连接币安并获取账户信息
"""

import asyncio
import time
import logging
import json
import sys
import aiohttp
import hashlib
import functools
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import websockets
import traceback

# 使用ccxt库进行交易所API交互
try:
    import ccxt.async_support as ccxt
except ImportError:
    print("请先安装ccxt库: pip install ccxt")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("binance_api_test")

# 延迟统计数据
api_latency_stats = {
    "operations": [],
    "summary": {
        "total_operations": 0,
        "total_time": 0,
        "min_time": float('inf'),
        "max_time": 0,
        "avg_time": 0
    }
}

def measure_latency(operation_name: str = None):
    """API操作延迟测量装饰器
    
    Args:
        operation_name: 操作名称，如果不提供则使用函数名
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 确定操作名称
            op_name = operation_name or func.__name__
            
            # 开始时间
            start_time = time.time()
            logger.info(f"开始执行 {op_name}...")
            
            try:
                # 执行实际操作
                result = await func(*args, **kwargs)
                return result
            finally:
                # 结束时间和延迟计算
                end_time = time.time()
                latency = end_time - start_time
                
                # 记录操作延迟
                api_latency_stats["operations"].append({
                    "name": op_name,
                    "start_time": start_time,
                    "end_time": end_time,
                    "latency": latency,
                    "timestamp": datetime.now().isoformat()
                })
                
                # 更新统计数据
                api_latency_stats["summary"]["total_operations"] += 1
                api_latency_stats["summary"]["total_time"] += latency
                api_latency_stats["summary"]["min_time"] = min(api_latency_stats["summary"]["min_time"], latency)
                api_latency_stats["summary"]["max_time"] = max(api_latency_stats["summary"]["max_time"], latency)
                api_latency_stats["summary"]["avg_time"] = (
                    api_latency_stats["summary"]["total_time"] / 
                    api_latency_stats["summary"]["total_operations"]
                )
                
                logger.info(f"完成 {op_name}，耗时: {latency:.3f}秒")
                
                # 详细延迟分析
                if latency > 1.0:
                    logger.warning(f"⚠️ {op_name} 操作延迟较高: {latency:.3f}秒")
                
        return wrapper
    return decorator

class BinanceApiTester:
    """币安API测试类"""
    
    def __init__(self, api_key: str, api_secret: str):
        """初始化测试器
        
        Args:
            api_key: 币安API密钥
            api_secret: 币安API密钥秘密
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.client = None
        self.common_symbols = ["BTC/USDT", "ETH/USDT", "BNB/USDT"]  # 常用交易对
        self.test_results = {
            "connection": {"success": False, "message": "", "time": 0},
            "account_info": {"success": False, "message": "", "time": 0, "data": None},
            "spot_balance": {"success": False, "message": "", "time": 0, "data": None},
            "futures_balance": {"success": False, "message": "", "time": 0, "data": None},
            "open_orders": {"success": False, "message": "", "time": 0, "data": None},
            "futures_order": {"success": False, "message": "", "time": 0, "data": None},  # 新增期货下单测试结果
            "websocket_account": {"success": False, "message": "", "time": 0, "data": None},  # 新增WebSocket账户数据测试结果
            "latency_stats": {"operations": [], "summary": {}},
            "ws_http_comparison": {"success": False, "message": "", "time": 0, "data": None},
            "connection_comparison": {"success": False, "message": "", "time": 0, "data": None},
            "order_latency": {"success": False, "message": "", "time": 0, "data": None}
        }
        # WebSocket相关属性
        self.ws = None
        self.ws_messages = []
        self.listen_key = None
    
    @measure_latency("获取Listen Key")
    async def get_listen_key(self, market_type: str = "future") -> str:
        """获取币安Listen Key
        
        Args:
            market_type: 市场类型，"spot"或"future"
        
        Returns:
            str: Listen Key
        
        Raises:
            Exception: 获取Listen Key失败时抛出异常
        """
        base_url = "https://fapi.binance.com" if market_type == "future" else "https://api.binance.com"
        endpoint = "/fapi/v1/listenKey" if market_type == "future" else "/api/v3/userDataStream"
        
        headers = {
            "X-MBX-APIKEY": self.api_key
        }
        
        logger.info(f"正在获取{market_type}市场的Listen Key...")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{base_url}{endpoint}", headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        listen_key = data.get("listenKey")
                        if listen_key:
                            logger.info(f"成功获取Listen Key: {listen_key[:8]}...")
                            self.listen_key = listen_key
                            return listen_key
                    
                    error_text = await response.text()
                    error_msg = f"获取Listen Key失败: HTTP {response.status}, {error_text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
        except Exception as e:
            logger.error(f"获取Listen Key异常: {str(e)}")
            raise
    
    @measure_latency("创建交易所客户端")
    async def create_client(self, market_type: str = "spot") -> None:
        """创建交易所客户端
        
        Args:
            market_type: 市场类型，"spot"或"future"
        """
        try:
            start_time = time.time()
            
            # 检查运行环境，确保Windows系统使用正确的事件循环
            if sys.platform.startswith('win'):
                try:
                    import platform
                    logger.info(f"检测到操作系统: {platform.system()} {platform.version()}")
                    current_loop = asyncio.get_event_loop()
                    logger.info(f"当前事件循环类型: {type(current_loop).__name__}")
                    
                    if type(current_loop).__name__ == 'ProactorEventLoop':
                        logger.warning("Windows系统上正在使用ProactorEventLoop，可能与aiodns不兼容")
                except Exception as loop_check_error:
                    logger.warning(f"检查事件循环时出错: {str(loop_check_error)}")
            
            # 记录客户端创建的各阶段延迟
            client_init_start = time.time()
            try:
                self.client = ccxt.binance({
                    'apiKey': self.api_key,
                    'secret': self.api_secret,
                    'enableRateLimit': True,
                    'options': {
                        'defaultType': market_type,
                        'adjustForTimeDifference': True,
                        'warnOnFetchOpenOrdersWithoutSymbol': False,  # 禁用警告
                    }
                })
                client_init_time = time.time() - client_init_start
                logger.info(f"初始化客户端对象耗时: {client_init_time:.3f}秒")
            except Exception as client_error:
                if "aiodns" in str(client_error) and sys.platform.startswith('win'):
                    logger.error(f"创建客户端失败，可能是Windows事件循环问题: {str(client_error)}")
                    logger.info("尝试安装和配置所需依赖: pip install aiodns windows-curses")
                    logger.info("如果已安装，请确保在运行前设置正确的事件循环策略")
                    
                    # 建议用户采取的修复步骤
                    suggestion = (
                        "\n修复建议:\n"
                        "1. 安装必要的依赖: pip install aiodns windows-curses\n"
                        "2. 在代码开头添加以下代码:\n"
                        "import asyncio\n"
                        "if sys.platform.startswith('win'):\n"
                        "    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())\n"
                    )
                    logger.info(suggestion)
                    
                raise
            
            # 加载市场
            markets_start = time.time()
            await self.client.load_markets()
            markets_time = time.time() - markets_start
            logger.info(f"加载市场数据耗时: {markets_time:.3f}秒")
            
            elapsed = time.time() - start_time
            
            self.test_results["connection"] = {
                "success": True,
                "message": f"成功连接到币安{market_type}市场",
                "time": elapsed,
                "details": {
                    "client_init_time": client_init_time,
                    "markets_loading_time": markets_time
                }
            }
            logger.info(f"成功连接到币安{market_type}市场，总耗时: {elapsed:.2f}秒")
            
        except Exception as e:
            elapsed = time.time() - start_time if 'start_time' in locals() else 0
            error_msg = f"连接币安API失败: {str(e)}"
            self.test_results["connection"] = {
                "success": False,
                "message": error_msg,
                "time": elapsed
            }
            logger.error(error_msg)
            
            # 针对常见错误提供更详细的排查建议
            if "aiodns" in str(e) and "SelectorEventLoop" in str(e):
                logger.warning("错误与Windows系统上的事件循环和aiodns库有关")
                logger.info("请确保已按建议设置了正确的事件循环策略")
            elif "Max retries exceeded" in str(e) or "Connection" in str(e):
                logger.warning("可能是网络连接问题，请检查您的网络连接是否正常")
                logger.info("如果使用代理或VPN，请确保它们配置正确")
            elif "Authentication" in str(e) or "API key" in str(e):
                logger.warning("可能是API密钥问题，请检查您的API密钥和密钥是否正确")
                logger.info("特别注意API密钥中的空格和特殊字符")
            
            # 确保客户端关闭
            if self.client:
                try:
                    await self.client.close()
                    self.client = None
                except Exception:
                    pass
            raise
    
    @measure_latency("获取账户信息")
    async def test_get_account_info(self) -> None:
        """测试获取账户信息"""
        try:
            start_time = time.time()
            # 确保我们有一个活跃的客户端
            if not self.client:
                await self.create_client()
            
            # 记录API调用延迟
            api_call_start = time.time()
            account_info = await self.client.fetch_balance()
            api_call_time = time.time() - api_call_start
            logger.info(f"账户信息API调用耗时: {api_call_time:.3f}秒")
            
            elapsed = time.time() - start_time
            
            # 筛选有余额的币种
            non_zero_balances = {
                currency: {
                    "free": float(balance['free']),
                    "used": float(balance['used']),
                    "total": float(balance['total'])
                }
                for currency, balance in account_info.items()
                if (isinstance(balance, dict) and
                    'free' in balance and
                    'used' in balance and
                    'total' in balance and
                    float(balance['total']) > 0)
                        }
            
            self.test_results["account_info"] = {
                "success": True,
                "message": f"成功获取账户信息，发现{len(non_zero_balances)}个有余额的币种",
                "time": elapsed,
                "data": non_zero_balances,
                "details": {
                    "api_call_time": api_call_time
                }
            }
            logger.info(f"成功获取账户信息，发现{len(non_zero_balances)}个有余额的币种，总耗时: {elapsed:.2f}秒")
            
        except Exception as e:
            elapsed = time.time() - start_time if 'start_time' in locals() else 0
            error_msg = f"获取账户信息失败: {str(e)}"
            self.test_results["account_info"] = {
                "success": False,
                "message": error_msg,
                "time": elapsed
            }
            logger.error(error_msg)
    
    @measure_latency("获取现货账户余额")
    async def test_get_spot_balance(self) -> None:
        """测试获取现货账户余额"""
        # 保存现有的客户端
        previous_client = self.client
        
        try:
            # 创建一个现货市场客户端
            create_client_start = time.time()
            await self.create_client(market_type="spot")
            create_client_time = time.time() - create_client_start
            
            start_time = time.time()
            
            # 记录API调用延迟
            api_call_start = time.time()
            balance = await self.client.fetch_balance()
            api_call_time = time.time() - api_call_start
            logger.info(f"现货余额API调用耗时: {api_call_time:.3f}秒")
            
            elapsed = time.time() - start_time
            
            # 筛选有余额的币种
            non_zero_balances = {
                currency: {
                    "free": float(balance['free']),
                    "used": float(balance['used']),
                    "total": float(balance['total'])
                }
                for currency, balance in balance.items()
                if (isinstance(balance, dict) and
                    'free' in balance and
                    'used' in balance and
                    'total' in balance and
                    float(balance['total']) > 0)
            }
            
            self.test_results["spot_balance"] = {
                "success": True,
                "message": f"成功获取现货账户余额，发现{len(non_zero_balances)}个有余额的币种",
                "time": elapsed,
                "data": non_zero_balances,
                "details": {
                    "create_client_time": create_client_time,
                    "api_call_time": api_call_time
                }
            }
            logger.info(f"成功获取现货账户余额，发现{len(non_zero_balances)}个有余额的币种，总耗时: {elapsed:.2f}秒")
            
        except Exception as e:
            elapsed = time.time() - start_time if 'start_time' in locals() else 0
            error_msg = f"获取现货账户余额失败: {str(e)}"
            self.test_results["spot_balance"] = {
                "success": False,
                "message": error_msg,
                "time": elapsed
            }
            logger.error(error_msg)
            
        finally:
            # 关闭现货客户端
            if self.client and self.client != previous_client:
                try:
                    await self.client.close()
                except Exception as e:
                    logger.error(f"关闭现货客户端失败: {str(e)}")
            
            # 恢复先前的客户端
            self.client = previous_client
    
    @measure_latency("获取合约账户余额")
    async def test_get_futures_balance(self) -> None:
        """测试获取合约账户余额"""
        # 保存现有的客户端
        previous_client = self.client
        
        try:
            # 创建一个合约市场客户端
            create_client_start = time.time()
            await self.create_client(market_type="future")
            create_client_time = time.time() - create_client_start
            
            start_time = time.time()
            
            # 记录API调用延迟
            api_call_start = time.time()
            balance = await self.client.fetch_balance()
            api_call_time = time.time() - api_call_start
            logger.info(f"合约余额API调用耗时: {api_call_time:.3f}秒")
            
            elapsed = time.time() - start_time
            
            # 筛选有余额的币种
            non_zero_balances = {
                currency: {
                    "free": float(balance['free']),
                    "used": float(balance['used']),
                    "total": float(balance['total'])
                }
                for currency, balance in balance.items()
                if (isinstance(balance, dict) and
                    'free' in balance and
                    'used' in balance and
                    'total' in balance and
                    float(balance['total']) > 0)
            }
            
            self.test_results["futures_balance"] = {
                "success": True,
                "message": f"成功获取合约账户余额，发现{len(non_zero_balances)}个有余额的币种",
                "time": elapsed,
                "data": non_zero_balances,
                "details": {
                    "create_client_time": create_client_time,
                    "api_call_time": api_call_time
                }
            }
            logger.info(f"成功获取合约账户余额，发现{len(non_zero_balances)}个有余额的币种，总耗时: {elapsed:.2f}秒")
            
        except Exception as e:
            elapsed = time.time() - start_time if 'start_time' in locals() else 0
            error_msg = f"获取合约账户余额失败: {str(e)}"
            self.test_results["futures_balance"] = {
                "success": False,
                "message": error_msg,
                "time": elapsed
            }
            logger.error(error_msg)
            
        finally:
            # 关闭合约客户端
            if self.client and self.client != previous_client:
                try:
                    await self.client.close()
                except Exception as e:
                    logger.error(f"关闭合约客户端失败: {str(e)}")
            
            # 恢复先前的客户端
            self.client = previous_client
    
    @measure_latency("获取未成交订单")
    async def test_get_open_orders(self) -> None:
        """测试获取当前未成交订单"""
        try:
            start_time = time.time()
            # 确保我们有一个活跃的客户端
            if not self.client:
                await self.create_client()
            
            # 获取常用交易对的未成交订单
            all_open_orders = []
            orders_by_symbol = {}
            
            # 记录每个阶段的延迟
            latency_details = {}
            
            # 尝试不带symbol参数获取所有订单
            try:
                logger.info("尝试获取所有未成交订单...")
                all_orders_start = time.time()
                open_orders = await self.client.fetch_open_orders()
                all_orders_time = time.time() - all_orders_start
                latency_details["all_orders_api_call"] = all_orders_time
                logger.info(f"获取所有未成交订单API调用耗时: {all_orders_time:.3f}秒")
                
                if open_orders:
                    all_open_orders.extend(open_orders)
                    logger.info(f"成功获取所有未成交订单: {len(open_orders)}个")
            except Exception as e:
                logger.warning(f"获取所有未成交订单失败，将尝试逐个交易对获取: {str(e)}")
                
                # 如果不成功，尝试逐个交易对获取
                symbol_latencies = {}
                for symbol in self.common_symbols:
                    try:
                        logger.info(f"获取{symbol}的未成交订单...")
                        symbol_start = time.time()
                        symbol_orders = await self.client.fetch_open_orders(symbol)
                        symbol_time = time.time() - symbol_start
                        symbol_latencies[symbol] = symbol_time
                        logger.info(f"获取{symbol}未成交订单API调用耗时: {symbol_time:.3f}秒")
                        
                        if symbol_orders:
                            all_open_orders.extend(symbol_orders)
                            orders_by_symbol[symbol] = len(symbol_orders)
                            logger.info(f"成功获取{symbol}的未成交订单: {len(symbol_orders)}个")
                    except Exception as symbol_error:
                        logger.warning(f"获取{symbol}的未成交订单失败: {str(symbol_error)}")
                
                latency_details["symbol_orders_api_calls"] = symbol_latencies
            
            elapsed = time.time() - start_time
            
            # 处理结果
            if all_open_orders:
                # 格式化订单信息
                formatted_orders = []
                for order in all_open_orders:
                    formatted_order = {
                        "id": order.get('id'),
                        "symbol": order.get('symbol'),
                        "type": order.get('type'),
                        "side": order.get('side'),
                        "price": order.get('price'),
                        "amount": order.get('amount'),
                        "cost": order.get('cost'),
                        "filled": order.get('filled'),
                        "remaining": order.get('remaining'),
                        "status": order.get('status'),
                        "timestamp": order.get('timestamp'),
                        "datetime": order.get('datetime')
                    }
                    formatted_orders.append(formatted_order)
                
                self.test_results["open_orders"] = {
                    "success": True,
                    "message": f"成功获取未成交订单，共{len(all_open_orders)}个",
                    "time": elapsed,
                    "data": {
                        "orders": formatted_orders,
                        "symbols_summary": orders_by_symbol
                    },
                    "details": latency_details
                }
                logger.info(f"成功获取未成交订单，共{len(all_open_orders)}个，总耗时: {elapsed:.2f}秒")
            else:
                self.test_results["open_orders"] = {
                    "success": True,
                    "message": "没有找到未成交订单",
                    "time": elapsed,
                    "data": [],
                    "details": latency_details
                }
                logger.info(f"没有找到未成交订单，总耗时: {elapsed:.2f}秒")
            
        except Exception as e:
            elapsed = time.time() - start_time if 'start_time' in locals() else 0
            error_msg = f"获取未成交订单失败: {str(e)}"
            self.test_results["open_orders"] = {
                "success": False,
                "message": error_msg,
                "time": elapsed
            }
            logger.error(error_msg)
    
    @measure_latency("期货下单测试")
    async def test_place_futures_order(self) -> None:
        """测试开设ETH合约多单，杠杆10倍，价值100 USDT"""
        # 保存现有的客户端
        previous_client = self.client
        
        try:
            # 创建一个合约市场客户端
            create_client_start = time.time()
            await self.create_client(market_type="future")
            create_client_time = time.time() - create_client_start
            
            # 设置ETH/USDT交易对和下单参数
            symbol = "ETH/USDT"
            leverage = 10
            order_value = 100  # USDT
            
            # 获取当前价格
            logger.info(f"获取 {symbol} 当前价格...")
            ticker_start = time.time()
            ticker = await self.client.fetch_ticker(symbol)
            ticker_time = time.time() - ticker_start
            logger.info(f"获取{symbol}价格API调用耗时: {ticker_time:.3f}秒")
            
            current_price = ticker['last']
            
            # 计算订单数量 (价值/价格)
            order_amount = order_value / current_price
            
            # 由于精度问题，需要对数量进行处理
            logger.info(f"处理订单数量精度...")
            market = self.client.market(symbol)
            precision = market['precision']['amount']
            if isinstance(precision, int):
                # 如果精度是小数位数
                order_amount = float(round(order_amount, precision))
            else:
                # 如果精度是最小交易单位
                order_amount = float(round(order_amount / precision) * precision)
            
            start_time = time.time()
            
            # 记录每个阶段的延迟
            latency_details = {
                "create_client_time": create_client_time,
                "ticker_api_call": ticker_time
            }
            
            # 设置杠杆
            logger.info(f"设置 {symbol} 杠杆为 {leverage}倍...")
            leverage_start = time.time()
            leverage_result = await self.client.set_leverage(leverage, symbol)
            leverage_time = time.time() - leverage_start
            latency_details["set_leverage_api_call"] = leverage_time
            logger.info(f"设置杠杆API调用耗时: {leverage_time:.3f}秒")
            
            # 设置全仓模式（用户设置为全仓）
            logger.info(f"设置 {symbol} 为全仓模式...")
            margin_mode_start = time.time()
            try:
                margin_mode_result = await self.client.set_margin_mode('cross', symbol)
                logger.info(f"成功设置为全仓模式")
            except Exception as e:
                # 如果已经是全仓模式，币安API会返回错误
                logger.warning(f"设置全仓模式失败，可能已经是全仓模式: {str(e)}")
                margin_mode_result = {"margin_mode": "cross", "status": "已存在或不需要更改"}
            margin_mode_time = time.time() - margin_mode_start
            latency_details["set_margin_mode_api_call"] = margin_mode_time
            logger.info(f"设置保证金模式API调用耗时: {margin_mode_time:.3f}秒")
            
            # 检查持仓模式(单向模式或对冲模式)
            logger.info(f"检查当前持仓模式...")
            # 用户表示已使用双向持仓模式
            position_mode = "hedge"
            logger.info(f"使用双向持仓模式(Hedge Mode)")
            
            # 下限价多单 (为了安全，使用limit而不是market)
            # 价格略高于市价以确保能够成交
            price = current_price * 1.005  # 价格上浮0.5%
            
            # 准备下单参数 - 移除导致错误的reduceOnly参数
            order_params = {
                'timeInForce': 'GTC',    # 成交为止
                'postOnly': False,        # 非仅挂单模式，允许成为吃单
                'positionSide': 'LONG'    # 在双向模式下，明确指定持仓方向为多头
            }
            
            # 尝试下单
            logger.info(f"尝试以双向模式(Hedge Mode)下单，持仓方向为多头(LONG)...")
            try:
                order_start = time.time()
                order_result = await self.client.create_order(
                    symbol=symbol,
                    type='limit',
                    side='buy',
                    amount=order_amount,
                    price=price,
                    params=order_params
                )
                order_time = time.time() - order_start
                latency_details["create_order_api_call"] = order_time
                logger.info(f"下单API调用耗时: {order_time:.3f}秒")
                logger.info(f"双向模式下单成功!")
            except Exception as hedge_error:
                error_msg = str(hedge_error)
                logger.error(f"双向模式下单失败: {error_msg}")
                raise hedge_error
            
            elapsed = time.time() - start_time
            
            if order_result:
                self.test_results["futures_order"] = {
                    "success": True,
                    "message": f"成功下ETH合约多单，杠杆{leverage}倍，价值{order_value} USDT，持仓模式: 双向，全仓",
                    "time": elapsed,
                    "data": {
                        "order_details": {
                            "symbol": symbol,
                            "leverage": leverage,
                            "price": price,
                            "amount": order_amount,
                            "value": order_value,
                            "current_price": current_price,
                            "position_mode": position_mode,
                            "margin_mode": "cross"
                        },
                        "order_result": {
                            "id": order_result.get('id', 'unknown'),
                            "status": order_result.get('status', 'unknown'),
                            "filled": order_result.get('filled', 0),
                            "remaining": order_result.get('remaining', order_amount),
                            "price": order_result.get('price', price),
                            "cost": order_result.get('cost', 0)
                        }
                    },
                    "details": latency_details
                }
                logger.info(f"成功下ETH合约多单，订单ID: {order_result.get('id', 'unknown')}, 总耗时: {elapsed:.2f}秒")
            else:
                raise Exception(f"下单失败: {error_msg}")
            
        except Exception as e:
            elapsed = time.time() - start_time if 'start_time' in locals() else 0
            error_msg = f"下ETH合约多单失败: {str(e)}"
            self.test_results["futures_order"] = {
                "success": False,
                "message": error_msg,
                "time": elapsed,
                "data": {
                    "error_details": str(e)
                } if 'start_time' in locals() else None
            }
            logger.error(error_msg)
            
            # 提供更详细的错误信息和解决建议
            if "positionSide" in str(e):
                suggestion = (
                    "下单时可能存在持仓方向设置问题。请检查:\n"
                    "1. 您的账户持仓模式是否确实为双向模式(Hedge Mode)\n"
                    "2. 如果是双向模式，下单时必须指定positionSide参数(LONG或SHORT)\n"
                    "3. 如果是单向模式，则不应该指定positionSide参数"
                )
                logger.info(f"建议: {suggestion}")
            elif "margin mode" in str(e) or "marginMode" in str(e):
                suggestion = (
                    "设置保证金模式失败。请检查:\n"
                    "1. 您的账户是否已经设置了全仓或逐仓模式\n"
                    "2. 您是否有足够的权限修改保证金模式"
                )
                logger.info(f"建议: {suggestion}")
                
        finally:
            # 关闭合约客户端
            if self.client and self.client != previous_client:
                try:
                    await self.client.close()
                except Exception as e:
                    logger.error(f"关闭合约客户端失败: {str(e)}")
            
            # 恢复先前的客户端
            self.client = previous_client
    
    @measure_latency("WebSocket账户数据测试")
    async def test_websocket_account(self, market_type: str = "future", duration: int = 60) -> None:
        """测试WebSocket账户数据推送
        
        连接到币安WebSocket API，监听账户数据更新
        
        Args:
            market_type: 市场类型，"spot"或"future"
            duration: 测试持续时间(秒)
        """
        try:
            start_time = time.time()
            
            # 记录各个阶段的延迟
            latency_details = {}
            
            # 先获取Listen Key
            try:
                listen_key_start = time.time()
                listen_key = await self.get_listen_key(market_type)
                listen_key_time = time.time() - listen_key_start
                latency_details["get_listen_key"] = listen_key_time
                logger.info(f"获取Listen Key耗时: {listen_key_time:.3f}秒")
            except Exception as e:
                error_msg = f"获取Listen Key失败: {str(e)}"
                self.test_results["websocket_account"] = {
                    "success": False,
                    "message": error_msg,
                    "time": time.time() - start_time,
                    "data": None
                }
                logger.error(error_msg)
                return
            
            # 构建WebSocket URL
            ws_base_url = "wss://fstream.binance.com/ws/" if market_type == "future" else "wss://stream.binance.com/ws/"
            ws_url = f"{ws_base_url}{listen_key}"
            
            logger.info(f"正在连接到WebSocket: {ws_url[:30]}...")
            
            # 记录收到的消息
            messages_received = 0
            last_account_update = None
            connection_time = None
            ws_session = None
            
            try:
                ws_connect_start = time.time()
                ws_session = aiohttp.ClientSession()
                self.ws = await ws_session.ws_connect(ws_url, heartbeat=30)
                
                connection_time = time.time()
                ws_connect_time = connection_time - ws_connect_start
                latency_details["websocket_connect"] = ws_connect_time
                logger.info(f"WebSocket连接耗时: {ws_connect_time:.3f}秒")
                logger.info(f"WebSocket连接成功，将监听{duration}秒...")
                
                # 设置结束时间
                end_time = time.time() + duration
                
                # 监听消息
                first_message_time = None
                while time.time() < end_time:
                    try:
                        # 设置超时，确保能够正常退出循环
                        msg = await asyncio.wait_for(
                            self.ws.receive(), 
                            timeout=min(5, end_time - time.time())
                        )
                        
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            if messages_received == 0:
                                first_message_time = time.time() - connection_time
                                latency_details["first_message_latency"] = first_message_time
                                logger.info(f"收到第一条WebSocket消息的延迟: {first_message_time:.3f}秒")
                                
                            messages_received += 1
                            data = json.loads(msg.data)
                            
                            # 保存消息
                            self.ws_messages.append(data)
                            
                            # 处理不同类型的消息
                            if "e" in data:
                                event_type = data.get("e")
                                logger.info(f"收到WebSocket事件: {event_type}")
                                
                                # 账户更新事件
                                if event_type == "ACCOUNT_UPDATE":
                                    last_account_update = data
                                    logger.info(f"收到账户更新: {json.dumps(data, indent=2)[:200]}...")
                                elif event_type == "MARGIN_CALL":
                                    logger.info(f"收到保证金通知: {json.dumps(data, indent=2)[:200]}...")
                                
                            else:
                                logger.info(f"收到其他WebSocket消息: {json.dumps(data, indent=2)[:200]}...")
                        
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            logger.error(f"WebSocket连接错误: {msg}")
                            break
                            
                        elif msg.type == aiohttp.WSMsgType.CLOSED:
                            logger.warning("WebSocket连接已关闭")
                            break
                            
                    except asyncio.TimeoutError:
                        # 超时，继续循环直到达到总持续时间
                        continue
                    except Exception as e:
                        logger.error(f"处理WebSocket消息异常: {str(e)}")
                
                elapsed = time.time() - start_time
                connection_duration = time.time() - connection_time if connection_time else 0
                
                # 保存测试结果
                self.test_results["websocket_account"] = {
                    "success": True,
                    "message": f"成功监听WebSocket {connection_duration:.1f}秒，收到{messages_received}条消息",
                    "time": elapsed,
                    "data": {
                        "messages_count": messages_received,
                        "connection_duration": connection_duration,
                        "last_account_update": last_account_update,
                        "all_messages": self.ws_messages[:5]  # 只保存前5条消息避免数据过大
                    },
                    "details": latency_details
                }
                
                logger.info(f"WebSocket测试完成，共收到{messages_received}条消息，总耗时: {elapsed:.2f}秒")
                
            except Exception as e:
                elapsed = time.time() - start_time
                error_msg = f"WebSocket连接异常: {str(e)}"
                self.test_results["websocket_account"] = {
                    "success": False,
                    "message": error_msg,
                    "time": elapsed,
                    "data": None
                }
                logger.error(error_msg)
            
            finally:
                # 关闭WebSocket连接
                if self.ws and not self.ws.closed:
                    await self.ws.close()
                if ws_session:
                    await ws_session.close()
                
        except Exception as e:
            elapsed = time.time() - start_time if 'start_time' in locals() else 0
            error_msg = f"WebSocket测试失败: {str(e)}"
            self.test_results["websocket_account"] = {
                "success": False,
                "message": error_msg,
                "time": elapsed,
                "data": None
            }
            logger.error(error_msg)
    
    @measure_latency("WebSocket与HTTP API对比测试")
    async def test_ws_vs_http(self, iterations: int = 10) -> Dict[str, Any]:
        """测试WebSocket和HTTP API的性能对比
        
        对比通过WebSocket和HTTP API获取相同数据的性能差异
        
        Args:
            iterations: 测试重复次数
            
        Returns:
            Dict: 测试结果对比
        """
        test_results = {
            "http": {
                "times": [],
                "avg_time": 0,
                "min_time": float('inf'),
                "max_time": 0
            },
            "websocket": {
                "times": [],
                "avg_time": 0,
                "min_time": float('inf'),
                "max_time": 0,
                "message_count": 0,
                "first_message_time": 0
            },
            "comparison": {
                "improvement_ratio": 0,
                "time_saved": 0
            }
        }
        
        try:
            logger.info(f"开始执行WebSocket与HTTP API对比测试 ({iterations}次)...")
            
            # 确保客户端已创建
            if not self.client:
                await self.create_client()
            
            # 1. HTTP API 测试
            logger.info("测试HTTP API性能...")
            symbol = "BTC/USDT"
            
            for i in range(iterations):
                logger.info(f"HTTP API测试 [{i+1}/{iterations}]")
                
                # 使用HTTP API获取价格
                http_start = time.time()
                await self.client.fetch_ticker(symbol)
                elapsed = time.time() - http_start
                
                # 记录耗时
                test_results["http"]["times"].append(elapsed)
                test_results["http"]["min_time"] = min(test_results["http"]["min_time"], elapsed)
                test_results["http"]["max_time"] = max(test_results["http"]["max_time"], elapsed)
                
                logger.info(f"HTTP API请求完成，耗时: {elapsed:.3f}秒")
                
                # 避免API限制
                await asyncio.sleep(0.5)
            
            # 计算HTTP平均耗时
            if test_results["http"]["times"]:
                test_results["http"]["avg_time"] = sum(test_results["http"]["times"]) / len(test_results["http"]["times"])
            
            # 2. WebSocket测试
            logger.info("测试WebSocket性能...")
            
            # 创建WebSocket连接
            ws_uri = f"wss://stream.binance.com:9443/ws/{symbol.lower().replace('/', '')}_ticker"
            ws_connect_start = time.time()
            ws = await websockets.connect(ws_uri)
            ws_connect_time = time.time() - ws_connect_start
            
            try:
                # 等待并处理WebSocket消息
                messages_received = 0
                first_message_time = None
                
                # 启动WebSocket连接
                ws_start = time.time()
                
                for i in range(iterations):
                    # 接收消息
                    message_start = time.time()
                    message = await asyncio.wait_for(ws.recv(), timeout=5)
                    message_time = time.time() - message_start
                    
                    # 记录首条消息时间
                    if messages_received == 0:
                        first_message_time = message_time
                        test_results["websocket"]["first_message_time"] = first_message_time
                    
                    # 记录耗时
                    test_results["websocket"]["times"].append(message_time)
                    test_results["websocket"]["min_time"] = min(test_results["websocket"]["min_time"], message_time)
                    test_results["websocket"]["max_time"] = max(test_results["websocket"]["max_time"], message_time)
                    
                    messages_received += 1
                    logger.info(f"WebSocket消息接收完成 [{messages_received}/{iterations}]，耗时: {message_time:.5f}秒")
                
                # 计算WebSocket平均耗时
                if test_results["websocket"]["times"]:
                    test_results["websocket"]["avg_time"] = sum(test_results["websocket"]["times"]) / len(test_results["websocket"]["times"])
                
                test_results["websocket"]["message_count"] = messages_received
                
            finally:
                # 关闭WebSocket连接
                if ws and not ws.closed:
                    await ws.close()
            
            # 计算比较结果
            if test_results["http"]["avg_time"] > 0 and test_results["websocket"]["avg_time"] > 0:
                test_results["comparison"]["improvement_ratio"] = test_results["http"]["avg_time"] / test_results["websocket"]["avg_time"]
                test_results["comparison"]["time_saved"] = test_results["http"]["avg_time"] - test_results["websocket"]["avg_time"]
            
            # 添加WebSocket连接时间
            test_results["websocket"]["connection_time"] = ws_connect_time
            
            # 添加到测试结果
            self.test_results["ws_http_comparison"] = {
                "success": True,
                "message": f"WebSocket比HTTP API快{test_results['comparison']['improvement_ratio']:.2f}倍",
                "time": 0,
                "data": test_results
            }
            
            return test_results
            
        except Exception as e:
            error_msg = f"WebSocket与HTTP API对比测试失败: {str(e)}"
            logger.error(error_msg)
            
            self.test_results["ws_http_comparison"] = {
                "success": False,
                "message": error_msg,
                "time": 0,
                "data": None
            }
            
            return {
                "error": error_msg
            }
    
    def print_ws_http_comparison(self) -> None:
        """打印WebSocket与HTTP API的对比结果"""
        if "ws_http_comparison" not in self.test_results:
            print("未执行WebSocket与HTTP API对比测试")
            return
        
        test_data = self.test_results["ws_http_comparison"].get("data")
        if not test_data:
            print("WebSocket与HTTP API对比测试数据不可用")
            return
            
        print("\n" + "=" * 80)
        print("WebSocket与HTTP API性能对比")
        print("=" * 80)
        
        # 打印统计信息
        print(f"HTTP API平均耗时: {test_data['http']['avg_time']:.5f}秒")
        print(f"WebSocket平均消息接收耗时: {test_data['websocket']['avg_time']:.5f}秒")
        print(f"WebSocket连接建立耗时: {test_data.get('websocket').get('connection_time', 0):.3f}秒")
        print(f"WebSocket首条消息接收耗时: {test_data.get('websocket').get('first_message_time', 0):.5f}秒")
        print(f"性能提升比例: {test_data['comparison']['improvement_ratio']:.2f}倍")
        print(f"平均节省时间: {test_data['comparison']['time_saved']:.5f}秒")
        
        # 打印详细数据
        print("\n详细测试数据:")
        print(f"{'测试':<5} {'HTTP API(秒)':<15} {'WebSocket(秒)':<15} {'节省时间(秒)':<15} {'提升比例':<10}")
        print("-" * 60)
        
        for i in range(min(len(test_data["http"]["times"]), len(test_data["websocket"]["times"]))):
            http_time = test_data["http"]["times"][i]
            ws_time = test_data["websocket"]["times"][i]
            saved = http_time - ws_time
            ratio = http_time / ws_time if ws_time > 0 else float('inf')
            
            print(f"{i+1:<5} {http_time:<15.5f} {ws_time:<15.5f} {saved:<15.5f} {ratio:<10.2f}倍")
        
        # 展示结论
        print("\n结论:")
        if test_data['comparison']['improvement_ratio'] > 20:
            print("✅ WebSocket提供了极其显著的性能提升，对于需要实时数据的场景，强烈推荐使用WebSocket")
        elif test_data['comparison']['improvement_ratio'] > 10:
            print("✅ WebSocket提供了显著的性能提升，对于需要实时数据的场景，推荐使用WebSocket")
        elif test_data['comparison']['improvement_ratio'] > 5:
            print("✅ WebSocket提供了明显的性能提升，适合实时数据场景")
        elif test_data['comparison']['improvement_ratio'] > 1:
            print("✅ WebSocket有一定性能优势，具体使用应根据应用场景需求")
        else:
            print("⚠️ 在此测试中，WebSocket性能提升不明显，可能需要进一步调查")
        
        print("\n注意事项:")
        print("- WebSocket初始连接需要额外的建立时间，但后续消息接收速度极快")
        print("- 对于需要持续接收大量数据的场景，WebSocket的优势更为明显")
        print("- WebSocket需要处理连接维护、心跳和重连等机制")
        
        print("\n" + "=" * 80)

    def print_latency_stats(self) -> None:
        """打印延迟统计信息"""
        print("\n" + "=" * 80)
        print("API延迟统计")
        print("=" * 80)
        
        # 复制全局延迟统计信息到测试结果
        self.test_results["latency_stats"] = {
            "operations": api_latency_stats["operations"],
            "summary": api_latency_stats["summary"]
        }
        
        # 打印汇总信息
        summary = api_latency_stats["summary"]
        print(f"总操作数: {summary['total_operations']}")
        print(f"平均延迟: {summary['avg_time']:.3f}秒")
        print(f"最小延迟: {summary['min_time']:.3f}秒")
        print(f"最大延迟: {summary['max_time']:.3f}秒")
        print(f"总延迟时间: {summary['total_time']:.3f}秒")
        
        # 按操作类型分组统计
        operations_by_type = {}
        for op in api_latency_stats["operations"]:
            if op["name"] not in operations_by_type:
                operations_by_type[op["name"]] = {
                    "count": 0,
                    "total_time": 0,
                    "min_time": float('inf'),
                    "max_time": 0
                }
            
            stats = operations_by_type[op["name"]]
            stats["count"] += 1
            stats["total_time"] += op["latency"]
            stats["min_time"] = min(stats["min_time"], op["latency"])
            stats["max_time"] = max(stats["max_time"], op["latency"])
        
        # 打印各操作类型的延迟统计
        print("\n操作类型延迟统计:")
        print(f"{'操作名称':<30} {'次数':<8} {'平均延迟(秒)':<15} {'最小延迟(秒)':<15} {'最大延迟(秒)':<15}")
        print("-" * 83)
        
        for name, stats in operations_by_type.items():
            avg_time = stats["total_time"] / stats["count"]
            print(f"{name:<30} {stats['count']:<8} {avg_time:<15.3f} {stats['min_time']:<15.3f} {stats['max_time']:<15.3f}")
        
        print("\n" + "=" * 80)
        
        # 分析延迟问题
        print("\n延迟分析:")
        high_latency_ops = [op for op in api_latency_stats["operations"] if op["latency"] > 1.0]
        if high_latency_ops:
            print(f"发现{len(high_latency_ops)}个延迟较高的操作:")
            for op in sorted(high_latency_ops, key=lambda x: x["latency"], reverse=True)[:5]:  # 显示最慢的5个
                print(f"  - {op['name']}: {op['latency']:.3f}秒 于 {op['timestamp']}")
        else:
            print("  未发现明显的延迟问题。")
            
        print("\n延迟分布:")
        latency_distribution = {
            "<0.1秒": 0,
            "0.1-0.5秒": 0,
            "0.5-1秒": 0,
            "1-2秒": 0,
            "2-5秒": 0,
            ">5秒": 0
        }
        
        for op in api_latency_stats["operations"]:
            latency = op["latency"]
            if latency < 0.1:
                latency_distribution["<0.1秒"] += 1
            elif latency < 0.5:
                latency_distribution["0.1-0.5秒"] += 1
            elif latency < 1:
                latency_distribution["0.5-1秒"] += 1
            elif latency < 2:
                latency_distribution["1-2秒"] += 1
            elif latency < 5:
                latency_distribution["2-5秒"] += 1
            else:
                latency_distribution[">5秒"] += 1
        
        for range_name, count in latency_distribution.items():
            percentage = (count / summary["total_operations"]) * 100 if summary["total_operations"] > 0 else 0
            print(f"  {range_name}: {count} 操作 ({percentage:.1f}%)")
            
        print("\n" + "=" * 80)

    @measure_latency("连接池与新建连接对比测试")
    async def test_connection_vs_pool(self, iterations: int = 5) -> Dict[str, Any]:
        """测试连接池与每次新建连接的性能对比
        
        多次执行相同的API操作，对比两种连接方式的性能差异
        
        Args:
            iterations: 每种方式的测试重复次数
            
        Returns:
            Dict: 测试结果对比
        """
        test_results = {
            "new_connection": {
                "times": [],
                "avg_time": 0,
                "min_time": float('inf'),
                "max_time": 0
            },
            "connection_pool": {
                "times": [],
                "avg_time": 0,
                "min_time": float('inf'),
                "max_time": 0
            },
            "comparison": {
                "improvement_ratio": 0,
                "time_saved": 0
            }
        }
        
        try:
            logger.info(f"开始执行连接池与新建连接对比测试 ({iterations}次)...")
            
            # 1. 每次新建连接的测试
            logger.info("测试每次新建连接的性能...")
            for i in range(iterations):
                logger.info(f"新建连接测试 [{i+1}/{iterations}]")
                
                # 创建新连接
                new_client_start = time.time()
                temp_client = ccxt.binance({
                    'apiKey': self.api_key,
                    'secret': self.api_secret,
                    'enableRateLimit': True,
                    'options': {
                        'defaultType': 'spot',
                        'adjustForTimeDifference': True,
                    }
                })
                
                try:
                    # 加载市场
                    await temp_client.load_markets()
                    
                    # 执行简单API操作
                    await temp_client.fetch_balance()
                    
                    # 记录总耗时
                    elapsed = time.time() - new_client_start
                    test_results["new_connection"]["times"].append(elapsed)
                    test_results["new_connection"]["min_time"] = min(test_results["new_connection"]["min_time"], elapsed)
                    test_results["new_connection"]["max_time"] = max(test_results["new_connection"]["max_time"], elapsed)
                    
                    logger.info(f"新建连接测试完成，耗时: {elapsed:.3f}秒")
                    
                finally:
                    # 确保关闭连接
                    await temp_client.close()
                
                # 等待一小段时间避免API限制
                await asyncio.sleep(1)
            
            # 计算平均时间
            if test_results["new_connection"]["times"]:
                test_results["new_connection"]["avg_time"] = sum(test_results["new_connection"]["times"]) / len(test_results["new_connection"]["times"])
            
            # 2. 连接池重用测试
            logger.info("测试连接池性能...")
            
            # 确保我们有一个连接池客户端
            if not self.client:
                await self.create_client()
            
            await asyncio.sleep(1)  # 确保客户端已准备好
            
            for i in range(iterations):
                logger.info(f"连接池测试 [{i+1}/{iterations}]")
                
                # 重用现有连接
                pool_start = time.time()
                
                # 执行简单API操作
                await self.client.fetch_balance()
                
                # 记录总耗时
                elapsed = time.time() - pool_start
                test_results["connection_pool"]["times"].append(elapsed)
                test_results["connection_pool"]["min_time"] = min(test_results["connection_pool"]["min_time"], elapsed)
                test_results["connection_pool"]["max_time"] = max(test_results["connection_pool"]["max_time"], elapsed)
                
                logger.info(f"连接池测试完成，耗时: {elapsed:.3f}秒")
                
                # 等待一小段时间避免API限制
                await asyncio.sleep(1)
            
            # 计算平均时间
            if test_results["connection_pool"]["times"]:
                test_results["connection_pool"]["avg_time"] = sum(test_results["connection_pool"]["times"]) / len(test_results["connection_pool"]["times"])
            
            # 计算比较结果
            if test_results["new_connection"]["avg_time"] > 0 and test_results["connection_pool"]["avg_time"] > 0:
                test_results["comparison"]["improvement_ratio"] = test_results["new_connection"]["avg_time"] / test_results["connection_pool"]["avg_time"]
                test_results["comparison"]["time_saved"] = test_results["new_connection"]["avg_time"] - test_results["connection_pool"]["avg_time"]
            
            # 添加到测试结果
            self.test_results["connection_comparison"] = {
                "success": True,
                "message": f"连接池比每次新建连接快{test_results['comparison']['improvement_ratio']:.2f}倍",
                "time": 0,
                "data": test_results
            }
            
            return test_results
            
        except Exception as e:
            error_msg = f"连接池对比测试失败: {str(e)}"
            logger.error(error_msg)
            self.test_results["connection_comparison"] = {
                "success": False,
                "message": error_msg,
                "time": 0,
                "data": None
            }
            
            return {
                "error": error_msg
            }
    
    def print_connection_comparison(self) -> None:
        """打印连接池与新建连接的对比结果"""
        if "connection_comparison" not in self.test_results:
            print("未执行连接池对比测试")
            return
        
        test_data = self.test_results["connection_comparison"].get("data")
        if not test_data:
            print("连接池对比测试数据不可用")
            return
            
        print("\n" + "=" * 80)
        print("连接池与新建连接性能对比")
        print("=" * 80)
        
        # 打印统计信息
        print(f"新建连接平均耗时: {test_data['new_connection']['avg_time']:.3f}秒")
        print(f"连接池平均耗时: {test_data['connection_pool']['avg_time']:.3f}秒")
        print(f"性能提升比例: {test_data['comparison']['improvement_ratio']:.2f}倍")
        print(f"平均节省时间: {test_data['comparison']['time_saved']:.3f}秒")
        
        # 打印详细数据
        print("\n详细测试数据:")
        print(f"{'测试':<5} {'新建连接(秒)':<15} {'连接池(秒)':<15} {'节省时间(秒)':<15} {'提升比例':<10}")
        print("-" * 60)
        
        for i in range(min(len(test_data["new_connection"]["times"]), len(test_data["connection_pool"]["times"]))):
            new_time = test_data["new_connection"]["times"][i]
            pool_time = test_data["connection_pool"]["times"][i]
            saved = new_time - pool_time
            ratio = new_time / pool_time if pool_time > 0 else float('inf')
            
            print(f"{i+1:<5} {new_time:<15.3f} {pool_time:<15.3f} {saved:<15.3f} {ratio:<10.2f}倍")
        
        # 展示结论
        print("\n结论:")
        if test_data['comparison']['improvement_ratio'] > 5:
            print("✅ 连接池提供了显著的性能提升，强烈推荐在生产环境中使用")
        elif test_data['comparison']['improvement_ratio'] > 2:
            print("✅ 连接池提供了明显的性能提升，建议在生产环境中使用")
        elif test_data['comparison']['improvement_ratio'] > 1.2:
            print("✅ 连接池提供了一定的性能提升，可考虑在生产环境中使用")
        else:
            print("⚠️ 连接池性能提升不明显，可能需要进一步调查")
        
        print("\n" + "=" * 80)

    async def run_all_tests(self) -> Dict[str, Any]:
        """运行所有测试"""
        try:
            logger.info("开始币安API测试...")
            logger.info("测试1: 连接到现货市场...")
            await self.create_client(market_type="spot")
            
            logger.info("测试2: 获取账户信息...")
            await self.test_get_account_info()
            
            logger.info("测试3: 获取现货余额...")
            await self.test_get_spot_balance()
            
            logger.info("测试4: 获取合约余额...")
            await self.test_get_futures_balance()
            
            logger.info("测试5: 获取未成交订单...")
            await self.test_get_open_orders()
            
            logger.info("测试6: 测试WebSocket账户数据推送...")
            # 询问用户是否要测试WebSocket功能
            should_test_ws = input("\n是否要测试WebSocket账户数据推送？这将监听60秒的账户更新 (y/n): ").strip().lower() == 'y'
            if should_test_ws:
                logger.info("执行WebSocket账户数据测试...")
                await self.test_websocket_account(market_type="future", duration=60)
            else:
                logger.info("跳过WebSocket账户数据测试...")
                self.test_results["websocket_account"] = {
                    "success": True,
                    "message": "用户选择跳过WebSocket账户数据测试",
                    "time": 0,
                    "data": None
                }
            
            logger.info("测试7: 开设ETH合约多单...")
            # 询问用户是否要测试下单功能
            should_test_order = input("\n是否要测试真实下单功能？这将使用您的资金开设ETH合约多单 (y/n): ").strip().lower() == 'y'
            if should_test_order:
                logger.info("执行ETH合约下单测试...")
                await self.test_place_futures_order()
            else:
                logger.info("跳过ETH合约下单测试...")
                self.test_results["futures_order"] = {
                    "success": True,
                    "message": "用户选择跳过ETH合约下单测试",
                    "time": 0,
                    "data": None
                }
            
        except Exception as e:
            logger.error(f"测试过程中发生错误: {str(e)}")
        finally:
            # 关闭客户端连接
            if self.client:
                try:
                    await self.client.close()
                    self.client = None
                except Exception as e:
                    logger.error(f"关闭客户端失败: {str(e)}")
            
            return self.test_results
    
    def print_results(self) -> None:
        """打印测试结果"""
        print("\n" + "=" * 80)
        print("币安API测试结果")
        print("=" * 80)
        
        for test_name, result in self.test_results.items():
            # 跳过延迟统计，将在单独的方法中展示
            if test_name == "latency_stats":
                continue
                
            success = result.get("success", False)
            message = result.get("message", "无结果信息")
            time_taken = result.get("time", 0)
            
            status = "✅ 成功" if success else "❌ 失败"
            print(f"\n{test_name.upper()}测试: {status}")
            print(f"  详情: {message}")
            print(f"  耗时: {time_taken:.2f}秒")
            
            # 显示详细的延迟信息
            details = result.get("details", {})
            if details:
                print("  延迟细节:")
                for key, value in details.items():
                    if isinstance(value, dict):
                        print(f"    {key}:")
                        for sub_key, sub_value in value.items():
                            print(f"      {sub_key}: {sub_value:.3f}秒")
                    else:
                        print(f"    {key}: {value:.3f}秒")
            
            # 根据测试类型打印详细信息
            data = result.get("data", None)
            if data:
                if test_name == "account_info" or test_name == "spot_balance" or test_name == "futures_balance":
                    # 打印余额信息
                    print("  余额:")
                    for currency, balance in data.items():
                        print(f"    {currency}: 可用 {balance.get('free', 0):.8f}, 冻结 {balance.get('used', 0):.8f}, 总计 {balance.get('total', 0):.8f}")
                
                elif test_name == "open_orders" and isinstance(data, dict) and "orders" in data:
                    # 打印订单信息
                    orders = data["orders"]
                    print(f"  未成交订单数量: {len(orders)}")
                    for i, order in enumerate(orders, 1):
                        print(f"    订单 {i}:")
                        print(f"      交易对: {order.get('symbol')}")
                        print(f"      类型: {order.get('type')} {order.get('side')}")
                        print(f"      价格: {order.get('price')}")
                        print(f"      数量: {order.get('amount')}")
                        print(f"      状态: {order.get('status')}")
                
                elif test_name == "futures_order" and isinstance(data, dict):
                    # 打印期货订单信息
                    if "order_details" in data and "order_result" in data:
                        details = data["order_details"]
                        result = data["order_result"]
                        
                        print("  订单详情:")
                        print(f"    交易对: {details.get('symbol')}")
                        print(f"    杠杆: {details.get('leverage')}倍")
                        print(f"    价格: {details.get('price')}")
                        print(f"    数量: {details.get('amount')}")
                        print(f"    价值: {details.get('value')} USDT")
                        print(f"    持仓模式: {details.get('position_mode', 'unknown')}")
                        
                        print("  订单结果:")
                        print(f"    订单ID: {result.get('id')}")
                        print(f"    状态: {result.get('status')}")
                        print(f"    已成交: {result.get('filled')}")
                        print(f"    未成交: {result.get('remaining')}")
                
                elif test_name == "websocket_account" and isinstance(data, dict):
                    # 打印WebSocket账户数据测试信息
                    print("  WebSocket测试详情:")
                    print(f"    收到消息数量: {data.get('messages_count', 0)}")
                    print(f"    连接持续时间: {data.get('connection_duration', 0):.1f}秒")
                    
                    # 如果有账户更新消息，打印摘要
                    account_update = data.get('last_account_update')
                    if account_update and isinstance(account_update, dict):
                        print("  最后一次账户更新:")
                        event_time = account_update.get('E')
                        if event_time:
                            event_datetime = datetime.fromtimestamp(event_time / 1000)
                            print(f"    时间: {event_datetime}")
                            
                        # 查看是否有余额更新
                        if 'a' in account_update and 'B' in account_update['a']:
                            balances = account_update['a']['B']
                            print(f"    余额更新数量: {len(balances)}")
                            for i, balance in enumerate(balances[:3], 1):  # 最多显示3个
                                print(f"      资产 {i}: {balance.get('a', '')}, 钱包余额: {balance.get('wb', '0')}")
                                
                        # 查看是否有持仓更新
                        if 'a' in account_update and 'P' in account_update['a']:
                            positions = account_update['a']['P']
                            print(f"    持仓更新数量: {len(positions)}")
                            for i, position in enumerate(positions[:3], 1):  # 最多显示3个
                                print(f"      持仓 {i}: {position.get('s', '')}, 数量: {position.get('pa', '0')}, 价格: {position.get('ep', '0')}")
        
        print("\n" + "=" * 80)
        
        # 总结
        success_count = sum(1 for result in self.test_results.items() if result[0] != "latency_stats" and result[1]["success"])
        total_tests = sum(1 for result in self.test_results.items() if result[0] != "latency_stats")
        print(f"\n总结: {success_count}/{total_tests} 项测试成功")
        
        if success_count == total_tests:
            print("🎉 恭喜！您的币安API可以正常工作。")
        else:
            print("⚠️ 有些测试未通过，请检查上面的错误信息。")
        
        print("=" * 80 + "\n")

    @staticmethod
    def print_welcome() -> None:
        """打印欢迎信息"""
        print("\n" + "=" * 80)
        print("币安API测试工具")
        print("=" * 80)
        print("该测试工具将帮助您测试Binance API连接、获取账户信息和下单等功能")
        print("并提供详细的延迟分析，帮助您了解API操作的实际耗时")
        print("=" * 80 + "\n")
    
    @staticmethod
    def get_user_input() -> tuple:
        """获取用户输入的API密钥"""
        print("\n请输入您的币安API密钥:")
        api_key = input("API Key: ").strip()
        api_secret = input("API Secret: ").strip()
        
        print("\n请选择测试类型:")
        print("1. 只读测试 (不会尝试下单)")
        print("2. WebSocket测试 (测试账户数据推送)")
        print("3. 完整测试 (包括WebSocket和测试下单)")
        test_type = input("您的选择 [1/2/3]: ").strip()
        
        test_websocket = test_type in ["2", "3"]
        test_futures_order = test_type == "3"
        
        return api_key, api_secret, test_websocket, test_futures_order

    @measure_latency("下单延迟分布测试")
    async def test_order_latency_distribution(self, iterations: int = 5, symbol: str = "BTC/USDT") -> Dict[str, Any]:
        """测试下单延迟分布
        
        多次执行下单操作，分析延迟分布情况
        
        Args:
            iterations: 测试重复次数
            symbol: 测试交易对，默认BTC/USDT
            
        Returns:
            Dict: 测试结果
        """
        test_results = {
            "order_times": [],
            "avg_time": 0,
            "min_time": float('inf'),
            "max_time": 0,
            "median_time": 0,
            "std_dev": 0,
            "percentiles": {},
            "distribution": {}
        }
        
        # 延迟分布区间（秒）
        latency_ranges = [
            (0, 0.1),      # 0-100ms
            (0.1, 0.2),    # 100-200ms
            (0.2, 0.3),    # 200-300ms
            (0.3, 0.5),    # 300-500ms
            (0.5, 0.7),    # 500-700ms
            (0.7, 1.0),    # 700ms-1s
            (1.0, 1.5),    # 1-1.5s
            (1.5, 2.0),    # 1.5-2s
            (2.0, 3.0),    # 2-3s
            (3.0, float('inf'))  # >3s
        ]
        
        # 初始化分布计数
        for start, end in latency_ranges:
            if end == float('inf'):
                test_results["distribution"][f">{start}s"] = 0
            else:
                test_results["distribution"][f"{start}-{end}s"] = 0
        
        try:
            logger.info(f"开始执行下单延迟分布测试 ({iterations}次)...")
            
            # 确保客户端已创建
            if not self.client:
                await self.create_client()
            
            # 获取交易对信息和当前价格
            market = self.client.market(symbol)
            ticker = await self.client.fetch_ticker(symbol)
            current_price = ticker['last']
            
            # 计算下单数量 (使用最小数量来避免实际成交)
            min_amount = market['limits']['amount']['min']
            amount = min_amount * 1.1  # 稍微高于最小数量
            
            # 计算价格 (使用远离当前价格的价格)
            price_multiplier = 0.7  # 比市场价低30%，确保不会被执行
            price = current_price * price_multiplier
            price = round(price, market['precision']['price'])
            
            logger.info(f"交易对: {symbol}, 当前价格: {current_price}, 测试价格: {price}, 数量: {amount}")
            
            for i in range(iterations):
                logger.info(f"下单延迟测试 [{i+1}/{iterations}]")
                
                try:
                    # 执行下单操作
                    order_start = time.time()
                    order = await self.client.create_limit_buy_order(
                        symbol=symbol,
                        amount=amount,
                        price=price
                    )
                    elapsed = time.time() - order_start
                    
                    # 记录耗时
                    test_results["order_times"].append(elapsed)
                    test_results["min_time"] = min(test_results["min_time"], elapsed)
                    test_results["max_time"] = max(test_results["max_time"], elapsed)
                    
                    # 将耗时分配到延迟区间
                    for start, end in latency_ranges:
                        if start <= elapsed < end:
                            if end == float('inf'):
                                test_results["distribution"][f">{start}s"] += 1
                            else:
                                test_results["distribution"][f"{start}-{end}s"] += 1
                            break
                    
                    logger.info(f"下单操作完成，订单ID: {order.get('id', 'unknown')}, 耗时: {elapsed:.3f}秒")
                    
                    # 立即取消订单
                    try:
                        await self.client.cancel_order(order['id'], symbol)
                        logger.info(f"订单已取消: {order.get('id', 'unknown')}")
                    except Exception as e:
                        logger.warning(f"取消订单失败: {str(e)}")
                    
                except Exception as e:
                    logger.error(f"下单测试失败: {str(e)}")
                
                # 等待一小段时间避免API限制
                await asyncio.sleep(1)
            
            # 计算统计数据
            if test_results["order_times"]:
                # 计算平均值
                test_results["avg_time"] = sum(test_results["order_times"]) / len(test_results["order_times"])
                
                # 排序时间数组用于计算中位数和百分位数
                sorted_times = sorted(test_results["order_times"])
                
                # 计算中位数
                mid = len(sorted_times) // 2
                if len(sorted_times) % 2 == 0:
                    test_results["median_time"] = (sorted_times[mid-1] + sorted_times[mid]) / 2
                else:
                    test_results["median_time"] = sorted_times[mid]
                
                # 计算标准差
                variance = sum((t - test_results["avg_time"]) ** 2 for t in test_results["order_times"]) / len(test_results["order_times"])
                test_results["std_dev"] = variance ** 0.5
                
                # 计算百分位数
                percentiles = [50, 75, 90, 95, 99]
                for p in percentiles:
                    idx = int(len(sorted_times) * p / 100)
                    test_results["percentiles"][f"p{p}"] = sorted_times[idx-1] if idx > 0 else sorted_times[0]
            
            # 添加到测试结果
            self.test_results["order_latency"] = {
                "success": True,
                "message": f"下单延迟分布测试完成，平均延迟: {test_results['avg_time']:.3f}秒",
                "time": 0,
                "data": test_results
            }
            
            return test_results
            
        except Exception as e:
            error_msg = f"下单延迟分布测试失败: {str(e)}"
            logger.error(error_msg)
            
            self.test_results["order_latency"] = {
                "success": False,
                "message": error_msg,
                "time": 0,
                "data": None
            }
            
            return {
                "error": error_msg
            }
    
    def print_order_latency_results(self) -> None:
        """打印下单延迟分布测试结果"""
        if "order_latency" not in self.test_results:
            print("未执行下单延迟分布测试")
            return
        
        test_data = self.test_results["order_latency"].get("data")
        if not test_data:
            print("下单延迟分布测试数据不可用")
            return
            
        print("\n" + "=" * 80)
        print("下单延迟分布分析")
        print("=" * 80)
        
        # 打印统计信息
        print(f"平均延迟: {test_data['avg_time']:.3f}秒")
        print(f"中位数延迟: {test_data['median_time']:.3f}秒")
        print(f"最小延迟: {test_data['min_time']:.3f}秒")
        print(f"最大延迟: {test_data['max_time']:.3f}秒")
        print(f"标准差: {test_data['std_dev']:.3f}秒")
        
        # 打印百分位数
        print("\n延迟百分位数:")
        for p, value in test_data['percentiles'].items():
            print(f"{p}: {value:.3f}秒")
        
        # 打印分布情况
        print("\n延迟分布:")
        total_count = len(test_data["order_times"])
        for range_str, count in test_data['distribution'].items():
            if count > 0:
                percentage = (count / total_count) * 100
                bar = "█" * int(percentage / 2)
                print(f"{range_str:<10}: {count:>3}/{total_count} ({percentage:>5.1f}%) {bar}")
        
        # 打印延迟评估
        print("\n延迟评估:")
        if test_data["avg_time"] < 0.3:
            print("✅ 优秀: 下单延迟非常低，适合高频交易")
        elif test_data["avg_time"] < 0.5:
            print("✅ 良好: 下单延迟较低，适合大多数交易策略")
        elif test_data["avg_time"] < 1.0:
            print("⚠️ 一般: 下单延迟在可接受范围内，但对于高频策略可能不够理想")
        elif test_data["avg_time"] < 2.0:
            print("⚠️ 较高: 下单延迟较高，可能影响某些时间敏感的交易策略")
        else:
            print("❌ 过高: 下单延迟过高，建议检查网络连接或API服务器状态")
        
        print("\n" + "=" * 80)

async def main():
    """主函数"""
    # 确保Windows上使用兼容的事件循环
    if sys.platform.startswith('win'):
        current_loop = asyncio.get_event_loop_policy().get_event_loop()
        if type(current_loop).__name__ == 'ProactorEventLoop':
            logger.warning("检测到Windows ProactorEventLoop，这可能导致aiodns问题")
            logger.info("尝试使用WindowsSelectorEventLoopPolicy...")
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            logger.info("已切换到Windows SelectorEventLoop以兼容aiodns")
            
    print("\n" + "=" * 80)
    print("Binance API 测试工具")
    print("=" * 80)
    print("该测试工具将帮助您测试Binance API连接、获取账户信息和下单等功能")
    print("并提供详细的延迟分析，帮助您了解API操作的实际耗时")
    print("=" * 80 + "\n")
    
    # 获取API密钥
    api_key = input("请输入Binance API Key: ").strip()
    api_secret = input("请输入Binance API Secret: ").strip()
    
    if not api_key or not api_secret:
        print("错误: API Key 和 Secret 不能为空")
        return
    
    # 获取测试选项
    test_websocket = input("是否测试WebSocket账户数据连接? (y/n, 默认: n): ").strip().lower() == 'y'
    test_futures = input("是否测试期货下单? (y/n, 默认: n): ").strip().lower() == 'y'
    test_connection_pool = input("是否执行连接池性能对比测试? (y/n, 默认: y): ").strip().lower() != 'n'
    test_ws_http = input("是否执行WebSocket与HTTP API性能对比测试? (y/n, 默认: y): ").strip().lower() != 'n'
    test_order_latency = input("是否执行下单延迟分布测试? (y/n, 默认: y): ").strip().lower() != 'n'
    
    # 获取测试参数
    iterations_pool = 5
    iterations_ws = 10
    iterations_order = 5
    
    if test_connection_pool:
        iterations_input = input(f"连接池测试重复次数 (默认: {iterations_pool}): ").strip()
        try:
            iterations_pool = int(iterations_input) if iterations_input else iterations_pool
        except ValueError:
            print(f"输入无效，使用默认值: {iterations_pool}")
    
    if test_ws_http:
        iterations_input = input(f"WebSocket与HTTP对比测试重复次数 (默认: {iterations_ws}): ").strip()
        try:
            iterations_ws = int(iterations_input) if iterations_input else iterations_ws
        except ValueError:
            print(f"输入无效，使用默认值: {iterations_ws}")
    
    if test_order_latency:
        iterations_input = input(f"下单延迟测试重复次数 (默认: {iterations_order}): ").strip()
        try:
            iterations_order = int(iterations_input) if iterations_input else iterations_order
        except ValueError:
            print(f"输入无效，使用默认值: {iterations_order}")
        
        test_symbol = input("测试交易对 (默认: BTC/USDT): ").strip()
        if not test_symbol:
            test_symbol = "BTC/USDT"
    
    # 创建测试器
    tester = BinanceApiTester(api_key, api_secret)
    client = None
    
    try:
        # 创建客户端连接
        print("\n正在测试API连接...")
        client = await tester.create_client()
        
        # 测试获取账户信息
        print("\n正在获取账户信息...")
        account_info = await tester.test_get_account_info()
        
        # 测试获取余额
        print("\n正在获取现货账户余额...")
        spot_balance = await tester.test_get_spot_balance()
        
        if test_futures:
            print("\n正在获取期货账户余额...")
            futures_balance = await tester.test_get_futures_balance()
        
        # 测试获取未成交订单
        print("\n正在获取未成交订单...")
        open_orders = await tester.test_get_open_orders()
        
        # 测试连接池性能对比
        if test_connection_pool:
            print(f"\n正在执行连接池性能对比测试 ({iterations_pool}次)...")
            await tester.test_connection_vs_pool(iterations_pool)
        
        # 测试WebSocket与HTTP API性能对比
        if test_ws_http:
            print(f"\n正在执行WebSocket与HTTP API性能对比测试 ({iterations_ws}次)...")
            await tester.test_ws_vs_http(iterations_ws)
        
        # 测试下单延迟分布
        if test_order_latency:
            print(f"\n正在执行下单延迟分布测试 ({iterations_order}次, 交易对: {test_symbol})...")
            await tester.test_order_latency_distribution(iterations_order, test_symbol)
        
        # 测试期货下单（可选）
        if test_futures:
            print("\n正在测试期货下单...")
            futures_order = await tester.test_place_futures_order()
        
        # 测试WebSocket账户数据连接（可选）
        if test_websocket:
            print("\n正在测试WebSocket账户数据连接...")
            await tester.test_websocket_account()
        
    except Exception as e:
        print(f"\n测试过程中发生错误: {e}")
        traceback.print_exc()
    finally:
        # 关闭客户端连接
        if client:
            print("\n关闭API客户端连接...")
            await client.close()
        
        # 断开WebSocket连接
        if hasattr(tester, 'ws') and tester.ws and not tester.ws.closed:
            print("关闭WebSocket连接...")
            await tester.ws.close()
    
    # 打印测试结果
    print("\n打印测试结果...")
    tester.print_results()
    
    # 打印延迟统计信息
    print("\n延迟分析报告...")
    tester.print_latency_stats()
    
    # 打印连接池对比结果
    if test_connection_pool and "connection_comparison" in tester.test_results:
        tester.print_connection_comparison()
    
    # 打印WebSocket与HTTP对比结果
    if test_ws_http and "ws_http_comparison" in tester.test_results:
        tester.print_ws_http_comparison()
    
    # 打印下单延迟分布结果
    if test_order_latency and "order_latency" in tester.test_results:
        tester.print_order_latency_results()
    
    print("\n测试完成!")

if __name__ == "__main__":
    # 在Windows系统上，解决aiodns需要SelectorEventLoop的问题
    if sys.platform.startswith('win'):
        import asyncio
        import platform
        # 强制使用SelectorEventLoop而不是默认的ProactorEventLoop
        if platform.system() == 'Windows':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            print("已切换到Windows SelectorEventLoop以兼容aiodns")
    
    asyncio.run(main())