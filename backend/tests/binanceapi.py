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
from typing import Dict, Any, Optional, List
from datetime import datetime

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
        }
        # WebSocket相关属性
        self.ws_connection = None
        self.ws_session = None
        self.ws_messages = []
        self.listen_key = None
    
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
    
    async def create_client(self, market_type: str = "spot") -> None:
        """创建交易所客户端
        
        Args:
            market_type: 市场类型，"spot"或"future"
        """
        try:
            start_time = time.time()
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
            
            # 加载市场
            await self.client.load_markets()
            elapsed = time.time() - start_time
            
            self.test_results["connection"] = {
                "success": True,
                "message": f"成功连接到币安{market_type}市场",
                "time": elapsed
            }
            logger.info(f"成功连接到币安{market_type}市场，耗时: {elapsed:.2f}秒")
            
        except Exception as e:
            elapsed = time.time() - start_time if 'start_time' in locals() else 0
            error_msg = f"连接币安API失败: {str(e)}"
            self.test_results["connection"] = {
                "success": False,
                "message": error_msg,
                "time": elapsed
            }
            logger.error(error_msg)
            # 确保客户端关闭
            if self.client:
                try:
                    await self.client.close()
                    self.client = None
                except Exception:
                    pass
            raise
    
    async def test_get_account_info(self) -> None:
        """测试获取账户信息"""
        try:
            start_time = time.time()
            # 确保我们有一个活跃的客户端
            if not self.client:
                await self.create_client()
            
            account_info = await self.client.fetch_balance()
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
                "data": non_zero_balances
            }
            logger.info(f"成功获取账户信息，发现{len(non_zero_balances)}个有余额的币种，耗时: {elapsed:.2f}秒")
            
        except Exception as e:
            elapsed = time.time() - start_time if 'start_time' in locals() else 0
            error_msg = f"获取账户信息失败: {str(e)}"
            self.test_results["account_info"] = {
                "success": False,
                "message": error_msg,
                "time": elapsed
            }
            logger.error(error_msg)
    
    async def test_get_spot_balance(self) -> None:
        """测试获取现货账户余额"""
        # 保存现有的客户端
        previous_client = self.client
        
        try:
            # 创建一个现货市场客户端
            await self.create_client(market_type="spot")
            
            start_time = time.time()
            balance = await self.client.fetch_balance()
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
                "data": non_zero_balances
            }
            logger.info(f"成功获取现货账户余额，发现{len(non_zero_balances)}个有余额的币种，耗时: {elapsed:.2f}秒")
            
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
    
    async def test_get_futures_balance(self) -> None:
        """测试获取合约账户余额"""
        # 保存现有的客户端
        previous_client = self.client
        
        try:
            # 创建一个合约市场客户端
            await self.create_client(market_type="future")
            
            start_time = time.time()
            balance = await self.client.fetch_balance()
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
                "data": non_zero_balances
            }
            logger.info(f"成功获取合约账户余额，发现{len(non_zero_balances)}个有余额的币种，耗时: {elapsed:.2f}秒")
            
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
            
            # 尝试不带symbol参数获取所有订单
            try:
                logger.info("尝试获取所有未成交订单...")
                open_orders = await self.client.fetch_open_orders()
                if open_orders:
                    all_open_orders.extend(open_orders)
                    logger.info(f"成功获取所有未成交订单: {len(open_orders)}个")
            except Exception as e:
                logger.warning(f"获取所有未成交订单失败，将尝试逐个交易对获取: {str(e)}")
                
                # 如果不成功，尝试逐个交易对获取
                for symbol in self.common_symbols:
                    try:
                        logger.info(f"获取{symbol}的未成交订单...")
                        symbol_orders = await self.client.fetch_open_orders(symbol)
                        if symbol_orders:
                            all_open_orders.extend(symbol_orders)
                            orders_by_symbol[symbol] = len(symbol_orders)
                            logger.info(f"成功获取{symbol}的未成交订单: {len(symbol_orders)}个")
                    except Exception as symbol_error:
                        logger.warning(f"获取{symbol}的未成交订单失败: {str(symbol_error)}")
            
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
                    }
                }
                logger.info(f"成功获取未成交订单，共{len(all_open_orders)}个，耗时: {elapsed:.2f}秒")
            else:
                self.test_results["open_orders"] = {
                    "success": True,
                    "message": "没有找到未成交订单",
                    "time": elapsed,
                    "data": []
                }
                logger.info(f"没有找到未成交订单，耗时: {elapsed:.2f}秒")
            
        except Exception as e:
            elapsed = time.time() - start_time if 'start_time' in locals() else 0
            error_msg = f"获取未成交订单失败: {str(e)}"
            self.test_results["open_orders"] = {
                "success": False,
                "message": error_msg,
                "time": elapsed
            }
            logger.error(error_msg)
    
    async def test_place_futures_order(self) -> None:
        """测试开设ETH合约多单，杠杆10倍，价值100 USDT"""
        # 保存现有的客户端
        previous_client = self.client
        
        try:
            # 创建一个合约市场客户端
            await self.create_client(market_type="future")
            
            # 设置ETH/USDT交易对和下单参数
            symbol = "ETH/USDT"
            leverage = 10
            order_value = 100  # USDT
            
            # 获取当前价格
            logger.info(f"获取 {symbol} 当前价格...")
            ticker = await self.client.fetch_ticker(symbol)
            current_price = ticker['last']
            
            # 计算订单数量 (价值/价格)
            # 注意：实际使用的杠杆不影响订单数量计算，杠杆只影响所需保证金
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
            
            # 设置杠杆
            logger.info(f"设置 {symbol} 杠杆为 {leverage}倍...")
            leverage_result = await self.client.set_leverage(leverage, symbol)
            
            # 设置全仓模式（用户设置为全仓）
            logger.info(f"设置 {symbol} 为全仓模式...")
            try:
                margin_mode_result = await self.client.set_margin_mode('cross', symbol)
                logger.info(f"成功设置为全仓模式")
            except Exception as e:
                # 如果已经是全仓模式，币安API会返回错误
                logger.warning(f"设置全仓模式失败，可能已经是全仓模式: {str(e)}")
                margin_mode_result = {"margin_mode": "cross", "status": "已存在或不需要更改"}
            
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
                order_result = await self.client.create_order(
                    symbol=symbol,
                    type='limit',
                    side='buy',
                    amount=order_amount,
                    price=price,
                    params=order_params
                )
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
                    }
                }
                logger.info(f"成功下ETH合约多单，订单ID: {order_result.get('id', 'unknown')}，耗时: {elapsed:.2f}秒")
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
    
    async def test_websocket_account(self, market_type: str = "future", duration: int = 60) -> None:
        """测试WebSocket账户数据推送
        
        连接到币安WebSocket API，监听账户数据更新
        
        Args:
            market_type: 市场类型，"spot"或"future"
            duration: 测试持续时间(秒)
        """
        try:
            start_time = time.time()
            
            # 先获取Listen Key
            try:
                listen_key = await self.get_listen_key(market_type)
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
            
            try:
                self.ws_session = aiohttp.ClientSession()
                self.ws_connection = await self.ws_session.ws_connect(ws_url, heartbeat=30)
                
                connection_time = time.time()
                logger.info(f"WebSocket连接成功，将监听{duration}秒...")
                
                # 设置结束时间
                end_time = time.time() + duration
                
                # 监听消息
                while time.time() < end_time:
                    try:
                        # 设置超时，确保能够正常退出循环
                        msg = await asyncio.wait_for(
                            self.ws_connection.receive(), 
                            timeout=min(5, end_time - time.time())
                        )
                        
                        if msg.type == aiohttp.WSMsgType.TEXT:
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
                    }
                }
                
                logger.info(f"WebSocket测试完成，共收到{messages_received}条消息，耗时: {elapsed:.2f}秒")
                
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
                if self.ws_connection:
                    await self.ws_connection.close()
                if self.ws_session:
                    await self.ws_session.close()
                
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
            
            logger.info("测试4: 获取未成交订单...")
            await self.test_get_open_orders()
            
            logger.info("测试5: 获取合约余额...")
            await self.test_get_futures_balance()
            
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
            success = result.get("success", False)
            message = result.get("message", "无结果信息")
            time_taken = result.get("time", 0)
            
            status = "✅ 成功" if success else "❌ 失败"
            print(f"\n{test_name.upper()}测试: {status}")
            print(f"  详情: {message}")
            print(f"  耗时: {time_taken:.2f}秒")
            
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
        success_count = sum(1 for result in self.test_results.values() if result["success"])
        print(f"\n总结: {success_count}/{len(self.test_results)} 项测试成功")
        
        if success_count == len(self.test_results):
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
        print("本工具将测试您的API密钥是否能正常连接币安并获取账户信息")
        print("请确保您使用的是只读API密钥，没有交易权限，以保障您的资金安全")
        print("测试将执行以下操作:")
        print("  1. 连接到币安API")
        print("  2. 获取账户信息")
        print("  3. 获取现货账户余额")
        print("  4. 获取合约账户余额")
        print("  5. 获取当前未成交订单")
        print("  6. [可选] 测试WebSocket账户数据推送 (监听60秒)")
        print("  7. [可选] 测试下ETH合约多单 (仅模拟，不会实际成交)")
        print("=" * 80)
    
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

async def main() -> None:
    """主函数"""
    try:
        # 打印欢迎信息
        BinanceApiTester.print_welcome()
        
        # 获取用户输入
        api_key, api_secret, test_websocket, test_futures_order = BinanceApiTester.get_user_input()
        
        # 输入合法性检查
        if not api_key or not api_secret:
            print("错误: API密钥和秘钥不能为空!")
            return
        
        # 创建测试器
        tester = BinanceApiTester(api_key, api_secret)
        
        # 执行测试
        try:
            # 连接测试
            await tester.create_client()
            
            # 账户信息测试
            await tester.test_get_account_info()
            
            # 现货余额测试
            await tester.test_get_spot_balance()
            
            # 合约余额测试
            await tester.test_get_futures_balance()
            
            # 未成交订单测试
            await tester.test_get_open_orders()
            
            # WebSocket账户数据测试 (可选)
            if test_websocket:
                print("\n开始测试WebSocket账户数据推送...")
                await tester.test_websocket_account(market_type="future", duration=60)
            
            # 期货下单测试 (可选)
            if test_futures_order:
                print("\n⚠️ 警告: 即将测试下ETH合约多单，仅用于测试，我们会使用限价单且设置较高价格，通常不会成交")
                confirm = input("是否继续? [y/N]: ").strip().lower()
                if confirm == "y":
                    await tester.test_place_futures_order()
                else:
                    print("跳过期货下单测试")
                    tester.test_results["futures_order"] = {
                        "success": True,
                        "message": "用户选择跳过ETH合约下单测试",
                        "time": 0,
                        "data": None
                    }
            
        finally:
            # 确保客户端关闭
            if tester.client:
                await tester.client.close()
            
            # 关闭WebSocket连接
            if hasattr(tester, 'ws_connection') and tester.ws_connection:
                await tester.ws_connection.close()
            if hasattr(tester, 'ws_session') and tester.ws_session:
                await tester.ws_session.close()
            
            # 打印测试结果
            tester.print_results()
    
    except Exception as e:
        logger.error(f"测试过程中出现错误: {str(e)}")
        print(f"\n测试过程中出现错误: {str(e)}")
    
    print("\n测试完成!")

if __name__ == "__main__":
    asyncio.run(main())