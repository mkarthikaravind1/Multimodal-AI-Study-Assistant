"""Add quiz_details.submitted_at (NULL = generated but never submitted)

Revision ID: 0002_quiz_submitted_at
Revises: 0001_baseline
Create Date: 2026-11-12

Idempotent: if the column already exists (it was briefly added by a startup
check in main.py), this migration only skips the ALTER.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_quiz_submitted_at"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("quiz_details")}
    if "submitted_at" in columns:
        return

    op.add_column("quiz_details", sa.Column("submitted_at", sa.DateTime(), nullable=True))
    # Old quizzes that were actually answered count as submitted
    op.execute(
        "UPDATE quiz_details SET submitted_at = attempted_at "
        "WHERE correct_answers + incorrect_answers > 0"
    )


def downgrade() -> None:
    op.drop_column("quiz_details", "submitted_at")
