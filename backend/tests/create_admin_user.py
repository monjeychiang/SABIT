#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
管理员用户创建工具

此脚本用于创建新的管理员用户或将现有用户设置为管理员。
使用SQLAlchemy ORM直接与数据库交互，确保数据一致性和安全性。
"""

import os
import sys
import logging
import argparse
import secrets
import string
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

def generate_referral_code(length=6):
    """生成随机推荐码"""
    chars = string.ascii_uppercase + string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))

def create_admin_user(username, email, password, update_existing=False):
    """
    创建新的管理员用户或将现有用户设置为管理员
    
    参数:
        username: 用户名
        email: 电子邮件地址
        password: 明文密码（将被安全哈希）
        update_existing: 如果用户已存在，是否更新为管理员
    """
    try:
        # 导入必要的模块 - 放在函数内以避免循环导入
        from app.db.database import SessionLocal
        from app.db.models.user import User
        from app.db.models.base import UserTag, get_china_time
        from app.core.security import get_password_hash
        
        # 创建数据库会话
        db = SessionLocal()
        
        try:
            # 检查用户是否已存在
            existing_user = db.query(User).filter(User.username == username).first()
            
            if existing_user:
                if not update_existing:
                    logger.info(f"用户 '{username}' 已存在！使用 --update 参数来更新此用户为管理员。")
                    return
                
                logger.info(f"用户 '{username}' 已存在，正在更新为管理员...")
                
                # 更新现有用户为管理员
                existing_user.is_admin = True
                existing_user.user_tag = UserTag.ADMIN
                existing_user.updated_at = get_china_time()
                
                db.commit()
                logger.info(f"成功将用户 '{username}' 更新为管理员！")
            else:
                logger.info(f"正在创建新的管理员用户 '{username}'...")
                
                # 生成唯一的推荐码
                referral_code = generate_referral_code()
                while db.query(User).filter(User.referral_code == referral_code).first():
                    referral_code = generate_referral_code()
                
                # 创建新的管理员用户
                new_user = User(
                    username=username,
                    email=email,
                    hashed_password=get_password_hash(password),
                    is_active=True,
                    is_verified=True,
                    is_admin=True,
                    user_tag=UserTag.ADMIN,
                    referral_code=referral_code,
                    created_at=get_china_time(),
                    updated_at=get_china_time()
                )
                
                db.add(new_user)
                db.commit()
                
                logger.info(f"管理员用户 '{username}' 创建成功！")
                logger.info(f"用户名: {username}")
                logger.info(f"邮箱: {email}")
                logger.info(f"推荐码: {referral_code}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"创建管理员用户时出错: {str(e)}", exc_info=True)
        sys.exit(1)

def main():
    """命令行入口点"""
    parser = argparse.ArgumentParser(description="创建或更新管理员用户")
    parser.add_argument("username", help="用户名")
    parser.add_argument("--email", help="电子邮件地址（创建新用户时必需）")
    parser.add_argument("--password", help="用户密码（创建新用户时必需）")
    parser.add_argument("--update", action="store_true", help="如果用户已存在，则更新为管理员")
    
    args = parser.parse_args()
    
    # 验证参数
    if not args.update and (not args.email or not args.password):
        print("创建新用户时必须提供电子邮件和密码")
        print("用法: python create_admin_user.py <用户名> --email <邮箱> --password <密码>")
        print("更新现有用户: python create_admin_user.py <用户名> --update")
        sys.exit(1)
    
    create_admin_user(args.username, args.email, args.password, args.update)

if __name__ == "__main__":
    main() 