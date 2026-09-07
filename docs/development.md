# Development Guide

## Requirements

Recommended local tools:

- Docker Engine + Docker Compose v2
- GNU Make
- Git

Native development additionally needs Python 3.13 and Node.js 22.

## Docker workflow

```bash
cp .env.example .env
make up
make ps
make logs
```

Stop services:

```bash
make down
```

## Backend

Run tests:

```bash
docker compose exec backend python manage.py test
```

Run checks/lint:

```bash
docker compose exec backend python manage.py check
docker compose exec backend ruff check .
```

Create migrations:

```bash
make makemigrations
make migrate
```

## Frontend

```bash
docker compose exec frontend npm run lint
docker compose exec frontend npm run build
```

## API schema

- `/api/schema/` — OpenAPI document
- `/api/docs/` — Swagger UI

All public backend endpoints added in later phases should appear in the OpenAPI schema.

## Phase boundaries

Phase 0 deliberately contains no product-domain tables beyond the Django scaffold. Tenancy/RBAC starts in Phase 1, networking/RADIUS in Phase 2.
