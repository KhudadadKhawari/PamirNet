# Phase 6 — Accounting, Sessions and Analytics

## Scope

Phase 6 turns FreeRADIUS accounting into PamirNet's live operational data plane.

Implemented:

- RADIUS `Start`, `Interim-Update` and `Stop` ingestion through `rlm_rest`
- tenant/NAS scoped session materialization
- 64-bit MikroTik accounting counters using octets + gigawords
- idempotent raw accounting-event storage
- subscriber and voucher quota-counter updates from accounting deltas
- hourly and daily usage aggregates
- online-session API and UI
- RADIUS CoA rate changes and Disconnect-Request controls on UDP 3799
- immediate subscriber package/status enforcement for live sessions
- live FUP enforcement after accounting updates
- tenant dashboard and custom-range analytics
- subscriber/voucher ranking and usage sorting
- persistent router latency, packet-loss and uptime samples
- 12-month raw accounting retention and 30-day router-health retention defaults

## Accounting flow

```text
MikroTik
  -> FreeRADIUS :1813
  -> pamirnet_rest accounting
  -> POST /api/internal/radius/accounting/
  -> RadiusAccountingEvent
  -> RadiusSession
  -> subscriber/voucher quota counters
  -> hourly/daily UsageAggregate
  -> effective policy evaluation
  -> CoA or Disconnect-Request when required
```

`Acct-Input-Octets` and `Acct-Output-Octets` are combined with the corresponding
Gigawords attributes before deltas are calculated. Retransmitted accounting packets
are deduplicated by an event fingerprint so usage cannot be counted twice.

## Live policy enforcement

Each active session stores the last applied MikroTik rate limit. After an accounting
update PamirNet recalculates the effective package/FUP policy:

- unchanged rate: no action
- changed rate: send CoA with `Mikrotik-Rate-Limit`
- blocked policy: send Disconnect-Request
- failed CoA: fall back to Disconnect-Request so re-authentication applies policy

Changing or renewing a subscriber package disconnects existing sessions immediately.
Disabling/suspending a subscriber also disconnects their active sessions.

MikroTik must accept incoming RADIUS CoA/Disconnect on UDP 3799 from the PamirNet VPS.
The same tenant router RADIUS secret is used for these requests.

## Storage

### `RadiusSession`

Materialized session state including username, identity, router, framed IP, MAC,
package/subscription reference, start/update/stop timestamps, cumulative bytes,
session duration and last control result.

### `RadiusAccountingEvent`

Append-only raw accounting records. Default retention is 365 days and is configurable
through `ACCOUNTING_RAW_RETENTION_DAYS`.

### `UsageAggregate`

Hourly and daily tenant/router/identity buckets containing upload, download, session
seconds and sample count. Aggregates are kept indefinitely in v1.

### `RouterHealthSample`

Historical router status, latency, packet loss and RouterOS uptime. Default retention
is 30 days through `ROUTER_HEALTH_RETENTION_DAYS`.

## Tenant APIs

```text
GET  /api/dashboard/
GET  /api/sessions/
GET  /api/sessions/{id}/
GET  /api/sessions/{id}/events/
POST /api/sessions/{id}/disconnect/
POST /api/sessions/{id}/refresh-policy/
GET  /api/analytics/usage/
GET  /api/analytics/identities/
GET  /api/network/routers/{id}/health-history/
```

Analytics endpoints accept custom `start`/`end` ISO timestamps. Usage series support
`hour` or `day` granularity. Identity analytics can filter subscribers/vouchers and
sort by total, upload, download or session time.

## Retention task

Celery Beat runs `accounting.cleanup_old_data` daily. It removes raw accounting events
older than the configured raw-retention period and router health samples older than
the configured health-retention period.

## Phase boundary

Phase 6 does not introduce PamirNet Edge. RADIUS, accounting and CoA remain central on
the VPS over the WireGuard-connected MikroTik network. Offline/local AAA remains a
future Edge capability.
