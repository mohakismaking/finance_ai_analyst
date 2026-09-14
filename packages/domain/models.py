"""Framework-independent models for finance data and its provenance.

Amounts are always stored as integer paise.  These immutable models deliberately
avoid database or LLM dependencies so every application boundary shares the same
financial invariants.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping
from uuid import UUID, uuid4


class TransactionDirection(StrEnum):
    """The effect of a transaction on the account balance."""

    DEBIT = "debit"
    CREDIT = "credit"


class TransactionStatus(StrEnum):
    """Lifecycle state of a normalized transaction."""

    POSTED = "posted"
    PENDING = "pending"
    REVERSED = "reversed"


class DuplicateCandidateStatus(StrEnum):
    """Human review state for a possible duplicate relationship."""

    PENDING_REVIEW = "pending_review"
    CONFIRMED_DUPLICATE = "confirmed_duplicate"
    NOT_A_DUPLICATE = "not_a_duplicate"


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    if value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError(f"{field_name} must use UTC")


@dataclass(frozen=True, slots=True)
class User:
    """An application user; authentication credentials are never stored here."""

    email: str
    display_name: str
    created_at: datetime
    id: UUID = field(default_factory=uuid4)
    external_auth_id: str | None = None
    is_active: bool = True

    def __post_init__(self) -> None:
        _require_non_empty(self.email, "email")
        if "@" not in self.email or self.email.startswith("@"):
            raise ValueError("email must be a valid email address")
        _require_non_empty(self.display_name, "display_name")
        if self.external_auth_id is not None:
            _require_non_empty(self.external_auth_id, "external_auth_id")
        _require_utc(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class StatementSource:
    """An immutable uploaded statement file belonging to one user."""

    user_id: UUID
    provider: str
    original_filename: str
    storage_key: str
    content_sha256: str
    uploaded_at: datetime
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        for field_name in (
            "provider",
            "original_filename",
            "storage_key",
            "content_sha256",
        ):
            _require_non_empty(getattr(self, field_name), field_name)
        _require_utc(self.uploaded_at, "uploaded_at")


@dataclass(frozen=True, slots=True)
class ParsedStatementRow:
    """Provider-specific row retained before normalization."""

    user_id: UUID
    statement_source_id: UUID
    row_number: int
    raw_values: Mapping[str, str]
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.row_number < 1:
            raise ValueError("row_number must be at least 1")
        if not self.raw_values:
            raise ValueError("raw_values must not be empty")
        object.__setattr__(self, "raw_values", MappingProxyType(dict(self.raw_values)))


@dataclass(frozen=True, slots=True)
class Transaction:
    """A normalized transaction traceable to its original statement row."""

    user_id: UUID
    statement_source_id: UUID
    parsed_statement_row_id: UUID
    occurred_on: date
    description: str
    amount_paise: int
    direction: TransactionDirection
    currency: str = "INR"
    status: TransactionStatus = TransactionStatus.POSTED
    external_reference: str | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        _require_non_empty(self.description, "description")
        if self.amount_paise <= 0:
            raise ValueError("amount_paise must be greater than zero")
        if len(self.currency) != 3 or not self.currency.isalpha():
            raise ValueError("currency must be a three-letter ISO currency code")
        object.__setattr__(self, "currency", self.currency.upper())


@dataclass(frozen=True, slots=True)
class DuplicateCandidate:
    """A reviewable possible-duplicate link; it never deletes source records."""

    user_id: UUID
    transaction_id: UUID
    possible_duplicate_transaction_id: UUID
    detected_at: datetime
    confidence_basis: str
    status: DuplicateCandidateStatus = DuplicateCandidateStatus.PENDING_REVIEW
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.transaction_id == self.possible_duplicate_transaction_id:
            raise ValueError("a transaction cannot be a duplicate candidate of itself")
        _require_non_empty(self.confidence_basis, "confidence_basis")
        _require_utc(self.detected_at, "detected_at")
