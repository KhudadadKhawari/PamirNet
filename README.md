# PamirNet

PamirNet is a multi-tenant ISP subscriber management and AAA platform for MikroTik networks, built around FreeRADIUS.

## Current status

**Phase 0 complete:** project foundation, Django/DRF, React/TypeScript, PostgreSQL, Redis/Celery, Docker Compose, OpenAPI and CI.

**Phase 1 complete:** JWT authentication, isolated tenants, Owner bootstrap, custom RBAC, platform administration, audited impersonation and append-only audit logs.

**Phase 2 complete:** MikroTik router registry, WireGuard provisioning, encrypted NAS/API credentials, RouterOS API/REST control, central FreeRADIUS clients and router health monitoring.

**Phase 3 complete:** packages, subscribers, encrypted RADIUS credentials, subscriptions, renewals, expiry, MAC locking and tenant-aware FreeRADIUS authorization.

**Phase 4 complete:** daily/weekly/monthly/subscription quotas, multi-stage FUP, effective-policy calculation and RADIUS throttle/block enforcement.

**Phase 5 complete:** voucher batches, 8-digit/6-digit numeric credentials, first-login activation, simultaneous-session rules, quota/expiry enforcement, CSV export and bulk disable.

**Phase 6 complete:** RADIUS Start/Interim/Stop accounting, live subscriber/voucher sessions, 64-bit usage ingestion, hourly/daily aggregates, CoA/disconnect controls, live FUP enforcement, tenant dashboard, custom-range analytics and router health history.

PamirNet Edge remains a future component. The current architecture uses a central VPS for FreeRADIUS and management, with MikroTik routers connected over WireGuard.

## Stack

- Backend: Python, Django, Django REST Framework
- Frontend: React, TypeScript, Vite, Tailwind CSS
- Data: PostgreSQL, Redis
- Async: Celery + Celery Beat
- AAA: FreeRADIUS + `rlm_rest`
- Network control: WireGuard + MikroTik RouterOS API/REST + RADIUS CoA
- Deployment: Docker Compose

## Development

```bash
cp .env.example .env
# Configure WIREGUARD_SERVER_PUBLIC_KEY, WIREGUARD_ENDPOINT,
# PAMIRNET_ENCRYPTION_KEY and RADIUS_INTERNAL_TOKEN.
docker compose up --build
```

- UI: `http://localhost:5173`
- API: `http://localhost:8000/api/`
- Swagger: `http://localhost:8000/api/docs/`

See the `docs/` directory for phase-specific architecture and implementation notes.

## Roadmap

- Phase 7: production hardening and AWKH rollout
- Future: PamirNet Edge for local/offline AAA and store-and-forward synchronization
