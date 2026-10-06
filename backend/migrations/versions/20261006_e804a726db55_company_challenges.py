"""company challenges

Revision ID: e804a726db55
Revises: 492a8796ffdf
Create Date: 2026-10-06 11:10:34.187746
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e804a726db55"
down_revision: str | None = "492a8796ffdf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "challenges",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("employer_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("specialization", sa.String(length=32), nullable=False),
        sa.Column(
            "grade",
            sa.Enum("intern", "junior", "middle", "senior", name="grade", native_enum=False, length=32),
            nullable=True,
        ),
        sa.Column("skills", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("time_per_question_sec", sa.Integer(), nullable=False),
        sa.Column("questions_per_attempt", sa.Integer(), nullable=True),
        sa.Column("questions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "published", "closed", name="challengestatus", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "grade IN ('intern', 'junior', 'middle', 'senior')", name=op.f("ck_challenges_grade_enum")
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'closed')", name=op.f("ck_challenges_status_enum")
        ),
        sa.ForeignKeyConstraint(
            ["employer_id"],
            ["employers.id"],
            name=op.f("fk_challenges_employer_id_employers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_challenges")),
    )
    op.create_index(op.f("ix_challenges_employer_id"), "challenges", ["employer_id"], unique=False)
    op.create_table(
        "challenge_attempts",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("challenge_id", sa.BigInteger(), nullable=False),
        sa.Column("candidate_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("in_progress", "completed", name="challengeattemptstatus", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("items", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("correct", sa.Integer(), nullable=False),
        sa.Column("scored_total", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('in_progress', 'completed')", name=op.f("ck_challenge_attempts_status_enum")
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name=op.f("fk_challenge_attempts_candidate_id_candidates"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["challenge_id"],
            ["challenges.id"],
            name=op.f("fk_challenge_attempts_challenge_id_challenges"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_challenge_attempts")),
        sa.UniqueConstraint("challenge_id", "candidate_id", name=op.f("uq_challenge_attempts_challenge_id")),
    )
    op.create_index(
        op.f("ix_challenge_attempts_candidate_id"), "challenge_attempts", ["candidate_id"], unique=False
    )
    op.create_index(
        op.f("ix_challenge_attempts_challenge_id"), "challenge_attempts", ["challenge_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_challenge_attempts_challenge_id"), table_name="challenge_attempts")
    op.drop_index(op.f("ix_challenge_attempts_candidate_id"), table_name="challenge_attempts")
    op.drop_table("challenge_attempts")
    op.drop_index(op.f("ix_challenges_employer_id"), table_name="challenges")
    op.drop_table("challenges")
