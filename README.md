# PamirNet

PamirNet is a multi-tenant ISP subscriber management and AAA platform for MikroTik networks, built around FreeRADIUS.

## Current status

**Phase 0 complete:** project foundation, Django/DRF, React/TypeScript, PostgreSQL, Redis/Celery, Docker Compose, OpenAPI and CI.

**Phase 1 complete:** JWT authentication, isolated tenants, Owner bootstrap, custom RBAC, platform administration, audited impersonation and append-only audit logs.

**Phase 2 complete:** MikroTik router registry, WireGuard provisioning, encrypted NAS/API credentials, RouterOS API/REST control, central FreeRADIUS clients and router health monitoring.

**Phase 3 implemented:**

- tenant-scoped package management with speed, duration and optional price
- subscriber profiles and encrypted RADIUS credentials
- manual or automatically generated subscriber credentials
- subscription history, renewal and immediate package switching
- calendar-based expiration with automatic expiry task
- manual and first-login MAC locking
- FreeRADIUS `rlm_rest` authorization against PamirNet
- NAS-based tenant resolution, allowing duplicate usernames across ISPs
- MikroTik rate-limit, session-timeout and interim-accounting reply attributes
- tenant Package and Subscriber UI

PamirNet Edge remains a future component. The current architecture uses a central VPS for FreeRADIUS and management, with MikroTik routers connected over WireGuard.

## Stack

- Backend: Python, Django, Django REST Framework
- Frontend: React, TypeScript, Vite, Tailwind CSS
- Data: PostgreSQL, Redis
- Async: Celery + Celery Beat
- AAA: FreeRADIUS + `rlm_rest`
- Network control: WireGuard + MikroTik RouterOS API/REST
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

See `docs/phase-2-networking.md` and `docs/phase-3-subscribers-radius.md`.

## Roadmap

- Phase 4: sessions/accounting, CoA and live-session controls
- Phase 5: quota/FUP engine
- Phase 6: voucher batches and CSV export
- Phase 7: analytics/dashboard/router health expansion
- Future: PamirNet Edge for local/offline AAA and store-and-forward synchronization
