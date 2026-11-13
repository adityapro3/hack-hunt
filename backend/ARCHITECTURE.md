# Backend Architecture Guide

This guide defines where code belongs so the repo stays easy to navigate as features grow.

## Layer Boundaries

- `backend/api/routers`: HTTP transport only (validation mapping, status codes, response shaping).
- `backend/schemas`: API request/response contracts (`pydantic` models).
- `backend/services`: domain/application logic grouped by business area.
- `backend/infra/postgres/tables`: persistence models (`sqlalchemy` ORM tables only).
- `backend/scrapers`: external source integrations and source-specific parsing.
- `backend/core`: app-wide config and shared enums/settings.

## Model Placement Rules

- SQLAlchemy entities live only in `backend/infra/postgres/tables`.
- API DTOs live only in `backend/schemas`.
- Domain-only lightweight structures (for internal orchestration) can use `@dataclass` inside the owning domain package under `backend/services/<domain>/...`.
- Avoid placing internal domain data containers in router files.

## Helper Function Rules

- Do not introduce a global catch-all `utils.py` at backend root.
- Keep helpers close to the owning domain and name by purpose:
  - `drafts.py` for draft querying/serialization
  - `research.py` for research retrieval/ranking
  - `prompts.py` for prompt/template logic
- Put truly cross-domain helpers under `backend/services/common` only when they are reused by multiple domains.

## Module Size Heuristic

When a module crosses about 250-300 lines and mixes concerns (DB + prompt + ranking + transport formatting), split by concern while keeping the same public service API.

## Public API Stability

Domain package `__init__.py` should expose stable service entry points for routers.
Internal refactors should preserve these exports to avoid router-level churn.
