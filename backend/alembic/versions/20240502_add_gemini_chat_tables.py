"""添加Gemini聊天相关数据表

Revision ID: 20240502_add_gemini_chat_tables
Revises: 20240501_add_referral_code
Create Date: 2024-05-02 10:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite
import datetime
import pytz

# revision identifiers, used by Alembic.
revision = '20240502_add_gemini_chat_tables'
down_revision = '20240501_add_referral_code'
branch_labels = None
depends_on = None

# 东八区时区，用于生成当前时间
TZ_CHINA = pytz.timezone('Asia/Shanghai')

def get_china_time():
    """返回中国标准时间"""
    return datetime.datetime.now(TZ_CHINA)

def upgrade():
    # 创建聊天会话表
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('title', sa.String(200), default='新对话'),
        sa.Column('created_at', sa.DateTime(), default=get_china_time),
        sa.Column('updated_at', sa.DateTime(), default=get_china_time, onupdate=get_china_time)
    )
    
    # 创建聊天消息表
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('chat_sessions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('role', sa.String(10), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), default=get_china_time)
    )
    
    # 添加索引以加速查询
    op.create_index('ix_chat_sessions_user_id', 'chat_sessions', ['user_id'])
    op.create_index('ix_chat_sessions_updated_at', 'chat_sessions', ['updated_at'])
    op.create_index('ix_chat_messages_session_id', 'chat_messages', ['session_id'])
    op.create_index('ix_chat_messages_created_at', 'chat_messages', ['created_at'])


def downgrade():
    # 删除表和索引
    op.drop_index('ix_chat_messages_created_at')
    op.drop_index('ix_chat_messages_session_id')
    op.drop_index('ix_chat_sessions_updated_at')
    op.drop_index('ix_chat_sessions_user_id')
    
    op.drop_table('chat_messages')
    op.drop_table('chat_sessions') 