"""비밀번호 해시. Argon2id 단방향."""

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from fastapi.concurrency import run_in_threadpool

_hasher = PasswordHasher()  # 기본 알고리즘이 Argon2id

# 계정이 없을 때도 검증 시간을 맞추기 위한 더미 해시 (타이밍 공격 방어).
# 모듈 로드 시 1회만 계산한다.
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing-equalization")


async def hash_password(password: str) -> str:
    """Argon2 는 CPU 를 수십~수백 ms 점유하므로 스레드풀로 분리한다.

    async 함수에서 직접 호출하면 그동안 이벤트 루프 전체가 멈춘다.
    """
    return await run_in_threadpool(_hasher.hash, password)


async def verify_password(password_hash: str, password: str) -> bool:
    def _verify() -> bool:
        try:
            return _hasher.verify(password_hash, password)
        except (VerifyMismatchError, VerificationError):
            return False

    return await run_in_threadpool(_verify)


async def waste_time_like_verify(password: str) -> None:
    """계정이 없을 때 호출. 실패하지만 소요 시간은 실제 검증과 같다.

    이것이 없으면 응답 시간 차이로 가입된 이메일을 열거할 수 있다.
    """
    await verify_password(_DUMMY_HASH, password)
