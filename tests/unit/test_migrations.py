from pathlib import Path

from packages.db.orm_models import Base


def test_initial_migration_and_orm_metadata_cover_the_same_tables() -> None:
    migrations = "".join(
        migration.read_text()
        for migration in Path("packages/db/migrations/versions").glob("*.py")
    )

    for table_name in Base.metadata.tables:
        assert f'"{table_name}"' in migrations


def test_alembic_environment_requires_an_explicit_database_url() -> None:
    environment = Path("packages/db/migrations/env.py").read_text()

    assert 'os.environ.get("DATABASE_URL")' in environment
