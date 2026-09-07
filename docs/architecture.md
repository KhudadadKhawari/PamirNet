# PamirNet Architecture

## Scope

PamirNet v1 is a centrally hosted multi-tenant ISP operations platform. One tenant represents one ISP/company. Tenant data is isolated from all other tenants. A self-hosted deployment represents a single ISP.

PamirNet Edge is intentionally deferred. The v1 architecture must not prevent adding a local Edge component later.

## v1 topology

```text
Browser
  |
  v
PamirNet Web (React)
  |
  v
PamirNet API (Django/DRF)
  |---- PostgreSQL
  |---- Redis / Celery
  |---- FreeRADIUS (future phase)
  |
  +---- WireGuard ---- MikroTik routers
                       |-- Hotspot
                       `-- PPPoE
```

## Components

### Backend

Django + DRF is the system of record for tenants, users, roles, routers, subscribers, packages, vouchers, subscriptions, audit logs and analytics metadata.

### Frontend

React + TypeScript provides an operations-first UI. The target UX is simple, dense and familiar to operators currently using Janitor RADIUS without cloning that interface.

### Database

PostgreSQL is the authoritative data store. All tenant-owned business records will carry tenant ownership and application queries must enforce tenant scoping. PostgreSQL RLS is planned as defense-in-depth once tenant models land.

### Async processing

Redis + Celery handles work that should not block API requests, such as CoA/disconnect actions, exports, aggregation and router checks.

### FreeRADIUS

FreeRADIUS will provide Hotspot and PPPoE AAA. PamirNet business models remain authoritative; FreeRADIUS-specific tables/views are an integration layer rather than the product domain model.

### Router connectivity

MikroTik routers will connect to the central VPS over WireGuard. RADIUS, RouterOS API/REST and CoA traffic stay on the private tunnel.

## Architectural principles

- modular monolith for the central application
- API-first backend
- tenant isolation by default
- no public MikroTik management APIs
- business domain independent from FreeRADIUS schema
- append-only audit history for sensitive actions
- aggregate analytics for dashboard performance
- future Edge support through replaceable RADIUS/network integration boundaries

## Deferred

- PamirNet Edge / offline AAA
- billing and payments
- notifications
- KYC
- DHCP/IPoE management
- advanced MikroTik shaping fields
- multi-site tenant hierarchy
