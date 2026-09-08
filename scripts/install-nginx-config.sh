#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${PAMIRNET_ENV_FILE:-$ROOT_DIR/.env.production}"
TEMPLATE="$ROOT_DIR/infra/nginx/pamirnet.conf.template"
TARGET="/etc/nginx/sites-available/pamirnet"

[[ -f "$ENV_FILE" ]] || { echo "Missing $ENV_FILE" >&2; exit 1; }
[[ -f "$TEMPLATE" ]] || { echo "Missing Nginx template" >&2; exit 1; }

# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a
: "${PAMIRNET_DOMAIN:?PAMIRNET_DOMAIN is required}"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-8080}"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

sed \
  -e "s/__PAMIRNET_DOMAIN__/${PAMIRNET_DOMAIN//\//\\/}/g" \
  -e "s/__BACKEND_PORT__/$BACKEND_PORT/g" \
  -e "s/__FRONTEND_PORT__/$FRONTEND_PORT/g" \
  "$TEMPLATE" > "$TMP"

sudo install -m 0644 "$TMP" "$TARGET"
sudo ln -sfn "$TARGET" /etc/nginx/sites-enabled/pamirnet
sudo nginx -t
sudo systemctl reload nginx

echo "Installed $TARGET for $PAMIRNET_DOMAIN"
