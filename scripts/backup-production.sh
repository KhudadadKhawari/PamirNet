#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${PAMIRNET_ENV_FILE:-$ROOT_DIR/.env.production}"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$ROOT_DIR/docker-compose.prod.yml")

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing production environment file: $ENV_FILE" >&2
  exit 1
fi

# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a
BACKUP_DIR="${PAMIRNET_BACKUP_DIR:-/var/backups/pamirnet}"
RETENTION_DAYS="${PAMIRNET_BACKUP_RETENTION_DAYS:-14}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_FILE="$BACKUP_DIR/pamirnet-$TIMESTAMP.dump"
CHECKSUM_FILE="$BACKUP_FILE.sha256"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

echo "Creating PostgreSQL backup: $BACKUP_FILE"
"${COMPOSE[@]}" exec -T db pg_dump \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --format=custom \
  --no-owner \
  --no-acl > "$BACKUP_FILE"

if [[ ! -s "$BACKUP_FILE" ]]; then
  echo "Backup is empty." >&2
  rm -f "$BACKUP_FILE"
  exit 1
fi

"${COMPOSE[@]}" exec -T db pg_restore --list < "$BACKUP_FILE" >/dev/null
(
  cd "$BACKUP_DIR"
  sha256sum "$(basename "$BACKUP_FILE")" > "$(basename "$CHECKSUM_FILE")"
)
chmod 600 "$BACKUP_FILE" "$CHECKSUM_FILE"

find "$BACKUP_DIR" -type f \( -name 'pamirnet-*.dump' -o -name 'pamirnet-*.dump.sha256' \) \
  -mtime "+$RETENTION_DAYS" -delete

echo "Backup completed and validated."
echo "IMPORTANT: PAMIRNET_ENCRYPTION_KEY and the WireGuard server private key are NOT in this backup."
