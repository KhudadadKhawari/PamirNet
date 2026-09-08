#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${PAMIRNET_ENV_FILE:-$ROOT_DIR/.env.production}"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$ROOT_DIR/docker-compose.prod.yml")

[[ -f "$ENV_FILE" ]] || { echo "Missing $ENV_FILE. Copy .env.production.example and configure it." >&2; exit 1; }

# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a
export PAMIRNET_BUILD_SHA="${PAMIRNET_BUILD_SHA:-$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)}"

if [[ "$(stat -c '%a' "$ENV_FILE" 2>/dev/null || echo 600)" =~ [2367][0-9][0-9]$ ]]; then
  echo "WARNING: $ENV_FILE may be readable by group/others; use chmod 600." >&2
fi

"${COMPOSE[@]}" config -q

echo "Building production images..."
PAMIRNET_BUILD_SHA="$PAMIRNET_BUILD_SHA" "${COMPOSE[@]}" build

echo "Starting database and Redis for preflight..."
"${COMPOSE[@]}" up -d db redis

echo "Running production configuration checks..."
"${COMPOSE[@]}" run --rm backend python manage.py production_preflight
"${COMPOSE[@]}" run --rm backend python manage.py check --deploy
"${COMPOSE[@]}" run --rm freeradius freeradius -XC

if "${COMPOSE[@]}" ps --status running backend 2>/dev/null | grep -q backend; then
  echo "Taking pre-deployment backup..."
  PAMIRNET_ENV_FILE="$ENV_FILE" "$ROOT_DIR/scripts/backup-production.sh"
fi

echo "Starting PamirNet production stack..."
PAMIRNET_BUILD_SHA="$PAMIRNET_BUILD_SHA" "${COMPOSE[@]}" up -d --remove-orphans

READY_URL="http://127.0.0.1:${BACKEND_PORT:-8000}/api/ready/"
for _ in {1..45}; do
  if curl -fsS -H 'X-Forwarded-Proto: https' "$READY_URL" >/dev/null; then
    echo "PamirNet API is ready."
    "${COMPOSE[@]}" ps
    exit 0
  fi
  sleep 2
done

echo "Deployment did not become ready. Recent logs:" >&2
"${COMPOSE[@]}" logs --tail=100 backend celery freeradius >&2 || true
exit 1
