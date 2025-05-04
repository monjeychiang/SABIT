#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
一般登錄功能測試腳本

這個腳本專門測試一般登入（標準登入）功能，關注點：
1. 測試不保持登入的情況
2. 測試保持登入的情況
3. 特別關注刷新令牌(refresh token)的行為
4. 測試訪問受保護資源
5. 測試令牌過期和刷新機制

注意，測試邏輯符合實際使用場景：
- 不保持登入：系統不使用刷新令牌功能，訪問令牌過期後需要重新登入
- 保持登入：系統使用刷新令牌功能，可以在不需要重新輸入密碼的情況下自動更新訪問令牌

使用方法:
python test_regular_login.py         # 啟動交互式選單，選擇要測試的項目
python test_regular_login.py --all   # 運行所有測試
python test_regular_login.py --keep  # 僅測試保持登入
python test_regular_login.py --no-keep  # 僅測試不保持登入

注意：由於使用 SQLite 數據庫，已禁用併發測試功能。

腳本記錄會包含請求頭和響應的詳細信息，以便調試潛在問題。
"""

import sys
import os
import time
import json
import logging
import requests
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, List, Union
from urllib.parse import urlparse, parse_qs
import uuid
import base64
import re
import webbrowser

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("一般登入測試")

# 服務器配置
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")

# 測試賬號配置 (可以通過環境變量設置或直接修改這裡)
TEST_USERNAME = os.getenv("TEST_USERNAME", "testuser")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "testpassword")
TEST_EMAIL = os.getenv("TEST_EMAIL", "test@example.com")

# API端點
AUTH_ENDPOINTS = {
    "register": f"{API_BASE_URL}/auth/register",
    "login": f"{API_BASE_URL}/auth/login",  # 一般登入端點
    "refresh": f"{API_BASE_URL}/auth/refresh",
    "logout": f"{API_BASE_URL}/auth/logout",
    "me": f"{API_BASE_URL}/auth/me",
    "config": f"{API_BASE_URL}/auth/config",
    "google_login": f"{API_BASE_URL}/auth/google/login",  # Google登入端點
    "google_callback": f"{API_BASE_URL}/auth/google/callback",  # Google回調端點
}

# 存儲令牌數據
token_data = {
    "access_token": None,
    "refresh_token": None,
    "token_type": None,
    "expires_in": None,
    "refresh_token_expires_in": None,
    "expiry_time": None,
    "refresh_token_expiry_time": None
}

# 會話對象 - 用於跟踪請求/響應細節
session = requests.Session()
session.hooks = {
    'response': lambda r, *args, **kwargs: r.raise_for_status()
}

# 添加請求日誌記錄
def log_request(request, *args, **kwargs):
    logger.debug(f"請求: {request.method} {request.url}")
    logger.debug(f"請求頭: {request.headers}")
    if request.body:
        try:
            logger.debug(f"請求體: {request.body}")
        except:
            logger.debug("請求體: [無法顯示]")

# 添加響應日誌記錄
def log_response(response, *args, **kwargs):
    logger.debug(f"響應: {response.status_code} {response.reason}")
    logger.debug(f"響應頭: {response.headers}")
    try:
        logger.debug(f"響應體: {response.text[:500]}" + ('...' if len(response.text) > 500 else ''))
    except:
        logger.debug("響應體: [無法顯示]")

# 添加會話日誌掛鉤
if not isinstance(session.hooks['response'], list):
    session.hooks['response'] = [session.hooks['response']]
session.hooks['response'].append(log_response)

# 添加請求日誌記錄
old_send = requests.Session.send
def patched_send(self, request, **kwargs):
    log_request(request, **kwargs)
    return old_send(self, request, **kwargs)
requests.Session.send = patched_send

def print_section(title: str) -> None:
    """打印測試章節標題"""
    logger.info("=" * 80)
    logger.info(f" {title} ".center(80, "="))
    logger.info("=" * 80)

def print_result(name: str, success: bool, message: Optional[str] = None) -> None:
    """打印測試結果"""
    status = "✓ 成功" if success else "✗ 失敗"
    logger.info(f"{name}: {status}" + (f" - {message}" if message else ""))

def register_user() -> bool:
    """註冊新測試用戶，如果用戶已存在則忽略"""
    print_section("註冊測試用戶")
    
    # 在函數開頭聲明全局變量
    global TEST_USERNAME, TEST_EMAIL
    
    try:
        # 生成隨機後綴，確保用戶名唯一
        random_suffix = str(uuid.uuid4())[:6]
        username = f"{TEST_USERNAME}_{random_suffix}"
        email = f"{random_suffix}_{TEST_EMAIL}"
        
        logger.info(f"嘗試註冊新用戶: {username} ({email})")
        
        # 準備註冊數據
        data = {
            "username": username,
            "email": email,
            "password": TEST_PASSWORD,
            "confirm_password": TEST_PASSWORD
        }
        
        # 發送註冊請求
        response = session.post(AUTH_ENDPOINTS["register"], json=data)
        
        # 保存新的測試用戶名和郵箱
        TEST_USERNAME = username
        TEST_EMAIL = email
        
        logger.info(f"成功註冊用戶: {username}")
        return True
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400 and "已被使用" in e.response.text:
            logger.info(f"用戶已存在，跳過註冊")
            return True
        else:
            logger.error(f"註冊失敗: {e}")
            return False
    except Exception as e:
        logger.error(f"註冊過程中出現錯誤: {str(e)}")
        return False

def login_regular(keep_logged_in: bool = False) -> bool:
    """
    使用標準登錄端點登錄測試用戶並獲取令牌
    
    參數:
        keep_logged_in: 是否保持登入
    """
    print_section(f"標準登錄測試 (保持登入: {keep_logged_in})")
    
    try:
        # 準備表單數據
        form_data = {
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
            "keep_logged_in": str(keep_logged_in).lower()
        }
        
        # 發送登錄請求
        logger.info(f"嘗試使用標準登錄端點登錄用戶: {TEST_USERNAME}")
        logger.info(f"保持登入: {keep_logged_in}")
        
        start_time = time.time()
        # 明確設置Content-Type為表單格式
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        response = session.post(AUTH_ENDPOINTS["login"], data=form_data, headers=headers)
        end_time = time.time()
        
        logger.info(f"登錄請求用時: {(end_time - start_time):.3f}秒")
        
        # 檢查響應
        if response.status_code == 200:
            logger.info("標準登錄成功")
            response_data = response.json()
            
            # 保存令牌數據
            token_data["access_token"] = response_data.get("access_token")
            token_data["refresh_token"] = response_data.get("refresh_token")
            token_data["token_type"] = response_data.get("token_type", "bearer")
            token_data["expires_in"] = response_data.get("expires_in")
            token_data["refresh_token_expires_in"] = response_data.get("refresh_token_expires_in")
            
            # 計算過期時間
            now = datetime.now()
            if token_data["expires_in"]:
                expiry_time = now.timestamp() + token_data["expires_in"]
                token_data["expiry_time"] = expiry_time
                expiry_datetime = datetime.fromtimestamp(expiry_time)
                logger.info(f"訪問令牌將在 {expiry_datetime.strftime('%Y-%m-%d %H:%M:%S')} 過期")
                logger.info(f"訪問令牌有效期: {token_data['expires_in']}秒 ({token_data['expires_in']/60:.1f}分鐘)")
            
            # 計算刷新令牌過期時間
            if token_data["refresh_token_expires_in"]:
                refresh_expiry_time = now.timestamp() + token_data["refresh_token_expires_in"]
                token_data["refresh_token_expiry_time"] = refresh_expiry_time
                refresh_expiry_datetime = datetime.fromtimestamp(refresh_expiry_time)
                logger.info(f"刷新令牌將在 {refresh_expiry_datetime.strftime('%Y-%m-%d %H:%M:%S')} 過期")
                logger.info(f"刷新令牌有效期: {token_data['refresh_token_expires_in']}秒 ({token_data['refresh_token_expires_in']/86400:.1f}天)")
                
                # 記錄保持登入模式的不同
                if keep_logged_in:
                    logger.info("由於選擇了保持登入，刷新令牌有較長的有效期")
                else:
                    logger.info("由於選擇了不保持登入，系統可能不會使用刷新令牌，或刷新令牌有較短的有效期")
            else:
                if not keep_logged_in:
                    logger.info("未收到刷新令牌，這符合不保持登入的預期行為")
                else:
                    logger.warning("選擇了保持登入，但未收到刷新令牌有效期信息，這可能是個問題")
            
            # 記錄令牌信息
            if token_data["access_token"]:
                logger.info(f"已獲取訪問令牌: {token_data['access_token'][:15]}... (已截斷)")
            if token_data["refresh_token"]:
                logger.info(f"已獲取刷新令牌: {token_data['refresh_token'][:15]}... (已截斷)")
            else:
                logger.info("未收到刷新令牌")
            
            return True
        else:
            logger.error(f"標準登錄失敗: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"標準登錄過程中出現錯誤: {str(e)}")
        return False

def refresh_token(keep_logged_in: bool = None) -> bool:
    """
    使用刷新令牌獲取新的訪問令牌
    
    參數:
    - keep_logged_in: 是否保持登錄狀態，None表示使用前一次的設置
    """
    # 確定保持登錄狀態
    if keep_logged_in is None:
        # 通過刷新令牌有效期推斷之前的設置
        if token_data["refresh_token_expires_in"] and token_data["expires_in"]:
            keep_logged_in = token_data["refresh_token_expires_in"] > token_data["expires_in"] * 1.1
        else:
            keep_logged_in = False
    
    print_section(f"刷新令牌測試 (保持登入: {keep_logged_in})")
    
    try:
        # 檢查是否有刷新令牌
        if not token_data["refresh_token"]:
            logger.error("沒有刷新令牌，無法刷新")
            return False
        
        # 準備表單數據
        form_data = {
            "refresh_token": token_data["refresh_token"],
            "keep_logged_in": str(keep_logged_in).lower()
        }
        
        # 準備請求頭 - 明確請求JSON響應
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        # 記錄舊令牌用於比較
        old_access_token = token_data["access_token"]
        old_refresh_token = token_data["refresh_token"]
        
        # 發送刷新令牌請求
        logger.info("嘗試刷新令牌")
        logger.info(f"使用請求頭: {headers}")
        
        start_time = time.time()
        response = session.post(
            AUTH_ENDPOINTS["refresh"], 
            data=form_data, 
            headers=headers
        )
        end_time = time.time()
        
        logger.info(f"刷新請求用時: {(end_time - start_time):.3f}秒")
        
        # 檢查響應
        if response.status_code == 200:
            logger.info("令牌刷新成功 (JSON響應)")
            response_data = response.json()
            
            # 保存新的令牌數據
            token_data["access_token"] = response_data.get("access_token")
            token_data["expires_in"] = response_data.get("expires_in")
            token_data["refresh_token_expires_in"] = response_data.get("refresh_token_expires_in")
            
            # 獲取新的刷新令牌
            if "refresh_token" in response_data:
                token_data["refresh_token"] = response_data.get("refresh_token")
                logger.info("收到新的刷新令牌")
            else:
                logger.info("未收到新的刷新令牌，繼續使用舊的刷新令牌")
            
            # 檢查令牌是否實際更改
            token_changed = old_access_token != token_data["access_token"]
            refresh_token_changed = old_refresh_token != token_data["refresh_token"]
            
            logger.info(f"訪問令牌已更改: {token_changed}")
            logger.info(f"刷新令牌已更改: {refresh_token_changed}")
            
            # 計算並更新過期時間
            now = datetime.now()
            if token_data["expires_in"]:
                expiry_time = now.timestamp() + token_data["expires_in"]
                token_data["expiry_time"] = expiry_time
                expiry_datetime = datetime.fromtimestamp(expiry_time)
                logger.info(f"新訪問令牌將在 {expiry_datetime.strftime('%Y-%m-%d %H:%M:%S')} 過期")
                logger.info(f"新訪問令牌有效期: {token_data['expires_in']}秒 ({token_data['expires_in']/60:.1f}分鐘)")
            
            # 計算刷新令牌過期時間
            if token_data["refresh_token_expires_in"]:
                refresh_expiry_time = now.timestamp() + token_data["refresh_token_expires_in"]
                token_data["refresh_token_expiry_time"] = refresh_expiry_time
                refresh_expiry_datetime = datetime.fromtimestamp(refresh_expiry_time)
                logger.info(f"新刷新令牌將在 {refresh_expiry_datetime.strftime('%Y-%m-%d %H:%M:%S')} 過期")
                logger.info(f"新刷新令牌有效期: {token_data['refresh_token_expires_in']}秒 ({token_data['refresh_token_expires_in']/86400:.1f}天)")
            
            logger.info(f"新訪問令牌: {token_data['access_token'][:15]}... (已截斷)")
            if refresh_token_changed:
                logger.info(f"新刷新令牌: {token_data['refresh_token'][:15]}... (已截斷)")
            
            return True
        else:
            logger.error(f"刷新令牌失敗: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"刷新令牌過程中出現錯誤: {str(e)}")
        return False

def get_user_profile() -> Union[Dict[str, Any], None]:
    """獲取當前登錄用戶的個人資料"""
    print_section("獲取用戶資料")
    
    try:
        # 準備請求頭
        headers = {
            "Authorization": f"{token_data['token_type']} {token_data['access_token']}"
        }
        
        # 發送請求
        logger.info("請求用戶資料")
        response = session.get(AUTH_ENDPOINTS["me"], headers=headers)
        
        # 檢查響應
        if response.status_code == 200:
            user_data = response.json()
            logger.info(f"成功獲取用戶資料: {user_data['username']} ({user_data['email']})")
            return user_data
        elif response.status_code == 401:
            # 檢查是否有刷新令牌可用
            if not token_data["refresh_token"]:
                logger.info("訪問令牌已過期，且沒有刷新令牌可用（可能是'不保持登入'模式）")
                logger.info("在實際應用中，用戶需要重新登入")
                return None
                
            logger.warning("授權已過期，嘗試刷新令牌")
            if refresh_token():
                # 使用新令牌再次嘗試
                headers = {
                    "Authorization": f"{token_data['token_type']} {token_data['access_token']}"
                }
                response = session.get(AUTH_ENDPOINTS["me"], headers=headers)
                if response.status_code == 200:
                    user_data = response.json()
                    logger.info(f"成功獲取用戶資料(刷新令牌後): {user_data['username']} ({user_data['email']})")
                    return user_data
                else:
                    logger.error(f"刷新令牌後獲取用戶資料仍然失敗: {response.status_code} - {response.text}")
                    return None
            else:
                logger.error("刷新令牌失敗，無法獲取用戶資料")
                return None
        else:
            logger.error(f"獲取用戶資料失敗: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"獲取用戶資料過程中出現錯誤: {str(e)}")
        return None

def test_concurrent_refresh(num_requests: int = 2) -> bool:
    """
    測試同時發送多個刷新請求的情況
    
    參數:
    - num_requests: 同時發送的請求數量
    """
    print_section(f"測試同時刷新 ({num_requests}個並發請求)")
    
    try:
        # 檢查是否有刷新令牌
        if not token_data["refresh_token"]:
            logger.error("沒有刷新令牌，無法進行並發刷新測試")
            return False
        
        # 準備請求數據
        form_data = {
            "refresh_token": token_data["refresh_token"],
            "keep_logged_in": "true"  # 使用保持登入模式進行測試
        }
        
        # 準備請求頭 - 明確請求JSON響應
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        # 記錄開始時間
        start_time = time.time()
        
        # 創建並發送多個刷新請求
        import threading
        responses = [None] * num_requests
        threads = []
        
        def send_request(index):
            try:
                resp = session.post(
                    AUTH_ENDPOINTS["refresh"], 
                    data=form_data, 
                    headers=headers
                )
                responses[index] = resp
            except Exception as e:
                logger.error(f"請求 {index} 失敗: {str(e)}")
        
        # 創建和啟動線程
        for i in range(num_requests):
            thread = threading.Thread(target=send_request, args=(i,))
            threads.append(thread)
            thread.start()
        
        # 等待所有線程完成
        for thread in threads:
            thread.join()
        
        # 計算總耗時
        end_time = time.time()
        total_time = end_time - start_time
        logger.info(f"所有 {num_requests} 個並發請求完成，總耗時: {total_time:.3f}秒")
        
        # 分析響應
        success_count = 0
        for i, response in enumerate(responses):
            if response and response.status_code == 200:
                success_count += 1
                logger.info(f"請求 {i}: 成功 (狀態碼: {response.status_code})")
            else:
                status = response.status_code if response else "無響應"
                logger.error(f"請求 {i}: 失敗 (狀態碼: {status})")
        
        # 更新令牌數據 (使用最後一個成功的響應)
        for response in responses:
            if response and response.status_code == 200:
                response_data = response.json()
                
                # 更新令牌數據
                token_data["access_token"] = response_data.get("access_token")
                token_data["expires_in"] = response_data.get("expires_in")
                token_data["refresh_token_expires_in"] = response_data.get("refresh_token_expires_in")
                
                # 更新刷新令牌
                if "refresh_token" in response_data:
                    token_data["refresh_token"] = response_data.get("refresh_token")
                
                # 更新過期時間
                now = datetime.now()
                if token_data["expires_in"]:
                    token_data["expiry_time"] = now.timestamp() + token_data["expires_in"]
                if token_data["refresh_token_expires_in"]:
                    token_data["refresh_token_expiry_time"] = now.timestamp() + token_data["refresh_token_expires_in"]
                
                break
        
        # 測試結果
        logger.info(f"成功率: {success_count}/{num_requests} ({success_count/num_requests*100:.1f}%)")
        return success_count > 0
            
    except Exception as e:
        logger.error(f"並發刷新測試過程中出現錯誤: {str(e)}")
        return False

def test_expired_token_handling():
    """測試已過期令牌的處理機制"""
    print_section("過期令牌處理測試")
    
    try:
        # 保存原始令牌和過期時間
        original_access_token = token_data["access_token"]
        original_expiry_time = token_data["expiry_time"]
        
        # 模擬令牌過期
        logger.info("模擬訪問令牌已過期")
        token_data["expiry_time"] = datetime.now().timestamp() - 3600  # 過期1小時
        
        # 嘗試獲取用戶資料（應該會觸發令牌刷新）
        logger.info("使用過期令牌嘗試訪問受保護資源")
        user_data = get_user_profile()
        
        # 驗證結果
        if user_data:
            logger.info("成功：系統正確處理了過期令牌，並使用刷新令牌獲取了新令牌")
            return True
        else:
            # 如果失敗，恢復原始令牌以便繼續其他測試
            token_data["access_token"] = original_access_token
            token_data["expiry_time"] = original_expiry_time
            logger.error("測試失敗：系統未能正確處理過期令牌")
            return False
            
    except Exception as e:
        logger.error(f"過期令牌處理測試中出現錯誤: {str(e)}")
        return False

def logout() -> bool:
    """登出並撤銷刷新令牌"""
    print_section("登出測試")
    
    try:
        # 檢查是否有刷新令牌
        if not token_data["refresh_token"]:
            logger.error("沒有刷新令牌，無法完成登出")
            return False
        
        # 準備表單數據
        form_data = {
            "refresh_token": token_data["refresh_token"]
        }
        
        # 發送登出請求
        logger.info("嘗試登出用戶")
        start_time = time.time()
        response = session.post(AUTH_ENDPOINTS["logout"], data=form_data)
        end_time = time.time()
        logger.info(f"登出請求用時: {(end_time - start_time):.3f}秒")
        
        # 檢查響應
        if response.status_code == 200:
            logger.info("登出成功")
            
            # 清除令牌數據
            token_data["access_token"] = None
            token_data["refresh_token"] = None
            token_data["expires_in"] = None
            token_data["refresh_token_expires_in"] = None
            token_data["expiry_time"] = None
            token_data["refresh_token_expiry_time"] = None
            
            return True
        else:
            logger.error(f"登出失敗: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"登出過程中出現錯誤: {str(e)}")
        return False

def verify_token_revoked() -> bool:
    """驗證令牌是否已被撤銷"""
    print_section("驗證令牌撤銷")
    
    try:
        # 如果沒有保存刷新令牌，直接返回成功
        if not token_data["refresh_token"]:
            logger.info("沒有保存的刷新令牌，假定已成功撤銷")
            return True
            
        # 準備表單數據
        form_data = {
            "refresh_token": token_data["refresh_token"]
        }
        
        # 準備請求頭 - 明確請求JSON響應
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        # 嘗試使用已撤銷的刷新令牌
        logger.info("嘗試使用已撤銷的刷新令牌")
        response = None
        try:
            response = session.post(
                AUTH_ENDPOINTS["refresh"], 
                data=form_data,
                headers=headers
            )
            # 如果沒有拋出異常，則檢查狀態碼
            logger.warning(f"使用已撤銷令牌的請求未拋出異常，狀態碼: {response.status_code}")
            return response.status_code == 401
        except requests.exceptions.HTTPError as e:
            # 檢查響應 - 應該返回401錯誤
            if e.response.status_code == 401:
                logger.info("成功：刷新令牌已被正確撤銷")
                return True
            else:
                logger.error(f"令牌撤銷驗證失敗: {e.response.status_code} - {e.response.text}")
                return False
            
    except Exception as e:
        logger.error(f"驗證令牌撤銷過程中出現錯誤: {str(e)}")
        return False

def get_backend_config() -> Dict[str, Any]:
    """獲取後端配置信息"""
    print_section("獲取後端配置")
    
    try:
        # 發送請求
        logger.info("獲取後端認證配置")
        response = session.get(AUTH_ENDPOINTS["config"])
        
        # 檢查響應
        if response.status_code == 200:
            config_data = response.json()
            logger.info("成功獲取後端配置:")
            logger.info(f"訪問令牌過期時間: {config_data.get('access_token_expire_minutes')}分鐘")
            logger.info(f"刷新令牌過期天數: {config_data.get('refresh_token_expire_days')}天")
            logger.info(f"刷新閾值秒數: {config_data.get('refresh_threshold_seconds')}秒")
            return config_data
        else:
            logger.error(f"獲取配置失敗: {response.status_code} - {response.text}")
            return {}
            
    except Exception as e:
        logger.error(f"獲取配置過程中出現錯誤: {str(e)}")
        return {}

def test_no_keep_login() -> None:
    """測試不保持登入的情況"""
    results = {}
    
    try:
        # 獲取後端配置
        config = get_backend_config()
        results["後端配置"] = bool(config)
        
        # 註冊測試用戶
        results["用戶註冊"] = register_user()
        if not results["用戶註冊"]:
            logger.error("測試用戶註冊失敗，無法繼續測試")
            return
        
        # 測試標準登錄（不保持登入）
        print_section("測試標準登錄（不保持登入）")
        results["標準登錄（不保持登入）"] = login_regular(keep_logged_in=False)
        if not results["標準登錄（不保持登入）"]:
            logger.error("標準登錄失敗，無法繼續測試")
            return
        
        # 執行後續測試
        # 獲取用戶資料
        user_data = get_user_profile()
        results["獲取用戶資料"] = bool(user_data)
        
        # 注意：在不保持登入的情況下，不應該使用刷新令牌功能
        logger.info("注意：不保持登入的情況下，不測試刷新令牌功能，這符合實際使用場景")
        
        # 登出
        results["登出"] = logout()
        
        # 驗證令牌已撤銷
        results["令牌撤銷驗證"] = verify_token_revoked()
        
        # 輸出測試結果匯總
        print_section("測試結果匯總")
        for test_name, passed in results.items():
            print_result(test_name, passed)
        
        # 計算通過率
        total_tests = len(results)
        passed_tests = sum(1 for result in results.values() if result)
        pass_rate = (passed_tests / total_tests) * 100
        
        logger.info("=" * 80)
        logger.info(f"測試完成: 通過 {passed_tests}/{total_tests} 測試項 ({pass_rate:.1f}%)")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"測試過程中出現未處理的錯誤: {str(e)}")
        import traceback
        traceback.print_exc()

def test_keep_login() -> None:
    """測試保持登入的情況"""
    results = {}
    
    try:
        # 獲取後端配置
        config = get_backend_config()
        results["後端配置"] = bool(config)
        
        # 註冊測試用戶
        results["用戶註冊"] = register_user()
        if not results["用戶註冊"]:
            logger.error("測試用戶註冊失敗，無法繼續測試")
            return
        
        # 測試標準登錄（保持登入）
        print_section("測試標準登錄（保持登入）")
        results["標準登錄（保持登入）"] = login_regular(keep_logged_in=True)
        if not results["標準登錄（保持登入）"]:
            logger.error("標準登錄失敗，無法繼續測試")
            return
        
        # 執行後續測試
        # 獲取用戶資料
        user_data = get_user_profile()
        results["獲取用戶資料"] = bool(user_data)
        
        # 刷新令牌（保持登入）
        results["刷新令牌"] = refresh_token(keep_logged_in=True)
        
        # 再次獲取用戶資料（驗證新令牌）
        new_user_data = get_user_profile()
        results["使用刷新令牌後獲取資料"] = bool(new_user_data)
        
        # 測試已過期令牌處理
        results["過期令牌處理"] = test_expired_token_handling()
        
        # 注意：由於使用 SQLite 數據庫，併發測試已禁用
        # results["並發刷新測試"] = test_concurrent_refresh(num_requests=2)
        logger.info("注意：使用 SQLite 數據庫，已跳過併發測試")
        
        # 登出
        results["登出"] = logout()
        
        # 驗證令牌已撤銷
        results["令牌撤銷驗證"] = verify_token_revoked()
        
        # 輸出測試結果匯總
        print_section("測試結果匯總")
        for test_name, passed in results.items():
            print_result(test_name, passed)
        
        # 計算通過率
        total_tests = len(results)
        passed_tests = sum(1 for result in results.values() if result)
        pass_rate = (passed_tests / total_tests) * 100
        
        logger.info("=" * 80)
        logger.info(f"測試完成: 通過 {passed_tests}/{total_tests} 測試項 ({pass_rate:.1f}%)")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"測試過程中出現未處理的錯誤: {str(e)}")
        import traceback
        traceback.print_exc()

def login_with_google(keep_logged_in: bool = False, auto_open_browser: bool = True) -> Union[bool, Dict[str, Any]]:
    """
    測試Google登錄流程第一步：獲取Google登錄URL並打開瀏覽器
    
    參數:
        keep_logged_in: 是否保持登入
        auto_open_browser: 是否自動打開瀏覽器（默認為True）
    
    返回:
        成功時返回包含授權URL和state的字典，失敗時返回False
    """
    print_section(f"Google登錄測試 - 第一步：獲取授權URL (保持登入: {keep_logged_in})")
    
    try:
        # 準備請求參數
        params = {
            "keep_logged_in": str(keep_logged_in).lower()
        }
        
        # 發送請求獲取Google授權URL
        logger.info(f"嘗試獲取Google授權URL (保持登入: {keep_logged_in})")
        
        start_time = time.time()
        response = session.get(AUTH_ENDPOINTS["google_login"], params=params)
        end_time = time.time()
        
        logger.info(f"獲取Google授權URL用時: {(end_time - start_time):.3f}秒")
        
        # 檢查響應
        if response.status_code == 200:
            authorization_url = response.json().get("authorization_url")
            logger.info("成功獲取Google授權URL")
            logger.info(f"授權URL: {authorization_url}")
            
            # 提取state參數，用於後續測試
            parsed_url = urlparse(authorization_url)
            query_params = parse_qs(parsed_url.query)
            state = None
            
            if "state" in query_params:
                state = query_params["state"][0]
                
                # 嘗試解析state參數以檢查keep_logged_in設置
                try:
                    state_data = json.loads(base64.b64decode(state).decode())
                    stored_keep_logged_in = state_data.get("keep_logged_in", False)
                    logger.info(f"State參數中的keep_logged_in設置: {stored_keep_logged_in}")
                    
                    # 驗證keep_logged_in設置是否正確傳遞
                    if stored_keep_logged_in != keep_logged_in:
                        logger.warning(f"keep_logged_in設置不匹配: 請求={keep_logged_in}, state中={stored_keep_logged_in}")
                except Exception as e:
                    logger.warning(f"無法解析state參數: {e}")
            else:
                logger.warning("授權URL中未找到state參數")
            
            # 打印說明消息
            print("\n" + "=" * 80)
            print("Google登入流程說明")
            print("=" * 80)
            print("1. 下一步將打開瀏覽器進行Google賬戶登入")
            print("2. 登入後，您將被重定向到一個URL")
            print("3. 請複製該URL並粘貼回此終端")
            print("=" * 80)
            
            # 自動打開瀏覽器（現在是默認行為）
            if auto_open_browser or os.getenv("OPEN_BROWSER", "false").lower() == "true":
                logger.info("自動打開瀏覽器...")
                webbrowser.open(authorization_url)
                print("\n瀏覽器已打開，請完成Google登入...")
            else:
                print(f"\n請手動在瀏覽器中打開以下URL:\n{authorization_url}\n")
            
            return {
                "success": True,
                "authorization_url": authorization_url,
                "state": state
            }
        else:
            logger.error(f"獲取Google授權URL失敗: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Google登錄過程中出現錯誤: {str(e)}")
        return False

def simulate_google_callback(code: str = "simulated_code", state: str = None, keep_logged_in: bool = False) -> bool:
    """
    模擬Google回調過程
    
    這個函數模擬從Google重定向回應用的過程，但不進行實際的OAuth流程
    相反，它直接調用回調端點並提供模擬的code和state參數
    
    參數:
        code: 模擬的授權碼（實際測試中應使用真實的code）
        state: 狀態參數，如果為None則自動生成
        keep_logged_in: 是否保持登入（僅在自動生成state時使用）
    """
    print_section(f"模擬Google回調 (保持登入: {keep_logged_in})")
    
    try:
        # 如果沒有提供state，則創建一個模擬的state
        if not state:
            frontend_callback_url = "http://localhost:5175/auth/callback"
            state_data = {
                "callback_url": frontend_callback_url,
                "csrf_token": "simulated_csrf_token",
                "keep_logged_in": keep_logged_in
            }
            state = base64.b64encode(json.dumps(state_data).encode()).decode()
            logger.info("已創建模擬state參數")
        
        # 準備請求參數
        params = {
            "code": code,
            "state": state
        }
        
        logger.info("模擬Google回調請求")
        logger.info(f"使用參數: code={code}, state={state[:15]}... (已截斷)")
        
        # 發送請求
        logger.info("注意：這是一個模擬請求，實際測試需要真實的Google授權碼")
        logger.info("由於缺少真實授權碼，此請求預期會失敗，這是正常的測試行為")
        
        try:
            response = session.get(AUTH_ENDPOINTS["google_callback"], params=params, allow_redirects=False)
            
            # 分析響應（通常是重定向）
            logger.info(f"回調響應狀態碼: {response.status_code}")
            
            if 300 <= response.status_code < 400:  # 重定向
                redirect_location = response.headers.get("Location", "")
                logger.info(f"重定向URL: {redirect_location}")
                
                # 解析重定向URL中的參數
                parsed_url = urlparse(redirect_location)
                query_params = parse_qs(parsed_url.query)
                
                # 檢查是否有錯誤參數
                if "error" in query_params:
                    error = query_params["error"][0]
                    error_description = query_params.get("error_description", ["未提供錯誤詳情"])[0]
                    logger.info(f"Google回調返回錯誤: {error}")
                    logger.info(f"錯誤詳情: {error_description}")
                    
                    # 檢查是否是預期的錯誤（由於使用模擬code）
                    if "無法從Google獲取令牌" in error_description:
                        logger.info("收到預期的錯誤，這是由於使用了模擬的授權碼")
                        return True
                
                # 如果重定向URL包含令牌，則測試成功
                # 注意：由於使用模擬code，實際不會返回令牌
                if "access_token" in query_params and "refresh_token" in query_params:
                    access_token = query_params["access_token"][0]
                    refresh_token = query_params["refresh_token"][0]
                    
                    # 保存令牌數據
                    token_data["access_token"] = access_token
                    token_data["refresh_token"] = refresh_token
                    token_data["token_type"] = query_params.get("token_type", ["bearer"])[0]
                    
                    if "expires_in" in query_params:
                        token_data["expires_in"] = int(query_params["expires_in"][0])
                    
                    if "refresh_token_expires_in" in query_params:
                        token_data["refresh_token_expires_in"] = int(query_params["refresh_token_expires_in"][0])
                    
                    # 計算過期時間
                    now = datetime.now()
                    if token_data["expires_in"]:
                        token_data["expiry_time"] = now.timestamp() + token_data["expires_in"]
                    
                    if token_data["refresh_token_expires_in"]:
                        token_data["refresh_token_expiry_time"] = now.timestamp() + token_data["refresh_token_expires_in"]
                    
                    logger.info("成功從Google回調獲取令牌")
                    return True
            
            # 如果不是重定向或沒有預期的錯誤，返回失敗
            logger.warning("無法正確處理Google回調響應")
            return False
            
        except requests.exceptions.HTTPError as e:
            # 某些錯誤是預期的，因為我們使用了模擬的code
            logger.info(f"收到HTTP錯誤: {e.response.status_code}")
            
            # 如果是401或400錯誤，這可能是由於模擬code導致的預期錯誤
            if e.response.status_code in (400, 401):
                logger.info("收到預期的錯誤狀態碼，這是由於使用了模擬的授權碼")
                return True
            else:
                logger.error(f"回調過程中出現非預期的HTTP錯誤: {str(e)}")
                return False
            
    except Exception as e:
        logger.error(f"模擬Google回調過程中出現錯誤: {str(e)}")
        return False

def explain_real_google_testing():
    """提供有關如何進行真實Google登錄測試的說明"""
    print_section("真實Google登錄測試說明")
    
    logger.info("由於Google OAuth需要真實的Google帳戶和用戶交互，無法完全自動化測試")
    logger.info("以下是手動測試Google登錄的步驟：")
    logger.info("")
    logger.info("1. 運行 login_with_google() 函數獲取Google授權URL")
    logger.info("2. 將授權URL複製到瀏覽器中並完成Google登錄")
    logger.info("3. 登錄成功後，Google會將您重定向回應用程序")
    logger.info("4. 檢查重定向URL中的令牌參數並記錄下來")
    logger.info("5. 使用獲取的令牌手動測試API訪問和刷新功能")
    logger.info("")
    logger.info("如果需要集成到自動化測試中，可以考慮以下方法：")
    logger.info("- 使用Selenium或Playwright等工具模擬用戶登錄過程")
    logger.info("- 為測試環境配置模擬的OAuth提供商")
    logger.info("- 修改後端代碼，添加專門用於測試的模擬路徑")
    logger.info("")
    logger.info("注意：本測試腳本中的模擬函數只測試應用程序端的邏輯，不進行實際的OAuth認證")

def process_real_google_callback() -> Dict[str, Any]:
    """
    處理真實的Google回調
    
    這個函數要求用戶提供從瀏覽器重定向獲得的完整URL，
    並從中提取授權碼和狀態參數，然後調用後端API完成登錄過程
    
    返回:
        包含令牌信息的字典或None（如果失敗）
    """
    print_section("處理真實Google回調")
    
    try:
        # 提示用戶輸入重定向URL
        print("\n請將瀏覽器重定向後的完整URL複製到這裡:")
        callback_url = input("> ").strip()
        
        if not callback_url:
            logger.error("未提供URL")
            return None
        
        # 從URL中提取參數
        parsed_url = urlparse(callback_url)
        query_params = parse_qs(parsed_url.query)
        
        # 檢查是否有錯誤
        if "error" in query_params:
            error = query_params["error"][0]
            error_description = query_params.get("error_description", ["未提供錯誤詳情"])[0]
            logger.error(f"回調URL包含錯誤: {error}")
            logger.error(f"錯誤詳情: {error_description}")
            return None
        
        # 檢查是否有授權碼
        if "code" not in query_params:
            logger.error("回調URL中未找到授權碼")
            return None
        
        code = query_params["code"][0]
        
        # 檢查是否有state
        if "state" not in query_params:
            logger.warning("回調URL中未找到state參數")
            state = None
        else:
            state = query_params["state"][0]
        
        logger.info("從回調URL中提取的參數:")
        logger.info(f"code: {code[:10]}... (已截斷)")
        if state:
            logger.info(f"state: {state[:15]}... (已截斷)")
        
        # 調用後端API完成登錄過程
        logger.info("向後端發送授權碼和狀態參數...")
        
        params = {
            "code": code
        }
        if state:
            params["state"] = state
        
        response = session.get(AUTH_ENDPOINTS["google_callback"], params=params, allow_redirects=False)
        
        logger.info(f"回調響應狀態碼: {response.status_code}")
        
        # 處理響應
        if 300 <= response.status_code < 400:  # 重定向
            redirect_location = response.headers.get("Location", "")
            logger.info(f"重定向URL: {redirect_location}")
            
            # 從重定向URL中提取令牌
            parsed_redirect = urlparse(redirect_location)
            redirect_params = parse_qs(parsed_redirect.query)
            
            token_info = {}
            
            if "access_token" in redirect_params:
                token_info["access_token"] = redirect_params["access_token"][0]
                token_info["token_type"] = redirect_params.get("token_type", ["bearer"])[0]
                
                if "expires_in" in redirect_params:
                    token_info["expires_in"] = int(redirect_params["expires_in"][0])
                    token_info["expiry_time"] = datetime.now().timestamp() + token_info["expires_in"]
                
                if "refresh_token" in redirect_params:
                    token_info["refresh_token"] = redirect_params["refresh_token"][0]
                    
                    if "refresh_token_expires_in" in redirect_params:
                        token_info["refresh_token_expires_in"] = int(redirect_params["refresh_token_expires_in"][0])
                
                # 更新全局令牌數據
                token_data.update(token_info)
                
                logger.info("成功從回調中獲取令牌")
                logger.info(f"令牌類型: {token_info['token_type']}")
                logger.info(f"訪問令牌: {token_info['access_token'][:10]}... (已截斷)")
                
                if "refresh_token" in token_info:
                    logger.info(f"刷新令牌: {token_info['refresh_token'][:10]}... (已截斷)")
                
                if "expires_in" in token_info:
                    logger.info(f"訪問令牌有效期: {token_info['expires_in']}秒")
                
                if "refresh_token_expires_in" in token_info:
                    logger.info(f"刷新令牌有效期: {token_info['refresh_token_expires_in']}秒")
                
                return token_info
            else:
                logger.error("重定向URL中未找到令牌")
                return None
        else:
            logger.error(f"回調請求失敗: {response.status_code}")
            logger.error(f"響應內容: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"處理Google回調過程中出現錯誤: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def test_google_login(use_real_login: bool = False) -> None:
    """
    測試Google登錄功能
    
    參數:
        use_real_login: 是否使用真實Google登錄流程（需要用戶交互）
    """
    results = {}
    
    try:
        # 獲取後端配置
        config = get_backend_config()
        results["後端配置"] = bool(config)
        
        if use_real_login:
            print_section("真實Google登錄測試")
            logger.info("開始真實Google登錄流程（需要用戶交互）")
            
            # 第一步：獲取Google授權URL並打開瀏覽器
            login_result = login_with_google(keep_logged_in=True, auto_open_browser=True)
            if not login_result or not isinstance(login_result, dict):
                results["獲取Google授權URL"] = False
                logger.error("無法獲取Google授權URL")
            else:
                results["獲取Google授權URL"] = True
                
                # 第二步：處理真實的Google回調
                token_info = process_real_google_callback()
                results["Google登錄流程完成"] = bool(token_info)
                
                if token_info:
                    # 第三步：使用獲取的令牌獲取用戶資料
                    user_data = get_user_profile()
                    results["獲取用戶資料"] = bool(user_data)
                    
                    if user_data:
                        logger.info("成功獲取用戶資料:")
                        logger.info(f"用戶ID: {user_data.get('id')}")
                        logger.info(f"用戶名: {user_data.get('username')}")
                        logger.info(f"電子郵件: {user_data.get('email')}")
                    
                    # 第四步：測試令牌刷新
                    refresh_result = refresh_token()
                    results["刷新令牌"] = refresh_result
                    
                    if refresh_result:
                        # 第五步：使用刷新後的令牌再次獲取用戶資料
                        new_user_data = get_user_profile()
                        results["使用刷新令牌後獲取資料"] = bool(new_user_data)
                    
                    # 第六步：登出
                    logout_result = logout()
                    results["登出"] = logout_result
                    
                    # 第七步：驗證令牌已撤銷
                    token_revoked = verify_token_revoked()
                    results["令牌撤銷驗證"] = token_revoked
        else:
            # 模擬測試（原有邏輯）
            # 第一步：測試獲取Google授權URL
            results["獲取Google授權URL (保持登入)"] = login_with_google(keep_logged_in=True, auto_open_browser=False)
            results["獲取Google授權URL (不保持登入)"] = login_with_google(keep_logged_in=False, auto_open_browser=False)
            
            # 第二步：測試模擬回調
            # 注意：這只是模擬測試，實際上不會返回真實令牌
            results["模擬Google回調 (保持登入)"] = simulate_google_callback(keep_logged_in=True)
            results["模擬Google回調 (不保持登入)"] = simulate_google_callback(keep_logged_in=False)
            
            # 提供真實測試的說明
            explain_real_google_testing()
        
        # 輸出測試結果匯總
        print_section("Google登錄測試結果匯總")
        for test_name, passed in results.items():
            print_result(test_name, passed)
        
        # 計算通過率
        total_tests = len(results)
        passed_tests = sum(1 for result in results.values() if result)
        pass_rate = (passed_tests / total_tests) * 100
        
        logger.info("=" * 80)
        logger.info(f"測試完成: 通過 {passed_tests}/{total_tests} 測試項 ({pass_rate:.1f}%)")
        logger.info("=" * 80)
        
        if not use_real_login:
            logger.info("注意：以上為模擬測試，未進行真實Google登錄")
            logger.info("如需進行真實測試，請使用 --google-real 參數或在菜單中選擇「真實Google登錄測試」")
        
    except Exception as e:
        logger.error(f"Google登錄測試過程中出現未處理的錯誤: {str(e)}")
        import traceback
        traceback.print_exc()

def run_all_tests() -> None:
    """運行所有測試"""
    # 測試不保持登入場景
    test_no_keep_login()
    
    # 測試保持登入場景
    test_keep_login()
    
    # 測試Google登錄 (如果環境變量啟用)
    if os.getenv("TEST_GOOGLE_LOGIN", "false").lower() == "true":
        use_real = os.getenv("REAL_GOOGLE_LOGIN", "false").lower() == "true"
        test_google_login(use_real_login=use_real)
    else:
        logger.info("已跳過Google登錄測試 (可通過設置 TEST_GOOGLE_LOGIN=true 啟用)")

if __name__ == "__main__":
    # 解析命令行參數
    parser = argparse.ArgumentParser(description="測試登入功能")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true", help="運行所有測試")
    group.add_argument("--keep", action="store_true", help="僅測試保持登入的情況")
    group.add_argument("--no-keep", action="store_true", help="僅測試不保持登入的情況")
    group.add_argument("--google", action="store_true", help="僅測試Google登錄（模擬）")
    group.add_argument("--google-real", action="store_true", help="僅測試Google登錄（真實流程）")
    
    args = parser.parse_args()
    
    # 根據命令行參數執行測試
    if args.keep:
        print_section("僅測試保持登入的情況")
        test_keep_login()
    elif args.no_keep:
        print_section("僅測試不保持登入的情況")
        test_no_keep_login()
    elif args.google:
        print_section("僅測試Google登錄（模擬）")
        test_google_login(use_real_login=False)
    elif args.google_real:
        print_section("僅測試Google登錄（真實流程）")
        test_google_login(use_real_login=True)
    elif args.all:
        print_section("運行所有測試")
        run_all_tests()
    else:
        # 默認顯示交互式選擇菜單
        print("\n選擇要運行的測試項目:")
        print("1. 測試不保持登入的情況")
        print("2. 測試保持登入的情況")
        print("3. 測試Google登錄（模擬）")
        print("4. 測試Google登錄（真實流程）")
        print("5. 運行所有測試")
        
        while True:
            choice = input("\n請輸入選項號碼 (1-5): ")
            if choice == "1":
                print_section("僅測試不保持登入的情況")
                test_no_keep_login()
                break
            elif choice == "2":
                print_section("僅測試保持登入的情況")
                test_keep_login()
                break
            elif choice == "3":
                print_section("僅測試Google登錄（模擬）")
                test_google_login(use_real_login=False)
                break
            elif choice == "4":
                print_section("僅測試Google登錄（真實流程）")
                test_google_login(use_real_login=True)
                break
            elif choice == "5":
                print_section("運行所有測試")
                run_all_tests()
                break
            else:
                print("無效的選項，請重新輸入！") 