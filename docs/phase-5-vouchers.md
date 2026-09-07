# Phase 5 — Vouchers

Status: complete

## Scope

Phase 5 adds tenant-isolated numeric voucher batches for MikroTik Hotspot/PPPoE authentication through the existing central FreeRADIUS integration.

## Voucher batches

- tenant-scoped batch name and package
- bulk quantity generation
- 8-digit numeric usernames
- 6-digit numeric passwords
- encrypted password storage
- configurable simultaneous sessions: 1, 2, 3 or unlimited
- generated-by audit metadata
- batch status counts
- bulk disable
- deletion only while the complete batch is unused
- authenticated CSV export containing printable credentials

## Voucher lifecycle

```text
Generated -> Active -> Expired
                   -> Consumed
Generated/Active -> Disabled
```

Activation occurs only after a successful RADIUS post-auth event. The package duration starts at that activation timestamp.

## RADIUS behavior

The NAS identifies the tenant. PamirNet resolves a username against subscriber credentials first and then vouchers. Subscriber and voucher usernames are prevented from colliding inside a tenant.

Generated and active vouchers return:

- `Cleartext-Password`
- `Mikrotik-Rate-Limit`
- `Session-Timeout`
- `Acct-Interim-Interval=60`
- `Simultaneous-Use` unless the batch is unlimited

Vouchers do not use MAC locking.

## Quota/FUP integration

Voucher usage counters support the same package policy scopes introduced in Phase 4:

- daily, reset at tenant-local midnight
- weekly, relative to voucher activation
- monthly, relative to voucher activation
- full voucher subscription period

The most restrictive matching policy applies. A subscription-period hard block marks the voucher consumed. Shorter-period blocks reject authentication until their usage period resets.

Actual RADIUS Start/Interim/Stop ingestion that advances these counters automatically is part of Phase 6.

## Operations

A Celery Beat task marks active vouchers expired when their package duration ends. Voucher batch generation, disable, deletion and CSV export are audited.
