# PamirNet Roadmap

## Phase 0 — Foundation

Status: complete

- architecture and domain documentation
- Docker Compose development environment
- Django/DRF backend scaffold
- React/TypeScript/Vite/Tailwind frontend scaffold
- PostgreSQL
- Redis + Celery
- OpenAPI/Swagger
- health endpoint/UI connectivity check
- GitHub Actions CI

## Phase 1 — Identity, tenancy and RBAC

Status: complete

- application authentication
- Tenant model and isolation
- Owner bootstrap
- custom tenant roles and granular permissions
- platform administrators
- audited tenant impersonation
- audit infrastructure

## Phase 2 — Networking and RADIUS

Status: complete

- router/NAS registration
- WireGuard onboarding/config generation
- FreeRADIUS service and REST integration
- MikroTik RouterOS API/REST integration
- Hotspot and PPPoE authentication foundation

## Phase 3 — Subscribers and subscriptions

Status: complete

- subscriber CRUD/search/filter
- manual/generated credentials
- MAC locking / first-login binding
- subscription lifecycle
- renewals and expiry
- immediate package changes
- base package speed/duration/price configuration

## Phase 4 — Packages and policy engine

Status: complete

- package CRUD
- speed limits
- durations
- optional package price/currency
- daily/weekly/monthly/subscription quotas
- multi-stage FUP
- effective-policy calculation
- RADIUS throttle/block enforcement
- package FUP/quota management UI

## Phase 5 — Vouchers

- voucher batches
- numeric credentials
- first-login activation
- simultaneous-session rules
- quota/expiry enforcement
- CSV export
- bulk disable

## Phase 6 — Accounting and analytics

- RADIUS Start/Interim/Stop ingestion
- raw session retention
- hourly/daily aggregates
- tenant dashboard
- per subscriber/voucher usage
- custom-range analytics
- sorting/filtering
- router latency/uptime/packet loss
- CoA/disconnect and live-session controls

## Phase 7 — Production hardening and AWKH rollout

- security hardening
- backups/restore validation
- load tests
- operational runbooks
- manual migration from Janitor RADIUS
- AWKH production deployment

## Future — PamirNet Edge

- local FreeRADIUS
- offline authentication
- local policy cache
- store-and-forward accounting
- Core/Edge synchronization
