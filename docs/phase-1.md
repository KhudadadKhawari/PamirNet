# Phase 1 — Identity, Tenancy and RBAC

Phase 1 establishes PamirNet's control-plane identity model before subscriber/RADIUS work begins.

## Authentication

- Django application users
- email/password login
- 15-minute JWT access token
- 7-day refresh token in an HttpOnly SameSite=Lax cookie
- refresh and logout endpoints
- refresh-token blacklist on logout
- tenant context embedded in server-issued JWT claims

Endpoints:

```text
POST /api/auth/login/
POST /api/auth/refresh/
POST /api/auth/logout/
GET  /api/auth/me/
```

A user with access to more than one tenant must select a tenant during login. Platform administrators log in without tenant context and enter tenants only through audited impersonation.

## Tenancy

One tenant represents one ISP/company. Tenant-owned API resources are resolved from the authenticated token and filtered server-side. Suspended tenants are rejected immediately even when a previously issued token has not expired.

Tenant settings currently include:

- name
- slug
- status
- timezone
- currency

Tenant users may edit name, timezone and currency. Tenant status remains platform-controlled.

## RBAC

Each new tenant is bootstrapped with a system `Owner` role. The Owner role receives every PamirNet permission. Custom roles are tenant-owned and can be assigned any subset of the permission catalog.

The last active Owner cannot be disabled or stripped of the Owner role. Non-Owners cannot grant or remove the Owner role even if they have general user-management permission.

Current permission catalog:

```text
dashboard.view
subscriber.view
subscriber.create
subscriber.edit
subscriber.disable
package.view
package.manage
voucher.view
voucher.generate
voucher.export
voucher.disable
session.view
session.disconnect
router.view
router.manage
analytics.view
role.manage
user.manage
audit.view
settings.manage
```

Tenant endpoints:

```text
GET/PATCH        /api/tenant/
GET              /api/permissions/
GET/POST         /api/roles/
GET/PATCH/DELETE /api/roles/{id}/
GET/POST         /api/users/
GET/PATCH/DELETE /api/users/{id}/
GET              /api/audit/
```

## Platform administration

Django superusers act as PamirNet platform administrators.

Platform endpoints:

```text
GET/POST  /api/platform/tenants/
GET/PATCH /api/platform/tenants/{id}/
POST      /api/platform/tenants/{id}/impersonate/
POST      /api/platform/impersonation/stop/
GET       /api/platform/audit/
```

Tenant creation bootstraps the first Owner user and Owner role in one transaction.

## Impersonation

Impersonation creates a database session and issues a short-lived tenant-scoped access token. The session is validated on every impersonated request. Starting and ending impersonation are audited, and actions performed while impersonating retain the impersonation session reference.

## Audit

Audit records contain:

- tenant
- actor
- impersonation session when applicable
- action
- target type/id
- source IP
- before/after JSON
- metadata
- timestamp

Application API and Django admin mutation of audit records is blocked. Database-level append-only hardening can be added during production hardening.

## UI foundation

The React application now includes:

- login flow
- refresh-cookie bootstrap
- tenant dashboard shell
- Janitor-familiar sidebar structure
- platform tenant list
- audited impersonation entry/exit flow

Detailed Users/Roles management screens remain part of the continuing Phase 1 UI work.
