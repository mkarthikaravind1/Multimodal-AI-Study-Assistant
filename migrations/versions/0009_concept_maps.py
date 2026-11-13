"""Concept maps / mind maps

Revision ID: 0009_concept_maps
Revises: 0008_exam_plans
Create Date: 2026-11-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_concept_maps"
down_revision = "0008_exam_plans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "concept_maps",
        sa.Column("map_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user_details.user_id"), nullable=False),
        sa.Column("source_type", sa.String(10), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("graph", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_concept_maps_map_id", "concept_maps", ["map_id"])
    op.create_index("ix_concept_maps_user_id", "concept_maps", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_concept_maps_user_id", table_name="concept_maps")
    op.drop_index("ix_concept_maps_map_id", table_name="concept_maps")
    op.drop_table("concept_maps")
