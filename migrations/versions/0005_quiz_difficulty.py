"""Quiz difficulty level

Revision ID: 0005_quiz_difficulty
Revises: 0004_flashcards
Create Date: 2026-11-13

Question types, explanations and per-question difficulty live inside the
existing quiz_details.questions JSON, so only the quiz-level difficulty
needs a column.
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_quiz_difficulty"
down_revision = "0004_flashcards"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("quiz_details", sa.Column("difficulty", sa.String(10), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("quiz_details") as batch:
        batch.drop_column("difficulty")
