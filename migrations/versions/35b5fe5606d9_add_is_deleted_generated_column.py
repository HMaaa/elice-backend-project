"""add is_deleted generated column

Revision ID: 35b5fe5606d9
Revises: a96d63f14b5a
Create Date: 2026-09-13 19:09:01.204810

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '35b5fe5606d9'
down_revision: Union[str, Sequence[str], None] = 'a96d63f14b5a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # is_deleted 는 deleted_at 에서 DB 가 계산하는 생성 컬럼이다.
    # 두 값이 어긋날 수 없고, 직접 UPDATE 하면 PostgreSQL 이 거부한다.
    for table in ("boards", "posts"):
        op.add_column(
            table,
            sa.Column(
                "is_deleted",
                sa.Boolean(),
                sa.Computed("deleted_at IS NOT NULL", persisted=True),
                nullable=False,
            ),
        )

    # 부분 인덱스 술어를 is_deleted 기준으로 재작성한다.
    op.drop_index("uq_boards_name", table_name="boards")
    op.create_index(
        "uq_boards_name", "boards", [sa.literal_column("lower(name)")], unique=True,
        postgresql_where=sa.text("NOT is_deleted"),
    )
    op.drop_index("ix_boards_public_count", table_name="boards")
    op.create_index(
        "ix_boards_public_count", "boards", [sa.literal_column("post_count DESC, id DESC")],
        postgresql_where=sa.text("is_public AND NOT is_deleted"),
    )
    op.drop_index("ix_boards_private_owner_count", table_name="boards")
    op.create_index(
        "ix_boards_private_owner_count", "boards",
        [sa.literal_column("owner_id, post_count DESC, id DESC")],
        postgresql_where=sa.text("NOT is_public AND NOT is_deleted"),
    )
    op.drop_index("ix_posts_board_id", table_name="posts")
    op.create_index(
        "ix_posts_board_id", "posts", ["board_id", sa.literal_column("id DESC")],
        postgresql_where=sa.text("NOT is_deleted"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_posts_board_id", table_name="posts")
    op.create_index(
        "ix_posts_board_id", "posts", ["board_id", sa.literal_column("id DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_index("ix_boards_private_owner_count", table_name="boards")
    op.create_index(
        "ix_boards_private_owner_count", "boards",
        [sa.literal_column("owner_id, post_count DESC, id DESC")],
        postgresql_where=sa.text("NOT is_public AND deleted_at IS NULL"),
    )
    op.drop_index("ix_boards_public_count", table_name="boards")
    op.create_index(
        "ix_boards_public_count", "boards", [sa.literal_column("post_count DESC, id DESC")],
        postgresql_where=sa.text("is_public AND deleted_at IS NULL"),
    )
    op.drop_index("uq_boards_name", table_name="boards")
    op.create_index(
        "uq_boards_name", "boards", [sa.literal_column("lower(name)")], unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    for table in ("posts", "boards"):
        op.drop_column(table, "is_deleted")
