#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${PAMIRNET_ENV_FILE:-$ROOT_DIR/.env.production}"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$ROOT_DIR/docker-compose.prod.yml")

usage() {
  echo "Usage: $0 <backup.dump> [--verify-only|--yes]" >&2
  exit 2
}

[[ $# -ge 1 ]] || usage
BACKUP_FILE="$1"
MODE="${2:-}"
[[ -f "$BACKUP_FILE" ]] || { echo "Backup not found: $BACKUP_FILE" >&2; exit 1; }
[[ -f "$ENV_FILE" ]] || { echo "Missing environment file: $ENV_FILE" >&2; exit 1; }

# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a
: "${PAMIRNET_DOMAIN:?PAMIRNET_DOMAIN is required}"

[[ "$POSTGRES_DB" =~ ^[A-Za-z0-9_]+$ ]] || { echo "Unsafe POSTGRES_DB value" >&2; exit 1; }
[[ "$POSTGRES_USER" =~ ^[A-Za-z0-9_]+$ ]] || { echo "Unsafe POSTGRES_USER value" >&2; exit 1; }

CHECKSUM_FILE="$BACKUP_FILE.sha256"
if [[ -f "$CHECKSUM_FILE" ]]; then
  echo "Verifying SHA-256 checksum..."
  (
    cd "$(dirname "$BACKUP_FILE")"
    sha256sum -c "$(basename "$CHECKSUM_FILE")"
  )
else
  echo "WARNING: checksum file not found; validating PostgreSQL archive only." >&2
fi

verify_archive() {
  local test_db="pamirnet_restore_check_$(date +%s)"
  echo "Validating archive structure..."
  "${COMPOSE[@]}" exec -T db pg_restore --list < "$BACKUP_FILE" >/dev/null
  echo "Restoring into temporary database $test_db..."
  "${COMPOSE[@]}" exec -T db createdb -U "$POSTGRES_USER" "$test_db"

  if ! "${COMPOSE[@]}" exec -T db pg_restore \
      -U "$POSTGRES_USER" \
      -d "$test_db" \
      --no-owner \
      --no-acl < "$BACKUP_FILE"; then
    "${COMPOSE[@]}" exec -T db dropdb -U "$POSTGRES_USER" --if-exists "$test_db" >/dev/null 2>&1 || true
    return 1
  fi

  if ! "${COMPOSE[@]}" exec -T db psql -U "$POSTGRES_USER" -d "$test_db" -Atc \
      "SELECT COUNT(*) FROM django_migrations;" >/dev/null; then
    "${COMPOSE[@]}" exec -T db dropdb -U "$POSTGRES_USER" --if-exists "$test_db" >/dev/null 2>&1 || true
    return 1
  fi

  "${COMPOSE[@]}" exec -T db dropdb -U "$POSTGRES_USER" "$test_db"
  echo "Restore validation passed."
}

verify_archive
[[ "$MODE" == "--verify-only" ]] && exit 0

if [[ "$MODE" != "--yes" ]]; then
  echo "Refusing destructive restore without --yes." >&2
  exit 1
fi

echo "Stopping application services..."
"${COMPOSE[@]}" stop backend celery celery-beat freeradius freeradius-reloader frontend

"${COMPOSE[@]}" exec -T db psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '$POSTGRES_DB' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS "$POSTGRES_DB";
CREATE DATABASE "$POSTGRES_DB" OWNER "$POSTGRES_USER";
SQL

"${COMPOSE[@]}" exec -T db pg_restore \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --no-owner \
  --no-acl < "$BACKUP_FILE"

"${COMPOSE[@]}" run --rm backend python manage.py migrate --noinput
"${COMPOSE[@]}" run --rm backend python manage.py render_radius_clients
"${COMPOSE[@]}" up -d

for _ in {1..30}; do
  if curl -fsS -H "Host: $PAMIRNET_DOMAIN" -H 'X-Forwarded-Proto: https' "http://127.0.0.1:${BACKEND_PORT:-8000}/api/ready/" >/dev/null; then
    echo "Restore completed successfully."
    exit 0
  fi
  sleep 2
done

echo "Restore finished but readiness did not recover in time. Inspect docker compose logs." >&2
exit 1
