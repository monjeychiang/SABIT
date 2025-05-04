"""添加用户推荐码字段

Revision ID: 20240501_add_referral_code
Revises: 
Create Date: 2024-05-01 12:00:00

"""
from alembic import op
import sqlalchemy as sa
import random
import string

# revision identifiers, used by Alembic.
revision = '20240501_add_referral_code'
down_revision = None
branch_labels = None
depends_on = None


def generate_random_code(length=6):
    """生成随机推荐码"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def upgrade():
    # 添加推荐码字段
    op.add_column('users', sa.Column('referral_code', sa.String(6), nullable=True, unique=True, index=True))
    # 添加推荐人ID字段
    op.add_column('users', sa.Column('referrer_id', sa.Integer, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))
    
    # 为现有用户生成唯一推荐码
    conn = op.get_bind()
    users = conn.execute(sa.text('SELECT id FROM users')).fetchall()
    
    # 已生成的推荐码集合，用于确保唯一性
    used_codes = set()
    
    # 为每个用户生成并更新推荐码
    for user in users:
        user_id = user[0]
        
        # 生成唯一的推荐码
        while True:
            code = generate_random_code()
            if code not in used_codes:
                used_codes.add(code)
                break
        
        # 更新用户的推荐码
        conn.execute(
            sa.text('UPDATE users SET referral_code = :code WHERE id = :user_id'),
            {'code': code, 'user_id': user_id}
        )


def downgrade():
    # 删除推荐人ID字段
    op.drop_column('users', 'referrer_id')
    # 删除推荐码字段
    op.drop_column('users', 'referral_code') 