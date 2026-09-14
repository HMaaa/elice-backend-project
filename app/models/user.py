from datetime import datetime

from sqlalchemy import TIMESTAMP, BigInteger, Identity, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    fullname: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        # 이메일은 대소문자를 구분한다. PostgreSQL 의 기본 비교가 대소문자를
        # 구분하므로 컬럼에 그대로 유일 제약을 건다.
        # (Kim@a.com 과 kim@a.com 은 서로 다른 계정)
        Index("uq_users_email", "email", unique=True),
    )

    def __repr__(self) -> str:  # pragma: no cover - 디버깅 편의용
        return f"<User id={self.id} email={self.email!r}>"
