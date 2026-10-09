"""clear_ocr_cache

Revision ID: 895ecd4e9720
Revises: f7ceefcacaaf
Create Date: 2026-10-09 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "895ecd4e9720"
down_revision: str | Sequence[str] | None = "f7ceefcacaaf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 清空旧的 RapidOCR 缓存, 之后添加的贴纸重新走 AI 识别
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("OcrCache"):
        op.execute(sa.delete(sa.table("OcrCache")))


def downgrade() -> None:
    pass
