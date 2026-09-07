# PamirNet

PamirNet is a multi-tenant ISP subscriber management and AAA platform for MikroTik networks, built around FreeRADIUS.

## Current status

Phase 0 foundation is complete. Phase 1 identity, tenancy and RBAC work is in progress.

Phase 0 established:

- architecture and domain documentation
- Django + Django REST Framework backend scaffold
- React + TypeScript + Vite frontend scaffold
- PostgreSQL, Redis and Celery development services
- Docker Compose development environment
- OpenAPI/Swagger support
- basic backend/frontend health integration
- GitHub Actions CI

Phase 1 now adds JWT authentication, tenant isolation, custom roles/permissions, platform administration, audited impersonation and append-only audit APIs. RADIUS and MikroTik integration remain Phase 2.

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
