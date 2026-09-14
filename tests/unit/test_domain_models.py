from dataclasses import FrozenInstanceError
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from packages.domain import (
    DuplicateCandidate,
    ParsedStatementRow,
    StatementSource,
    Transaction,
    TransactionDirection,
    User,
)


def test_user_has_no_credentials_and_requires_a_valid_identity() -> None:
    user = User(
        email="ada@example.com",
        display_name="Ada Lovelace",
        external_auth_id="identity-provider|ada-123",
        created_at=datetime.now(timezone.utc),
    )

    assert user.is_active is True
    assert user.external_auth_id == "identity-provider|ada-123"

    with pytest.raises(ValueError, match="valid email"):
        User(
            email="not-an-email",
            display_name="Ada Lovelace",
            created_at=datetime.now(timezone.utc),
        )


def test_statement_source_is_immutable_and_requires_utc_upload_time() -> None:
    source = StatementSource(
        user_id=uuid4(),
        provider="hdfc",
        original_filename="january.csv",
        storage_key="uploads/a1b2.csv",
        content_sha256="a" * 64,
        uploaded_at=datetime.now(timezone.utc),
    )

    with pytest.raises(FrozenInstanceError):
        source.provider = "icici"  # type: ignore[misc]

    with pytest.raises(ValueError, match="timezone-aware"):
        StatementSource(
            user_id=uuid4(),
            provider="hdfc",
            original_filename="january.csv",
            storage_key="uploads/a1b2.csv",
            content_sha256="a" * 64,
            uploaded_at=datetime.now(),
        )


def test_normalized_transaction_uses_integer_paise_and_keeps_row_provenance() -> None:
    user_id = uuid4()
    source_id = uuid4()
    row = ParsedStatementRow(
        user_id=user_id,
        statement_source_id=source_id,
        row_number=4,
        raw_values={"Narration": "Coffee shop", "Amount": "125.50"},
    )

    transaction = Transaction(
        user_id=user_id,
        statement_source_id=source_id,
        parsed_statement_row_id=row.id,
        occurred_on=date(2026, 9, 1),
        description="Coffee shop",
        amount_paise=12_550,
        direction=TransactionDirection.DEBIT,
    )

    assert transaction.amount_paise == 12_550
    assert transaction.parsed_statement_row_id == row.id
    assert transaction.currency == "INR"
    with pytest.raises(TypeError):
        row.raw_values["Amount"] = "999.00"  # type: ignore[index]

    with pytest.raises(ValueError, match="greater than zero"):
        Transaction(
            user_id=user_id,
            statement_source_id=source_id,
            parsed_statement_row_id=row.id,
            occurred_on=date(2026, 9, 1),
            description="Refund",
            amount_paise=0,
            direction=TransactionDirection.CREDIT,
        )


def test_duplicate_candidate_requires_two_distinct_transactions() -> None:
    transaction_id = uuid4()

    with pytest.raises(ValueError, match="cannot be a duplicate"):
        DuplicateCandidate(
            user_id=uuid4(),
            transaction_id=transaction_id,
            possible_duplicate_transaction_id=transaction_id,
            detected_at=datetime.now(timezone.utc),
            confidence_basis="same date and amount",
        )
