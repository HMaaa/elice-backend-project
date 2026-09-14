from datetime import datetime

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    Computed,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    board_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("boards.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    # 소프트 삭제. deleted_at 이 언제 지웠는지를 담고,
    # is_deleted 는 그 값에서 DB 가 자동 계산하는 생성 컬럼이다.
    # 두 컬럼을 각각 관리하면 값이 어긋날 수 있어 단일 진실 공급원으로 묶었다.
    # (is_deleted 에 직접 쓰면 PostgreSQL 이 거부한다)
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, Computed("deleted_at IS NOT NULL", persisted=True), nullable=False
    )

    __table_args__ = (
        # 게시판별 최신순 커서 페이징 전용. 삭제된 글은 인덱스에서 제외한다.
        Index(
            "ix_posts_board_id",
            "board_id",
            text("id DESC"),
            postgresql_where=text("NOT is_deleted"),
        ),
        # FK 참조 무결성 검사(사용자 삭제 시)와 작성자 기준 조회
        Index("ix_posts_author", "author_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - 디버깅 편의용
        return f"<Post id={self.id} board_id={self.board_id} title={self.title!r}>"
