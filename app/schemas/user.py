from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, TypeAdapter, field_validator

# RFC 5321 기준 길이 제한. EmailStr 은 문법만 보고 길이는 강제하지 않는다.
_MAX_EMAIL_LENGTH = 254  # 주소 전체
_MAX_LOCAL_LENGTH = 64  # '@' 앞부분

# 형식 검사에만 쓴다. EmailStr 은 도메인을 소문자로 바꾸므로 반환값은 버린다.
_email_format = TypeAdapter(EmailStr)


def _validate_email(v: str) -> str:
    """형식만 검사하고 **입력값을 그대로** 돌려준다.

    대소문자를 변환하지 않으므로 저장·비교 모두 완전 일치 기준이다.
    앞뒤 공백만 제거한다(주소의 일부가 아니므로).
    """
    email = v.strip()

    if len(email) > _MAX_EMAIL_LENGTH:
        raise ValueError(f"email must be at most {_MAX_EMAIL_LENGTH} characters")

    # 국제화 주소(IDN·SMTPUTF8)는 문법상 유효하지만 처리하지 못하는 메일 시스템이 많다.
    if not email.isascii():
        raise ValueError("email must contain ASCII characters only")

    _email_format.validate_python(email)  # 형식 검증 (반환값 미사용)

    local, _, _domain = email.partition("@")
    if len(local) > _MAX_LOCAL_LENGTH:
        raise ValueError(f"the part before '@' must be at most {_MAX_LOCAL_LENGTH} characters")

    return email


class SignUpRequest(BaseModel):
    fullname: str = Field(min_length=1, max_length=100)
    # str 로 받아 입력값을 보존한다. EmailStr 로 받으면 도메인이 소문자로 바뀐다.
    email: str = Field(max_length=_MAX_EMAIL_LENGTH)
    # max_length 는 긴 입력으로 Argon2 연산을 유발하는 DoS 를 막는다.
    password: str = Field(min_length=8, max_length=128)

    @field_validator("fullname")
    @classmethod
    def strip_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("fullname must not be blank")
        return stripped

    @field_validator("email")
    @classmethod
    def check_email(cls, v: str) -> str:
        return _validate_email(v)


class LoginRequest(BaseModel):
    email: str = Field(max_length=_MAX_EMAIL_LENGTH)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def check_email(cls, v: str) -> str:
        return _validate_email(v)


class UserResponse(BaseModel):
    """password_hash 가 없다. response_model 로 유출을 구조적으로 차단한다."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    fullname: str
    email: str
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
