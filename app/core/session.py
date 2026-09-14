"""Redis 세션. 사용자당 키 하나 = 세션 하나(단일 세션).

    key    session:{user_id}
    value  {"token": "<난수>", "created_at": "..."}
    TTL    SESSION_TTL_SECONDS

access_token 은 "{user_id}.{난수}" 형식이다. 조회에 user_id 가 필요하므로 접두한다.
SET 이 덮어쓰기이므로 재로그인 시 기존 세션이 자동으로 무효화된다.
"""

import hmac
import json
import secrets
from datetime import UTC, datetime

from app.core.config import get_settings
from app.core.redis import get_redis

_KEY = "session:{user_id}"
_TOKEN_BYTES = 32  # 256비트


def _key(user_id: int | str) -> str:
    return _KEY.format(user_id=user_id)


async def create(user_id: int) -> str:
    """로그인. 기존 세션이 있으면 덮어써서 자동으로 무효화한다."""
    raw = secrets.token_urlsafe(_TOKEN_BYTES)
    payload = json.dumps({"token": raw, "created_at": datetime.now(UTC).isoformat()})
    await get_redis().set(_key(user_id), payload, ex=get_settings().session_ttl_seconds)
    return f"{user_id}.{raw}"


async def get_user_id(access_token: str) -> int | None:
    """요청 인증. 유효하면 user_id 를 반환하고 TTL 을 연장한다(슬라이딩 만료)."""
    user_id, sep, raw = access_token.partition(".")
    if not sep or not user_id.isdigit() or not raw:
        return None

    key = _key(user_id)
    data = await get_redis().get(key)
    if data is None:
        return None

    stored = json.loads(data).get("token", "")
    # 상수 시간 비교. 일반 == 는 일치한 길이가 응답 시간에 드러난다.
    if not hmac.compare_digest(stored, raw):
        return None

    await get_redis().expire(key, get_settings().session_ttl_seconds)
    return int(user_id)


async def revoke(user_id: int) -> None:
    """로그아웃."""
    await get_redis().delete(_key(user_id))
