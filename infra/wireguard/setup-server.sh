#!/usr/bin/env bash
set -euo pipefail

WG_INTERFACE="${WG_INTERFACE:-wg0}"
WG_ADDRESS="${WG_ADDRESS:-10.250.0.1/16}"
WG_PORT="${WG_PORT:-51820}"
WG_PRIVATE_KEY="${WG_PRIVATE_KEY:?Set WG_PRIVATE_KEY to the VPS private key first}"

if [[ $EUID -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi

command -v wg >/dev/null || { echo "Install wireguard-tools first." >&2; exit 1; }
install -d -m 700 /etc/wireguard
cat >"/etc/wireguard/${WG_INTERFACE}.conf" <<EOF
[Interface]
Address = ${WG_ADDRESS}
ListenPort = ${WG_PORT}
PrivateKey = ${WG_PRIVATE_KEY}
SaveConfig = true
EOF
chmod 600 "/etc/wireguard/${WG_INTERFACE}.conf"
systemctl enable "wg-quick@${WG_INTERFACE}"
systemctl restart "wg-quick@${WG_INTERFACE}"
wg show "${WG_INTERFACE}"
