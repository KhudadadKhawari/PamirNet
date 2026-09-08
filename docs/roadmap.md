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
- central FreeRADIUS service
- MikroTik RouterOS API/REST integration
- router health foundation

## Phase 3 — Subscribers and subscriptions

Status: complete

- package foundation
- subscriber CRUD/search/filter
- manual/generated credentials
- MAC locking / first-login binding
- subscription lifecycle
- renewals and expiry
- immediate package changes
- tenant-aware FreeRADIUS authorization

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

## Phase 5 — Vouchers

Status: complete

- voucher batches
- 8-digit numeric usernames / 6-digit numeric passwords
- first-login activation
- simultaneous-session rules including unlimited
- quota/FUP and expiry enforcement
- CSV export
- bulk disable and safe unused-batch deletion

## Phase 6 — Accounting and analytics

Status: complete

- RADIUS Start/Interim/Stop ingestion
- online session state
- CoA/disconnect and immediate policy changes
- subscriber/voucher usage counter updates
- 12-month raw accounting retention
- hourly/daily aggregates
- tenant dashboard
- per subscriber/voucher usage
- custom-range analytics
- sorting/filtering
- router latency/uptime/packet loss history

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
