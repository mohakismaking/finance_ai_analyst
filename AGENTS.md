# AGENTS.md

## Project

AI-powered personal finance analyst.

## Goal

Build a production-quality V1 while keeping the architecture
simple enough for a single developer to understand.

## Architecture Principles

1. Financial calculations must be deterministic.
2. Never ask the LLM to calculate financial totals.
3. LLMs may classify, interpret, route and explain.
4. Preserve raw uploaded transactions.
5. Never silently delete duplicate transactions.
6. Agent tools must have explicit schemas.
7. Prefer simple architecture over unnecessary abstractions.
8. Keep LLM provider behind an abstraction.
9. All important agent behavior must have tests.
10. No production secrets in source code.

## Repository Layout

- `apps/api/` holds the HTTP API application boundary.
- `apps/web/` holds the Next.js user interface.
- `packages/domain/` holds business entities, enums, and finance rules.
- `packages/ingestion/` holds provider-specific statement parsers and normalization.
- `packages/analytics/` holds deterministic financial calculations and query services.
- `packages/agent/` holds LangGraph state, graphs, prompts, and tool definitions.
- `packages/llm/` holds the provider-neutral LLM interface and provider adapters.
- `packages/db/` holds database models, migrations, and repositories.
- `tests/fixtures/` contains sanitized statement samples only; never add real statements.
- `data/uploads/` is local development storage for uploaded originals and must stay untracked.
- `docs/decisions/` records material architecture decisions and their rationale.

## Data Rules

- Each uploaded file is an immutable statement source.
- Store parsed provider fields before producing normalized transactions.
- Every normalized transaction must trace to its statement source and raw row.
- Duplicate detection creates reviewable candidate links; it must not erase source data.
- Store money as integer paise, never floating-point values.
- Scope every database query and agent tool to the authenticated user.

## Development Rules

- Run tests after meaningful changes.
- Use pytest for automated tests. Put them in `tests/unit/`, `tests/integration/`, or `tests/e2e/` based on scope.
- Name pytest files `test_*.py` and test functions `test_*`. Run all tests with `uv run pytest`, or a focused suite with `uv run pytest tests/unit`.
- Use sanitized fixtures only; test deterministic financial calculations and agent/tool schemas independently of LLM services.
- Sync development tools with `uv sync --group dev`.
- Format Python code with Black before committing: `uv run black .`.
- Check formatting without modifying files with `uv run black --check .`.
- Black uses its standard 88-character line length; do not manually reformat its output.
- Do not modify unrelated files.
- Keep changes small and reviewable.
- Explain architectural decisions before large changes.
- Don't introduce dependencies without justification.
