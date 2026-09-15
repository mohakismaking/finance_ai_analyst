from packages.db import (
    Base,
    DuplicateCandidateModel,
    ParsedStatementRowModel,
    StatementSourceModel,
    TransactionModel,
    UserModel,
)


def test_postgresql_orm_registers_all_finance_tables() -> None:
    assert set(Base.metadata.tables) == {
        "duplicate_candidates",
        "parsed_statement_rows",
        "statement_sources",
        "transactions",
        "users",
    }
    assert UserModel.__tablename__ == "users"
    assert StatementSourceModel.__tablename__ == "statement_sources"
    assert ParsedStatementRowModel.__tablename__ == "parsed_statement_rows"
    assert TransactionModel.__tablename__ == "transactions"
    assert DuplicateCandidateModel.__tablename__ == "duplicate_candidates"


def test_transaction_schema_enforces_paise_and_raw_row_provenance() -> None:
    constraints = {
        constraint.name for constraint in TransactionModel.__table__.constraints
    }
    foreign_key_columns = {
        column.name
        for constraint in TransactionModel.__table__.foreign_key_constraints
        for column in constraint.columns
    }

    assert "positive_amount_paise" in constraints
    assert "parsed_statement_row_id" in foreign_key_columns


def test_duplicate_schema_supports_many_pairwise_links_without_self_links() -> None:
    constraints = {
        constraint.name for constraint in DuplicateCandidateModel.__table__.constraints
    }

    assert "different_transactions" in constraints
    assert "canonical_transaction_pair" in constraints
