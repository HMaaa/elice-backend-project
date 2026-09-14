from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ErrorCode, NotFoundError, PermissionDeniedError
from app.core.pagination import decode_cursor, encode_cursor
from app.models.post import Post
from app.models.user import User
from app.repositories import board_repo, post_repo
from app.schemas.post import PostCreate, PostUpdate
from app.services import board_service

_NOT_FOUND = "게시글을 찾을 수 없습니다."
_BOARD_NOT_FOUND = "게시판을 찾을 수 없습니다."
_NOT_AUTHOR = "본인이 작성한 게시글만 수정·삭제할 수 있습니다."


def _not_found() -> NotFoundError:
    return NotFoundError(_NOT_FOUND, code=ErrorCode.POST_NOT_FOUND)


def _board_not_found() -> NotFoundError:
    return NotFoundError(_BOARD_NOT_FOUND, code=ErrorCode.BOARD_NOT_FOUND)


# --------------------------------------------------------------- 권한 판단

async def get_accessible(db: AsyncSession, *, post_id: int, user: User) -> Post:
    """상위 게시판 접근 권한까지 확인한다. 모든 읽기 경로의 단일 통로.

    작성자일 필요는 없다. 공개 게시판의 글은 누구나 읽는다.
    """
    row = await post_repo.get_with_board(db, post_id)
    if row is None or not (row.board_is_public or row.board_owner_id == user.id):
        # 없음과 접근 불가를 구분하지 않는다. 구분하면 존재가 드러난다.
        raise _not_found()
    return row.post


async def get_owned(db: AsyncSession, *, post_id: int, user: User) -> Post:
    """수정·삭제용. 게시판 접근 -> 작성자 순으로 검사한다.

    순서가 중요하다. 작성자를 먼저 보면 접근 불가 게시판의 글에 403 이 나가
    그 글과 게시판이 존재한다는 사실이 샌다.
    """
    post = await get_accessible(db, post_id=post_id, user=user)
    if post.author_id != user.id:
        raise PermissionDeniedError(_NOT_AUTHOR)
    return post


# ------------------------------------------------------------------- 동작

async def create(db: AsyncSession, *, payload: PostCreate, author: User) -> Post:
    # 접근할 수 없는 게시판이면 여기서 404 (BOARD_NOT_FOUND)
    await board_service.get_readable(db, board_id=payload.board_id, user=author)
    try:
        post = await post_repo.create(
            db,
            board_id=payload.board_id,
            author_id=author.id,
            title=payload.title,
            content=payload.content,
        )
        # INSERT 와 카운트 갱신이 같은 트랜잭션이어야 한다
        await board_repo.change_post_count(db, payload.board_id, delta=1)
        await db.commit()
    except IntegrityError:
        # 확인과 INSERT 사이에 게시판이 삭제된 경우 (FK 위반)
        await db.rollback()
        raise _board_not_found() from None
    return post


async def update(db: AsyncSession, *, post_id: int, payload: PostUpdate, user: User) -> Post:
    post = await get_owned(db, post_id=post_id, user=user)

    if payload.title is not None:
        post.title = payload.title
    if payload.content is not None:
        post.content = payload.content

    await db.commit()
    await db.refresh(post)
    return post


async def delete(db: AsyncSession, *, post_id: int, user: User) -> None:
    post = await get_owned(db, post_id=post_id, user=user)
    board_id = post.board_id
    await post_repo.delete(db, post)
    await board_repo.change_post_count(db, board_id, delta=-1)
    await db.commit()


async def list_by_board(
    db: AsyncSession, *, board_id: int, user: User, cursor: str | None, limit: int
):
    """게시판의 게시글 목록.

    게시판에 접근할 수 없으면 빈 배열이 아니라 404 다.
    빈 배열을 주면 "그 게시판은 존재하는데 글이 없구나" 로 읽혀 존재가 노출된다.
    """
    await board_service.get_readable(db, board_id=board_id, user=user)

    decoded = decode_cursor(cursor, keys=("id",)) if cursor else None
    rows = await post_repo.list_by_board(
        db,
        board_id=board_id,
        cursor_id=decoded["id"] if decoded else None,
        limit=limit + 1,
    )

    has_next = len(rows) > limit
    items = rows[:limit]
    next_cursor = encode_cursor({"id": items[-1].id}) if has_next and items else None
    return items, next_cursor, has_next
