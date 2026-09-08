# Security Hardening Baseline

## Network exposure

Publicly expose only:

- TCP 80/443: Nginx
- UDP 51820: WireGuard
- SSH: restricted administrator source addresses where practical

Do not publicly expose:

- PostgreSQL 5432
- Redis 6379
- Django/Gunicorn 8000
- frontend container 8080
- MikroTik API/REST
- RADIUS 1812/1813

RADIUS must bind to the WireGuard server address and MikroTik management must traverse WireGuard.

## VPS firewall example

Adjust the SSH source before applying:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from <ADMIN_IP>/32 to any port 22 proto tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 51820/udp
sudo ufw allow in on wg0 to any port 1812 proto udp
sudo ufw allow in on wg0 to any port 1813 proto udp
sudo ufw enable
```

CoA/Disconnect traffic is sent from PamirNet to MikroTik UDP 3799 over WireGuard.

## Application controls

Phase 7 enables:

- production-only secure cookies
- HTTPS redirect
- HSTS
- trusted-origin CSRF configuration
- explicit `ALLOWED_HOSTS`
- `X-Frame-Options: DENY`
- `nosniff`
- same-origin referrer policy
- login throttling in DRF and Nginx
- non-root Django/Celery production containers
- loopback-only web container publishing
- authenticated internal FreeRADIUS REST API
- encrypted RADIUS/router credentials at rest
- append-only operational audit records
- production preflight validation

## Secret handling

Required production secrets:

- `DJANGO_SECRET_KEY`
- `POSTGRES_PASSWORD`
- `REDIS_PASSWORD`
- `PAMIRNET_ENCRYPTION_KEY`
- `RADIUS_INTERNAL_TOKEN`
- WireGuard private key
- MikroTik credentials/RADIUS secrets stored encrypted by PamirNet

Rules:

- `.env.production` mode `0600`
- no secrets in GitHub issues, PRs, CI logs or screenshots
- keep `PAMIRNET_ENCRYPTION_KEY` in a separate protected backup
- rotate router RADIUS/API credentials after suspected disclosure
- rotate platform/user passwords after account compromise

## MikroTik management

For every managed router:

- allow RADIUS only from PamirNet WireGuard IP
- allow CoA UDP 3799 only from PamirNet WireGuard IP
- restrict RouterOS API/API-SSL/REST to the WireGuard management range
- disable Telnet/FTP/API variants that are not required
- restrict Winbox/SSH management to trusted management networks
- use unique RADIUS secrets per router

Do not repeat the existing broad management exposure found on legacy ISP routers.

## Host hardening

Recommended baseline:

```bash
sudo apt update && sudo apt full-upgrade -y
sudo systemctl enable --now unattended-upgrades
sudo sshd -T | grep -E 'passwordauthentication|permitrootlogin'
```

Target SSH configuration:

```text
PasswordAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
```

Use a non-root sudo administrator and preserve a tested recovery path before changing SSH.

## Validation

Before each production deployment:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm backend python manage.py production_preflight
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm backend python manage.py check --deploy
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm freeradius freeradius -XC
```

After deployment:

```bash
curl -fsS https://<domain>/api/health/
curl -fsS https://<domain>/api/ready/
sudo ss -lntup
sudo wg show
```

Review audit logs and authentication failures during the first hours after cutover.
