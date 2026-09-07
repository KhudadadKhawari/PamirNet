# PamirNet Domain Model

This document captures the agreed v1 domain before implementation.

## Tenancy

- one tenant = one ISP/company
- no branches/sites inside a tenant
- tenant-owned data is isolated
- SaaS supports many tenants
- self-hosted mode represents one ISP

## Platform administration

Platform administrators can manage tenants and use audited tenant impersonation for support.

## Tenant users and RBAC

Each tenant starts with an Owner. The Owner can create custom roles and choose granular permissions. The last Owner cannot remove their own Owner access.

Planned permission groups include subscribers, packages, vouchers, routers, sessions, analytics, audit, roles/users and tenant settings.

## Router

A tenant can register multiple MikroTik routers/NAS devices. Routers provide the RADIUS NAS identity used to resolve the tenant during authentication.

## Subscriber

Required:

- name

Optional:

- phone
- address
- notes
- package/subscription
- expiry
- status
- MAC lock

Statuses:

- Active
- Disabled
- Expired
- Suspended
- Quota Exhausted

Subscriber credentials may be manually selected or generated.

MAC locking modes:

- none
- manually configured MAC
- bind on first login

## Package

A package contains:

- name/description
- duration
- base download/upload maximum speed
- optional informational price and tenant currency
- simultaneous-session limit
- zero or more usage/FUP policies

Duration is calendar duration from activation.

Changing a subscriber package takes effect immediately.

## Usage/FUP policy

Policies can independently apply to:

- daily usage
- weekly usage
- monthly usage
- current subscription-period usage

Usage is upload + download combined.

Each policy may contain multiple threshold stages. A stage can throttle to a new up/down speed or block access. When multiple policies are active, the most restrictive effective speed wins.

Daily counters reset at tenant-local midnight. Weekly and monthly periods are relative to subscription activation. Subscription-period counters reset on renewal.

## Subscription

Package assignment is represented by a subscription period rather than overwritten directly on the subscriber. Renewal starts a new period and resets quota/FUP counters.

## Voucher batch

A batch defines package, quantity, simultaneous sessions and credential generation settings.

Defaults:

- numeric username: 8 digits
- numeric password: 6 digits
- activation: first successful login
- no MAC locking

Vouchers support CSV export and bulk status management.

Voucher lifecycle:

```text
Generated -> Active -> Consumed/Expired
     |          |
     +----------+-> Disabled
```

## RADIUS session/accounting

Raw sessions retain login/logout, router, IP, MAC, byte counters and termination reason. Raw accounting is retained for 12 months. Hourly/daily aggregates are retained long-term.

## Router health

v1 monitoring includes:

- reachability
- latency
- packet loss
- uptime

## Audit log

Sensitive actions record actor, tenant, action, timestamp, source IP and relevant before/after state. Audit records are append-only.
