# Phase 4 — Packages and Policy Engine

Status: complete

## Scope

Phase 4 adds usage-aware package policy enforcement on top of the Phase 3 subscriber and RADIUS flow.

## Package policies

A package may define at most one policy for each usage scope:

- `daily`
- `weekly`
- `monthly`
- `subscription`

Each policy contains one or more threshold stages. Thresholds use combined upload + download usage and are configured in decimal GB.

Stage actions:

- `throttle`: lower effective download/upload speed
- `block`: reject authentication once the threshold is reached

Multiple scopes may be active at the same time. PamirNet calculates the effective speed by taking the most restrictive download and upload values from all currently matched stages. Any matched block stage wins over throttling.

## Counter periods

`SubscriptionUsageCounter` tracks independent counters for each scope.

- daily: reset at tenant-local midnight
- weekly: 7-day windows relative to subscription activation
- monthly: calendar-month windows relative to subscription activation
- subscription: full current subscription period

Counters belong to a subscription, so renewals and immediate package changes naturally start a fresh set of usage periods.

## Policy engine

`subscribers.policy.calculate_effective_policy()` returns:

- effective download speed
- effective upload speed
- whether access is blocked
- matched policy stages
- current usage and period bounds for each configured scope

`record_usage_delta()` is the single write path for adding combined RADIUS usage to all scopes. Phase 6 accounting ingestion will feed Start/Interim/Stop deltas into this function.

## RADIUS behavior

Authorization now evaluates the effective package policy before returning MikroTik attributes.

- no matched stage: package base speed is returned
- throttle stage: `Mikrotik-Rate-Limit` contains the effective reduced speed
- block stage: authentication is rejected and subscriber status becomes `quota_exhausted`
- when a rolling quota resets and the subscriber is no longer blocked, a later authorization restores the subscriber to `active`

The subscriber endpoint also exposes:

`GET /api/subscribers/{id}/effective-policy/`

This is intended for operations/debugging and returns current usage, matched stages and effective access policy.

## UI

The Packages page includes an FUP/quota editor supporting all four scopes and multiple stages per scope.

## Phase boundary

Phase 4 provides the policy model, counters, calculation and RADIUS enforcement path. Full RADIUS accounting ingestion, historical session retention and analytics remain Phase 6.
