from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security, session
from app.core.exceptions import AuthenticationError, DuplicateError, ErrorCode
from app.models.user import User
from app.repositories import user_repo
from app.schemas.user import LoginRequest, SignUpRequest

# 두 분기의 메시지가 갈라지지 않도록 상수로 고정한다.
# 구분하면 가입된 이메일을 외부에서 열거할 수 있다.
_LOGIN_FAILED = "이메일 또는 비밀번호가 올바르지 않습니다."
_DUPLICATE_EMAIL = "이미 사용 중인 이메일입니다."


async def sign_up(db: AsyncSession, payload: SignUpRequest) -> User:
    if await user_repo.exists_by_email(db, payload.email):
        raise DuplicateError(_DUPLICATE_EMAIL, code=ErrorCode.EMAIL_ALREADY_EXISTS)

    password_hash = await security.hash_password(payload.password)
    try:
        user = await user_repo.create(
            db,
            fullname=payload.fullname,
            email=payload.email,
            password_hash=password_hash,
        )
        await db.commit()
    except IntegrityError:
        # 사전 확인을 통과한 동시 요청이 유일 제약에서 충돌한 경우.
        # 사용자에게는 일관되게 409 를 보여준다.
        await db.rollback()
        raise DuplicateError(_DUPLICATE_EMAIL, code=ErrorCode.EMAIL_ALREADY_EXISTS) from None
    return user


async def login(db: AsyncSession, payload: LoginRequest) -> str:
    user = await user_repo.get_by_email(db, payload.email)
    if user is None:
        # 즉시 반환하면 응답 시간이 짧아 계정 존재 여부가 드러난다.
        await security.waste_time_like_verify(payload.password)
        raise AuthenticationError(_LOGIN_FAILED, code=ErrorCode.INVALID_CREDENTIALS)

    if not await security.verify_password(user.password_hash, payload.password):
        raise AuthenticationError(_LOGIN_FAILED, code=ErrorCode.INVALID_CREDENTIALS)

    return await session.create(user.id)


async def logout(user_id: int) -> None:
    await session.revoke(user_id)
