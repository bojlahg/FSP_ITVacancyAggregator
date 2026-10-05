"""rate limit hits in postgres

Revision ID: b7e1c2d4a9f0
Revises: 6a9a5c5c9361
Create Date: 2026-10-05 13:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7e1c2d4a9f0"
down_revision: str | None = "6a9a5c5c9361"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_hits",
        sa.Column("key", sa.String(length=200), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("key", "window_start", name=op.f("pk_rate_limit_hits")),
    )


def downgrade() -> None:
    op.drop_table("rate_limit_hits")
