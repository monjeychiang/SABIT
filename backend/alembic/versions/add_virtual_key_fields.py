"""add virtual key fields

Revision ID: 1a2b3c4d5e6f
Revises: previous_revision_id
Create Date: 2023-05-10 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '1a2b3c4d5e6f'
down_revision = 'previous_revision_id'  # 替換為實際的上一個修訂版本ID
branch_labels = None
depends_on = None


def upgrade():
    # 添加虛擬密鑰相關字段
    op.add_column('exchange_apis', sa.Column('virtual_key_id', sa.String(64), nullable=True))
    op.add_column('exchange_apis', sa.Column('permissions', sa.JSON(), nullable=True))
    op.add_column('exchange_apis', sa.Column('rate_limit', sa.Integer(), nullable=True))
    op.add_column('exchange_apis', sa.Column('last_used_at', sa.DateTime(), nullable=True))
    op.add_column('exchange_apis', sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'))
    
    # 創建索引
    op.create_index(op.f('ix_exchange_apis_virtual_key_id'), 'exchange_apis', ['virtual_key_id'], unique=True)
    
    # 為現有記錄生成虛擬密鑰ID
    conn = op.get_bind()
    conn.execute("""
    UPDATE exchange_apis
    SET virtual_key_id = md5(random()::text || clock_timestamp()::text)
    WHERE virtual_key_id IS NULL;
    """)
    
    # 設置默認權限
    conn.execute("""
    UPDATE exchange_apis
    SET permissions = '{"read": true, "trade": true}'
    WHERE permissions IS NULL;
    """)


def downgrade():
    # 刪除索引
    op.drop_index(op.f('ix_exchange_apis_virtual_key_id'), table_name='exchange_apis')
    
    # 刪除列
    op.drop_column('exchange_apis', 'is_active')
    op.drop_column('exchange_apis', 'last_used_at')
    op.drop_column('exchange_apis', 'rate_limit')
    op.drop_column('exchange_apis', 'permissions')
    op.drop_column('exchange_apis', 'virtual_key_id') 