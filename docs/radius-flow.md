# RADIUS Flow

FreeRADIUS integration is implemented after Phase 0. This document defines the intended behavior so the application model does not drift toward FreeRADIUS-specific schema.

## Tenant resolution

Subscriber/voucher usernames are unique inside a tenant, not globally.

```text
Access-Request
  -> identify NAS/router by tunnel IP / NAS record
  -> resolve tenant
  -> resolve username inside tenant
  -> resolve Subscriber or Voucher identity
```

This allows two ISPs to use the same numeric username safely.

## Authentication checks

Before Access-Accept, PamirNet/FreeRADIUS policy must evaluate:

- credential validity
- identity status
- subscription/voucher activation and expiry
- MAC lock for subscribers
- simultaneous sessions
- active quota/FUP stages

## Reply policy

Replies may include MikroTik attributes such as rate limits, session timeout and accounting interim interval.

The initial target accounting interval is 60 seconds.

## Voucher first activation

The first successful login atomically moves a voucher from Generated to Active and calculates its expiry from the assigned package duration.

## Accounting

MikroTik sends Start, Interim-Update and Stop records. Accounting drives:

- online session state
- subscriber/voucher usage
- FUP/quota enforcement
- analytics aggregation

Raw accounting is retained for 12 months; aggregates are retained long-term.

## CoA / Disconnect

Immediate package/status/policy changes will trigger CoA where supported. If a policy cannot be applied safely in-session, PamirNet may disconnect the session and require re-authentication.

## Data model boundary

PamirNet business tables are authoritative. Standard FreeRADIUS tables/views may be used as an integration projection, but product logic must not be designed around `radcheck`/`radreply` as primary domain models.
