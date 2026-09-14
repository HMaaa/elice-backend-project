"""soft delete for boards and posts

Revision ID: a96d63f14b5a
Revises: 0a806283fdf1
Create Date: 2026-09-13 19:01:18.499360

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a96d63f14b5a'
down_revision: Union[str, Sequence[str], None] = '0a806283fdf1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('boards', sa.Column('deleted_at', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('posts', sa.Column('deleted_at', sa.TIMESTAMP(timezone=True), nullable=True))

    # 표현식·부분 인덱스는 autogenerate 가 다루지 못하므로 직접 작성한다.
    # 모두 "살아있는 행만" 담도록 술어에 deleted_at IS NULL 을 넣는다.
    op.drop_index('uq_boards_name', table_name='boards')
    op.create_index(
        'uq_boards_name', 'boards', [sa.literal_column('lower(name)')], unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )
    op.drop_index('ix_boards_public_count', table_name='boards')
    op.create_index(
        'ix_boards_public_count', 'boards', [sa.literal_column('post_count DESC, id DESC')],
        postgresql_where=sa.text('is_public AND deleted_at IS NULL'),
    )
    op.drop_index('ix_boards_private_owner_count', table_name='boards')
    op.create_index(
        'ix_boards_private_owner_count', 'boards',
        [sa.literal_column('owner_id, post_count DESC, id DESC')],
        postgresql_where=sa.text('NOT is_public AND deleted_at IS NULL'),
    )
    op.drop_index('ix_posts_board_id', table_name='posts')
    op.create_index(
        'ix_posts_board_id', 'posts', ['board_id', sa.literal_column('id DESC')],
        postgresql_where=sa.text('deleted_at IS NULL'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_posts_board_id', table_name='posts')
    op.create_index('ix_posts_board_id', 'posts', ['board_id', sa.literal_column('id DESC')])
    op.drop_index('ix_boards_private_owner_count', table_name='boards')
    op.create_index(
        'ix_boards_private_owner_count', 'boards',
        [sa.literal_column('owner_id, post_count DESC, id DESC')],
        postgresql_where=sa.text('NOT is_public'),
    )
    op.drop_index('ix_boards_public_count', table_name='boards')
    op.create_index(
        'ix_boards_public_count', 'boards', [sa.literal_column('post_count DESC, id DESC')],
        postgresql_where=sa.text('is_public'),
    )
    op.drop_index('uq_boards_name', table_name='boards')
    op.create_index('uq_boards_name', 'boards', [sa.literal_column('lower(name)')], unique=True)
    op.drop_column('posts', 'deleted_at')
    op.drop_column('boards', 'deleted_at')
