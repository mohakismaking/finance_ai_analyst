"""Persistence operations needed by the statement-upload API."""

from __future__ import annotations

from datetime import datetime
import os
from uuid import UUID

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from .orm_models import FinancialPeriodModel, StatementSourceModel


class SqlAlchemyStatementRepository:
    """Small repository for statement creation, scoped to one user at a time."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def financial_period_exists(
        self, *, user_id: UUID, financial_period_id: UUID
    ) -> bool:
        with self._session_factory() as session:
            return (
                session.scalar(
                    select(FinancialPeriodModel.id).where(
                        FinancialPeriodModel.id == financial_period_id,
                        FinancialPeriodModel.user_id == user_id,
                    )
                )
                is not None
            )

    def create_statement(
        self,
        *,
        statement_id: UUID,
        user_id: UUID,
        financial_period_id: UUID,
        provider: str,
        original_filename: str,
        storage_key: str,
        content_sha256: str,
        uploaded_at: datetime,
        content_type: str,
        file_size_bytes: int,
    ) -> StatementSourceModel:
        statement = StatementSourceModel(
            id=statement_id,
            user_id=user_id,
            financial_period_id=financial_period_id,
            provider=provider,
            original_filename=original_filename,
            storage_key=storage_key,
            content_sha256=content_sha256,
            uploaded_at=uploaded_at,
            content_type=content_type,
            file_size_bytes=file_size_bytes,
        )
        with self._session_factory.begin() as session:
            session.add(statement)
        return statement


def repository_from_database_url(database_url: str) -> SqlAlchemyStatementRepository:
    """Create a PostgreSQL repository without embedding credentials in code."""

    engine = create_engine(database_url, pool_pre_ping=True)
    return SqlAlchemyStatementRepository(sessionmaker(engine))


def repository_from_environment() -> SqlAlchemyStatementRepository:
    """Read the required database URL at the application boundary."""

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set before starting the API")
    return repository_from_database_url(database_url)
