"""添加聊天室最大成员数和公告字段

Revision ID: 20240503_add_chatroom_fields
Revises: 20240502_add_gemini_chat_tables
Create Date: 2024-05-03 01:30:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20240503_add_chatroom_fields'
down_revision = '20240502_add_gemini_chat_tables'
branch_labels = None
depends_on = None


def upgrade():
    # 添加max_members字段，默认值为0（表示不限制成员数量）
    op.add_column('chat_rooms', sa.Column('max_members', sa.Integer(), nullable=False, server_default='0'))
    
    # 添加announcement字段，允许为空
    op.add_column('chat_rooms', sa.Column('announcement', sa.String(500), nullable=True))
    
    # 添加备注说明两个字段的用途
    print("已添加chat_rooms表的max_members字段(默认值0，表示不限制成员数量)和announcement字段(聊天室公告)")


def downgrade():
    # 删除字段
    op.drop_column('chat_rooms', 'announcement')
    op.drop_column('chat_rooms', 'max_members') 