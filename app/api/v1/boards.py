from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.v1.deps import CurrentUser, DbSession
from app.core.pagination import DEFAULT_LIMIT, MAX_LIMIT
from app.schemas.board import (
    BoardCreate,
    BoardListResponse,
    BoardResponse,
    BoardSort,
    BoardUpdate,
    SortOrder,
)
from app.services import board_service

router = APIRouter()


@router.post("", response_model=BoardResponse, status_code=status.HTTP_201_CREATED)
async def create_board(payload: BoardCreate, db: DbSession, user: CurrentUser) -> BoardResponse:
    """게시판을 생성합니다.

    이름은 대소문자를 무시하고 유일해야 하며, 중복 시 409 를 반환합니다.
    """
    board = await board_service.create(db, payload=payload, owner=user)
    return BoardResponse.model_validate(board)


@router.get("", response_model=BoardListResponse)
async def list_boards(
    db: DbSession,
    user: CurrentUser,
    sort: Annotated[BoardSort, Query()] = BoardSort.CREATED_AT,
    order: Annotated[SortOrder, Query()] = SortOrder.DESC,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    cursor: Annotated[str | None, Query()] = None,
) -> BoardListResponse:
    """게시판 목록을 조회합니다.

    본인이 생성했거나 전체 공개된 게시판만 조회됩니다.
    `sort=post_count` 로 게시글 갯수 순 정렬이 가능합니다.
    다음 페이지는 응답의 `next_cursor` 를 `cursor` 로 전달하면 됩니다.
    """
    items, next_cursor, has_next = await board_service.list_boards(
        db, user=user, sort=sort, order=order, cursor=cursor, limit=limit
    )
    return BoardListResponse(
        items=[BoardResponse.model_validate(b) for b in items],
        next_cursor=next_cursor,
        has_next=has_next,
    )


@router.get("/{board_id}", response_model=BoardResponse)
async def get_board(board_id: int, db: DbSession, user: CurrentUser) -> BoardResponse:
    """게시판을 조회합니다.

    본인이 생성했거나 전체 공개된 게시판만 조회할 수 있습니다.
    조회 권한이 없으면 존재 여부를 숨기기 위해 404 를 반환합니다.
    """
    board = await board_service.get_readable(db, board_id=board_id, user=user)
    return BoardResponse.model_validate(board)


@router.patch("/{board_id}", response_model=BoardResponse)
async def update_board(
    board_id: int, payload: BoardUpdate, db: DbSession, user: CurrentUser
) -> BoardResponse:
    """게시판의 name, public 을 수정합니다. 타 유저의 게시판은 수정할 수 없습니다."""
    board = await board_service.update(db, board_id=board_id, payload=payload, user=user)
    return BoardResponse.model_validate(board)


@router.delete("/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_board(board_id: int, db: DbSession, user: CurrentUser) -> None:
    """게시판을 삭제합니다. 타 유저의 게시판은 삭제할 수 없습니다."""
    await board_service.delete(db, board_id=board_id, user=user)
