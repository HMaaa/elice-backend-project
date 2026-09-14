from fastapi import APIRouter, status

from app.api.v1.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.schemas.user import LoginRequest, SignUpRequest, TokenResponse, UserResponse
from app.services import auth_service

router = APIRouter()


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def sign_up(payload: SignUpRequest, db: DbSession) -> UserResponse:
    """계정을 생성합니다.

    이메일은 대소문자를 구분하지 않으며, 중복 시 409 를 반환합니다.
    """
    user = await auth_service.sign_up(db, payload)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    """로그인하고 해당 세션의 access token 을 반환합니다.

    이미 로그인된 상태에서 다시 로그인하면 기존 세션은 무효화됩니다.
    """
    access_token = await auth_service.login(db, payload)
    return TokenResponse(
        access_token=access_token, expires_in=get_settings().session_ttl_seconds
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: CurrentUser) -> None:
    """현재 로그인 세션을 로그아웃합니다."""
    await auth_service.logout(current_user.id)
