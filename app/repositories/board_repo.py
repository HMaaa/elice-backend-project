from sqlalchemy import Select, func, select, tuple_, union_all, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.board import Board
from app.schemas.board import BoardSort, SortOrder

# 살아있는 행만 본다. 모든 조회의 공통 조건.
# ~ 는 SQL 의 NOT 으로 컴파일된다. .is_(False) 를 쓰면 `IS false` 가 되어
# 부분 인덱스 술어(`NOT is_deleted`)와 동치임을 플래너가 증명하지 못한다.
ALIVE = ~Board.is_deleted


async def get(db: AsyncSession, board_id: int) -> Board | None:
    stmt = select(Board).where(Board.id == board_id, ALIVE)
    return (await db.execute(stmt)).scalar_one_or_none()


async def exists_by_name(db: AsyncSession, name: str, *, exclude_id: int | None = None) -> bool:
    """uq_boards_name 이 lower(name) 표현식 인덱스이므로 쿼리도 같은 형태여야 한다."""
    stmt = (
        select(func.count())
        .select_from(Board)
        .where(func.lower(Board.name) == name.lower(), ALIVE)
    )
    if exclude_id is not None:
        # 자기 자신의 현재 이름으로 수정하는 것은 중복이 아니다.
        stmt = stmt.where(Board.id != exclude_id)
    return bool((await db.execute(stmt)).scalar_one())


async def create(db: AsyncSession, *, name: str, is_public: bool, owner_id: int) -> Board:
    board = Board(name=name, is_public=is_public, owner_id=owner_id)
    db.add(board)
    await db.flush()
    await db.refresh(board)
    return board


async def delete(db: AsyncSession, board: Board) -> None:
    """소프트 삭제. 행을 지우지 않고 deleted_at 을 채운다.

    게시글은 물리적으로 남지만 상위 게시판이 조회되지 않으므로 접근할 수 없다.
    """
    await db.execute(update(Board).where(Board.id == board.id).values(deleted_at=func.now()))


async def change_post_count(db: AsyncSession, board_id: int, *, delta: int) -> None:
    """게시글 수를 증감한다.

    ★ 반드시 UPDATE 문 안에서 계산해야 한다. 애플리케이션에서 현재 값을 읽어와
    더한 뒤 쓰면 동시 요청에서 갱신이 유실된다(lost update).
    실측: 동시 10회 증가 시 읽고-더하고-쓰기는 1, DB 계산은 10.

    `Board.post_count + delta` 는 파이썬 덧셈이 아니라 SQL 식으로 컴파일된다.
    """
    await db.execute(
        update(Board).where(Board.id == board_id).values(post_count=Board.post_count + delta)
    )


def _apply_keyset(stmt: Select, *, sort: BoardSort, order: SortOrder, cursor: dict | None):
    """정렬과 커서 조건을 건다.

    PostgreSQL 의 행 값 비교 `(a, b) < (x, y)` 를 쓴다.
    `a < x OR (a = x AND b < y)` 로 풀어 쓰면 인덱스를 타지 못한다.
    """
    descending = order is SortOrder.DESC

    if sort is BoardSort.POST_COUNT:
        keys = (Board.post_count, Board.id)
        order_by = (
            (Board.post_count.desc(), Board.id.desc())
            if descending
            else (Board.post_count.asc(), Board.id.asc())
        )
        if cursor is not None:
            point = (cursor["pc"], cursor["id"])
            stmt = stmt.where(
                tuple_(*keys) < point if descending else tuple_(*keys) > point
            )
    else:
        # identity 시퀀스는 단조 증가하므로 id 순서 = 생성 순서다.
        # created_at 은 동점이 가능해 단독으로는 안정적인 전순서가 아니다.
        order_by = (Board.id.desc(),) if descending else (Board.id.asc(),)
        if cursor is not None:
            stmt = stmt.where(
                Board.id < cursor["id"] if descending else Board.id > cursor["id"]
            )

    return stmt.order_by(*order_by), order_by


async def list_readable(
    db: AsyncSession,
    *,
    user_id: int,
    sort: BoardSort,
    order: SortOrder,
    cursor: dict | None,
    limit: int,
) -> list[Board]:
    """조회 가능한 게시판 목록.

    조회 범위는 `is_public OR owner_id = me` 인데, 이 OR 를 한 쿼리에 그대로 쓰면
    플래너가 정렬된 인덱스 스캔을 포기하고 Seq Scan 으로 떨어진다.
    서로 겹치지 않는 두 집합으로 쪼개 각각 전용 부분 인덱스를 타게 한 뒤 병합한다.

    ② 브랜치의 `NOT is_public` 이 없으면 내가 만든 공개 게시판이 양쪽에 걸려
    중복으로 나온다. 배타적이기 때문에 UNION(중복 제거) 대신 UNION ALL 을 쓸 수 있다.
    """
    # ① 공개 게시판 전체
    # ★ Board.is_public 을 그대로 쓴다. .is_(True) 는 SQL 로 `IS true` 가 되는데,
    #   부분 인덱스 술어(`WHERE is_public`)와 동치임을 플래너가 증명하지 못해
    #   Seq Scan 으로 떨어진다. (실측 0.012ms -> 9.956ms)
    public_stmt, _ = _apply_keyset(
        select(Board).where(Board.is_public, ALIVE),
        sort=sort,
        order=order,
        cursor=cursor,
    )
    # ② 내 비공개 게시판 (~ 는 SQL 의 NOT)
    private_stmt, _ = _apply_keyset(
        select(Board).where(Board.owner_id == user_id, ~Board.is_public, ALIVE),
        sort=sort,
        order=order,
        cursor=cursor,
    )

    combined = union_all(public_stmt.limit(limit), private_stmt.limit(limit)).subquery()
    merged = aliased(Board, combined)

    descending = order is SortOrder.DESC
    if sort is BoardSort.POST_COUNT:
        final_order = (
            (merged.post_count.desc(), merged.id.desc())
            if descending
            else (merged.post_count.asc(), merged.id.asc())
        )
    else:
        final_order = (merged.id.desc(),) if descending else (merged.id.asc(),)

    stmt = select(merged).order_by(*final_order).limit(limit)
    return list((await db.execute(stmt)).scalars().all())
