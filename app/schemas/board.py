from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BoardSort(StrEnum):
    CREATED_AT = "created_at"
    POST_COUNT = "post_count"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


def _strip_not_blank(v: str) -> str:
    stripped = v.strip()
    if not stripped:
        raise ValueError("name must not be blank")
    return stripped


class BoardCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    public: bool

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return _strip_not_blank(v)


class BoardUpdate(BaseModel):
    """부분 수정. 두 필드 모두 선택이지만 최소 하나는 있어야 한다."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    public: bool | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str | None) -> str | None:
        return _strip_not_blank(v) if v is not None else None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "BoardUpdate":
        if self.name is None and self.public is None:
            raise ValueError("at least one of 'name' or 'public' is required")
        return self


class BoardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    # DB 컬럼은 is_public, API 필드명은 명세대로 public
    public: bool = Field(validation_alias="is_public")
    owner_id: int
    post_count: int
    created_at: datetime
    updated_at: datetime


class BoardListResponse(BaseModel):
    items: list[BoardResponse]
    next_cursor: str | None
    has_next: bool
