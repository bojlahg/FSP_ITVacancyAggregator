"""express test attempt purpose

Revision ID: 3a055980727f
Revises: 30d57fe601a9
Create Date: 2026-10-06 19:38:17.920022
"""

from collections.abc import Sequence

from alembic import op

revision: str = "3a055980727f"
down_revision: str | None = "30d57fe601a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# CHECK enum-колонки autogenerate не сравнивает — меняем вручную (app/core/types.py add_enum_checks)
NAME = "ck_test_attempts_purpose_enum"
OLD = "purpose IN ('calibration', 'upgrade', 'downgrade', 'vacancy_preview')"
NEW = "purpose IN ('calibration', 'upgrade', 'downgrade', 'vacancy_preview', 'express')"


def upgrade() -> None:
    op.drop_constraint(op.f(NAME), "test_attempts", type_="check")
    op.create_check_constraint(op.f(NAME), "test_attempts", NEW)


def downgrade() -> None:
    op.execute("DELETE FROM test_attempts WHERE purpose = 'express'")
    op.drop_constraint(op.f(NAME), "test_attempts", type_="check")
    op.create_check_constraint(op.f(NAME), "test_attempts", OLD)
