# Load Testing

Phase 7 includes `scripts/loadtest_radius.py` for synthetic load against PamirNet's internal FreeRADIUS REST endpoints.

Do not run accounting load tests against the production AWKH tenant unless you intentionally want to create real session/accounting usage.

## Staging setup

Create an isolated tenant/router/subscriber, then run from a host that can reach the backend internal API.

Authorize-only example:

```bash
python scripts/loadtest_radius.py \
  --base-url http://127.0.0.1:8000 \
  --token "$RADIUS_INTERNAL_TOKEN" \
  --nas-ip 10.250.0.10 \
  --username 10000001 \
  --mode authorize \
  --requests 5000 \
  --workers 100
```

Mixed authorization/accounting example:

```bash
python scripts/loadtest_radius.py \
  --base-url http://127.0.0.1:8000 \
  --token "$RADIUS_INTERNAL_TOKEN" \
  --nas-ip 10.250.0.10 \
  --usernames-file migration-output/test-usernames.txt \
  --mode mixed \
  --requests 2000 \
  --workers 75
```

The harness reports:

- successful jobs
- HTTP request count
- failures
- elapsed time
- requests/sec
- mean/p50/p95/p99/max latency

## Initial acceptance targets

For the first ~1,000-subscriber deployment, validate on the actual VPS class before AWKH cutover:

- zero application errors during a 15-minute sustained test
- p95 internal authorize latency < 200 ms under expected peak load
- p99 internal authorize latency < 500 ms
- no PostgreSQL connection exhaustion
- no Redis/Celery instability
- accounting counters remain correct after concurrent interim updates
- FreeRADIUS remains responsive while analytics/dashboard queries are active

These are initial operational targets and should be revised using real AWKH traffic after deployment.

## Production observation after cutover

Load-test numbers do not replace real monitoring. During AWKH rollout watch:

- RADIUS request timeouts/rejects
- online session count
- hourly aggregate traffic
- API readiness
- PostgreSQL size/CPU/IO
- router latency and packet loss

Do not tune Gunicorn/Celery worker counts blindly. Measure first, then change `GUNICORN_WORKERS`, `GUNICORN_THREADS`, and `CELERY_CONCURRENCY` in `.env.production`.
