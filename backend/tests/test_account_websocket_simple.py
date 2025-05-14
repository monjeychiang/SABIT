#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import websockets
import requests
import json
import logging
import getpass
import sys
import argparse
import traceback  # 新增：用於打印詳細堆疊跟踪

# 配置基本日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SimpleAccountTester:
    def __init__(self, base_url="http://localhost:8000", debug=False):
        """初始化測試器"""
        self.base_url = base_url
        self.api_url = f"{base_url}/api/v1"
        # 轉換HTTP URL為WebSocket URL
        self.ws_url = base_url.replace('http://', 'ws://').replace('https://', 'wss://')
        self.token = None
        self.exchange = "binance"
        self.debug = debug
        # 直接使用的 API 密鑰
        self.direct_api_key = None
        self.direct_api_secret = None
        
        # 如果開啟調試模式，設置更詳細的日誌級別
        if self.debug:
            logging.getLogger().setLevel(logging.DEBUG)
            logger.debug("調試模式已啟用")
        
    async def run_test(self, username, password, api_key=None, api_secret=None, test_simple_endpoint=False, use_direct_api=False):
        """執行完整測試流程"""
        # 步驟1: 登入獲取JWT令牌
        if not self.login(username, password):
            logger.error("登入失敗，測試終止")
            return False
            
        # 步驟2: 處理 API 密鑰
        if use_direct_api and api_key and api_secret:
            # 直接使用提供的 API 密鑰，不存入數據庫
            self.direct_api_key = api_key
            self.direct_api_secret = api_secret
            logger.info(f"將直接使用提供的 API 密鑰，不涉及數據庫加密/解密")
        elif api_key and api_secret:
            # 存入數據庫
            if not self.set_api_key(api_key, api_secret):
                logger.error("設置API密鑰失敗，測試終止")
                return False
        else:
            # 檢查是否已有API密鑰
            if not self.check_api_key_exists() and not test_simple_endpoint and not use_direct_api:
                logger.error(f"未找到{self.exchange}的API密鑰，測試終止")
                return False
        
        # 步驟2.5: 檢查後端API是否可用
        if not self.check_backend_api():
            logger.error("後端API不可用，測試終止")
            logger.info("請確認API地址正確，並且服務器正在運行")
            return False
                
        # 步驟3: 測試WebSocket連接
        if test_simple_endpoint:
            # 先測試簡單的測試端點
            logger.info("測試簡單WebSocket端點")
            if await self.test_simple_websocket():
                logger.info("簡單WebSocket端點測試成功")
                
                # 簡單端點成功，詢問是否繼續測試主要端點
                if input("簡單WebSocket測試成功，是否繼續測試賬戶數據WebSocket? (y/n): ").lower() == 'y':
                    return await self.test_websocket(use_direct_api)
                else:
                    return True
            else:
                logger.error("簡單WebSocket端點測試失敗，問題可能在於基本WebSocket功能")
                return False
        else:
            # 直接測試主要端點
            return await self.test_websocket(use_direct_api)
            
    async def test_simple_websocket(self):
        """測試簡單的WebSocket測試端點"""
        # 構建WebSocket URL - 添加 token 作為查詢參數
        ws_test_url = f"{self.ws_url}/test-websocket?token={self.token}"
        
        try:
            logger.info(f"連接到測試WebSocket: {ws_test_url}")
            
            # 添加更多的連接選項
            connect_kwargs = {
                "ping_interval": 30,
                "open_timeout": 20,  # 增加超時時間
                "max_size": None,    # 不限制消息大小
                "close_timeout": 10,  # 增加關閉超時
            }
            
            # 使用更多選項連接
            async with websockets.connect(ws_test_url, **connect_kwargs) as websocket:
                logger.info("等待測試WebSocket回應...")
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                logger.info(f"收到測試WebSocket回應: {response}")
                
                if response == "連接成功":
                    logger.info("測試WebSocket連接成功")
                    return True
                else:
                    logger.error(f"測試WebSocket回應異常: {response}")
                    return False
                    
        except asyncio.TimeoutError:
            logger.error("等待測試WebSocket回應超時")
            return False
        except websockets.exceptions.ConnectionClosedError as e:
            logger.error(f"測試WebSocket連接被關閉: {e}")
            if self.debug:
                logger.debug(f"關閉代碼: {e.code}, 原因: {e.reason}")
            return False
        except Exception as e:
            logger.error(f"測試WebSocket連接錯誤: {str(e)}")
            if self.debug:
                logger.debug(traceback.format_exc())
            return False
    
    def login(self, username, password):
        """登入系統獲取JWT令牌"""
        try:
            logger.info("正在登入系統...")
            
            # 構建登入請求
            login_url = f"{self.api_url}/auth/login"
            login_data = {
                "username": username,
                "password": password
            }
            
            # 發送登入請求
            response = requests.post(login_url, data=login_data, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"登入失敗: 狀態碼 {response.status_code}")
                if self.debug:
                    logger.debug(f"響應內容: {response.text}")
                return False
                
            # 解析返回的JWT令牌
            response_data = response.json()
            self.token = response_data.get("access_token")
            
            if not self.token:
                logger.error("登入成功但未獲取到JWT令牌")
                return False
                
            logger.info("登入成功，已獲取JWT令牌")
            if self.debug:
                logger.debug(f"令牌長度: {len(self.token)}")
                logger.debug(f"令牌前20個字符: {self.token[:20]}...")
            return True
            
        except Exception as e:
            logger.error(f"登入過程發生錯誤: {str(e)}")
            if self.debug:
                logger.debug(traceback.format_exc())
            return False
    
    def set_api_key(self, api_key, api_secret):
        """設置API密鑰"""
        if not self.token:
            logger.error("未登入，無法設置API密鑰")
            return False
            
        try:
            logger.info(f"設置{self.exchange}的API密鑰...")
            
            # 檢查是否已有API密鑰
            headers = {"Authorization": f"Bearer {self.token}"}
            check_url = f"{self.api_url}/api-keys"
            
            check_response = requests.get(check_url, headers=headers, timeout=10)
            if check_response.status_code != 200:
                logger.error(f"檢查API密鑰失敗: 狀態碼 {check_response.status_code}")
                if self.debug:
                    logger.debug(f"響應內容: {check_response.text}")
                return False
                
            existing_keys = check_response.json()
            existing_key = next((k for k in existing_keys if k["exchange"] == self.exchange), None)
            
            # 設置API密鑰
            api_data = {
                "api_key": api_key,
                "api_secret": api_secret
            }
            
            if existing_key:
                # 更新現有API密鑰
                logger.info(f"更新已有API密鑰")
                update_url = f"{self.api_url}/api-keys/{self.exchange}"
                response = requests.put(update_url, json=api_data, headers=headers, timeout=10)
            else:
                # 創建新的API密鑰
                logger.info("創建新的API密鑰")
                create_url = f"{self.api_url}/api-keys"
                api_data["exchange"] = self.exchange
                response = requests.post(create_url, json=api_data, headers=headers, timeout=10)
            
            if response.status_code not in (200, 201):
                logger.error(f"設置API密鑰失敗: 狀態碼 {response.status_code}")
                if self.debug:
                    logger.debug(f"響應內容: {response.text}")
                return False
                
            result = response.json()
            if result.get("success", False):
                logger.info(f"成功設置{self.exchange}的API密鑰")
                return True
            else:
                logger.error(f"設置API密鑰失敗: {result.get('message', '未知錯誤')}")
                return False
                
        except Exception as e:
            logger.error(f"設置API密鑰時發生錯誤: {str(e)}")
            if self.debug:
                logger.debug(traceback.format_exc())
            return False
            
    def check_api_key_exists(self):
        """檢查是否已有API密鑰配置"""
        if not self.token:
            logger.error("未登入，無法檢查API密鑰")
            return False
            
        try:
            logger.info("檢查是否有可用的API密鑰配置...")
            
            headers = {"Authorization": f"Bearer {self.token}"}
            check_url = f"{self.api_url}/api-keys"
            
            check_response = requests.get(check_url, headers=headers, timeout=10)
            if check_response.status_code != 200:
                logger.error(f"檢查API密鑰失敗: 狀態碼 {check_response.status_code}")
                if self.debug:
                    logger.debug(f"響應內容: {check_response.text}")
                return False
                
            existing_keys = check_response.json()
            existing_key = next((k for k in existing_keys if k["exchange"] == self.exchange), None)
            
            if existing_key:
                logger.info(f"找到{self.exchange}的API密鑰配置")
                return True
            else:
                logger.info(f"未找到{self.exchange}的API密鑰配置")
                return False
                
        except Exception as e:
            logger.error(f"檢查API密鑰時發生錯誤: {str(e)}")
            if self.debug:
                logger.debug(traceback.format_exc())
            return False
            
    def check_backend_api(self):
        """檢查後端API是否可用"""
        try:
            logger.info("檢查後端API是否可用...")
            
            # 檢查基本API端點
            headers = {"Authorization": f"Bearer {self.token}"}
            
            # 嘗試使用已知可用的API端點
            check_url = f"{self.api_url}/api-keys"
            check_response = requests.get(check_url, headers=headers, timeout=5)
            
            if check_response.status_code == 200:
                logger.info("後端API連接正常")
                return True
            else:
                logger.error(f"無法訪問API，狀態碼: {check_response.status_code}")
                if self.debug:
                    logger.debug(f"響應內容: {check_response.text}")
                return False
                
        except Exception as e:
            logger.error(f"檢查後端API時發生錯誤: {str(e)}")
            if self.debug:
                logger.debug(traceback.format_exc())
            return False
            
    async def test_websocket(self, use_direct_api=False):
        """測試WebSocket連接獲取賬戶資訊"""
        if not self.token:
            logger.error("未登入，無法測試WebSocket連接")
            return False
            
        # 構建WebSocket URL，包含token作為查詢參數
        ws_account_url = f"{self.ws_url}/account/futures-account/{self.exchange}?token={self.token}"
        
        try:
            logger.info(f"連接到WebSocket: {ws_account_url}")
            
            # 添加連接參數
            connect_kwargs = {
                "ping_interval": 30,
                "open_timeout": 20,  # 增加超時時間
                "max_size": None,    # 不限制消息大小
                "close_timeout": 10,  # 增加關閉超時
            }
            
            # 嘗試直接連接
            if self.debug:
                logger.debug(f"令牌長度: {len(self.token)} 字符")
                logger.debug(f"令牌前10個字符: {self.token[:10]}...")
            
            async with websockets.connect(ws_account_url, **connect_kwargs) as websocket:
                # 連接已建立，等待服務器回應
                logger.info("WebSocket連接已建立，等待服務器回應")
                
                # 如果直接使用 API 密鑰，發送特殊指令
                if use_direct_api and self.direct_api_key and self.direct_api_secret:
                    logger.info("使用直接模式，發送API密鑰直接給WebSocket")
                    direct_api_msg = json.dumps({
                        "direct_api": True,
                        "api_key": self.direct_api_key,
                        "api_secret": self.direct_api_secret
                    })
                    await websocket.send(direct_api_msg)
                    logger.info("已發送直接API密鑰")
                
                # 等待連接確認
                logger.info("等待連接確認...")
                response = await asyncio.wait_for(websocket.recv(), timeout=15.0)
                data = json.loads(response)
                
                # 檢查響應
                if not data.get("success", False):
                    error_msg = data.get("message", "未知錯誤")
                    logger.error(f"WebSocket認證失敗: {error_msg}")
                    if "error" in data:
                        logger.error(f"詳細錯誤: {data['error']}")
                    return False
                
                logger.info(f"WebSocket認證成功: {data.get('message', 'No message')}")
                
                # 進入數據處理階段
                return await self._process_websocket_data(websocket)
                    
        except asyncio.TimeoutError:
            logger.error("等待WebSocket應答超時")
            return False
        except websockets.exceptions.ConnectionClosed as e:
            logger.error(f"WebSocket連接被關閉: {e}")
            if self.debug:
                logger.debug(f"關閉代碼: {e.code}, 原因: {e.reason}")
            return False
        except Exception as e:
            logger.error(f"WebSocket連接錯誤: {str(e)}")
            if self.debug:
                logger.debug(traceback.format_exc())
            return False
            
    async def _process_websocket_data(self, websocket):
        """處理WebSocket接收到的數據"""
        try:
            logger.info("等待接收賬戶資料...")
            response = await asyncio.wait_for(websocket.recv(), timeout=20.0)  # 增加超時時間
            data = json.loads(response)
            
            # 檢查是否收到賬戶資料
            if "data" in data:
                logger.info("成功接收到賬戶資料!")
                
                # 顯示部分資料（類似於前端展示）
                if "balances" in data["data"]:
                    balances = data["data"]["balances"]
                    logger.info(f"餘額數量: {len(balances)}")
                    
                    # 顯示前3個餘額
                    for i, balance in enumerate(balances[:3]):
                        logger.info(f"餘額 {i+1}: {balance.get('asset')} - 可用: {balance.get('free')}")
                
                if "positions" in data["data"]:
                    positions = data["data"]["positions"]
                    active_positions = [p for p in positions if float(p.get('positionAmt', 0)) != 0]
                    logger.info(f"持倉數量: {len(active_positions)}")
                    
                    # 顯示前3個持倉
                    for i, position in enumerate(active_positions[:3]):
                        logger.info(f"持倉 {i+1}: {position.get('symbol')} - 數量: {position.get('positionAmt')}")
                
                return True
            else:
                logger.error("未能接收到賬戶資料")
                if self.debug and data:
                    logger.debug(f"收到的數據: {json.dumps(data, indent=2)}")
                return False
                
        except asyncio.TimeoutError:
            logger.error("等待賬戶資料超時")
            return False
        except Exception as e:
            logger.error(f"處理WebSocket數據時出錯: {str(e)}")
            if self.debug:
                logger.debug(traceback.format_exc())
            return False

async def main():
    # 解析命令行參數
    parser = argparse.ArgumentParser(description='帳戶WebSocket簡易測試工具')
    parser.add_argument('--debug', action='store_true', help='啟用調試模式')
    parser.add_argument('--url', help='API基礎URL', default='')
    parser.add_argument('--username', help='用戶名')
    parser.add_argument('--password', help='密碼 (不建議使用)')
    parser.add_argument('--api-key', help='API密鑰')
    parser.add_argument('--api-secret', help='API密鑰密碼 (不建議使用)')
    parser.add_argument('--test-simple', action='store_true', help='先測試簡單的WebSocket端點')
    parser.add_argument('--direct-api', action='store_true', help='直接使用提供的API密鑰，不涉及數據庫')
    args = parser.parse_args()
    
    # 使用方式說明
    print("===== 帳戶WebSocket簡易測試工具 =====")
    print("此工具測試與實際前端相同的WebSocket連接流程")
    
    # 獲取伺服器URL
    base_url = args.url
    if not base_url:
        base_url = input("請輸入API基礎URL (默認: http://localhost:8000): ").strip()
    if not base_url:
        base_url = "http://localhost:8000"
    
    # 建立測試器
    tester = SimpleAccountTester(base_url, debug=args.debug)
    
    # 獲取用戶憑據
    username = args.username
    if not username:
        username = input("請輸入用戶名: ").strip()
    
    password = args.password
    if not password:
        password = getpass.getpass("請輸入密碼: ")
    
    # 詢問是否需要設置API密鑰
    api_key = args.api_key
    api_secret = args.api_secret
    
    if not api_key and not api_secret and (not args.test_simple or args.direct_api):
        use_direct_api = args.direct_api or input("是否直接使用API密鑰進行測試 (不存入數據庫)? (y/n): ").strip().lower() == 'y'
        
        if use_direct_api:
            print("\n直接測試模式: API密鑰將直接用於測試，繞過數據庫加密/解密環節")
            api_key = input("請輸入API密鑰: ").strip()
            api_secret = getpass.getpass("請輸入API密鑰密碼: ")
        elif not args.test_simple:
            setup_api = input("是否需要設置API密鑰? (y/n): ").strip().lower()
            if setup_api == 'y':
                api_key = input("請輸入API密鑰: ").strip()
                api_secret = getpass.getpass("請輸入API密鑰密碼: ")
    else:
        use_direct_api = args.direct_api
    
    # 執行測試
    result = await tester.run_test(
        username, 
        password, 
        api_key, 
        api_secret,
        test_simple_endpoint=args.test_simple,
        use_direct_api=use_direct_api
    )
    
    if result:
        print("✅ 測試成功! WebSocket連接正常工作。")
    else:
        print("❌ 測試失敗! 請檢查錯誤信息。")
        
        # 提供進一步調試建議
        print("\n調試建議:")
        print("1. 使用 --debug 參數啟用詳細日誌")
        print("2. 使用 --test-simple 參數先測試簡單WebSocket端點")
        print("3. 使用 --direct-api 參數直接使用API密鑰，繞過數據庫")
        print("4. 檢查後端服務器是否正常運行")
        print("5. 檢查後端日誌是否有錯誤信息")
        print("6. 確認API密鑰是否有正確權限")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n測試已中斷")
        sys.exit(0) 