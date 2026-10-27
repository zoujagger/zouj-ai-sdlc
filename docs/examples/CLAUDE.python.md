<!-- Example "Project notes" for CLAUDE.md, Python stack (bootstrap --stack python). Copy, then edit to match your project. -->
## Project notes
- **Stack:** Python 3.12, FastAPI, SQLAlchemy 2, PostgreSQL 16, Celery + Redis for background jobs. Dependencies via `uv`.
- **Layout:** `app/api/` (routers, thin), `app/services/` (business logic), `app/models/` (ORM), `migrations/` (Alembic), `tests/` mirrors `app/`.
- **Commands:** `make check` = `ruff check .` + `mypy .` + `pytest -q`. One test: `pytest tests/services/test_x.py -k name`.
- **Conventions:** type hints everywhere (`mypy --strict` on `app/`); services never import from `api/`; money is `Decimal`, never float.
- **Gotchas:** tests use a real Postgres (`docker compose up db`), not SQLite; Alembic migrations must be reversible (`downgrade` implemented).
