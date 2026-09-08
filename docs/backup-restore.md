# Backup and Restore

## What must be protected

PamirNet recovery requires more than the PostgreSQL database.

1. PostgreSQL backup (`scripts/backup-production.sh`)
2. `PAMIRNET_ENCRYPTION_KEY`
3. WireGuard server private key/config
4. `.env.production` or an equivalent secure secret store
5. TLS private key/certificate can be reissued, but preserving it simplifies recovery

Do not store production secrets in Git.

## Database backup

```bash
bash scripts/backup-production.sh
```

The script creates a PostgreSQL custom-format archive, validates it with `pg_restore --list`, writes a SHA-256 checksum and removes backups older than the configured retention period.

Default path:

```text
/var/backups/pamirnet/
```

## Automated schedule

Phase 7 includes a systemd timer that runs at 00:15, 06:15, 12:15 and 18:15 UTC.

If PamirNet is installed at `/opt/PamirNet`:

```bash
sudo cp infra/systemd/pamirnet-backup.service /etc/systemd/system/
sudo cp infra/systemd/pamirnet-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pamirnet-backup.timer
sudo systemctl list-timers pamirnet-backup.timer
```

If the repository lives elsewhere, edit `WorkingDirectory`, `Environment` and `ExecStart` in the service first.

For production, copy backups to a second machine/object-storage location after creation. A backup stored only on the PamirNet VPS is not sufficient disaster recovery.

## Restore validation

Validate a backup by restoring it into a temporary PostgreSQL database:

```bash
bash scripts/restore-production.sh /var/backups/pamirnet/pamirnet-YYYYMMDDTHHMMSSZ.dump --verify-only
```

Run this regularly, not only during an incident.

## Full restore

```bash
bash scripts/restore-production.sh /var/backups/pamirnet/pamirnet-YYYYMMDDTHHMMSSZ.dump --yes
```

The script:

- validates the archive first
- stops PamirNet application services
- recreates the production database
- restores the archive
- runs current migrations
- regenerates FreeRADIUS clients
- starts the stack
- waits for readiness

## Disaster recovery sequence

On a replacement VPS:

1. install Docker, WireGuard and Nginx
2. restore `.env.production` from the protected secret store
3. restore the original `PAMIRNET_ENCRYPTION_KEY`
4. restore WireGuard private key/config, or rotate every MikroTik peer if the key is unavailable
5. deploy the same or compatible PamirNet release
6. start PostgreSQL/Redis
7. restore the database archive
8. regenerate RADIUS clients
9. verify `/api/ready/`
10. test one subscriber and one voucher before restoring all traffic

## Recovery objectives

Initial operational targets for AWKH rollout:

- RPO: <= 6 hours with four database backups/day
- RTO: <= 2 hours when VPS replacement and secret backups are available

These are operational targets, not guarantees. Measure them during a restore drill and adjust the schedule/resources accordingly.
