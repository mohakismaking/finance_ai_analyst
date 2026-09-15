"""Create the initial personal-finance schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


transaction_direction = postgresql.ENUM(
    "debit", "credit", name="transaction_direction", create_type=False
)
transaction_status = postgresql.ENUM(
    "posted", "pending", "reversed", name="transaction_status", create_type=False
)
duplicate_candidate_status = postgresql.ENUM(
    "pending_review",
    "confirmed_duplicate",
    "not_a_duplicate",
    name="duplicate_candidate_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    transaction_direction.create(bind, checkfirst=True)
    transaction_status.create(bind, checkfirst=True)
    duplicate_candidate_status.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("external_auth_id", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("external_auth_id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    op.create_index(
        "ix_users_external_auth_id", "users", ["external_auth_id"], unique=False
    )

    op.create_table(
        "statement_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("char_length(content_sha256) = 64", name="valid_sha256"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "user_id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_statement_sources_user_id", "statement_sources", ["user_id"])

    op.create_table(
        "parsed_statement_rows",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("statement_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column(
            "raw_values", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.CheckConstraint("row_number >= 1", name="positive_row_number"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["statement_source_id", "user_id"],
            ["statement_sources.id", "statement_sources.user_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "user_id", "statement_source_id"),
        sa.UniqueConstraint("statement_source_id", "row_number"),
    )
    op.create_index(
        "ix_parsed_statement_rows_user_id", "parsed_statement_rows", ["user_id"]
    )
    op.create_index(
        "ix_parsed_statement_rows_statement_source_id",
        "parsed_statement_rows",
        ["statement_source_id"],
    )

    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("statement_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "parsed_statement_row_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("direction", transaction_direction, nullable=False),
        sa.Column(
            "currency", sa.String(length=3), server_default="INR", nullable=False
        ),
        sa.Column(
            "status", transaction_status, server_default="posted", nullable=False
        ),
        sa.Column("external_reference", sa.String(length=255), nullable=True),
        sa.CheckConstraint("amount_paise > 0", name="positive_amount_paise"),
        sa.CheckConstraint("char_length(currency) = 3", name="three_letter_currency"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["parsed_statement_row_id", "user_id", "statement_source_id"],
            [
                "parsed_statement_rows.id",
                "parsed_statement_rows.user_id",
                "parsed_statement_rows.statement_source_id",
            ],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "user_id"),
        sa.UniqueConstraint("parsed_statement_row_id"),
    )
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"])
    op.create_index("ix_transactions_occurred_on", "transactions", ["occurred_on"])
    op.create_index(
        "ix_transactions_external_reference", "transactions", ["external_reference"]
    )

    op.create_table(
        "duplicate_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "possible_duplicate_transaction_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence_basis", sa.Text(), nullable=False),
        sa.Column(
            "status",
            duplicate_candidate_status,
            server_default="pending_review",
            nullable=False,
        ),
        sa.CheckConstraint(
            "transaction_id <> possible_duplicate_transaction_id",
            name="different_transactions",
        ),
        sa.CheckConstraint(
            "transaction_id < possible_duplicate_transaction_id",
            name="canonical_transaction_pair",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["transaction_id", "user_id"],
            ["transactions.id", "transactions.user_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["possible_duplicate_transaction_id", "user_id"],
            ["transactions.id", "transactions.user_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "transaction_id", "possible_duplicate_transaction_id"
        ),
    )
    op.create_index(
        "ix_duplicate_candidates_user_id", "duplicate_candidates", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_duplicate_candidates_user_id", table_name="duplicate_candidates")
    op.drop_table("duplicate_candidates")
    op.drop_index("ix_transactions_external_reference", table_name="transactions")
    op.drop_index("ix_transactions_occurred_on", table_name="transactions")
    op.drop_index("ix_transactions_user_id", table_name="transactions")
    op.drop_table("transactions")
    op.drop_index(
        "ix_parsed_statement_rows_statement_source_id",
        table_name="parsed_statement_rows",
    )
    op.drop_index(
        "ix_parsed_statement_rows_user_id", table_name="parsed_statement_rows"
    )
    op.drop_table("parsed_statement_rows")
    op.drop_index("ix_statement_sources_user_id", table_name="statement_sources")
    op.drop_table("statement_sources")
    op.drop_index("ix_users_external_auth_id", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    duplicate_candidate_status.drop(bind, checkfirst=True)
    transaction_status.drop(bind, checkfirst=True)
    transaction_direction.drop(bind, checkfirst=True)
