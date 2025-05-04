import sys
import os
import logging
from datetime import datetime
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# 导入相关模块
from app.db.models import User, UserTag

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

def format_datetime(dt):
    """格式化日期时间为可读格式"""
    if dt is None:
        return "从未登录"
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def get_user_tag_name(tag):
    """获取用户标签的中文名称"""
    tag_names = {
        'admin': '管理员',
        'regular': '普通用户',
        'premium': '高级用户'
    }
    return tag_names.get(tag, '未知')

def query_all_users(output_file):
    """查询所有用户及其登录信息，并输出到文件"""
    db = SessionLocal()
    try:
        users = db.query(User).order_by(desc(User.last_login_at)).all()
        
        if not users:
            logger.info("数据库中没有用户记录")
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write("数据库中没有用户记录\n")
            return
        
        logger.info(f"找到 {len(users)} 个用户记录:")
        
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"找到 {len(users)} 个用户记录:\n")
            f.write("=" * 100 + "\n")
            
            # 写入表头
            f.write(f"{'ID':<5} {'用户名':<15} {'邮箱':<30} {'用户类型':<10} {'状态':<8} {'最后登录时间':<20} {'登录IP':<15} {'API密钥':<10}\n")
            f.write("-" * 100 + "\n")
            
            # 写入用户数据
            for user in users:
                status = "活跃" if user.is_active else "禁用"
                api_key_status = "已设置" if user.api_key else "未设置"
                
                f.write(f"{user.id:<5} {user.username:<15} {user.email:<30} {get_user_tag_name(user.user_tag):<10} "
                      f"{status:<8} {format_datetime(user.last_login_at):<20} {user.last_login_ip or '未知':<15} "
                      f"{api_key_status:<10}\n")
            
            f.write("-" * 100 + "\n\n")
        
    except Exception as e:
        logger.error(f"查询用户失败: {str(e)}")
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"查询用户失败: {str(e)}\n")
    finally:
        db.close()

def query_users_with_login_history(output_file):
    """查询有登录历史的用户，并输出到文件"""
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.last_login_at.isnot(None)).order_by(desc(User.last_login_at)).all()
        
        if not users:
            logger.info("没有用户有登录历史记录")
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write("没有用户有登录历史记录\n")
            return
        
        logger.info(f"找到 {len(users)} 个有登录历史的用户:")
        
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"找到 {len(users)} 个有登录历史的用户:\n")
            f.write("=" * 70 + "\n")
            
            # 写入表头
            f.write(f"{'ID':<5} {'用户名':<15} {'用户类型':<10} {'最后登录时间':<20} {'登录IP':<15}\n")
            f.write("-" * 70 + "\n")
            
            # 写入用户数据
            for user in users:
                f.write(f"{user.id:<5} {user.username:<15} {get_user_tag_name(user.user_tag):<10} "
                      f"{format_datetime(user.last_login_at):<20} {user.last_login_ip or '未知':<15}\n")
            
            f.write("-" * 70 + "\n\n")
        
    except Exception as e:
        logger.error(f"查询用户登录历史失败: {str(e)}")
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"查询用户登录历史失败: {str(e)}\n")
    finally:
        db.close()

def main():
    """主函数，执行查询测试"""
    output_file = "user_query_results.txt"
    
    # 创建或清空输出文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("数据库查询结果\n")
        f.write("=" * 50 + "\n\n")
    
    logger.info(f"开始查询数据库中的用户记录，结果将保存到 {output_file}...")
    
    # 查询所有用户
    logger.info("\n所有用户信息:")
    with open(output_file, 'a', encoding='utf-8') as f:
        f.write("所有用户信息:\n")
    query_all_users(output_file)
    
    # 查询有登录历史的用户
    logger.info("\n有登录历史的用户:")
    with open(output_file, 'a', encoding='utf-8') as f:
        f.write("\n有登录历史的用户:\n")
    query_users_with_login_history(output_file)
    
    logger.info(f"查询完成！结果已保存到 {output_file}")

if __name__ == "__main__":
    main() 