"""Factory for the HTTP API."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

from fastapi import Depends, FastAPI, File, Form, Header, UploadFile

from packages.db.statement_repository import repository_from_environment

from .statements import (
    LocalRawStatementStorage,
    StatementRepository,
    StatementUploadResponse,
    StatementUploadService,
    upload_statement,
)


def create_app(*, repository: StatementRepository, upload_root: Path) -> FastAPI:
    """Build the API with explicit infrastructure dependencies."""

    app = FastAPI(title="Finance AI Analyst API")
    service = StatementUploadService(repository, LocalRawStatementStorage(upload_root))

    async def get_current_user_id(x_user_id: UUID = Header(alias="X-User-ID")) -> UUID:
        return x_user_id

    @app.post(
        "/v1/statements",
        response_model=StatementUploadResponse,
        status_code=201,
    )
    async def create_statement_upload(
        financial_period_id: UUID = Form(),
        provider: str = Form(),
        file: UploadFile = File(),
        user_id: UUID = Depends(get_current_user_id),
    ) -> StatementUploadResponse:
        return await upload_statement(
            service=service,
            user_id=user_id,
            financial_period_id=financial_period_id,
            provider=provider,
            file=file,
        )

    return app


def create_app_from_environment() -> FastAPI:
    """Build the runnable API from environment-provided infrastructure settings."""

    upload_root = Path(os.environ.get("UPLOAD_STORAGE_DIR", "data/uploads"))
    return create_app(
        repository=repository_from_environment(),
        upload_root=upload_root,
    )
