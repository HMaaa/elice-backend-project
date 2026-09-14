"""도메인 예외와 에러 코드.

서비스 계층은 HTTP 를 모르는 도메인 예외를 던지고,
main.py 에 등록된 전역 핸들러가 상태코드와 응답 형태로 변환한다.
덕분에 서비스 테스트에 HTTP 컨텍스트가 필요 없다.

모든 에러 응답은 형태가 동일하다:

    {"code": "EMAIL_ALREADY_EXISTS", "detail": "이미 사용 중인 이메일입니다."}

`detail` 은 사람이 읽는 메시지라 바뀔 수 있고, `code` 는 클라이언트가 분기에 쓰는
계약이므로 한번 정하면 바꾸지 않는다.
"""

import logging
from enum import StrEnum

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class ErrorCode(StrEnum):
    # 400
    BAD_REQUEST = "BAD_REQUEST"
    INVALID_CURSOR = "INVALID_CURSOR"
    # 401
    AUTH_REQUIRED = "AUTH_REQUIRED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    # 403
    PERMISSION_DENIED = "PERMISSION_DENIED"
    # 404
    NOT_FOUND = "NOT_FOUND"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    BOARD_NOT_FOUND = "BOARD_NOT_FOUND"
    POST_NOT_FOUND = "POST_NOT_FOUND"
    # 409
    CONFLICT = "CONFLICT"
    EMAIL_ALREADY_EXISTS = "EMAIL_ALREADY_EXISTS"
    BOARD_NAME_ALREADY_EXISTS = "BOARD_NAME_ALREADY_EXISTS"
    # 422
    VALIDATION_ERROR = "VALIDATION_ERROR"
    # 500
    INTERNAL_ERROR = "INTERNAL_ERROR"


class DomainError(Exception):
    """도메인 예외의 기반 클래스."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: ErrorCode = ErrorCode.BAD_REQUEST
    default_message: str = "잘못된 요청입니다."

    def __init__(self, message: str | None = None, *, code: ErrorCode | None = None) -> None:
        self.message = message or self.default_message
        if code is not None:
            self.code = code
        super().__init__(self.message)


class NotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = ErrorCode.NOT_FOUND
    default_message = "대상을 찾을 수 없습니다."


class PermissionDeniedError(DomainError):
    status_code = status.HTTP_403_FORBIDDEN
    code = ErrorCode.PERMISSION_DENIED
    default_message = "권한이 없습니다."


class DuplicateError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = ErrorCode.CONFLICT
    default_message = "이미 존재하는 값입니다."


class AuthenticationError(DomainError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = ErrorCode.AUTH_REQUIRED
    default_message = "인증이 필요합니다."


def _error_response(
    status_code: int, code: ErrorCode, detail: str, **extra: object
) -> JSONResponse:
    content: dict[str, object] = {"code": code.value, "detail": detail}
    content.update(extra)
    headers = {}
    if status_code == status.HTTP_401_UNAUTHORIZED:
        # 401 응답에는 WWW-Authenticate 헤더가 있어야 한다 (RFC 7235)
        headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse(status_code=status_code, content=content, headers=headers)


async def domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    return _error_response(exc.status_code, exc.code, exc.message)


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """FastAPI 기본 422 응답에 code 를 붙여 형태를 통일한다.

    필드별 상세는 `errors` 에 담는다. 어떤 필드가 왜 틀렸는지 알려주면
    클라이언트가 폼에 바로 표시할 수 있다.
    """
    assert isinstance(exc, RequestValidationError)
    errors = [
        {
            "field": ".".join(str(p) for p in err["loc"][1:]) or str(err["loc"][0]),
            "message": err["msg"],
            "type": err["type"],
        }
        for err in exc.errors()
    ]
    return _error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        ErrorCode.VALIDATION_ERROR,
        "입력값이 올바르지 않습니다.",
        errors=errors,
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """예상치 못한 예외. 내부 정보를 응답에 노출하지 않는다."""
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return _error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        ErrorCode.INTERNAL_ERROR,
        "서버 내부 오류가 발생했습니다.",
    )
