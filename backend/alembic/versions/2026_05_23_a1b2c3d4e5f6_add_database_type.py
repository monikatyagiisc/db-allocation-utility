"""add database_type column

Revision ID: a1b2c3d4e5f6
Revises: df5300413f39
Create Date: 2026-05-23 22:00:00.000000+00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "df5300413f39"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("database_records", sa.Column("database_type", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_database_records_database_type"), "database_records", ["database_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_database_records_database_type"), table_name="database_records")
    op.drop_column("database_records", "database_type")
