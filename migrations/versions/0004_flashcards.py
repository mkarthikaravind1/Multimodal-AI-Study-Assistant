"""Spaced-repetition flashcards

Revision ID: 0004_flashcards
Revises: 0003_citations_loop_viva
Create Date: 2026-11-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_flashcards"
down_revision = "0003_citations_loop_viva"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "flashcards",
        sa.Column("card_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user_details.user_id"), nullable=False),
        sa.Column("front", sa.Text(), nullable=False),
        sa.Column("back", sa.Text(), nullable=False),
        sa.Column("topic", sa.String(255), nullable=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("note_id", sa.Integer(), sa.ForeignKey("notes.note_id"), nullable=True),
        sa.Column("quiz_id", sa.Integer(), sa.ForeignKey("quiz_details.quiz_id"), nullable=True),
        sa.Column("ease_factor", sa.DECIMAL(4, 2), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("repetitions", sa.Integer(), nullable=False),
        sa.Column("lapses", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=False),
        sa.Column("last_reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_index("ix_flashcards_card_id", "flashcards", ["card_id"])
    op.create_index("ix_flashcards_user_id", "flashcards", ["user_id"])
    op.create_index("ix_flashcards_due_at", "flashcards", ["due_at"])


def downgrade() -> None:
    op.drop_index("ix_flashcards_due_at", table_name="flashcards")
    op.drop_index("ix_flashcards_user_id", table_name="flashcards")
    op.drop_index("ix_flashcards_card_id", table_name="flashcards")
    op.drop_table("flashcards")
