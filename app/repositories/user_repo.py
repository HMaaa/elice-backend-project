from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    # 이메일은 대소문자를 구분한다. uq_users_email 유일 인덱스를 그대로 탄다.
    stmt = select(User).where(User.email == email)
    return (await db.execute(stmt)).scalar_one_or_none()


async def exists_by_email(db: AsyncSession, email: str) -> bool:
    stmt = select(func.count()).select_from(User).where(User.email == email)
    return bool((await db.execute(stmt)).scalar_one())


async def create(db: AsyncSession, *, fullname: str, email: str, password_hash: str) -> User:
    user = User(fullname=fullname, email=email, password_hash=password_hash)
    db.add(user)
    await db.flush()  # DB 기본값(id, created_at)을 채운다
    await db.refresh(user)
    return user
