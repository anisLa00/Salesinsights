"""Multi-tenancy: businesses, members, invitations, and business_uid backfill.

Safe for databases that already contain data. The `business_uid` columns are
added as nullable, existing products/customers/sales are moved into a default
business owned by the existing demo user, and only then are the columns made
NOT NULL. No table is dropped and no row is deleted.

Revision ID: 0002_multi_tenancy
Revises: 0001_baseline
Create Date: 2026-09-02
"""

import uuid
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0002_multi_tenancy"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_BUSINESS_NAME = "Sales Insight Demo Business"
DEFAULT_OWNER_EMAIL = "demo@example.com"
SCOPED_TABLES = ("products", "customers", "sales")


def _inspector():
    return sa.inspect(op.get_bind())


def _has_column(table: str, column: str) -> bool:
    return column in {c["name"] for c in _inspector().get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(_inspector().get_table_names())

    # ------------------------------------------------------------------
    # 1. New tenancy tables
    # ------------------------------------------------------------------
    if "businesses" not in tables:
        op.create_table(
            "businesses",
            sa.Column("uid", sa.UUID(), nullable=False),
            sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("owner_uid", sa.UUID(), nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
            sa.Column("updated_at", sa.TIMESTAMP(), nullable=True),
            sa.ForeignKeyConstraint(["owner_uid"], ["users.uid"]),
            sa.PrimaryKeyConstraint("uid"),
        )
        op.create_index("ix_businesses_owner_uid", "businesses", ["owner_uid"])

    if "business_members" not in tables:
        op.create_table(
            "business_members",
            sa.Column("uid", sa.UUID(), nullable=False),
            sa.Column("business_uid", sa.UUID(), nullable=False),
            sa.Column("user_uid", sa.UUID(), nullable=False),
            sa.Column("role", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("joined_at", sa.TIMESTAMP(), nullable=True),
            sa.ForeignKeyConstraint(["business_uid"], ["businesses.uid"]),
            sa.ForeignKeyConstraint(["user_uid"], ["users.uid"]),
            sa.PrimaryKeyConstraint("uid"),
        )
        op.create_index(
            "ix_business_members_business_uid", "business_members", ["business_uid"]
        )
        op.create_index(
            "ix_business_members_user_uid", "business_members", ["user_uid"]
        )

    if "business_invitations" not in tables:
        op.create_table(
            "business_invitations",
            sa.Column("uid", sa.UUID(), nullable=False),
            sa.Column("business_uid", sa.UUID(), nullable=False),
            sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("role", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("invited_by_uid", sa.UUID(), nullable=True),
            sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
            sa.Column("expires_at", sa.TIMESTAMP(), nullable=False),
            sa.Column("accepted_at", sa.TIMESTAMP(), nullable=True),
            sa.ForeignKeyConstraint(["business_uid"], ["businesses.uid"]),
            sa.ForeignKeyConstraint(["invited_by_uid"], ["users.uid"]),
            sa.PrimaryKeyConstraint("uid"),
        )
        op.create_index(
            "ix_business_invitations_business_uid",
            "business_invitations",
            ["business_uid"],
        )
        op.create_index(
            "ix_business_invitations_email", "business_invitations", ["email"]
        )
        op.create_index(
            "ix_business_invitations_status", "business_invitations", ["status"]
        )

    # ------------------------------------------------------------------
    # 2. Add business_uid as NULLABLE so existing rows survive
    # ------------------------------------------------------------------
    for table in SCOPED_TABLES:
        if not _has_column(table, "business_uid"):
            op.add_column(table, sa.Column("business_uid", sa.UUID(), nullable=True))

    # ------------------------------------------------------------------
    # 3. Backfill existing rows into a default business
    # ------------------------------------------------------------------
    rows_needing_backfill = sum(
        bind.execute(
            sa.text(f"SELECT count(*) FROM {table} WHERE business_uid IS NULL")
        ).scalar_one()
        for table in SCOPED_TABLES
    )

    if rows_needing_backfill:
        owner_uid = bind.execute(
            sa.text("SELECT uid FROM users WHERE email = :email LIMIT 1"),
            {"email": DEFAULT_OWNER_EMAIL},
        ).scalar_one_or_none()

        if owner_uid is None:
            # Fall back to the oldest account so we never invent a user.
            owner_uid = bind.execute(
                sa.text("SELECT uid FROM users ORDER BY created_at NULLS LAST LIMIT 1")
            ).scalar_one_or_none()

        if owner_uid is None:
            raise RuntimeError(
                "Cannot backfill business_uid: there are existing "
                f"products/customers/sales ({rows_needing_backfill} rows) but no "
                "users to own them. Create a user, then re-run this migration."
            )

        # Reuse the default business if a previous partial run created it.
        business_uid = bind.execute(
            sa.text("SELECT uid FROM businesses WHERE name = :name LIMIT 1"),
            {"name": DEFAULT_BUSINESS_NAME},
        ).scalar_one_or_none()

        if business_uid is None:
            business_uid = uuid.uuid4()
            now = datetime.now()
            bind.execute(
                sa.text(
                    "INSERT INTO businesses (uid, name, owner_uid, created_at, updated_at) "
                    "VALUES (:uid, :name, :owner_uid, :now, :now)"
                ),
                {
                    "uid": business_uid,
                    "name": DEFAULT_BUSINESS_NAME,
                    "owner_uid": owner_uid,
                    "now": now,
                },
            )

        # Ensure the owner has an owner-role membership.
        has_membership = bind.execute(
            sa.text(
                "SELECT 1 FROM business_members "
                "WHERE business_uid = :b AND user_uid = :u LIMIT 1"
            ),
            {"b": business_uid, "u": owner_uid},
        ).scalar_one_or_none()

        if not has_membership:
            bind.execute(
                sa.text(
                    "INSERT INTO business_members "
                    "(uid, business_uid, user_uid, role, is_active, joined_at) "
                    "VALUES (:uid, :b, :u, 'owner', true, :now)"
                ),
                {
                    "uid": uuid.uuid4(),
                    "b": business_uid,
                    "u": owner_uid,
                    "now": datetime.now(),
                },
            )

        for table in SCOPED_TABLES:
            bind.execute(
                sa.text(
                    f"UPDATE {table} SET business_uid = :b WHERE business_uid IS NULL"
                ),
                {"b": business_uid},
            )

    # ------------------------------------------------------------------
    # 4. Lock the tenant boundary in: NOT NULL + FK + index
    # ------------------------------------------------------------------
    def _has_business_fk(table: str) -> bool:
        """True if *any* FK already maps business_uid -> businesses.

        Matched on columns rather than constraint name: if the table was first
        created by ``create_all`` the constraint carries PostgreSQL's
        auto-generated name, and matching on our name alone would add a
        duplicate constraint.
        """
        return any(
            fk.get("referred_table") == "businesses"
            and fk.get("constrained_columns") == ["business_uid"]
            for fk in _inspector().get_foreign_keys(table)
        )

    existing_indexes = {
        table: {ix["name"] for ix in _inspector().get_indexes(table)}
        for table in SCOPED_TABLES
    }

    for table in SCOPED_TABLES:
        op.alter_column(table, "business_uid", existing_type=sa.UUID(), nullable=False)

        if not _has_business_fk(table):
            op.create_foreign_key(
                f"fk_{table}_business_uid_businesses",
                table,
                "businesses",
                ["business_uid"],
                ["uid"],
            )

        ix_name = f"ix_{table}_business_uid"
        if ix_name not in existing_indexes[table]:
            op.create_index(ix_name, table, ["business_uid"])


def downgrade() -> None:
    for table in SCOPED_TABLES:
        op.drop_index(f"ix_{table}_business_uid", table_name=table)
        op.drop_constraint(
            f"fk_{table}_business_uid_businesses", table, type_="foreignkey"
        )
        op.drop_column(table, "business_uid")

    op.drop_table("business_invitations")
    op.drop_table("business_members")
    op.drop_table("businesses")
