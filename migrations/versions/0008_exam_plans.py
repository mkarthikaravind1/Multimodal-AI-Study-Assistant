"""Exam planner

Revision ID: 0008_exam_plans
Revises: 0007_user_language
Create Date: 2026-11-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_exam_plans"
down_revision = "0007_user_language"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exam_plans",
        sa.Column("plan_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user_details.user_id"), nullable=False),
        sa.Column("exam_name", sa.String(200), nullable=False),
        sa.Column("exam_date", sa.Date(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("minutes_per_day", sa.Integer(), nullable=False),
        sa.Column("rest_days", sa.JSON(), nullable=False),
        sa.Column("topics", sa.JSON(), nullable=False),
        sa.Column("days", sa.JSON(), nullable=False),
        sa.Column("syllabus_filename", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_exam_plans_plan_id", "exam_plans", ["plan_id"])
    op.create_index("ix_exam_plans_user_id", "exam_plans", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_exam_plans_user_id", table_name="exam_plans")
    op.drop_index("ix_exam_plans_plan_id", table_name="exam_plans")
    op.drop_table("exam_plans")
