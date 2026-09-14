from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://developer:devpassword@127.0.0.1:25000/developer"
    db_pool_size: int = 10
    db_max_overflow: int = 10

    redis_url: str = "redis://127.0.0.1:25100/0"
    session_ttl_seconds: int = 3600

    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
