"""Reply language preference

Revision ID: 0007_user_language
Revises: 0006_solution_checks
Create Date: 2026-11-13

Existing users get "en", which is how the app behaved before.
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_user_language"
down_revision = "0006_solution_checks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("user_details") as batch:
        batch.add_column(
            sa.Column("preferred_language", sa.String(12), nullable=False, server_default="en")
        )


def downgrade() -> None:
    with op.batch_alter_table("user_details") as batch:
        batch.drop_column("preferred_language")
