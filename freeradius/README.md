# PamirNet FreeRADIUS

Phase 3 connects FreeRADIUS authorization to the PamirNet API through `rlm_rest`.

The NAS is identified by `Packet-Src-IP-Address`, which is the MikroTik WireGuard tunnel IP. PamirNet uses that router to resolve the tenant, so the same subscriber username may exist in different tenants.

The authorize hook returns:

- `control:Cleartext-Password`
- `control:Simultaneous-Use`
- `reply:Mikrotik-Rate-Limit`
- `reply:Session-Timeout`
- `reply:Acct-Interim-Interval`

The post-auth hook records successful authentication and implements `bind on first login` MAC locking.

`RADIUS_INTERNAL_TOKEN` must match between the FreeRADIUS and backend containers. Do not expose the internal authorize endpoints outside the application network.
