"""initial schema

Revision ID: df5300413f39
Revises:
Create Date: 2026-05-23 15:40:42.771888+00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "df5300413f39"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)

    op.create_table(
        "database_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("serial_number", sa.Integer(), nullable=True),
        sa.Column("database_name", sa.String(length=255), nullable=False),
        sa.Column("cics_transactions", sa.Integer(), nullable=True),
        sa.Column("prod_mirror", sa.String(length=32), nullable=True),
        sa.Column("release", sa.String(length=64), nullable=True),
        sa.Column("lifecycle", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("assignee", sa.String(length=255), nullable=True),
        sa.Column("team", sa.String(length=255), nullable=True),
        sa.Column("project", sa.String(length=255), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("can_be_released", sa.String(length=8), nullable=True),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_database_records_database_name"), "database_records", ["database_name"], unique=False)
    op.create_index(op.f("ix_database_records_end_date"), "database_records", ["end_date"], unique=False)
    op.create_index(op.f("ix_database_records_id"), "database_records", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_database_records_id"), table_name="database_records")
    op.drop_index(op.f("ix_database_records_end_date"), table_name="database_records")
    op.drop_index(op.f("ix_database_records_database_name"), table_name="database_records")
    op.drop_table("database_records")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
