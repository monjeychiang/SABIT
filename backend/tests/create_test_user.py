import os
import sys
from sqlalchemy.orm import Session

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from app.db.database import engine, Base
from app.db.models import User
from app.core.security import get_password_hash

def create_test_user():
    """创建测试用户账号"""
    print("正在创建测试用户...")
    
    # 创建数据库会话
    with Session(engine) as session:
        # 检查用户是否已存在
        username = "testuser"
        existing_user = session.query(User).filter(User.username == username).first()
        if existing_user:
            print(f"用户 '{username}' 已经存在！")
            return
        
        # 创建新用户
        new_user = User(
            username=username,
            email="test@example.com",
            hashed_password=get_password_hash("password123"),
            is_active=True,
            is_verified=True
        )
        
        session.add(new_user)
        session.commit()
        print(f"测试用户 '{username}' 创建成功！")
        print("用户名: testuser")
        print("密码: password123")

if __name__ == "__main__":
    create_test_user() 