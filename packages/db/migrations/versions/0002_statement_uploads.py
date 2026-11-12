"""Add financial-period assignment and upload status to statement sources.

Revision ID: 0002_statement_uploads
Revises: 0001_initial_schema
Create Date: 2026-09-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_statement_uploads"
down_revision: Union[str, Sequence[str], None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

statement_processing_status = postgresql.ENUM(
    "pending", name="statement_processing_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    statement_processing_status.create(bind, checkfirst=True)

    op.create_table(
        "financial_periods",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.CheckConstraint("ends_on >= starts_on", name="valid_financial_period_range"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "user_id"),
        sa.UniqueConstraint("user_id", "starts_on", "ends_on"),
    )
    op.create_index("ix_financial_periods_user_id", "financial_periods", ["user_id"])

    op.add_column(
        "statement_sources",
        sa.Column("financial_period_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "statement_sources",
        sa.Column("content_type", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "statement_sources",
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "statement_sources",
        sa.Column(
            "processing_status",
            statement_processing_status,
            server_default="pending",
            nullable=True,
        ),
    )
    op.create_index(
        "ix_statement_sources_financial_period_id",
        "statement_sources",
        ["financial_period_id"],
    )
    op.create_foreign_key(
        "statement_sources_financial_period_user_fk",
        "statement_sources",
        "financial_periods",
        ["financial_period_id", "user_id"],
        ["id", "user_id"],
        ondelete="RESTRICT",
    )

    op.execute("UPDATE statement_sources SET content_type = 'text/csv'")
    op.execute("UPDATE statement_sources SET file_size_bytes = 1")
    op.execute("UPDATE statement_sources SET processing_status = 'pending'")
    op.alter_column("statement_sources", "content_type", nullable=False)
    op.alter_column("statement_sources", "file_size_bytes", nullable=False)
    op.alter_column("statement_sources", "processing_status", nullable=False)


def downgrade() -> None:
    op.drop_constraint(
        "statement_sources_financial_period_user_fk",
        "statement_sources",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_statement_sources_financial_period_id", table_name="statement_sources"
    )
    op.drop_column("statement_sources", "processing_status")
    op.drop_column("statement_sources", "file_size_bytes")
    op.drop_column("statement_sources", "content_type")
    op.drop_column("statement_sources", "financial_period_id")
    op.drop_index("ix_financial_periods_user_id", table_name="financial_periods")
    op.drop_table("financial_periods")
    statement_processing_status.drop(op.get_bind(), checkfirst=True)
