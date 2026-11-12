from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from apps.api.main import create_app, create_app_from_environment


class FakeStatementRepository:
    def __init__(self, financial_period_id: UUID) -> None:
        self.financial_period_id = financial_period_id
        self.created_statements: list[dict[str, object]] = []

    def financial_period_exists(
        self, *, user_id: UUID, financial_period_id: UUID
    ) -> bool:
        return financial_period_id == self.financial_period_id

    def create_statement(self, **values: object) -> object:
        self.created_statements.append(values)
        return object()


def _client(tmp_path: Path) -> tuple[TestClient, FakeStatementRepository, UUID, UUID]:
    user_id = uuid4()
    financial_period_id = uuid4()
    repository = FakeStatementRepository(financial_period_id)
    return (
        TestClient(create_app(repository=repository, upload_root=tmp_path)),
        repository,
        user_id,
        financial_period_id,
    )


def test_upload_csv_stores_raw_file_creates_statement_and_returns_pending(
    tmp_path: Path,
) -> None:
    client, repository, user_id, financial_period_id = _client(tmp_path)
    statement_contents = b"Date,Amount\n2026-09-01,125.50\n"

    response = client.post(
        "/v1/statements",
        headers={"X-User-ID": str(user_id)},
        data={"financial_period_id": str(financial_period_id), "provider": "hdfc"},
        files={
            "file": (
                "September.csv",
                statement_contents,
                "text/csv",
            )
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["financial_period_id"] == str(financial_period_id)
    assert body["processing_status"] == "pending"
    assert len(repository.created_statements) == 1

    statement = repository.created_statements[0]
    assert statement["user_id"] == user_id
    assert statement["financial_period_id"] == financial_period_id
    assert statement["file_size_bytes"] == len(statement_contents)
    raw_file = tmp_path / str(user_id) / f"{body['id']}.csv"
    assert raw_file.read_bytes() == statement_contents


def test_upload_rejects_an_unsupported_file_type_without_storing_it(
    tmp_path: Path,
) -> None:
    client, repository, user_id, _ = _client(tmp_path)

    response = client.post(
        "/v1/statements",
        headers={"X-User-ID": str(user_id)},
        data={"financial_period_id": str(uuid4()), "provider": "hdfc"},
        files={"file": ("statement.pdf", b"%PDF-1.7", "application/pdf")},
    )

    assert response.status_code == 422
    assert repository.created_statements == []
    assert list(tmp_path.rglob("*")) == []


def test_upload_requires_a_financial_period_owned_by_the_user(tmp_path: Path) -> None:
    client, repository, user_id, _ = _client(tmp_path)

    response = client.post(
        "/v1/statements",
        headers={"X-User-ID": str(user_id)},
        data={"financial_period_id": str(uuid4()), "provider": "hdfc"},
        files={"file": ("statement.csv", b"Date,Amount\n", "text/csv")},
    )

    assert response.status_code == 404
    assert repository.created_statements == []
    assert list(tmp_path.rglob("*")) == []


def test_app_can_be_created_from_environment(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://test:unused@localhost:5432/finance"
    )
    monkeypatch.setenv("UPLOAD_STORAGE_DIR", str(tmp_path))

    app = create_app_from_environment()

    assert app.title == "Finance AI Analyst API"
