"""task template pools

Revision ID: 492a8796ffdf
Revises: 34dee8279256
Create Date: 2026-10-06 04:59:31.863059
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "492a8796ffdf"
down_revision: str | None = "34dee8279256"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("employer_tasks", sa.Column("template_pool", sa.String(length=128), nullable=True))
    op.add_column(
        "task_assignments",
        sa.Column(
            "template_id", sa.String(length=128), nullable=True, comment="Шаблон, выбранный при выдаче"
        ),
    )


def downgrade() -> None:
    op.drop_column("task_assignments", "template_id")
    op.drop_column("employer_tasks", "template_pool")
