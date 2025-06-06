#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import time
import argparse
from getpass import getpass

class GridTradingTester:
    def __init__(self, base_url):
        self.base_url = base_url
        self.token = None
        self.headers = {
            "Content-Type": "application/json"
        }
        self.strategy_id = None
        self.exchange = "BINANCE"  # 預設交易所

    def login(self, username, password, keep_logged_in=False):
        """登入系統並獲取認證token"""
        endpoint = f"{self.base_url}/api/v1/auth/login"
        
        # 使用FormData格式進行登入請求
        form_data = {
            "username": username,
            "password": password,
            "keep_logged_in": str(keep_logged_in).lower()
        }
        
        print(f"\n[*] 嘗試登入: {username}")
        
        # 使用correct content-type for form data
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        # 發送POST請求
        response = requests.post(
            endpoint, 
            data=form_data,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            # 從響應中獲取token
            self.token = data.get("access_token")
            refresh_token = data.get("refresh_token")
            
            if self.token:
                self.headers["Authorization"] = f"Bearer {self.token}"
                print(f"[+] 登入成功! 用戶: {username}")
                print(f"[+] 令牌類型: {data.get('token_type', 'bearer')}")
                print(f"[+] 過期時間: {data.get('expires_in', '未知')}秒")
                return True
            else:
                print(f"[-] 登入成功但未獲取到令牌")
                return False
        else:
            print(f"[-] 登入失敗: {response.status_code}")
            print(f"[-] 錯誤信息: {response.text}")
            return False

    def create_strategy(self, strategy_params):
        """創建網格交易策略"""
        if not self.token:
            print("[-] 未登入，請先登入")
            return False
        
        # 修正API端點路徑
        endpoint = f"{self.base_url}/api/v1/trading/grid/create/{self.exchange}"
        
        print("\n[*] 正在創建網格交易策略...")
        response = requests.post(endpoint, headers=self.headers, json=strategy_params)
        
        if response.status_code in [200, 201]:
            data = response.json()
            self.strategy_id = data.get("grid_id")
            print(f"[+] 策略創建成功! ID: {self.strategy_id}")
            print(f"[+] 策略詳情: {json.dumps(data, indent=2, ensure_ascii=False)}")
            return True
        else:
            print(f"[-] 創建策略失敗: {response.status_code}")
            print(f"[-] 錯誤信息: {response.text}")
            return False

    def get_strategies(self):
        """獲取所有網格交易策略"""
        if not self.token:
            print("[-] 未登入，請先登入")
            return False
        
        # 修正API端點路徑
        endpoint = f"{self.base_url}/api/v1/trading/grid/list/{self.exchange}"
        
        print("\n[*] 獲取所有網格交易策略...")
        response = requests.get(endpoint, headers=self.headers)
        
        if response.status_code == 200:
            data = response.json()
            print(f"[+] 成功獲取策略列表! 總數: {len(data)}")
            for idx, strategy in enumerate(data):
                print(f"\n--- 策略 {idx+1} ---")
                print(f"ID: {strategy.get('id')}")
                print(f"交易對: {strategy.get('symbol')}")
                print(f"狀態: {strategy.get('status')}")
                print(f"網格類型: {strategy.get('grid_type')}")
            return data
        else:
            print(f"[-] 獲取策略列表失敗: {response.status_code}")
            print(f"[-] 錯誤信息: {response.text}")
            return False

    def start_strategy(self, strategy_id=None):
        """啟動網格交易策略"""
        if not self.token:
            print("[-] 未登入，請先登入")
            return False
        
        if not strategy_id:
            strategy_id = self.strategy_id
            
        if not strategy_id:
            print("[-] 未指定策略ID")
            return False
            
        # 修正API端點路徑
        endpoint = f"{self.base_url}/api/v1/trading/grid/start/{self.exchange}/{strategy_id}"
        
        print(f"\n[*] 正在啟動策略 ID: {strategy_id}...")
        response = requests.post(endpoint, headers=self.headers)
        
        if response.status_code == 200:
            data = response.json()
            print(f"[+] 策略啟動成功!")
            print(f"[+] 訊息: {data.get('message')}")
            return True
        else:
            print(f"[-] 啟動策略失敗: {response.status_code}")
            print(f"[-] 錯誤信息: {response.text}")
            return False

    def stop_strategy(self, strategy_id=None):
        """停止網格交易策略"""
        if not self.token:
            print("[-] 未登入，請先登入")
            return False
        
        if not strategy_id:
            strategy_id = self.strategy_id
            
        if not strategy_id:
            print("[-] 未指定策略ID")
            return False
            
        # 修正API端點路徑
        endpoint = f"{self.base_url}/api/v1/trading/grid/stop/{self.exchange}/{strategy_id}"
        
        print(f"\n[*] 正在停止策略 ID: {strategy_id}...")
        response = requests.post(endpoint, headers=self.headers)
        
        if response.status_code == 200:
            data = response.json()
            print(f"[+] 策略停止成功!")
            print(f"[+] 訊息: {data.get('message')}")
            return True
        else:
            print(f"[-] 停止策略失敗: {response.status_code}")
            print(f"[-] 錯誤信息: {response.text}")
            return False

    def delete_strategy(self, strategy_id=None):
        """刪除網格交易策略"""
        if not self.token:
            print("[-] 未登入，請先登入")
            return False
        
        if not strategy_id:
            strategy_id = self.strategy_id
            
        if not strategy_id:
            print("[-] 未指定策略ID")
            return False
            
        # 修正API端點路徑
        endpoint = f"{self.base_url}/api/v1/trading/grid/delete/{self.exchange}/{strategy_id}"
        
        print(f"\n[*] 正在刪除策略 ID: {strategy_id}...")
        response = requests.delete(endpoint, headers=self.headers)
        
        if response.status_code in [200, 204]:
            data = response.json() if response.status_code == 200 else {"success": True}
            print(f"[+] 策略刪除成功!")
            if "message" in data:
                print(f"[+] 訊息: {data.get('message')}")
            return True
        else:
            print(f"[-] 刪除策略失敗: {response.status_code}")
            print(f"[-] 錯誤信息: {response.text}")
            return False

    def get_strategy_orders(self, strategy_id=None):
        """獲取策略的訂單列表"""
        if not self.token:
            print("[-] 未登入，請先登入")
            return False
        
        if not strategy_id:
            strategy_id = self.strategy_id
            
        if not strategy_id:
            print("[-] 未指定策略ID")
            return False
            
        # 修正API端點路徑
        endpoint = f"{self.base_url}/api/v1/trading/grid/detail/{self.exchange}/{strategy_id}"
        
        print(f"\n[*] 獲取策略 ID: {strategy_id} 的詳情...")
        response = requests.get(endpoint, headers=self.headers)
        
        if response.status_code == 200:
            data = response.json()
            if "orders" in data:
                orders = data["orders"]
                print(f"[+] 成功獲取訂單列表! 訂單數量: {len(orders)}")
                for idx, order in enumerate(orders):
                    print(f"\n--- 訂單 {idx+1} ---")
                    print(f"ID: {order.get('order_id')}")
                    print(f"類型: {order.get('order_type')}")
                    print(f"價格: {order.get('price')}")
                    print(f"數量: {order.get('quantity')}")
                    print(f"狀態: {order.get('status')}")
            else:
                print(f"[+] 策略詳情: {json.dumps(data, indent=2, ensure_ascii=False)}")
            return data
        else:
            print(f"[-] 獲取策略詳情失敗: {response.status_code}")
            print(f"[-] 錯誤信息: {response.text}")
            return False

    def select_exchange(self):
        """選擇交易所"""
        print("\n可用交易所:")
        exchanges = ["BINANCE", "BYBIT", "OKX", "MEXC"]
        for idx, exchange in enumerate(exchanges):
            print(f"{idx+1}. {exchange}")
        
        exchange_idx = int(input("\n請選擇交易所 [1-4]: ")) - 1
        if 0 <= exchange_idx < len(exchanges):
            self.exchange = exchanges[exchange_idx]
            print(f"[+] 已選擇交易所: {self.exchange}")
        else:
            print(f"[*] 無效選擇，使用默認交易所: {self.exchange}")

    def interactive_test(self):
        """互動式測試網格交易API"""
        print("\n" + "="*50)
        print("網格交易後端API互動式測試")
        print("="*50)
        
        # 登入
        username = input("請輸入用戶名: ")
        password = getpass("請輸入密碼: ")
        keep_logged_in = input("是否保持登入狀態? (y/n): ").lower() == 'y'
        
        if not self.login(username, password, keep_logged_in):
            print("[-] 登入失敗，退出測試")
            return
            
        # 選擇交易所
        self.select_exchange()
        
        # 互動式菜單
        while True:
            print("\n" + "="*50)
            print("網格交易測試菜單")
            print("="*50)
            print("1. 創建網格交易策略")
            print("2. 獲取所有策略")
            print("3. 啟動指定策略")
            print("4. 停止指定策略")
            print("5. 獲取策略詳情")
            print("6. 刪除指定策略")
            print("7. 切換交易所")
            print("0. 退出測試")
            
            choice = input("\n請選擇操作 [0-7]: ")
            
            if choice == '0':
                print("\n[*] 測試結束，再見!")
                break
            elif choice == '1':
                self.create_strategy_interactive()
            elif choice == '2':
                self.get_strategies()
            elif choice == '3':
                strategy_id = input("請輸入要啟動的策略ID (留空使用上次創建的策略): ")
                self.start_strategy(strategy_id if strategy_id else None)
            elif choice == '4':
                strategy_id = input("請輸入要停止的策略ID (留空使用上次創建的策略): ")
                self.stop_strategy(strategy_id if strategy_id else None)
            elif choice == '5':
                strategy_id = input("請輸入要查詢詳情的策略ID (留空使用上次創建的策略): ")
                self.get_strategy_orders(strategy_id if strategy_id else None)
            elif choice == '6':
                strategy_id = input("請輸入要刪除的策略ID (留空使用上次創建的策略): ")
                self.delete_strategy(strategy_id if strategy_id else None)
            elif choice == '7':
                self.select_exchange()
            else:
                print("[-] 無效選擇，請重新選擇")

    def create_strategy_interactive(self):
        """互動式創建網格交易策略"""
        print("\n" + "="*50)
        print("創建網格交易策略")
        print("="*50)
        
        # 交易對選擇
        print("\n可用交易對:")
        pairs = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT", "XRPUSDT"]
        for idx, pair in enumerate(pairs):
            print(f"{idx+1}. {pair}")
        
        pair_idx = int(input("\n請選擇交易對 [1-6]: ")) - 1
        symbol = pairs[pair_idx] if 0 <= pair_idx < len(pairs) else "BTCUSDT"
        
        # 網格類型
        grid_types = ["ARITHMETIC", "GEOMETRIC"]
        print("\n網格類型:")
        print("1. 等差網格 (ARITHMETIC)")
        print("2. 等比網格 (GEOMETRIC)")
        grid_type_idx = int(input("\n請選擇網格類型 [1-2]: ")) - 1
        grid_type = grid_types[grid_type_idx] if 0 <= grid_type_idx < len(grid_types) else "ARITHMETIC"
        
        # 策略方向
        strategy_types = ["BULLISH", "BEARISH", "NEUTRAL"]
        print("\n策略方向:")
        print("1. 做多 (BULLISH)")
        print("2. 做空 (BEARISH)")
        print("3. 中性 (NEUTRAL)")
        strategy_type_idx = int(input("\n請選擇策略方向 [1-3]: ")) - 1
        strategy_type = strategy_types[strategy_type_idx] if 0 <= strategy_type_idx < len(strategy_types) else "NEUTRAL"
        
        # 價格設置
        lower_price = float(input("\n請輸入最低價格 (USDT): "))
        upper_price = float(input("請輸入最高價格 (USDT): "))
        grid_number = int(input("請輸入網格數量 [4-100]: "))
        grid_number = max(4, min(grid_number, 100))
        
        # 投資設置
        total_investment = float(input("\n請輸入總投資額 (USDT): "))
        leverage = int(input("請輸入槓桿倍數 [1-125]: "))
        leverage = max(1, min(leverage, 125))
        
        # 風控設置 (選填)
        print("\n風控設置 (可選，直接按Enter跳過)")
        stop_loss = input("止損價格 (USDT): ")
        stop_loss = float(stop_loss) if stop_loss else None
        
        take_profit = input("止盈價格 (USDT): ")
        take_profit = float(take_profit) if take_profit else None
        
        profit_collection = input("盈利收集比例 (%) [0-100]: ")
        profit_collection = float(profit_collection) if profit_collection else None
        
        # 整合參數
        strategy_params = {
            "symbol": symbol,
            "grid_type": grid_type,
            "strategy_type": strategy_type,
            "lower_price": lower_price,
            "upper_price": upper_price,
            "grid_number": grid_number,
            "total_investment": total_investment,
            "leverage": leverage
        }
        
        # 添加可選參數
        if stop_loss is not None:
            strategy_params["stop_loss"] = stop_loss
        if take_profit is not None:
            strategy_params["take_profit"] = take_profit
        if profit_collection is not None:
            strategy_params["profit_collection"] = profit_collection
        
        # 確認參數
        print("\n" + "="*50)
        print("策略參數確認")
        print("="*50)
        for key, value in strategy_params.items():
            print(f"{key}: {value}")
        
        confirm = input("\n確認創建策略? (y/n): ")
        if confirm.lower() == 'y':
            self.create_strategy(strategy_params)
        else:
            print("\n[*] 已取消創建策略")

def main():
    parser = argparse.ArgumentParser(description='網格交易後端API測試腳本')
    parser.add_argument('-u', '--url', default='http://127.0.0.1:8000', 
                        help='後端API基地址 (默認: http://127.0.0.1:8000)')
    parser.add_argument('--non-interactive', action='store_true',
                        help='非互動模式，使用默認參數執行測試')
    args = parser.parse_args()
    
    tester = GridTradingTester(args.url)
    
    if args.non_interactive:
        # 非互動模式測試流程
        username = input("用戶名: ")
        password = getpass("密碼: ")
        
        if not tester.login(username, password):
            return
        
        # 創建策略
        strategy_params = {
            "symbol": "BTCUSDT",
            "grid_type": "ARITHMETIC",
            "strategy_type": "NEUTRAL",
            "lower_price": 50000,
            "upper_price": 60000,
            "grid_number": 10,
            "total_investment": 1000,
            "leverage": 1
        }
        
        if tester.create_strategy(strategy_params):
            time.sleep(1)
            tester.start_strategy()
            time.sleep(1)
            tester.get_strategy_orders()
            time.sleep(1)
            tester.stop_strategy()
            time.sleep(1)
            tester.delete_strategy()
    else:
        # 互動模式
        tester.interactive_test()

if __name__ == "__main__":
    main()