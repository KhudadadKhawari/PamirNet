# Infrastructure

PamirNet keeps development and production deployment intentionally simple.

## Development

Use the root `docker-compose.yml`.

## Production

Use:

- `docker-compose.prod.yml` — PostgreSQL, Redis, Django/Gunicorn, Celery, FreeRADIUS and static frontend
- `infra/nginx/pamirnet.conf.template` — host Nginx TLS/reverse-proxy configuration
- `infra/wireguard/` — WireGuard server/router onboarding assets
- `infra/systemd/pamirnet-backup.*` — four-times-daily backup timer/service
- `scripts/deploy-production.sh` — preflight/build/deploy/readiness flow
- `scripts/backup-production.sh` — validated PostgreSQL backup
- `scripts/restore-production.sh` — restore verification/full restore

The public VPS exposes HTTPS and WireGuard. RADIUS is bound only to the WireGuard server IP. PostgreSQL, Redis, Gunicorn and the static frontend are never directly public.

Kubernetes is intentionally out of scope for the initial ~1,000-subscriber deployment.
