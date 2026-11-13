"""Tutor chat history: session titles, last-activity time and document focus

Revision ID: 0010_tutor_session_history
Revises: 0009_concept_maps
Create Date: 2026-11-13

Existing sessions get their title from their first question and updated_at
from started_at, so the history sidebar shows them sensibly straight away.
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0010_tutor_session_history"
down_revision = "0009_concept_maps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tutor_sessions") as batch:
        batch.add_column(sa.Column("title", sa.String(200), nullable=True))
        batch.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("material_id", sa.Integer(), nullable=True))

    # Back-fill titles for existing chats (the same rule new chats use)
    from Services.chat_titles import session_title

    conn = op.get_bind()
    sessions = sa.table(
        "tutor_sessions",
        sa.column("session_id", sa.Integer),
        sa.column("messages", sa.JSON),
        sa.column("started_at", sa.DateTime),
        sa.column("title", sa.String),
        sa.column("updated_at", sa.DateTime),
    )
    for row in conn.execute(sa.select(sessions.c.session_id, sessions.c.messages, sessions.c.started_at)).fetchall():
        messages = row.messages
        if isinstance(messages, str):           # some drivers return JSON as text
            try:
                messages = json.loads(messages)
            except ValueError:
                messages = []
        conn.execute(
            sessions.update()
            .where(sessions.c.session_id == row.session_id)
            .values(title=session_title(messages or []), updated_at=row.started_at)
        )


def downgrade() -> None:
    with op.batch_alter_table("tutor_sessions") as batch:
        batch.drop_column("material_id")
        batch.drop_column("updated_at")
        batch.drop_column("title")
