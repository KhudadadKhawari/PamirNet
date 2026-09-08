# PamirNet

PamirNet is a multi-tenant ISP subscriber management and AAA platform for MikroTik networks, built around FreeRADIUS.

## Current status

**Phases 0–6 complete:** foundation, tenancy/RBAC, MikroTik/WireGuard/FreeRADIUS integration, subscribers, packages/FUP, vouchers, RADIUS accounting, live sessions, CoA/disconnect, analytics and router health history.

**Phase 7 implementation complete:** hardened production Compose stack, Gunicorn/static production images, Nginx/TLS template, production preflight checks, readiness probes, backup/restore tooling, load-test harness, subscriber CSV migration tooling and AWKH rollout/rollback runbooks.

The actual AWKH live cutover is an operational maintenance action requiring access to the production VPS and MikroTik. PamirNet Edge remains a future component; v1 AAA is centralized on the VPS.

## Stack

- Backend: Python, Django, Django REST Framework
- Frontend: React, TypeScript, Vite, Tailwind CSS
- Data: PostgreSQL, Redis
- Async: Celery + Celery Beat
- AAA: FreeRADIUS + `rlm_rest`
- Network control: WireGuard + MikroTik RouterOS API/REST + RADIUS CoA
- Deployment: Docker Compose + Nginx

## Development

```bash
cp .env.example .env
docker compose up --build
```

- UI: `http://localhost:5173`
- API: `http://localhost:8000/api/`
- Swagger: `http://localhost:8000/api/docs/`

## Production

```bash
cp .env.production.example .env.production
chmod 600 .env.production
# Configure production domain, secrets and WireGuard values.
bash scripts/deploy-production.sh
```

Production documentation:

- `docs/production-deployment.md`
- `docs/security-hardening.md`
- `docs/backup-restore.md`
- `docs/operations-runbook.md`
- `docs/load-testing.md`
- `docs/awkh-rollout.md`

## Roadmap

The centralized v1 platform is feature-complete through Phase 7 implementation. The next architectural milestone is **PamirNet Edge** for local/offline AAA, policy caching and store-and-forward synchronization.
