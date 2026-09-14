"""커서(keyset) 페이지네이션 공용 유틸.

커서는 정렬 키를 base64 로 인코딩한 **불투명 문자열**이다.
클라이언트가 해석하지 못하게 해서, 내부 정렬 방식을 바꿔도 API 계약이 유지된다.
"""

import base64
import binascii
import json
from typing import Any

from app.core.exceptions import DomainError, ErrorCode

DEFAULT_LIMIT = 10
MAX_LIMIT = 100


class InvalidCursorError(DomainError):
    status_code = 400
    code = ErrorCode.INVALID_CURSOR
    default_message = "잘못된 커서입니다."


def encode_cursor(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode()
    # '=' 패딩은 URL 에서 인코딩이 필요해 떼어낸다. 디코딩할 때 다시 붙인다.
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str, *, keys: tuple[str, ...]) -> dict[str, int]:
    """커서를 해석한다. 형식이나 키가 맞지 않으면 400 을 던진다."""
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded))
    except (ValueError, binascii.Error) as exc:
        raise InvalidCursorError() from exc

    if not isinstance(data, dict) or set(data) != set(keys):
        raise InvalidCursorError()
    if not all(isinstance(data[k], int) for k in keys):
        raise InvalidCursorError()
    return data
