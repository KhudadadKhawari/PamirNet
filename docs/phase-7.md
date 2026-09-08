# Phase 7 — Production Hardening and AWKH Rollout

Phase 7 turns the Phase 0–6 application into a production-deployable central PamirNet v1 release.

## Delivered

- production Docker Compose stack with no public PostgreSQL/Redis exposure
- Gunicorn backend and optimized static frontend images
- host Nginx TLS/reverse-proxy configuration
- production configuration preflight and Django deploy checks
- liveness/readiness endpoints
- secure-cookie/HSTS/host/CSRF protections and login throttling
- validated PostgreSQL backup and destructive restore tooling
- four-times-daily systemd backup timer
- RADIUS authorize/accounting load-test harness
- normalized subscriber CSV migration command
- security, backup, deployment and operations runbooks
- AWKH staged migration, cutover and rollback plan
- CI builds production images and validates production Compose/tooling

## Phase boundary

The repository-side Phase 7 implementation is complete. Live AWKH cutover requires production VPS and MikroTik access and must be executed during a maintenance window using `docs/awkh-rollout.md`.

PamirNet Edge/offline AAA is explicitly outside v1 and remains the next architectural milestone.
