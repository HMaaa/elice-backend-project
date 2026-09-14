from typing import NamedTuple

from sqlalchemy import Row, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import Board
from app.models.post import Post


class PostWithBoard(NamedTuple):
    """게시글과 권한 판정에 필요한 상위 게시판 정보."""

    post: Post
    board_is_public: bool
    board_owner_id: int


# 살아있는 행만 본다. ~ 는 SQL 의 NOT 으로 컴파일된다.
# .is_(False) 는 `IS false` 가 되어 부분 인덱스를 타지 못한다.
POST_ALIVE = ~Post.is_deleted
BOARD_ALIVE = ~Board.is_deleted


async def get_with_board(db: AsyncSession, post_id: int) -> PostWithBoard | None:
    """게시글과 상위 게시판 권한 정보를 한 번의 쿼리로 가져온다.

    게시글을 먼저 조회하고 게시판을 다시 조회하면 왕복이 2회가 된다.
    """
    stmt = (
        select(Post, Board.is_public, Board.owner_id)
        .join(Board, Board.id == Post.board_id)
        # 게시판이 삭제되면 그 안의 게시글도 조회되지 않는다.
        # 권한 판정에 이미 조인하고 있어 조건 하나만 더 붙이면 된다.
        .where(Post.id == post_id, POST_ALIVE, BOARD_ALIVE)
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        return None
    return PostWithBoard(row[0], row[1], row[2])


async def create(
    db: AsyncSession, *, board_id: int, author_id: int, title: str, content: str
) -> Post:
    post = Post(board_id=board_id, author_id=author_id, title=title, content=content)
    db.add(post)
    await db.flush()
    await db.refresh(post)
    return post


async def delete(db: AsyncSession, post: Post) -> None:
    """소프트 삭제."""
    await db.execute(update(Post).where(Post.id == post.id).values(deleted_at=func.now()))


async def list_by_board(
    db: AsyncSession, *, board_id: int, cursor_id: int | None, limit: int
) -> list[Row]:
    """게시판의 게시글 목록 (최신순).

    ★ content 를 SELECT 하지 않는다. 응답 스키마에서만 빼면 이미 20,000자 × N 개를
    네트워크로 받아 파이썬 객체로 만든 뒤라 아무 절약이 되지 않는다.

    ix_posts_board_id (board_id, id DESC) 를 그대로 탄다.
    """
    stmt = (
        select(
            Post.id,
            Post.board_id,
            Post.author_id,
            Post.title,
            Post.created_at,
            Post.updated_at,
        )
        .where(Post.board_id == board_id, POST_ALIVE)
        .order_by(Post.id.desc())
        .limit(limit)
    )
    if cursor_id is not None:
        stmt = stmt.where(Post.id < cursor_id)
    return list((await db.execute(stmt)).all())
