# Phase 3 — Packages, Subscribers, Subscriptions and RADIUS Authorization

## Scope

Phase 3 makes PamirNet an actual subscriber AAA control plane. It intentionally does not add accounting/session history, CoA, quota/FUP enforcement or vouchers; those remain later phases.

## Domain

### Package

A tenant owns its own packages. A package defines:

- name/description
- calendar duration (`day`, `week`, `month`)
- maximum download/upload speed in Mbps
- optional informational price in the tenant currency
- simultaneous session preference
- enabled/disabled state

Quota and multi-stage FUP policies are added in Phase 5.

### Subscriber

Required: name.

Optional: phone, address, notes, package, status and MAC lock.

Credentials are separate from the subscriber profile and encrypted at rest. Usernames are unique only within a tenant. If username/password are omitted during creation, PamirNet generates an 8-digit numeric username and a 12-character password. Generated passwords are returned once.

### Subscription

Package assignment creates a subscription period. Package changes close the previous active subscription and start a new period immediately. Renewal starts a new period and preserves previous subscription records.

Daily quota reset rules are not part of Phase 3. Calendar expiration uses the selected package duration; month durations preserve the activation day where possible.

## RADIUS authorization

```text
MikroTik over WireGuard
        |
        | Access-Request
        v
FreeRADIUS
        |
        | rlm_rest (internal Docker network)
        v
PamirNet /api/internal/radius/authorize/
        |
        +-- Packet-Src-IP-Address -> Router -> Tenant
        +-- tenant + User-Name -> SubscriberCredential
        +-- subscriber status
        +-- active subscription / expiration
        +-- package enabled
        +-- MAC lock
        v
FreeRADIUS reply attributes
```

The backend returns `Cleartext-Password` to FreeRADIUS only at authorization time. The credential remains encrypted in PostgreSQL. FreeRADIUS performs PAP/CHAP validation using its standard modules.

Successful authorization returns:

- `control:Cleartext-Password`
- `control:Simultaneous-Use`
- `reply:Mikrotik-Rate-Limit` (`upload/download`)
- `reply:Session-Timeout`
- `reply:Acct-Interim-Interval = 60`

Unknown/disabled/expired subscribers return `Auth-Type = Reject`.

## Tenant isolation

The NAS source tunnel IP is authoritative for tenant resolution. Therefore identical usernames can safely exist in different ISPs:

```text
Router 10.250.0.10 -> AWKH -> username 42424242
Router 10.250.0.20 -> Other ISP -> username 42424242
```

No tenant identifier is accepted from the subscriber.

## MAC locking

Modes:

- `none`
- `manual`
- `first_login`

For `first_login`, authorization does not bind the MAC before password validation. The FreeRADIUS post-auth hook records the MAC only after a successful authentication. Later requests from a different MAC are rejected.

## Internal API security

FreeRADIUS authenticates to the backend with `X-PamirNet-Radius-Token`. Set a long random `RADIUS_INTERNAL_TOKEN` in production and keep the internal endpoints reachable only from the application network.

## Expiration

Celery Beat checks expired subscriptions every minute. Authorization also performs expiration checks synchronously so expired access cannot continue merely because the periodic task is delayed.

## Phase 4 boundary

Phase 4 adds RADIUS accounting/session records, live-session visibility, CoA/disconnect and immediate enforcement against already-connected sessions.
