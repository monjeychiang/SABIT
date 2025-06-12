#!/usr/bin/env python
"""
刷新令牌管理優化腳本

此腳本用於：
1. 刪除已撤銷（is_revoked=True）的刷新令牌
2. 刪除已過期的令牌
3. 分析令牌使用情況

優化策略：採用"更新而非新增"的令牌管理方式，每個用戶+設備只保留一個活躍令牌。
"""

from sqlalchemy import text, func
import sys
import os
import datetime

# 添加項目根目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal
from app.db.models.user import RefreshToken


def cleanup_invalid_tokens():
    """刪除所有無效的令牌（已撤銷或已過期）"""
    db = SessionLocal()
    now = datetime.datetime.now()
    
    try:
        # 一次性刪除所有無效令牌
        deleted_count = db.query(RefreshToken).filter(
            (RefreshToken.is_revoked == True) | (RefreshToken.expires_at < now)
        ).delete()
        
        db.commit()
        print(f"成功刪除 {deleted_count} 個無效令牌（已撤銷或已過期）")
        return deleted_count
    except Exception as e:
        db.rollback()
        print(f"刪除過程中發生錯誤: {e}")
        return 0
    finally:
        db.close()


def analyze_token_usage():
    """分析令牌使用情況"""
    db = SessionLocal()
    try:
        total = db.query(func.count(RefreshToken.id)).scalar()
        active = db.query(func.count(RefreshToken.id)).filter(
            RefreshToken.is_revoked == False,
            RefreshToken.expires_at > datetime.datetime.now()
        ).scalar()
        
        revoked = db.query(func.count(RefreshToken.id)).filter(
            RefreshToken.is_revoked == True
        ).scalar()
        
        expired = db.query(func.count(RefreshToken.id)).filter(
            RefreshToken.expires_at < datetime.datetime.now()
        ).scalar()
        
        active_users = db.query(func.count(func.distinct(RefreshToken.user_id))).filter(
            RefreshToken.is_revoked == False,
            RefreshToken.expires_at > datetime.datetime.now()
        ).scalar()
        
        print("\n===== 令牌統計資料 =====")
        print(f"令牌總數: {total}")
        print(f"活躍令牌: {active}")
        print(f"已撤銷令牌: {revoked}")
        print(f"已過期令牌: {expired}")
        print(f"有活躍令牌的用戶數: {active_users}")
        
        if active_users > 0:
            print(f"每用戶平均活躍令牌數: {active/active_users:.2f}")
            
        # 檢查是否有用戶擁有多個令牌（可能是在唯一約束實施前的遺留數據）
        users_with_multiple_tokens = db.query(
            RefreshToken.user_id, 
            func.count(RefreshToken.id).label('token_count')
        ).filter(
            RefreshToken.is_revoked == False,
            RefreshToken.expires_at > datetime.datetime.now()
        ).group_by(RefreshToken.user_id).having(
            func.count(RefreshToken.id) > 1
        ).all()
        
        if users_with_multiple_tokens:
            print(f"\n⚠️ 發現 {len(users_with_multiple_tokens)} 個用戶擁有多個活躍令牌")
            print("這些用戶可能是在實施唯一約束前創建的令牌，建議執行遷移來合併冗餘令牌")
            
    except Exception as e:
        print(f"分析令牌使用情況時發生錯誤: {e}")
    finally:
        db.close()


def consolidate_tokens():
    """合併每個用戶的多個活躍令牌（處理歷史數據）"""
    db = SessionLocal()
    try:
        # 查找每個用戶/設備組合的令牌數量
        duplicates = db.query(
            RefreshToken.user_id,
            RefreshToken.device_id,
            func.count(RefreshToken.id).label('token_count')
        ).filter(
            RefreshToken.is_revoked == False,
            RefreshToken.expires_at > datetime.datetime.now()
        ).group_by(
            RefreshToken.user_id,
            RefreshToken.device_id
        ).having(
            func.count(RefreshToken.id) > 1
        ).all()
        
        if not duplicates:
            print("沒有發現需要合併的令牌")
            return 0
            
        print(f"發現 {len(duplicates)} 個用戶/設備組合需要合併令牌")
        total_deleted = 0
        
        for user_id, device_id, token_count in duplicates:
            # 找出該用戶在此設備上的所有活躍令牌
            tokens = db.query(RefreshToken).filter(
                RefreshToken.user_id == user_id,
                RefreshToken.device_id == device_id,
                RefreshToken.is_revoked == False,
                RefreshToken.expires_at > datetime.datetime.now()
            ).order_by(RefreshToken.updated_at.desc()).all()
            
            # 保留最新的令牌，刪除其他的
            for token in tokens[1:]:
                db.delete(token)
                total_deleted += 1
        
        db.commit()
        print(f"成功刪除 {total_deleted} 個冗餘令牌")
        return total_deleted
    except Exception as e:
        db.rollback()
        print(f"合併令牌過程中發生錯誤: {e}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    print("===== 開始令牌管理優化 =====")
    print(f"當前時間: {datetime.datetime.now()}")
    
    # 分析當前令牌統計資料
    print("\n[步驟1] 分析當前令牌使用情況")
    analyze_token_usage()
    
    # 合併令牌（處理歷史數據）
    print("\n[步驟2] 合併冗餘令牌")
    consolidated = consolidate_tokens()
    
    # 清理無效令牌
    print("\n[步驟3] 清理無效令牌")
    deleted = cleanup_invalid_tokens()
    
    # 最終分析
    print("\n[步驟4] 分析處理後令牌使用情況")
    analyze_token_usage()
    
    print("\n===== 令牌管理優化完成 =====")
    print(f"合併了 {consolidated} 個冗餘令牌")
    print(f"刪除了 {deleted} 個無效令牌")
    print(f"處理時間: {datetime.datetime.now()}") 