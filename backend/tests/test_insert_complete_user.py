import sys
import os
import logging
from datetime import datetime
import pytz
from getpass import getpass
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# 导入相关模块
from app.db.models.user import User
from app.db.models.base import UserTag, get_china_time
from app.core.security import get_password_hash
from app.db.database import Base

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 数据库连接
DB_URL = "sqlite:///trading.db"
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_test_user(username, email, password, user_tag=UserTag.REGULAR, is_admin=False, is_active=True, 
                    last_login_ip="127.0.0.1", api_key=None, api_secret=None):
    """
    创建一个完整的测试用户，包括所有字段
    """
    db = SessionLocal()
    try:
        # 检查用户名是否已存在
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            logger.info(f"用户名 '{username}' 已存在，跳过创建")
            return existing_user, False
        
        # 检查邮箱是否已存在
        existing_email = db.query(User).filter(User.email == email).first()
        if existing_email:
            logger.info(f"邮箱 '{email}' 已被使用，跳过创建")
            return existing_email, False
        
        # 创建新用户，包含所有字段
        hashed_password = get_password_hash(password)
        now = get_china_time()
        
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            is_active=is_active,
            is_admin=is_admin,
            user_tag=user_tag,
            created_at=now,
            updated_at=now,
            api_key=api_key,
            api_secret=api_secret,
            last_login_ip=last_login_ip,
            last_login_at=now
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        logger.info(f"用户 '{username}' 创建成功，ID: {user.id}")
        return user, True
        
    except Exception as e:
        db.rollback()
        logger.error(f"创建用户失败: {str(e)}")
        raise
    finally:
        db.close()

def main():
    """
    主函数，创建测试用户
    """
    logger.info("开始测试创建完整用户记录...")
    
    # 创建一个普通用户
    regular_user, created = create_test_user(
        username="testuser1",
        email="testuser1@example.com",
        password="testpassword",
        user_tag=UserTag.REGULAR,
        is_admin=False,
        is_active=True,
        last_login_ip="192.168.1.100",
        api_key="test_api_key_123",
        api_secret="test_api_secret_456"
    )
    
    if created:
        logger.info(f"普通用户创建成功: {regular_user.username}, IP: {regular_user.last_login_ip}")
    else:
        logger.info(f"普通用户已存在: {regular_user.username}")
    
    # 创建一个高级用户
    premium_user, created = create_test_user(
        username="premium1",
        email="premium1@example.com",
        password="premiumpass",
        user_tag=UserTag.PREMIUM,
        is_admin=False,
        is_active=True,
        last_login_ip="192.168.1.101",
        api_key="premium_api_key_789",
        api_secret="premium_api_secret_012"
    )
    
    if created:
        logger.info(f"高级用户创建成功: {premium_user.username}, IP: {premium_user.last_login_ip}")
    else:
        logger.info(f"高级用户已存在: {premium_user.username}")
    
    # 创建一个管理员用户
    admin_user, created = create_test_user(
        username="admintest",
        email="admintest@example.com",
        password="adminpassword",
        user_tag=UserTag.ADMIN,
        is_admin=True,
        is_active=True,
        last_login_ip="192.168.1.102"
    )
    
    if created:
        logger.info(f"管理员用户创建成功: {admin_user.username}, IP: {admin_user.last_login_ip}")
    else:
        logger.info(f"管理员用户已存在: {admin_user.username}")
    
    logger.info("测试完成！")

if __name__ == "__main__":
    main() 