"""라우터에서 재사용하는 의존성."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import session
from app.core.database import get_db
from app.core.exceptions import AuthenticationError
from app.models.user import User
from app.repositories import user_repo

# auto_error=False: 헤더가 없을 때 FastAPI 기본 403 대신 우리 401 을 내보낸다.
_bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> User:
    if credentials is None:
        raise AuthenticationError()

    user_id = await session.get_user_id(credentials.credentials)
    if user_id is None:
        raise AuthenticationError()

    user = await user_repo.get(db, user_id)
    if user is None:
        # 세션은 남아있는데 계정이 사라진 경우. 세션을 정리한다.
        await session.revoke(user_id)
        raise AuthenticationError()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
