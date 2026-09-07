# Security Baseline

Phase 0 establishes security constraints that later implementation must preserve.

## Tenant isolation

- every tenant-owned resource is scoped to a tenant
- request handlers must never trust a tenant identifier supplied by the client when tenant context can be derived from authentication
- object-level authorization is mandatory
- PostgreSQL RLS is planned as defense-in-depth after tenant models are implemented

## Credentials

Application user passwords use Django's password hashing.

RADIUS subscriber/voucher credentials may need reversible access depending on the selected RADIUS authentication method. They must therefore be encrypted at rest with keys separated from database data and never logged in plaintext.

## Router connectivity

- MikroTik API/REST must not be exposed publicly
- SaaS routers communicate through WireGuard
- RADIUS shared secrets and router credentials are secrets
- management credentials must be encrypted at rest
- CoA/RADIUS traffic remains private to the management network

## Platform administration

Tenant impersonation is explicit and audited. The UI must clearly show when a platform administrator is impersonating a tenant.

## Audit

Sensitive create/update/delete/disable/impersonate/disconnect/export operations should be recorded with actor, tenant, source IP, timestamp and before/after state when practical.

Audit entries are append-only to application users.

## API

- HTTPS only in production
- secure cookies/tokens in later auth phase
- CORS allowlist, never wildcard in production
- rate limiting added before public deployment
- OpenAPI schema is maintained as part of the codebase

## Deployment

- secrets stay outside Git
- containers run with minimum required privileges
- database and Redis are private services
- production DEBUG is disabled
- backups and restore tests are required before AWKH production migration

## Deferred Edge consideration

Future PamirNet Edge will require signed/authenticated synchronization and local secret protection, but Edge is out of scope for v1 implementation.
