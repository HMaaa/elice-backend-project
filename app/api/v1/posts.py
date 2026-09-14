from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.v1.deps import CurrentUser, DbSession
from app.core.pagination import DEFAULT_LIMIT, MAX_LIMIT
from app.schemas.post import (
    PostCreate,
    PostListItem,
    PostListResponse,
    PostResponse,
    PostUpdate,
)
from app.services import post_service

router = APIRouter()

# 게시글 목록은 게시판에 종속된 하위 자원이라 /boards/{board_id}/posts 로 둔다.
# 권한 검사(상위 게시판 접근 가능 여부)가 URL 구조와 일치해 읽기 쉽다.
board_posts_router = APIRouter()


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(payload: PostCreate, db: DbSession, user: CurrentUser) -> PostResponse:
    """게시글을 생성합니다.

    본인이 조회할 수 있는 게시판에만 작성할 수 있습니다.
    공개 게시판이면 소유자가 아니어도 작성할 수 있습니다.
    """
    post = await post_service.create(db, payload=payload, author=user)
    return PostResponse.model_validate(post)


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(post_id: int, db: DbSession, user: CurrentUser) -> PostResponse:
    """게시글을 조회합니다.

    본인이 생성했거나 전체 공개된 게시판의 게시글만 조회할 수 있습니다.
    작성자가 아니어도 조회됩니다.
    """
    post = await post_service.get_accessible(db, post_id=post_id, user=user)
    return PostResponse.model_validate(post)


@router.patch("/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: int, payload: PostUpdate, db: DbSession, user: CurrentUser
) -> PostResponse:
    """게시글의 title, content 를 수정합니다. 타 유저의 게시글은 수정할 수 없습니다."""
    post = await post_service.update(db, post_id=post_id, payload=payload, user=user)
    return PostResponse.model_validate(post)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(post_id: int, db: DbSession, user: CurrentUser) -> None:
    """게시글을 삭제합니다. 타 유저의 게시글은 삭제할 수 없습니다."""
    await post_service.delete(db, post_id=post_id, user=user)


@board_posts_router.get("/{board_id}/posts", response_model=PostListResponse)
async def list_board_posts(
    board_id: int,
    db: DbSession,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    cursor: Annotated[str | None, Query()] = None,
) -> PostListResponse:
    """게시판의 게시글 목록을 최신순으로 조회합니다.

    본인이 조회할 수 있는 게시판만 사용할 수 있습니다.
    응답에는 본문(content)이 포함되지 않습니다. 본문은 단건 조회로 가져가세요.
    """
    rows, next_cursor, has_next = await post_service.list_by_board(
        db, board_id=board_id, user=user, cursor=cursor, limit=limit
    )
    return PostListResponse(
        items=[PostListItem.model_validate(r) for r in rows],
        next_cursor=next_cursor,
        has_next=has_next,
    )
