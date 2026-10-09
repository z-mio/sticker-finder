"""initial_schema

Revision ID: 719d322d3cdb
Revises:
Create Date: 2026-10-09 10:00:00.000000

"""

from collections.abc import Sequence

revision: str = "719d322d3cdb"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
