"""Statement upload endpoint and immutable local-file storage."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

from fastapi import File, Form, Header, HTTPException, UploadFile, status
from pydantic import BaseModel

SUPPORTED_CONTENT_TYPES = frozenset({"text/csv", "application/csv"})
CHUNK_SIZE_BYTES = 1024 * 1024


@dataclass(frozen=True, slots=True)
class StoredRawFile:
    storage_key: str
    content_sha256: str
    file_size_bytes: int
    content_type: str


class StatementRepository(Protocol):
    def financial_period_exists(
        self, *, user_id: UUID, financial_period_id: UUID
    ) -> bool: ...

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
    ) -> object: ...


class LocalRawStatementStorage:
    """Stores uploads beneath a configured root using generated paths only."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    @staticmethod
    def validate_upload_metadata(upload: UploadFile) -> None:
        original_filename = upload.filename or ""
        content_type = (upload.content_type or "").lower().split(";", 1)[0]
        if Path(original_filename).suffix.lower() != ".csv":
            raise ValueError("Only .csv statement files are supported")
        if content_type not in SUPPORTED_CONTENT_TYPES:
            raise ValueError("Statement content type must be text/csv")

    async def save(
        self, *, user_id: UUID, statement_id: UUID, upload: UploadFile
    ) -> StoredRawFile:
        original_filename = upload.filename or ""
        content_type = (upload.content_type or "").lower().split(";", 1)[0]
        self.validate_upload_metadata(upload)

        storage_key = f"{user_id}/{statement_id}.csv"
        destination = self._resolve_storage_key(storage_key)
        temporary = destination.with_suffix(".part")
        destination.parent.mkdir(parents=True, exist_ok=True)

        digest = hashlib.sha256()
        file_size_bytes = 0
        sample = bytearray()
        try:
            with temporary.open("xb") as raw_file:
                while chunk := await upload.read(CHUNK_SIZE_BYTES):
                    raw_file.write(chunk)
                    digest.update(chunk)
                    file_size_bytes += len(chunk)
                    if len(sample) < 4096:
                        sample.extend(chunk[: 4096 - len(sample)])
            self._validate_csv_content(bytes(sample), file_size_bytes)
            temporary.replace(destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

        return StoredRawFile(
            storage_key=storage_key,
            content_sha256=digest.hexdigest(),
            file_size_bytes=file_size_bytes,
            content_type=content_type,
        )

    def delete(self, storage_key: str) -> None:
        self._resolve_storage_key(storage_key).unlink(missing_ok=True)

    def _resolve_storage_key(self, storage_key: str) -> Path:
        destination = (self._root / storage_key).resolve()
        if not destination.is_relative_to(self._root):
            raise ValueError("storage key must remain inside the upload root")
        return destination

    @staticmethod
    def _validate_csv_content(sample: bytes, file_size_bytes: int) -> None:
        if file_size_bytes == 0:
            raise ValueError("Statement file must not be empty")
        if sample.startswith(b"%PDF-") or b"\x00" in sample:
            raise ValueError("Statement file content is not CSV text")
        try:
            sample.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise ValueError("Statement file must be UTF-8 CSV") from error


class StatementUploadResponse(BaseModel):
    id: UUID
    financial_period_id: UUID
    processing_status: str


class StatementUploadService:
    def __init__(
        self, repository: StatementRepository, storage: LocalRawStatementStorage
    ) -> None:
        self._repository = repository
        self._storage = storage

    async def upload(
        self,
        *,
        user_id: UUID,
        financial_period_id: UUID,
        provider: str,
        upload: UploadFile,
    ) -> StatementUploadResponse:
        if not provider.strip():
            raise ValueError("provider must not be empty")
        self._storage.validate_upload_metadata(upload)
        if not self._repository.financial_period_exists(
            user_id=user_id, financial_period_id=financial_period_id
        ):
            raise LookupError("financial period was not found")

        statement_id = uuid4()
        stored_file = await self._storage.save(
            user_id=user_id, statement_id=statement_id, upload=upload
        )
        try:
            self._repository.create_statement(
                statement_id=statement_id,
                user_id=user_id,
                financial_period_id=financial_period_id,
                provider=provider.strip(),
                original_filename=upload.filename or "statement.csv",
                storage_key=stored_file.storage_key,
                content_sha256=stored_file.content_sha256,
                uploaded_at=datetime.now(timezone.utc),
                content_type=stored_file.content_type,
                file_size_bytes=stored_file.file_size_bytes,
            )
        except Exception:
            self._storage.delete(stored_file.storage_key)
            raise

        return StatementUploadResponse(
            id=statement_id,
            financial_period_id=financial_period_id,
            processing_status="pending",
        )


async def current_user_id(x_user_id: UUID = Header(alias="X-User-ID")) -> UUID:
    """Temporary identity adapter until the authentication boundary is added."""

    return x_user_id


async def upload_statement(
    service: StatementUploadService,
    user_id: UUID,
    financial_period_id: UUID = Form(),
    provider: str = Form(),
    file: UploadFile = File(),
) -> StatementUploadResponse:
    """Upload one CSV statement; extraction is intentionally deferred."""

    try:
        return await service.upload(
            user_id=user_id,
            financial_period_id=financial_period_id,
            provider=provider,
            upload=file,
        )
    except LookupError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error
