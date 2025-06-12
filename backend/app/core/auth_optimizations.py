"""
認證優化整合模組

此模組負責整合所有認證相關優化，並提供統一的接口來初始化和
使用這些優化功能。作為應用程式的入口點，在FastAPI啟動時
初始化所有認證優化系統。
"""

import asyncio
import logging
import threading
import time
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.async_auth import auth_pool
from app.core.token_validation import verify_token_optimized, cleanup_token_caches
from app.core.token_refresh import token_refresh_manager
from app.db.database import get_db

# 設置日誌記錄
logger = logging.getLogger(__name__)

# 週期性任務管理
class PeriodicTaskManager:
    """
    週期性任務管理器
    
    負責執行定期維護任務，如緩存清理、資源回收等。
    """
    
    def __init__(self):
        self.running = False
        self.cleanup_interval = 300  # 默認5分鐘執行一次清理
        self.cleanup_thread = None
        
    def start(self):
        """啟動週期性任務"""
        if self.running:
            return
            
        self.running = True
        self.cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self.cleanup_thread.start()
        logger.info("認證系統週期性維護任務已啟動")
        
    def stop(self):
        """停止週期性任務"""
        self.running = False
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=2.0)
        logger.info("認證系統週期性維護任務已停止")
        
    def _cleanup_worker(self):
        """清理工作線程"""
        while self.running:
            try:
                time.sleep(self.cleanup_interval)
                self._perform_cleanup()
            except Exception as e:
                logger.error(f"執行週期性清理任務時發生錯誤: {str(e)}")
                
    def _perform_cleanup(self):
        """執行清理任務"""
        try:
            # 清理令牌驗證緩存
            cleanup_token_caches()
            
            # 清理令牌刷新管理器
            token_refresh_manager.cleanup()
            
            logger.debug("已完成認證系統週期性維護任務")
        except Exception as e:
            logger.error(f"執行清理任務時發生錯誤: {str(e)}")

# 創建全局實例
task_manager = PeriodicTaskManager()

async def initialize_auth_optimizations(app: FastAPI):
    """
    初始化所有認證優化功能
    
    在FastAPI應用啟動時調用，設置各種優化機制和任務。
    
    參數:
        app: FastAPI應用實例
    """
    logger.info("初始化認證優化系統...")
    
    # 啟動非同步認證處理池
    await auth_pool.start_workers()
    logger.info("非同步認證處理池已啟動")
    
    # 啟動令牌刷新批處理
    await token_refresh_manager.start_batch_processing()
    logger.info("令牌刷新批處理已啟動")
    
    # 啟動週期性任務管理器
    task_manager.start()
    
    # 設置應用關閉時的清理動作
    @app.on_event("shutdown")
    async def shutdown_auth_optimizations():
        logger.info("關閉認證優化系統...")
        
        # 關閉非同步認證處理池
        await auth_pool.shutdown()
        
        # 停止令牌刷新批處理
        token_refresh_manager.batch_processing = False
        
        # 停止週期性任務
        task_manager.stop()
        
        logger.info("認證優化系統已關閉")

# 優化的依賴項，可替代原有的依賴項
async def get_current_user_optimized(
    request: Request,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """
    優化的當前用戶獲取依賴項
    
    使用優化的令牌驗證機制，減少驗證開銷，提高性能。
    
    參數:
        request: 請求對象
        db: 數據庫會話
        background_tasks: 背景任務
        
    返回:
        用戶對象
    """
    # 從授權頭獲取令牌
    authorization = request.headers.get("Authorization")
    if not authorization:
        return None
        
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            return None
    except ValueError:
        return None
        
    # 使用優化的令牌驗證
    try:
        payload = verify_token_optimized(token, db)
        
        # 獲取用戶名
        username = payload.get("sub")
        if not username:
            return None
            
        # 從數據庫獲取用戶 - 因為 verify_token_optimized 已經做了這一步
        # 所以理論上這裡可以省略，但為了安全和兼容性保留
        from app.db.models.user import User
        user = db.query(User).filter(User.username == username).first()
        
        # 在背景記錄用戶活動
        if background_tasks and user:
            background_tasks.add_task(
                token_refresh_manager.activity_tracker.record_activity,
                user.id,
                "api_request"
            )
            
        return user
    except Exception as e:
        logger.debug(f"令牌驗證失敗: {str(e)}")
        return None

# 輔助函數：獲取動態刷新閾值
def get_dynamic_refresh_threshold(user_id: int) -> int:
    """
    獲取用戶的動態刷新閾值
    
    根據用戶活躍度計算適合的令牌刷新閾值。
    
    參數:
        user_id: 用戶ID
        
    返回:
        刷新閾值（秒）
    """
    return token_refresh_manager.calculate_dynamic_refresh_threshold(user_id) 