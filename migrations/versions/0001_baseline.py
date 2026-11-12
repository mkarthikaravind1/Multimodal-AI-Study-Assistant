"""Baseline: the schema as it was before migrations were introduced

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-12

Existing databases already have these tables — mark them as being at this
revision with `alembic stamp 0001_baseline` instead of running it.
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_details",
        sa.Column("user_id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("student_class", sa.String(50)),
        sa.Column("role", sa.Enum("student", "admin", name="roleenum"), nullable=False),
        sa.Column("registered_date", sa.DateTime()),
    )
    op.create_index("ix_user_details_user_id", "user_details", ["user_id"])

    op.create_table(
        "notes",
        sa.Column("note_id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("youtube_links", sa.JSON()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user_details.user_id"), nullable=False),
    )
    op.create_index("ix_notes_note_id", "notes", ["note_id"])

    op.create_table(
        "quiz_details",
        sa.Column("quiz_id", sa.Integer(), primary_key=True),
        sa.Column("topic", sa.String(255), nullable=False),
        sa.Column("questions", sa.JSON(), nullable=False),
        sa.Column("total_questions", sa.Integer(), nullable=False),
        sa.Column("correct_answers", sa.Integer(), nullable=False),
        sa.Column("incorrect_answers", sa.Integer(), nullable=False),
        sa.Column("score_percentage", sa.DECIMAL(5, 2), nullable=False),
        sa.Column("attempted_at", sa.DateTime()),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user_details.user_id"), nullable=False),
        sa.Column("note_id", sa.Integer(), sa.ForeignKey("notes.note_id"), nullable=False),
    )
    op.create_index("ix_quiz_details_quiz_id", "quiz_details", ["quiz_id"])

    op.create_table(
        "tutor_sessions",
        sa.Column("session_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user_details.user_id"), nullable=False),
        sa.Column("note_id", sa.Integer(), sa.ForeignKey("notes.note_id"), nullable=True),
        sa.Column("messages", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime()),
    )
    op.create_index("ix_tutor_sessions_session_id", "tutor_sessions", ["session_id"])

    op.create_table(
        "uploaded_materials",
        sa.Column("material_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user_details.user_id"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(50), nullable=False),
        sa.Column("total_chunks", sa.Integer(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime()),
    )
    op.create_index("ix_uploaded_materials_material_id", "uploaded_materials", ["material_id"])


def downgrade() -> None:
    for table in ["uploaded_materials", "tutor_sessions", "quiz_details", "notes", "user_details"]:
        op.drop_table(table)
