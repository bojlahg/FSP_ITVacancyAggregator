"""search index unconfirmed grade

Revision ID: 2ed3755e2b17
Revises: 3a055980727f
Create Date: 2026-10-06 19:36:26.455563
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2ed3755e2b17"
down_revision: str | None = "3a055980727f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # NULL — грейд не подтверждён тестом: строка кандидата без категории (docs/implementation.md §8.2)
    op.alter_column("candidate_search_index", "grade", existing_type=sa.VARCHAR(length=32), nullable=True)
    op.alter_column(
        "candidate_search_index", "theta", existing_type=sa.DOUBLE_PRECISION(precision=53), nullable=True
    )


def downgrade() -> None:
    op.execute("DELETE FROM candidate_search_index WHERE grade IS NULL OR theta IS NULL")
    op.alter_column(
        "candidate_search_index", "theta", existing_type=sa.DOUBLE_PRECISION(precision=53), nullable=False
    )
    op.alter_column("candidate_search_index", "grade", existing_type=sa.VARCHAR(length=32), nullable=False)
