from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DuplicateError,
    ErrorCode,
    NotFoundError,
    PermissionDeniedError,
)
from app.core.pagination import decode_cursor, encode_cursor
from app.models.board import Board
from app.models.user import User
from app.repositories import board_repo
from app.schemas.board import BoardCreate, BoardSort, BoardUpdate, SortOrder

_NOT_FOUND = "게시판을 찾을 수 없습니다."
_DUPLICATE_NAME = "이미 사용 중인 게시판 이름입니다."
_NOT_OWNER = "본인이 생성한 게시판만 수정·삭제할 수 있습니다."


def _not_found() -> NotFoundError:
    return NotFoundError(_NOT_FOUND, code=ErrorCode.BOARD_NOT_FOUND)


def _duplicate() -> DuplicateError:
    return DuplicateError(_DUPLICATE_NAME, code=ErrorCode.BOARD_NAME_ALREADY_EXISTS)


# --------------------------------------------------------------- 권한 판단

async def get_readable(db: AsyncSession, *, board_id: int, user: User) -> Board:
    """조회 권한까지 확인한다. 모든 읽기 경로의 단일 통로.

    '없음' 과 '권한 없음' 을 구분하지 않고 둘 다 404 를 낸다.
    403 을 내면 비공개 게시판의 존재 여부가 드러난다.
    """
    board = await board_repo.get(db, board_id)
    if board is None or not (board.is_public or board.owner_id == user.id):
        raise _not_found()
    return board


async def get_owned(db: AsyncSession, *, board_id: int, user: User) -> Board:
    """수정·삭제용. 조회 권한 -> 소유권 순으로 검사한다.

    순서가 중요하다. 소유권을 먼저 보면 비공개 게시판에 403 이 나가
    그 게시판이 존재한다는 사실이 샌다.
    """
    board = await get_readable(db, board_id=board_id, user=user)
    if board.owner_id != user.id:
        raise PermissionDeniedError(_NOT_OWNER)
    return board


# ------------------------------------------------------------------- 동작

async def create(db: AsyncSession, *, payload: BoardCreate, owner: User) -> Board:
    if await board_repo.exists_by_name(db, payload.name):
        raise _duplicate()
    try:
        board = await board_repo.create(
            db, name=payload.name, is_public=payload.public, owner_id=owner.id
        )
        await db.commit()
    except IntegrityError:
        # 사전 확인을 통과한 동시 요청이 유일 제약에서 충돌한 경우
        await db.rollback()
        raise _duplicate() from None
    return board


async def update(db: AsyncSession, *, board_id: int, payload: BoardUpdate, user: User) -> Board:
    board = await get_owned(db, board_id=board_id, user=user)

    if payload.name is not None:
        # 자기 자신의 현재 이름으로 바꾸는 것은 중복이 아니다
        if await board_repo.exists_by_name(db, payload.name, exclude_id=board.id):
            raise _duplicate()
        board.name = payload.name
    if payload.public is not None:
        board.is_public = payload.public

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise _duplicate() from None
    await db.refresh(board)
    return board


async def delete(db: AsyncSession, *, board_id: int, user: User) -> None:
    board = await get_owned(db, board_id=board_id, user=user)
    await board_repo.delete(db, board)
    await db.commit()


async def list_boards(
    db: AsyncSession,
    *,
    user: User,
    sort: BoardSort,
    order: SortOrder,
    cursor: str | None,
    limit: int,
) -> tuple[list[Board], str | None, bool]:
    keys = ("pc", "id") if sort is BoardSort.POST_COUNT else ("id",)
    decoded = decode_cursor(cursor, keys=keys) if cursor else None

    # limit + 1 개를 받아 초과분 유무로 has_next 를 판정한다.
    # 전체 개수를 COUNT 하면 목록 조회만큼 비싸다.
    rows = await board_repo.list_readable(
        db, user_id=user.id, sort=sort, order=order, cursor=decoded, limit=limit + 1
    )

    has_next = len(rows) > limit
    items = rows[:limit]

    next_cursor = None
    if has_next and items:
        last = items[-1]
        payload = (
            {"pc": last.post_count, "id": last.id}
            if sort is BoardSort.POST_COUNT
            else {"id": last.id}
        )
        next_cursor = encode_cursor(payload)

    return items, next_cursor, has_next
