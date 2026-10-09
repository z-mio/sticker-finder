"""ingest_queue

Revision ID: 9c1f3a2b84de
Revises: 895ecd4e9720
Create Date: 2026-10-09 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9c1f3a2b84de"
down_revision: str | Sequence[str] | None = "895ecd4e9720"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # create_all 先行, 全新库表已存在, 只补旧库缺的部分
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("IngestJob"):
        op.create_table(
            "IngestJob",
            sa.Column("id", sa.INTEGER(), nullable=False),
            sa.Column("kind", sa.String(), nullable=False),
            sa.Column("uid", sa.INTEGER(), nullable=False),
            sa.Column("set_name", sa.String(), nullable=False),
            sa.Column("title", sa.String(), nullable=True),
            sa.Column("chat_id", sa.INTEGER(), nullable=True),
            sa.Column("message_id", sa.INTEGER(), nullable=True),
            sa.Column("total", sa.INTEGER(), nullable=False),
            sa.Column("done", sa.INTEGER(), nullable=False),
            sa.Column("failed", sa.INTEGER(), nullable=False),
            sa.Column("stopped", sa.Boolean(), nullable=False),
            sa.Column("auto_index_id", sa.INTEGER(), nullable=True),
            sa.Column("target_hash", sa.INTEGER(), nullable=True),
            sa.Column("created_at", sa.Float(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_IngestJob_uid", "IngestJob", ["uid"])
    if not inspector.has_table("IngestTask"):
        op.create_table(
            "IngestTask",
            sa.Column("id", sa.INTEGER(), nullable=False),
            sa.Column("job_id", sa.INTEGER(), nullable=False),
            sa.Column("uid", sa.INTEGER(), nullable=False),
            sa.Column("file_id", sa.String(), nullable=False),
            sa.Column("file_unique_id", sa.String(), nullable=False),
            sa.Column("mime_type", sa.String(), nullable=True),
            sa.Column("emoji", sa.String(), nullable=True),
            sa.Column("set_name", sa.String(), nullable=False),
            sa.Column("date", sa.INTEGER(), nullable=False),
            sa.ForeignKeyConstraint(["job_id"], ["IngestJob.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("uid", "file_unique_id", name="uix_task_uid_sticker"),
            sqlite_autoincrement=True,
        )
        op.create_index("ix_IngestTask_job_id", "IngestTask", ["job_id"])


def downgrade() -> None:
    op.drop_table("IngestTask")
    op.drop_table("IngestJob")
