# Production Deployment

PamirNet v1 runs centrally on a VPS. MikroTik routers reach the VPS over WireGuard; PamirNet Edge/offline AAA remains a future component.

## Host requirements

- Ubuntu 24.04 LTS or equivalent
- Docker Engine + Docker Compose v2
- WireGuard
- Nginx
- Certbot
- DNS A/AAAA record for the PamirNet domain
- TCP 80/443 open publicly
- UDP 51820 open publicly for WireGuard
- RADIUS UDP 1812/1813 bound only to the WireGuard server IP
- SSH restricted to administrator source addresses/keys

Recommended starting size for the current ~1,000-subscriber target: 4 vCPU, 8 GB RAM, 80+ GB SSD. Increase storage based on accounting retention and backup volume.

## 1. Prepare the host

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2 wireguard nginx certbot python3-certbot-nginx
sudo systemctl enable --now docker nginx
sudo usermod -aG docker "$USER"
```

Log out/in after adding the Docker group.

## 2. Configure PamirNet

```bash
git clone https://github.com/KhudadadKhawari/PamirNet.git
cd PamirNet
cp .env.production.example .env.production
chmod 600 .env.production
```

Generate secrets independently:

```bash
openssl rand -hex 48                      # DJANGO_SECRET_KEY
openssl rand -hex 48                      # POSTGRES_PASSWORD
openssl rand -hex 48                      # REDIS_PASSWORD
openssl rand -hex 48                      # RADIUS_INTERNAL_TOKEN
python3 - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
```

`PAMIRNET_ENCRYPTION_KEY` is critical. Losing it makes stored subscriber/RADIUS/router credentials undecryptable. Store a protected copy outside the VPS.

## 3. Configure WireGuard

Use the existing PamirNet WireGuard tooling under `infra/wireguard/` and the Phase 2 router onboarding flow. The VPS should own the configured server address, normally `10.250.0.1/16`.

Verify:

```bash
sudo wg show
ip addr show wg0
```

Set in `.env.production`:

```text
WIREGUARD_SERVER_ADDRESS=10.250.0.1/16
RADIUS_BIND_IP=10.250.0.1
WIREGUARD_ENDPOINT=<public-vps-ip>:51820
```

Never set `RADIUS_BIND_IP=0.0.0.0` on the public VPS.

## 4. Obtain TLS certificate

Before installing the final PamirNet Nginx config:

```bash
sudo certbot certonly --nginx -d pamirnet.example.com
```

Replace the example domain with the production value configured as `PAMIRNET_DOMAIN`.

## 5. Install reverse proxy

```bash
bash scripts/install-nginx-config.sh
```

The generated host Nginx configuration:

- terminates TLS
- redirects HTTP to HTTPS
- rate-limits login requests
- proxies `/api/`, `/admin/` and `/static/` to Django
- proxies the React application to the frontend container
- adds baseline security headers

## 6. Deploy

```bash
bash scripts/deploy-production.sh
```

The deployment script:

1. validates Docker Compose
2. builds production images
3. starts PostgreSQL/Redis
4. runs `production_preflight`
5. runs Django deploy checks
6. validates FreeRADIUS configuration
7. takes a pre-deployment backup when replacing a running installation
8. starts the full stack
9. waits for `/api/ready/`

## 7. Verify

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml ps
curl -fsS https://pamirnet.example.com/api/health/
curl -fsS https://pamirnet.example.com/api/ready/
sudo wg show
sudo ss -lunp | grep -E ':1812|:1813|:51820'
```

RADIUS 1812/1813 should be reachable through WireGuard only.

## Updates

```bash
git pull --ff-only
bash scripts/deploy-production.sh
```

Always retain the pre-deployment backup until the new release has been verified with real authentication/accounting traffic.

## Rollback

Application rollback:

```bash
git checkout <previous-good-sha>
bash scripts/deploy-production.sh
```

If the release included an incompatible data migration, restore the pre-deployment database backup using `scripts/restore-production.sh` after checking the migration's reversibility.
