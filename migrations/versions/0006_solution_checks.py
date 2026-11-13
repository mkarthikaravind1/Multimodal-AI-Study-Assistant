"""Handwritten solution checks

Revision ID: 0006_solution_checks
Revises: 0005_quiz_difficulty
Create Date: 2026-11-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_solution_checks"
down_revision = "0005_quiz_difficulty"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "solution_checks",
        sa.Column("check_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user_details.user_id"), nullable=False),
        sa.Column("topic", sa.String(255), nullable=True),
        sa.Column("problem", sa.Text(), nullable=True),
        sa.Column("expected_answer", sa.String(255), nullable=True),
        sa.Column("final_answer", sa.String(255), nullable=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("stored_path", sa.String(500), nullable=True),
        sa.Column("mime_type", sa.String(50), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("verdict", sa.String(20), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("rechecks", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_solution_checks_check_id", "solution_checks", ["check_id"])
    op.create_index("ix_solution_checks_user_id", "solution_checks", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_solution_checks_user_id", table_name="solution_checks")
    op.drop_index("ix_solution_checks_check_id", table_name="solution_checks")
    op.drop_table("solution_checks")
