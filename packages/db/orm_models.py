"""SQLAlchemy mappings for PostgreSQL persistence.

Domain dataclasses remain in :mod:`packages.domain`.  These mapped classes are
the persistence representation and preserve the database-level invariants that
cannot safely be delegated to an LLM or caller.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from packages.domain.models import (
    DuplicateCandidateStatus,
    TransactionDirection,
    TransactionStatus,
)


def _enum_values(enum_class: type[Any]) -> list[str]:
    return [member.value for member in enum_class]


class Base(DeclarativeBase):
    """Base class shared by all PostgreSQL ORM mappings."""


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    external_auth_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class StatementSourceModel(Base):
    __tablename__ = "statement_sources"
    __table_args__ = (
        UniqueConstraint("id", "user_id"),
        CheckConstraint("char_length(content_sha256) = 64", name="valid_sha256"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(100))
    original_filename: Mapped[str] = mapped_column(String(512))
    storage_key: Mapped[str] = mapped_column(String(1024), unique=True)
    content_sha256: Mapped[str] = mapped_column(String(64))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ += (
        ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
    )


class ParsedStatementRowModel(Base):
    __tablename__ = "parsed_statement_rows"
    __table_args__ = (
        UniqueConstraint("statement_source_id", "row_number"),
        UniqueConstraint("id", "user_id", "statement_source_id"),
        CheckConstraint("row_number >= 1", name="positive_row_number"),
        ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["statement_source_id", "user_id"],
            ["statement_sources.id", "statement_sources.user_id"],
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False, index=True
    )
    statement_source_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False, index=True
    )
    row_number: Mapped[int] = mapped_column(nullable=False)
    raw_values: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class TransactionModel(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("id", "user_id"),
        UniqueConstraint("parsed_statement_row_id"),
        CheckConstraint("amount_paise > 0", name="positive_amount_paise"),
        CheckConstraint("char_length(currency) = 3", name="three_letter_currency"),
        ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["parsed_statement_row_id", "user_id", "statement_source_id"],
            [
                "parsed_statement_rows.id",
                "parsed_statement_rows.user_id",
                "parsed_statement_rows.statement_source_id",
            ],
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False, index=True
    )
    statement_source_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False, index=True
    )
    parsed_statement_row_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text)
    amount_paise: Mapped[int] = mapped_column(nullable=False)
    direction: Mapped[TransactionDirection] = mapped_column(
        Enum(
            TransactionDirection,
            name="transaction_direction",
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default="INR"
    )
    status: Mapped[TransactionStatus] = mapped_column(
        Enum(
            TransactionStatus,
            name="transaction_status",
            values_callable=_enum_values,
        ),
        nullable=False,
        server_default=TransactionStatus.POSTED.value,
    )
    external_reference: Mapped[str | None] = mapped_column(String(255), index=True)


class DuplicateCandidateModel(Base):
    __tablename__ = "duplicate_candidates"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "transaction_id", "possible_duplicate_transaction_id"
        ),
        CheckConstraint(
            "transaction_id <> possible_duplicate_transaction_id",
            name="different_transactions",
        ),
        CheckConstraint(
            "transaction_id < possible_duplicate_transaction_id",
            name="canonical_transaction_pair",
        ),
        ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["transaction_id", "user_id"],
            ["transactions.id", "transactions.user_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["possible_duplicate_transaction_id", "user_id"],
            ["transactions.id", "transactions.user_id"],
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False, index=True
    )
    transaction_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    possible_duplicate_transaction_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    confidence_basis: Mapped[str] = mapped_column(Text)
    status: Mapped[DuplicateCandidateStatus] = mapped_column(
        Enum(
            DuplicateCandidateStatus,
            name="duplicate_candidate_status",
            values_callable=_enum_values,
        ),
        nullable=False,
        server_default=DuplicateCandidateStatus.PENDING_REVIEW.value,
    )
