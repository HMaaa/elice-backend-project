from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_TITLE_LENGTH = 200
# text 는 사실상 무제한이라 그대로 두면 수십 MB 요청이 가능하다.
MAX_CONTENT_LENGTH = 20_000


def _strip_not_blank(v: str) -> str:
    stripped = v.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


class PostCreate(BaseModel):
    board_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)
    content: str = Field(min_length=1, max_length=MAX_CONTENT_LENGTH)

    @field_validator("title", "content")
    @classmethod
    def strip(cls, v: str) -> str:
        return _strip_not_blank(v)


class PostUpdate(BaseModel):
    """부분 수정. board_id 는 없다 — 게시글 이동은 지원하지 않는다.

    이동을 허용하면 두 게시판의 post_count 를 함께 조정해야 하는데,
    명세에 없는 기능이라 스키마에서 원천 차단한다.
    """

    title: str | None = Field(default=None, min_length=1, max_length=MAX_TITLE_LENGTH)
    content: str | None = Field(default=None, min_length=1, max_length=MAX_CONTENT_LENGTH)

    @field_validator("title", "content")
    @classmethod
    def strip(cls, v: str | None) -> str | None:
        return _strip_not_blank(v) if v is not None else None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "PostUpdate":
        if self.title is None and self.content is None:
            raise ValueError("at least one of 'title' or 'content' is required")
        return self


class PostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    board_id: int
    author_id: int
    title: str
    content: str
    created_at: datetime
    updated_at: datetime


class PostListItem(BaseModel):
    """목록 전용. content 가 없다.

    본문이 20,000자까지 가능해 10개만 담아도 응답이 200KB 가 될 수 있다.
    목록 화면은 제목만 보여주므로 전송하지 않는다. 본문은 단건 조회로 가져간다.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    board_id: int
    author_id: int
    title: str
    created_at: datetime
    updated_at: datetime


class PostListResponse(BaseModel):
    items: list[PostListItem]
    next_cursor: str | None
    has_next: bool
