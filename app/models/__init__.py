"""모델 등록 지점.

Alembic 의 --autogenerate 가 Base.metadata 에서 테이블을 찾으려면
모든 모델이 import 되어 있어야 한다.
"""

from app.models.board import Board
from app.models.post import Post
from app.models.user import User

__all__ = ["Board", "Post", "User"]
