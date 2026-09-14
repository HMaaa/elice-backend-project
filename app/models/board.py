from datetime import datetime

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Board(Base):
    __tablename__ = "boards"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # 컬럼명이 is_public 인 이유: public 은 PostgreSQL 의 기본 스키마 이름이자
    # GRANT 키워드라 컬럼명으로 쓰면 매번 따옴표가 필요하다. API 는 public 으로 노출한다.
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    owner_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # 게시글 수 비정규화. 집계값으로 정렬하면 인덱스를 쓸 수 없어 매번 전량 집계가 된다.
    post_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
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
        # 카운트가 음수가 되면 로직 버그다. GREATEST 로 깎아 감추지 않고 에러로 드러낸다.
        CheckConstraint("post_count >= 0", name="ck_boards_post_count_non_negative"),
        # 이름은 대소문자를 무시한다. "Free" 와 "free" 를 별개 게시판으로 두면 혼동된다.
        # 부분 인덱스라 삭제된 게시판의 이름은 다시 쓸 수 있다.
        Index(
            "uq_boards_name",
            text("lower(name)"),
            unique=True,
            postgresql_where=text("NOT is_deleted"),
        ),
        # 목록 조회는 (공개 전체) UNION ALL (내 비공개) 로 분기한다.
        # 두 브랜치가 각각 전용 부분 인덱스를 타도록 조건을 배타적으로 나눈다.
        Index(
            "ix_boards_public_count",
            text("post_count DESC, id DESC"),
            postgresql_where=text("is_public AND NOT is_deleted"),
        ),
        Index(
            "ix_boards_private_owner_count",
            text("owner_id, post_count DESC, id DESC"),
            postgresql_where=text("NOT is_public AND NOT is_deleted"),
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - 디버깅 편의용
        return f"<Board id={self.id} name={self.name!r} public={self.is_public}>"
