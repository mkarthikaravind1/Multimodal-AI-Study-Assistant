"""Teacher role, classes, class members, assignments

Revision ID: 0011_teacher_classes
Revises: 0010_tutor_session_history
Create Date: 2026-11-14

- user_details.role gains "teacher" (MySQL ENUM is altered in place)
- classes / class_members / class_assignments tables
- quiz_details.assignment_id links a student's attempt to its assignment
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_teacher_classes"
down_revision = "0010_tutor_session_history"
branch_labels = None
depends_on = None

OLD_ROLES = sa.Enum("student", "admin", name="roleenum")
NEW_ROLES = sa.Enum("student", "admin", "teacher", name="roleenum")


def upgrade() -> None:
    with op.batch_alter_table("user_details") as batch:
        batch.alter_column("role", existing_type=OLD_ROLES, type_=NEW_ROLES, existing_nullable=False)

    op.create_table(
        "classes",
        sa.Column("class_id", sa.Integer(), primary_key=True),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("user_details.user_id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("subject", sa.String(120), nullable=True),
        sa.Column("join_code", sa.String(6), nullable=False),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_index("ix_classes_class_id", "classes", ["class_id"])
    op.create_index("ix_classes_teacher_id", "classes", ["teacher_id"])
    op.create_index("ix_classes_join_code", "classes", ["join_code"], unique=True)

    op.create_table(
        "class_members",
        sa.Column("member_id", sa.Integer(), primary_key=True),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.class_id"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("user_details.user_id"), nullable=False),
        sa.Column("joined_at", sa.DateTime()),
        sa.UniqueConstraint("class_id", "student_id", name="uq_class_member"),
    )
    op.create_index("ix_class_members_member_id", "class_members", ["member_id"])
    op.create_index("ix_class_members_class_id", "class_members", ["class_id"])
    op.create_index("ix_class_members_student_id", "class_members", ["student_id"])

    op.create_table(
        "class_assignments",
        sa.Column("assignment_id", sa.Integer(), primary_key=True),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.class_id"), nullable=False),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("user_details.user_id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("topic", sa.String(200), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("questions", sa.JSON(), nullable=False),
        sa.Column("question_types", sa.JSON(), nullable=False),
        sa.Column("difficulty", sa.String(10), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_index("ix_class_assignments_assignment_id", "class_assignments", ["assignment_id"])
    op.create_index("ix_class_assignments_class_id", "class_assignments", ["class_id"])

    with op.batch_alter_table("quiz_details") as batch:
        batch.add_column(sa.Column("assignment_id", sa.Integer(), nullable=True))
        batch.create_index("ix_quiz_details_assignment_id", ["assignment_id"])


def downgrade() -> None:
    with op.batch_alter_table("quiz_details") as batch:
        batch.drop_index("ix_quiz_details_assignment_id")
        batch.drop_column("assignment_id")

    op.drop_index("ix_class_assignments_class_id", table_name="class_assignments")
    op.drop_index("ix_class_assignments_assignment_id", table_name="class_assignments")
    op.drop_table("class_assignments")
    op.drop_index("ix_class_members_student_id", table_name="class_members")
    op.drop_index("ix_class_members_class_id", table_name="class_members")
    op.drop_index("ix_class_members_member_id", table_name="class_members")
    op.drop_table("class_members")
    op.drop_index("ix_classes_join_code", table_name="classes")
    op.drop_index("ix_classes_teacher_id", table_name="classes")
    op.drop_index("ix_classes_class_id", table_name="classes")
    op.drop_table("classes")

    # Teachers become students before "teacher" is removed from the ENUM
    op.execute("UPDATE user_details SET role = 'student' WHERE role = 'teacher'")
    with op.batch_alter_table("user_details") as batch:
        batch.alter_column("role", existing_type=NEW_ROLES, type_=OLD_ROLES, existing_nullable=False)
