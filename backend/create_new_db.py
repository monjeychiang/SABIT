#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
创建全新数据库脚本

此脚本将创建一个全新的数据库文件，替换当前的数据库。
它将完全避开与现有数据库交互的问题，提供一个干净的数据库环境。
"""

import os
import sys
import logging
import time
import shutil
from pathlib import Path
from datetime import datetime
from sqlalchemy import inspect, create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """创建新数据库的主函数"""
    try:
        logger.info("开始创建全新数据库...")
        
        # 显示警告
        print("\n" + "="*80)
        print("警告: 此操作将创建全新数据库，所有现有数据将无法访问！")
        print("请确保已备份所有重要数据。")
        print("="*80 + "\n")

        # 增加确认步骤
        confirm = input("确认创建新数据库吗？(y/n): ")
        if confirm.lower() not in ['y', 'yes']:
            logger.info("操作已取消。")
            return
            
        # 加载环境变量
        load_dotenv()
        
        # 直接指定数据库文件路径
        # 确保我们在backend目录下创建数据库
        script_dir = os.path.dirname(os.path.abspath(__file__))  # 脚本所在目录（backend目录）
        db_abs_path = os.path.join(script_dir, "trading.db")
        
        # 修改数据库URL为明确的路径
        db_url = f"sqlite:///{db_abs_path}"
        
        logger.info(f"将在以下位置创建数据库: {db_abs_path}")
        logger.info(f"数据库URL: {db_url}")
        
        # 检查数据库文件是否存在
        if os.path.exists(db_abs_path):
            # 备份现有数据库
            backup_dir = os.path.join(script_dir, "db_backups")
            os.makedirs(backup_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(backup_dir, f"trading_{timestamp}.db.bak")
            
            logger.info(f"正在备份现有数据库到: {backup_file}")
            shutil.copy2(db_abs_path, backup_file)
            logger.info("数据库备份完成")
            
            # 删除现有数据库文件
            logger.info("正在删除现有数据库文件...")
            os.remove(db_abs_path)
            logger.info("现有数据库文件已删除")
        
        # 导入数据库模型，确保可以创建所有表
        logger.info("导入所有模型定义...")
        
        # 先创建空的数据库文件
        with open(db_abs_path, 'w') as f:
            pass
        logger.info(f"已创建新的空数据库文件: {db_abs_path}")
        
        # 创建数据库引擎 - 使用明确的数据库URL
        new_engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True
        )
        
        # 导入所有模型
        from app.db.database import Base
        
        # 导入基础枚举类型
        from app.db.models.base import UserTag, NotificationType
        logger.info("导入基础枚举完成")
        
        # 导入用户相关模型
        from app.db.models.user import User, RefreshToken
        logger.info("导入用户模型完成")
        
        # 导入聊天相关模型
        from app.db.models.chat import ChatSession, ChatMessage, ChatMessageUsage
        logger.info("导入聊天模型完成")
        
        # 导入交易API相关模型
        from app.db.models.exchange_api import ExchangeAPI
        logger.info("导入交易API模型完成")
        
        # 导入聊天室相关模型
        from app.db.models.chatroom import ChatRoom, ChatRoomMessage, ChatRoomMember
        logger.info("导入聊天室模型完成")
        
        # 导入通知相关模型
        from app.db.models.notification import Notification
        logger.info("导入通知模型完成")
        
       
        # 在新数据库中创建所有表
        logger.info("创建所有表...")
        Base.metadata.create_all(bind=new_engine)
        
        # 验证表是否正确创建
        inspector = inspect(new_engine)
        created_tables = inspector.get_table_names()
        logger.info(f"成功创建的表: {created_tables}")
        
        # 验证所有预期的表是否已创建
        expected_tables = [
            'users', 'refresh_tokens', 'chat_sessions', 'chat_messages', 
            'chat_message_usage', 'exchange_apis', 'chat_rooms', 
            'chat_room_messages', 'chat_room_members', 'notifications',
            'notification_settings'
        ]
        
        for table in expected_tables:
            if table in created_tables:
                columns = [col['name'] for col in inspector.get_columns(table)]
                logger.info(f"{table}表包含的列: {columns}")
            else:
                logger.error(f"错误: {table}表未创建!")
        
        # 显示数据库文件的最终位置
        print(f"\n新数据库文件已创建在: {db_abs_path}")
        print(f"数据库URL: {db_url}")
        print("请确认这个位置与应用期望的数据库位置相匹配。")
        
        logger.info("全新数据库创建成功！")
        print("\n" + "="*80)
        print("全新数据库已创建！您现在可以使用一个完全干净的数据库环境。")
        print("旧数据库已备份，如需恢复，请查看db_backups目录。")
        print("="*80 + "\n")
        
    except Exception as e:
        logger.error(f"创建新数据库时出错: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 