"""Baseline schema: users, products, customers, sales.

This captures the schema as it existed before multi-tenancy, which until now
was created at startup by ``SQLModel.metadata.create_all`` rather than by
Alembic. It is written to be **idempotent**: on a database that already has
these tables (an existing deployment) every step is skipped, so
``alembic upgrade head`` is safe to run against both existing and fresh
databases without needing a manual ``alembic stamp``.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-09-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _existing_tables()

    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("uid", sa.UUID(), nullable=False),
            sa.Column("username", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("first_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("last_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column(
                "password_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False
            ),
            sa.Column("is_verified", sa.Boolean(), nullable=False),
            sa.Column("role", sa.VARCHAR(), server_default="user", nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
            sa.Column("updated_at", sa.TIMESTAMP(), nullable=True),
            sa.Column("verification_email_sent_at", sa.TIMESTAMP(), nullable=True),
            sa.PrimaryKeyConstraint("uid"),
        )

    if "products" not in tables:
        op.create_table(
            "products",
            sa.Column("uid", sa.UUID(), nullable=False),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("category", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("unit_price", sa.NUMERIC(precision=12, scale=2), nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
            sa.Column("updated_at", sa.TIMESTAMP(), nullable=True),
            sa.PrimaryKeyConstraint("uid"),
        )

    if "customers" not in tables:
        op.create_table(
            "customers",
            sa.Column("uid", sa.UUID(), nullable=False),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("region", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
            sa.PrimaryKeyConstraint("uid"),
        )

    if "sales" not in tables:
        op.create_table(
            "sales",
            sa.Column("uid", sa.UUID(), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column(
                "total_amount", sa.NUMERIC(precision=12, scale=2), nullable=False
            ),
            sa.Column("product_uid", sa.UUID(), nullable=True),
            sa.Column("customer_uid", sa.UUID(), nullable=True),
            sa.Column("user_uid", sa.UUID(), nullable=True),
            sa.Column("sold_at", sa.TIMESTAMP(), nullable=True),
            sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
            sa.ForeignKeyConstraint(["customer_uid"], ["customers.uid"]),
            sa.ForeignKeyConstraint(["product_uid"], ["products.uid"]),
            sa.ForeignKeyConstraint(["user_uid"], ["users.uid"]),
            sa.PrimaryKeyConstraint("uid"),
        )


def downgrade() -> None:
    # Only drop what this migration is responsible for creating.
    for table in ("sales", "customers", "products", "users"):
        op.drop_table(table)
