from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

import app.models  # noqa: F401  모든 모델을 Base.metadata 에 등록한다
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import Base, engine
from app.core.exceptions import (
    DomainError,
    domain_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from app.core.redis import get_redis

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 없는 테이블만 만든다. 이미 있으면 건드리지 않으므로 재시작해도 안전하다.
    # 인덱스·CHECK 제약·생성 컬럼까지 모델 정의 그대로 생성된다.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    await get_redis().aclose()
    await engine.dispose()


_DESCRIPTION = """
게시판 서비스 API.

### 인증 방법

1. `POST /auth/signup` 으로 계정을 만듭니다.
2. `POST /auth/login` 으로 `access_token` 을 받습니다.
3. 우측 상단 **Authorize** 버튼을 눌러 토큰을 붙여넣습니다.

`signup` · `login` 을 제외한 모든 API 는 `Authorization: Bearer <access_token>`
헤더가 필요하며, 없거나 만료되면 **401** 을 반환합니다.
"""

app = FastAPI(
    title="Elice Board API",
    version="0.1.0",
    description=_DESCRIPTION,
    lifespan=lifespan,
)

# 모든 에러 응답을 {"code", "detail"} 형태로 통일한다.
# 서비스 계층이 HTTPException 을 모르게 하는 것이 목적이다.
app.add_exception_handler(DomainError, domain_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)

app.include_router(api_router, prefix="/api/v1")
