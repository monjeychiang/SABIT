import requests
import json
import os
import logging
from datetime import datetime

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
TEST_USERNAME = os.getenv("TEST_USERNAME", "test_user")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "test_password")

def test_login_event():
    """測試登入成功事件的生成"""
    try:
        logger.info("開始測試登入成功事件...")
        
        # 第一步：登入獲取令牌
        login_url = f"{API_BASE_URL}/auth/login"
        login_data = {
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
            "keep_logged_in": "true"
        }
        
        logger.info(f"嘗試登入: {TEST_USERNAME}")
        response = requests.post(login_url, data=login_data)
        
        if response.status_code != 200:
            logger.error(f"登入失敗: {response.status_code} - {response.text}")
            return False
        
        logger.info("登入成功，獲取令牌")
        token_data = response.json()
        access_token = token_data.get("access_token")
        
        if not access_token:
            logger.error("響應中沒有找到訪問令牌")
            return False
            
        # 在用戶登入成功時，系統應該已經自動發送了登入成功事件
        # 這裡我們只需等待幾秒鐘，讓事件有時間被處理
        import time
        time.sleep(2)
        
        logger.info("登入成功事件應該已經被系統自動發送和處理")
        logger.info("檢查用戶通知列表，應該能看到登入成功通知")
        
        # 獲取用戶通知
        notifications_url = f"{API_BASE_URL}/notifications"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        notification_response = requests.get(
            notifications_url, 
            headers=headers,
            params={"page": 1, "per_page": 10}
        )
        
        if notification_response.status_code != 200:
            logger.error(f"獲取通知失敗: {notification_response.status_code} - {notification_response.text}")
            return False
            
        notifications = notification_response.json()
        
        # 檢查是否有登入成功的通知
        login_notifications = [
            n for n in notifications.get("items", []) 
            if "登入成功" in n.get("title", "")
        ]
        
        if login_notifications:
            logger.info(f"找到 {len(login_notifications)} 條登入成功通知")
            latest_notification = login_notifications[0]
            logger.info(f"最新通知: {latest_notification.get('title')} - {latest_notification.get('message')}")
            return True
        else:
            logger.warning("未找到登入成功通知，這可能是因為通知尚未被處理或系統配置問題")
            return False
            
    except Exception as e:
        logger.error(f"測試過程中出錯: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 80)
    print("登入成功事件測試")
    print("=" * 80)
    result = test_login_event()
    print("=" * 80)
    print(f"測試結果: {'成功' if result else '失敗'}")
    print("=" * 80) 