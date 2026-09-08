# Operations Runbook

Commands assume repository root and `.env.production`.

```bash
COMPOSE='docker compose --env-file .env.production -f docker-compose.prod.yml'
```

## Routine checks

```bash
$COMPOSE ps
curl -fsS https://<domain>/api/health/
curl -fsS https://<domain>/api/ready/
sudo wg show
sudo ss -lunp | grep -E ':1812|:1813|:51820'
$COMPOSE logs --tail=100 backend celery freeradius
```

Daily:

- readiness is green
- database backup completed
- disk has comfortable free space
- no unusual RADIUS reject/timeout spike
- routers show expected latency/packet loss

Weekly:

- validate one backup with `--verify-only`
- review platform/tenant audit activity
- install security updates during maintenance window
- inspect Docker disk consumption

## API unavailable

```bash
$COMPOSE ps
$COMPOSE logs --tail=200 backend db redis
curl -v -H 'X-Forwarded-Proto: https' http://127.0.0.1:8000/api/ready/
```

If database/Redis are healthy but backend is unhealthy:

```bash
$COMPOSE restart backend celery celery-beat
```

Do not blindly restart PostgreSQL during an active backup/restore.

## FreeRADIUS unavailable

```bash
$COMPOSE ps freeradius
$COMPOSE logs --tail=200 freeradius
$COMPOSE run --rm freeradius freeradius -XC
sudo wg show
sudo tcpdump -ni wg0 'udp port 1812 or udp port 1813'
```

Regenerate NAS clients if needed:

```bash
$COMPOSE exec backend python manage.py render_radius_clients
$COMPOSE restart freeradius
```

## MikroTik RADIUS timeouts

Check path in order:

1. WireGuard peer handshake
2. router tunnel IP
3. VPS firewall
4. RADIUS UDP 1812/1813 binding
5. router RADIUS secret
6. FreeRADIUS logs
7. backend internal RADIUS REST health

```bash
sudo wg show
sudo ss -lunp | grep -E ':1812|:1813'
$COMPOSE logs -f freeradius backend
```

## CoA/Disconnect fails

PamirNet sends UDP 3799 to the MikroTik tunnel IP.

Verify RouterOS:

```routeros
/radius incoming print
/ip firewall filter print where protocol=udp
```

Verify VPS:

```bash
sudo tcpdump -ni wg0 udp port 3799
```

If CoA cannot apply a new rate, PamirNet attempts Disconnect so the next authentication receives the updated policy.

## PostgreSQL disk pressure

```bash
df -h
$COMPOSE exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "SELECT pg_size_pretty(pg_database_size(current_database()));"
```

Do not delete PostgreSQL files directly. First inspect accounting retention, Docker logs and old backups.

```bash
du -sh /var/backups/pamirnet/* 2>/dev/null | sort -h | tail
sudo docker system df
```

## Redis unavailable

Redis affects Celery/background operations, not persisted subscriber/accounting state stored in PostgreSQL.

```bash
$COMPOSE logs --tail=100 redis celery celery-beat
$COMPOSE restart redis celery celery-beat
```

## Stale online session

If a NAS failed to send Stop, inspect the session and router first. Avoid bulk database edits during normal operations. Use PamirNet Disconnect where possible; stale-session reconciliation can be added later if production data shows it is required.

## Emergency rollback to Janitor for AWKH

Use `docs/awkh-rollout.md`. The legacy Janitor entry should remain intact but disabled during the initial 72-hour observation period.

## Backup failure

```bash
bash scripts/backup-production.sh
$COMPOSE logs --tail=100 db
```

Never consider a backup successful until the script completes archive validation and checksum creation.

## Restore drill

```bash
bash scripts/restore-production.sh /var/backups/pamirnet/<backup>.dump --verify-only
```

A production restore requires explicit `--yes`.

## Deployment failure

The deploy script prints recent backend/Celery/FreeRADIUS logs on readiness failure.

```bash
git log --oneline -10
git checkout <previous-good-sha>
bash scripts/deploy-production.sh
```

If schema changes prevent application rollback, evaluate the migration and restore the pre-deployment backup instead of forcing an older application against a newer schema.
