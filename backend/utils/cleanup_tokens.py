#!/usr/bin/env python
"""
清理已撤銷的 refresh tokens 腳本

此腳本用於定期清理數據庫中標記為已撤銷（is_revoked=True）的刷新令牌，
減少數據庫冗餘並提高查詢效能。可以手動執行或設置為定時任務。
"""

from sqlalchemy import text
import sys
import os
import datetime

# 添加項目根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal
from app.db.models.user import RefreshToken


def cleanup_revoked_tokens():
    """刪除所有已撤銷的 refresh tokens"""
    db = SessionLocal()
    try:
        # 方法一：使用原生 SQL
        # result = db.execute(text("DELETE FROM refresh_tokens WHERE is_revoked = TRUE"))
        # deleted_count = result.rowcount
        
        # 方法二：使用 SQLAlchemy ORM (推薦)
        deleted_count = db.query(RefreshToken).filter(RefreshToken.is_revoked == True).delete()
        
        db.commit()
        print(f"成功刪除 {deleted_count} 個已撤銷的刷新令牌")
        return deleted_count
    except Exception as e:
        db.rollback()
        print(f"刪除過程中發生錯誤: {e}")
        return 0
    finally:
        db.close()


def cleanup_expired_tokens():
    """刪除所有已過期的 refresh tokens"""
    db = SessionLocal()
    now = datetime.datetime.now()
    
    try:
        deleted_count = db.query(RefreshToken).filter(
            RefreshToken.expires_at < now
        ).delete()
        
        db.commit()
        print(f"成功刪除 {deleted_count} 個已過期的刷新令牌")
        return deleted_count
    except Exception as e:
        db.rollback()
        print(f"刪除過程中發生錯誤: {e}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    print("===== 開始清理令牌數據 =====")
    print(f"當前時間: {datetime.datetime.now()}")
    
    # 刪除已撤銷的令牌
    revoked_count = cleanup_revoked_tokens()
    
    # 刪除已過期的令牌 (即使未被標記為撤銷)
    expired_count = cleanup_expired_tokens()
    
    print(f"總共刪除 {revoked_count + expired_count} 個令牌")
    print("===== 清理完成 =====") 