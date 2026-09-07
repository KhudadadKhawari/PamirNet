#!/bin/sh
set -eu
FILE=/etc/freeradius/3.0/clients.d/pamirnet/pamirnet.conf
previous=""
while true; do
    current=$(sha256sum "$FILE" 2>/dev/null | awk '{print $1}' || true)
    if [ -n "$previous" ] && [ "$current" != "$previous" ]; then
        kill -HUP 1 2>/dev/null || true
    fi
    previous="$current"
    sleep 2
done
