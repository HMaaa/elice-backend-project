from fastapi import APIRouter

from app.api.v1 import auth, boards, posts

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(boards.router, prefix="/boards", tags=["boards"])
# 게시글 목록은 게시판 하위 자원이므로 /boards/{board_id}/posts 에 붙인다.
api_router.include_router(posts.board_posts_router, prefix="/boards", tags=["posts"])
api_router.include_router(posts.router, prefix="/posts", tags=["posts"])
