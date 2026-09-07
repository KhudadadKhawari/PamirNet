# Phase 2 — Networking, WireGuard and FreeRADIUS

Phase 2 adds the central networking control plane. PamirNet Edge remains deferred.

## Architecture

```text
MikroTik RouterOS 7+
  |  WireGuard (10.250.0.0/16)
  |-- RADIUS auth/accounting --> FreeRADIUS on PamirNet VPS
  |<-- CoA (future session phase) -- PamirNet
  `-- RouterOS API/REST <------ Django/Celery

PamirNet backend
  |-- router registry + encrypted credentials
  |-- WireGuard peer/config generator
  |-- FreeRADIUS client config renderer
  `-- 30-second health checks
```

## Router onboarding

1. Configure the VPS WireGuard server and set `WIREGUARD_SERVER_PUBLIC_KEY` + `WIREGUARD_ENDPOINT`.
2. In **Networking > Routers**, create the router using its RouterOS API credentials.
3. PamirNet allocates a unique tunnel address, generates a per-router WireGuard key and RADIUS secret, and returns a one-time RouterOS script.
4. Run the returned server peer command on the VPS and paste the RouterOS script into the MikroTik terminal.
5. Use **Test connection** in PamirNet. Successful tests capture RouterOS version, uptime, latency and application-level packet loss.

The generated MikroTik configuration enables Hotspot and PPP RADIUS usage, one-minute accounting interim updates, RADIUS incoming/CoA on UDP 3799, and restricts the selected management API service to the PamirNet WireGuard server IP.

## FreeRADIUS clients

Django stores RouterOS API credentials and RADIUS secrets encrypted at rest. For FreeRADIUS runtime use, enabled router RADIUS client definitions are rendered into the shared `pamirnet.conf` file. The FreeRADIUS reloader watches the file and sends HUP after changes.

Subscriber authentication policies are intentionally Phase 3; Phase 2 establishes trusted NAS connectivity and the RADIUS runtime.

## WireGuard server setup

Generate a VPS key pair:

```bash
cd backend
python manage.py wireguard_server_keys
```

Store the private key outside PamirNet and place only the public key in the application environment. On an Ubuntu VPS:

```bash
sudo apt install wireguard-tools
sudo WG_PRIVATE_KEY='<private-key>' \
  WG_ADDRESS='10.250.0.1/16' \
  WG_PORT=51820 \
  ./infra/wireguard/setup-server.sh
```

Open UDP/51820 on the VPS firewall. RADIUS UDP/1812 and UDP/1813 should only be reachable through the WireGuard path/firewall policy in production.

## RouterOS compatibility

WireGuard requires RouterOS 7+. Legacy RouterOS API (`8728`) is the default management protocol because the traffic is already encrypted by WireGuard. API-SSL and REST are also supported. REST requires RouterOS 7 and HTTPS (`www-ssl`).

## Secrets

Set a dedicated `PAMIRNET_ENCRYPTION_KEY` in production. Do not rely on the development fallback derived from `DJANGO_SECRET_KEY`.
