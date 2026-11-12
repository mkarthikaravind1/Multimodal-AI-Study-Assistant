"""Citations, self-healing loop and viva mode

Revision ID: 0003_citations_loop_viva
Revises: 0002_quiz_submitted_at
Create Date: 2026-11-12

- uploaded_materials.stored_path : original file kept for clickable citations
- quiz_details.user_answers      : the student's answers (needed to find mistakes)
- quiz_details.parent_quiz_id    : retest quiz -> the quiz it is fixing
- viva_sessions                  : oral exam sessions
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_citations_loop_viva"
down_revision = "0002_quiz_submitted_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("uploaded_materials", sa.Column("stored_path", sa.String(500), nullable=True))
    # batch mode: plain ALTERs on MySQL, copy-and-move on SQLite (which can't ALTER constraints)
    with op.batch_alter_table("quiz_details") as batch:
        batch.add_column(sa.Column("user_answers", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("parent_quiz_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_quiz_details_parent_quiz_id", "quiz_details", ["parent_quiz_id"], ["quiz_id"]
        )

    op.create_table(
        "viva_sessions",
        sa.Column("viva_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user_details.user_id"), nullable=False),
        sa.Column("note_id", sa.Integer(), sa.ForeignKey("notes.note_id"), nullable=False),
        sa.Column("topic", sa.String(255), nullable=False),
        sa.Column("questions", sa.JSON(), nullable=False),
        sa.Column("total_score", sa.Integer(), nullable=True),
        sa.Column("max_score", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_viva_sessions_viva_id", "viva_sessions", ["viva_id"])


def downgrade() -> None:
    op.drop_index("ix_viva_sessions_viva_id", table_name="viva_sessions")
    op.drop_table("viva_sessions")
    with op.batch_alter_table("quiz_details") as batch:
        batch.drop_constraint("fk_quiz_details_parent_quiz_id", type_="foreignkey")
        batch.drop_column("parent_quiz_id")
        batch.drop_column("user_answers")
    op.drop_column("uploaded_materials", "stored_path")
