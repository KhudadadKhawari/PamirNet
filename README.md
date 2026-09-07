# PamirNet

PamirNet is a multi-tenant ISP subscriber management and AAA platform for MikroTik networks, built around FreeRADIUS.

## Current status

**Phase 0 complete:** project foundation, Django/DRF, React/TypeScript, PostgreSQL, Redis/Celery, Docker Compose, OpenAPI and CI.

**Phase 1 complete:** JWT authentication, isolated tenants, Owner bootstrap, custom RBAC, platform administration, audited impersonation and append-only audit logs.

**Phase 2 implemented:**

- per-tenant MikroTik router registry
- central WireGuard provisioning for RouterOS 7+
- automatic tunnel IP allocation
- one-time MikroTik onboarding scripts
- encrypted RouterOS credentials and RADIUS shared secrets
- RouterOS legacy API, API-SSL and REST connectivity
- FreeRADIUS runtime and dynamically rendered NAS/client configuration
- automatic FreeRADIUS client reloads
- periodic router uptime/latency/packet-loss health checks
- router connectivity testing and key rotation from the UI
- Docker/Celery Beat integration

PamirNet Edge remains a future component. The current architecture uses a central VPS for FreeRADIUS and management, with MikroTik routers connected over WireGuard.

## Stack

- Backend: Python, Django, Django REST Framework
- Frontend: React, TypeScript, Vite, Tailwind CSS
- Data: PostgreSQL, Redis
- Async: Celery + Celery Beat
- AAA: FreeRADIUS
- Network control: WireGuard + MikroTik RouterOS API/REST
- Deployment: Docker Compose

## Development

```bash
cp .env.example .env
# Configure WIREGUARD_SERVER_PUBLIC_KEY, WIREGUARD_ENDPOINT and PAMIRNET_ENCRYPTION_KEY.
docker compose up --build
```

- UI: `http://localhost:5173`
- API: `http://localhost:8000/api/`
- Swagger: `http://localhost:8000/api/docs/`

See `docs/phase-2-networking.md` for MikroTik/FreeRADIUS onboarding and WireGuard server setup.

## Roadmap

- Phase 3: packages, subscribers, subscriptions and actual RADIUS authorization
- Phase 4: sessions/accounting, CoA and MAC locking
- Phase 5: quota/FUP engine
- Phase 6: voucher batches and CSV export
- Phase 7: analytics/dashboard/router health expansion
- Future: PamirNet Edge for local/offline AAA and store-and-forward synchronization
