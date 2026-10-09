"""ocr_cache_and_auto_index_hash

Revision ID: f7ceefcacaaf
Revises: 719d322d3cdb
Create Date: 2026-10-09 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f7ceefcacaaf"
down_revision: str | Sequence[str] | None = "719d322d3cdb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # create_all 先行, 全新库表和列都已存在, 只补旧库缺的部分
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("OcrCache"):
        op.create_table(
            "OcrCache",
            sa.Column("sticker_unique_id", sa.String(), nullable=False),
            sa.Column("tag", sa.String(), nullable=False),
            sa.PrimaryKeyConstraint("sticker_unique_id"),
        )
    columns = [c["name"] for c in inspector.get_columns("AutoIndexSticker")]
    if "hash" not in columns:
        op.add_column("AutoIndexSticker", sa.Column("hash", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("AutoIndexSticker") as batch_op:
        batch_op.drop_column("hash")
    op.drop_table("OcrCache")
