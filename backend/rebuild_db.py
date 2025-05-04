#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数据库重建脚本

警告：这将删除所有现有数据，请确保在运行此脚本之前已备份重要数据。
"""

import os
import sys
import logging
import time
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """重建数据库的主函数"""
    try:
        logger.info("开始重建数据库...")
        
        # 显示明确的数据删除警告
        print("\n" + "="*80)
        print("警告: 此操作将删除数据库中的所有表和数据！")
        print("请确保已备份所有重要数据。")
        print("="*80 + "\n")

        # 增加确认步骤
        confirm = input("确认删除所有数据吗？(y/n): ")
        if confirm.lower() not in ['y', 'yes']:
            logger.info("操作已取消，数据库保持不变。")
            return
            
        # 先导入数据库引擎，确保可以连接到数据库
        from app.db.database import Base, engine, get_db
        from sqlalchemy.orm import Session
        
        # 检查数据库连接
        try:
            connection = engine.connect()
            connection.close()
            logger.info("数据库连接测试成功")
        except Exception as db_error:
            logger.error(f"数据库连接测试失败: {str(db_error)}")
            return
        
        # 导入所有模型，确保SQLAlchemy了解所有表定义
        logger.info("导入所有模型定义...")
        
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
        
        # 导入通知设置相关模型
        from app.db.models.notification_settings import NotificationSetting
        logger.info("导入通知设置模型完成")
        
        # 检查聊天室模型的字段
        logger.info(f"ChatRoom模型包含以下列: {[c.name for c in ChatRoom.__table__.columns]}")
        
        # 检查所有表是否被正确识别
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        expected_tables = [
            'users', 'refresh_tokens', 'chat_sessions', 'chat_messages', 
            'chat_message_usage', 'exchange_apis', 'chat_rooms', 
            'chat_room_messages', 'chat_room_members', 'notifications',
            'notification_settings'
        ]
        
        logger.info(f"识别到的表名列表: {table_names}")
        
        for table in expected_tables:
            if table not in Base.metadata.tables:
                logger.warning(f"警告: 表 '{table}' 没有在元数据中注册")
        
        # 使用原生SQL先清空所有表内容
        logger.info("正在清空所有表数据...")
        with Session(engine) as session:
            # 先禁用外键约束检查（对于支持此功能的数据库）
            try:
                # SQLite
                session.execute(text("PRAGMA foreign_keys = OFF;"))
                # PostgreSQL
                session.execute(text("SET CONSTRAINTS ALL DEFERRED;"))
                # MySQL/MariaDB
                session.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
            except SQLAlchemyError as e:
                logger.warning(f"禁用外键约束时出错，这可能是正常的，取决于数据库类型: {str(e)}")
                
            # 删除每个表中的所有数据
            for table_name in table_names:
                try:
                    session.execute(text(f"DELETE FROM {table_name};"))
                    logger.info(f"已清空表 {table_name} 中的所有数据")
                except SQLAlchemyError as e:
                    logger.warning(f"清空表 {table_name} 时出错: {str(e)}")
            
            # 尝试提交事务
            try:
                session.commit()
                logger.info("所有表数据已清空并提交")
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"提交清空数据操作时出错: {str(e)}")
                
            # 重新启用外键约束检查
            try:
                # SQLite
                session.execute(text("PRAGMA foreign_keys = ON;"))
                # PostgreSQL
                session.execute(text("SET CONSTRAINTS ALL IMMEDIATE;"))
                # MySQL/MariaDB
                session.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
                session.commit()
            except SQLAlchemyError as e:
                logger.warning(f"重新启用外键约束时出错，这可能是正常的: {str(e)}")
        
        # 手动执行表的删除和创建操作
        logger.info("正在删除所有现有表和数据...")
        print("\n开始删除所有表和数据，此操作不可逆...")
        Base.metadata.drop_all(bind=engine)
        logger.info("所有表和数据已成功删除")
        
        # 稍作暂停，以便操作更清晰
        time.sleep(1)
        
        logger.info("创建所有表...")
        Base.metadata.create_all(bind=engine)
        
        # 验证表是否正确创建
        inspector = inspect(engine)
        created_tables = inspector.get_table_names()
        logger.info(f"成功创建的表: {created_tables}")
        
        # 验证所有表的创建
        for table in expected_tables:
            if table in created_tables:
                columns = [col['name'] for col in inspector.get_columns(table)]
                logger.info(f"{table}表包含的列: {columns}")
                
                # 验证表是否为空
                with Session(engine) as session:
                    try:
                        count = session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                        logger.info(f"表 {table} 中有 {count} 条记录")
                        if count > 0:
                            logger.warning(f"警告: 表 {table} 中还有数据，清空失败!")
                    except SQLAlchemyError as e:
                        logger.error(f"检查表 {table} 数据时出错: {str(e)}")
            else:
                logger.error(f"错误: {table}表未创建!")
        
        logger.info("数据库重建成功！所有表结构都已更新，所有旧数据已被删除。")
        print("\n" + "="*80)
        print("数据库重建完成！所有数据已被清除，表结构已更新。")
        print("="*80 + "\n")
        
    except Exception as e:
        logger.error(f"重建数据库时出错: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 