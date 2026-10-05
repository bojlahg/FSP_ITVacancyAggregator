"""unique attempt item position

Revision ID: 34dee8279256
Revises: 6c4fbeaf033a
Create Date: 2026-10-06 04:05:13.972644
"""

from collections.abc import Sequence

from alembic import op

revision: str = "34dee8279256"
down_revision: str | None = "6c4fbeaf033a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Дубли позиции — следствие гонки параллельных запросов (ревью 06.10, №4): остаётся первое задание
    op.execute(
        """
        DELETE FROM test_attempt_items a
        USING test_attempt_items b
        WHERE a.attempt_id = b.attempt_id AND a.position = b.position AND a.id > b.id
        """
    )
    op.create_unique_constraint(
        op.f("uq_test_attempt_items_attempt_id"), "test_attempt_items", ["attempt_id", "position"]
    )


def downgrade() -> None:
    op.drop_constraint(op.f("uq_test_attempt_items_attempt_id"), "test_attempt_items", type_="unique")
