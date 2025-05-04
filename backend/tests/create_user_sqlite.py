import sqlite3
import os
from werkzeug.security import generate_password_hash
from datetime import datetime

def create_test_user():
    """直接使用SQLite创建测试用户"""
    # 获取数据库文件路径
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trading.db')
    
    # 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 获取用户表的列信息
    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()
    print("用户表结构:", columns)
    
    # 检查用户是否存在
    cursor.execute("SELECT * FROM users WHERE username = ?", ("testuser",))
    user = cursor.fetchone()
    
    if user:
        print("用户 'testuser' 已存在!")
        conn.close()
        return
    
    # 生成密码哈希
    hashed_password = generate_password_hash("password123")
    # 获取当前时间
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        # 根据实际表结构插入用户
        cursor.execute("""
        INSERT INTO users (username, email, hashed_password, is_active, is_verified, created_at, api_key, api_secret, user_tag)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ("testuser", "test@example.com", hashed_password, 1, 1, now, "", ""))
        
        conn.commit()
        print("测试用户创建成功!")
        print("用户名: testuser")
        print("密码: password123")
    except sqlite3.Error as e:
        print(f"创建用户时出错: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    create_test_user() 