import requests
import time
import sys
import os

# 設置控制台輸出編碼為 UTF-8
os.system('chcp 65001')

def check_backend_health(url, max_retries=30, delay=1):
    """
    檢查後端服務是否正常運行
    :param url: 健康檢查的URL
    :param max_retries: 最大重試次數
    :param delay: 每次重試的延遲時間（秒）
    :return: 是否正常運行
    """
    sys.stdout.buffer.write("正在檢查後端服務...\n".encode('utf-8'))
    sys.stdout.buffer.flush()
    
    for i in range(max_retries):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                sys.stdout.buffer.write("後端服務正常運行！\n".encode('utf-8'))
                sys.stdout.buffer.flush()
                return True
        except requests.RequestException:
            pass
        
        if i < max_retries - 1:  # 不是最後一次嘗試
            sys.stdout.buffer.write(f"等待後端服務啟動... ({i + 1}/{max_retries})\n".encode('utf-8'))
            sys.stdout.buffer.flush()
            time.sleep(delay)
    
    sys.stdout.buffer.write("錯誤：後端服務未能正常啟動！\n".encode('utf-8'))
    sys.stdout.buffer.flush()
    return False

if __name__ == "__main__":
    health_check_url = "http://localhost:8000/health"
    if not check_backend_health(health_check_url):
        sys.exit(1)  # 如果健康檢查失敗，返回錯誤碼 1
    sys.exit(0)  # 健康檢查成功，返回 0 