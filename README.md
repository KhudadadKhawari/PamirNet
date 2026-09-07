# PamirNet

PamirNet is a multi-tenant ISP subscriber management and AAA platform for MikroTik networks, built around FreeRADIUS.

## Phase 0 status

Phase 0 establishes the project foundation:

- architecture and domain documentation
- Django + Django REST Framework backend scaffold
- React + TypeScript + Vite frontend scaffold
- PostgreSQL, Redis and Celery development services
- Docker Compose development environment
- OpenAPI/Swagger support
- basic backend/frontend health integration
- GitHub Actions CI

RADIUS, MikroTik, subscriber, package, voucher and analytics functionality starts in later phases.

## Stack

- Backend: Python, Django, Django REST Framework
- Database: PostgreSQL
- Async/cache: Redis + Celery
- Frontend: React, TypeScript, Vite, Tailwind CSS
- API docs: drf-spectacular / OpenAPI
- AAA: FreeRADIUS (Phase 2+)
- Deployment: Docker Compose initially

## Quick start

```bash
cp .env.example .env
make up
```

Then open:

- UI: http://localhost:5173
- API health: http://localhost:8000/api/health/
- API docs: http://localhost:8000/api/docs/
- OpenAPI schema: http://localhost:8000/api/schema/

## Repository layout

```text
PamirNet/
├── backend/        Django/DRF API
├── frontend/       React/TypeScript UI
├── freeradius/     FreeRADIUS integration (future phases)
├── infra/          deployment/networking infrastructure
├── docs/           architecture and product specifications
├── .github/        CI workflows
├── docker-compose.yml
└── Makefile
```

See [docs/roadmap.md](docs/roadmap.md) for implementation phases.
