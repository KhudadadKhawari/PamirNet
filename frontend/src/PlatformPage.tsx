import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import {
  apiErrorMessage,
  request,
  type AuditLog,
  type Me,
  type PlatformUser,
  type TenantSummary,
} from "./api";

type PlatformTab = "tenants" | "users" | "audit";

type PlatformPageProps = {
  access: string;
  me: Me;
  onAccessChanged: (access: string) => Promise<void>;
  onLogout: () => Promise<void>;
};

export function PlatformPage({ access, me, onAccessChanged, onLogout }: PlatformPageProps) {
  const [tab, setTab] = useState<PlatformTab>("tenants");

  return (
    <main className="min-h-screen bg-slate-100 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="flex items-center justify-between px-6 py-4">
          <div>
            <div className="font-bold">PamirNet Platform</div>
            <div className="text-xs text-slate-500">{me.email}</div>
          </div>
          <button className="rounded border border-slate-300 px-3 py-1.5 text-sm" onClick={onLogout}>
            Sign out
          </button>
        </div>
        <nav className="flex gap-1 px-6">
          {(["tenants", "users", "audit"] as PlatformTab[]).map((item) => (
            <button
              key={item}
              className={`border-b-2 px-4 py-3 text-sm font-medium capitalize ${
                tab === item
                  ? "border-slate-900 text-slate-900"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
              onClick={() => setTab(item)}
            >
              {item}
            </button>
          ))}
        </nav>
      </header>

      <section className="mx-auto max-w-7xl p-6">
        {tab === "tenants" && (
          <TenantsPanel access={access} onAccessChanged={onAccessChanged} />
        )}
        {tab === "users" && <PlatformUsersPanel access={access} />}
        {tab === "audit" && <PlatformAuditPanel access={access} />}
      </section>
    </main>
  );
}

function TenantsPanel({
  access,
  onAccessChanged,
}: {
  access: string;
  onAccessChanged: (access: string) => Promise<void>;
}) {
  const [tenants, setTenants] = useState<TenantSummary[]>([]);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState<TenantSummary | null>(null);

  const loadTenants = useCallback(async () => {
    try {
      setTenants(await request<TenantSummary[]>("/platform/tenants/", {}, access));
      setError("");
    } catch (rawError) {
      setError(apiErrorMessage(rawError, "Unable to load tenants."));
    }
  }, [access]);

  useEffect(() => {
    void loadTenants();
  }, [loadTenants]);

  async function impersonate(tenant: TenantSummary) {
    try {
      const result = await request<{ access: string }>(
        `/platform/tenants/${tenant.id}/impersonate/`,
        {
          method: "POST",
          body: JSON.stringify({ reason: "Platform administration" }),
        },
        access,
      );
      await onAccessChanged(result.access);
    } catch (rawError) {
      setError(apiErrorMessage(rawError, "Unable to impersonate tenant."));
    }
  }

  async function toggleTenant(tenant: TenantSummary) {
    try {
      await request<TenantSummary>(
        `/platform/tenants/${tenant.id}/`,
        {
          method: "PATCH",
          body: JSON.stringify({ status: tenant.status === "active" ? "suspended" : "active" }),
        },
        access,
      );
      await loadTenants();
    } catch (rawError) {
      setError(apiErrorMessage(rawError, "Unable to update tenant."));
    }
  }

  return (
    <div>
      <PanelHeader
        title="Tenants"
        description="Create ISPs, manage status and enter support sessions."
        actionLabel={showCreate ? "Cancel" : "Create tenant"}
        onAction={() => setShowCreate((value) => !value)}
      />
      {error && <ErrorBanner text={error} />}
      {showCreate && (
        <CreateTenantForm
          access={access}
          onCreated={async () => {
            setShowCreate(false);
            await loadTenants();
          }}
        />
      )}
      {editing && (
        <EditTenantForm
          access={access}
          tenant={editing}
          onCancel={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null);
            await loadTenants();
          }}
        />
      )}

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="px-4 py-3">ISP</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Timezone</th>
              <th className="px-4 py-3">Currency</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {tenants.map((tenant) => (
              <tr key={tenant.id} className="border-t border-slate-100">
                <td className="px-4 py-3">
                  <div className="font-medium">{tenant.name}</div>
                  <div className="text-xs text-slate-500">{tenant.slug}</div>
                </td>
                <td className="px-4 py-3">
                  <StatusPill active={tenant.status === "active"} text={tenant.status} />
                </td>
                <td className="px-4 py-3">{tenant.timezone}</td>
                <td className="px-4 py-3">{tenant.currency}</td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-2">
                    <button className="rounded border border-slate-300 px-3 py-1.5" onClick={() => setEditing(tenant)}>
                      Edit
                    </button>
                    <button className="rounded border border-slate-300 px-3 py-1.5" onClick={() => void toggleTenant(tenant)}>
                      {tenant.status === "active" ? "Suspend" : "Reactivate"}
                    </button>
                    <button
                      className="rounded border border-slate-300 px-3 py-1.5 disabled:opacity-50"
                      disabled={tenant.status !== "active"}
                      onClick={() => void impersonate(tenant)}
                    >
                      Impersonate
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {tenants.length === 0 && <EmptyRow columns={5} text="No tenants yet." />}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CreateTenantForm({ access, onCreated }: { access: string; onCreated: () => Promise<void> }) {
  const [form, setForm] = useState({
    name: "",
    slug: "",
    timezone: "Asia/Kabul",
    currency: "AFN",
    owner_email: "",
    owner_name: "",
    owner_password: "",
  });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await request<TenantSummary>(
        "/platform/tenants/",
        { method: "POST", body: JSON.stringify(form) },
        access,
      );
      await onCreated();
    } catch (rawError) {
      setError(apiErrorMessage(rawError, "Unable to create tenant."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className="mb-5 rounded-lg border border-slate-200 bg-white p-5">
      <h2 className="mb-1 font-semibold">Create tenant</h2>
      <p className="mb-4 text-sm text-slate-500">
        The initial Owner is created here. Additional platform-assigned users automatically become Tenant Admins.
      </p>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <InputField label="ISP name" value={form.name} onChange={(value) => setForm({ ...form, name: value })} required />
        <InputField label="Slug" value={form.slug} onChange={(value) => setForm({ ...form, slug: slugify(value) })} required />
        <InputField label="Timezone" value={form.timezone} onChange={(value) => setForm({ ...form, timezone: value })} required />
        <InputField label="Currency" value={form.currency} onChange={(value) => setForm({ ...form, currency: value.toUpperCase() })} required />
        <InputField label="Owner email" type="email" value={form.owner_email} onChange={(value) => setForm({ ...form, owner_email: value })} required />
        <InputField label="Owner name (new user)" value={form.owner_name} onChange={(value) => setForm({ ...form, owner_name: value })} />
        <InputField label="Owner password (new user)" type="password" value={form.owner_password} onChange={(value) => setForm({ ...form, owner_password: value })} />
      </div>
      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      <button className="mt-4 rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60" disabled={submitting}>
        {submitting ? "Creating…" : "Create tenant"}
      </button>
    </form>
  );
}

function EditTenantForm({
  access,
  tenant,
  onCancel,
  onSaved,
}: {
  access: string;
  tenant: TenantSummary;
  onCancel: () => void;
  onSaved: () => Promise<void>;
}) {
  const [form, setForm] = useState({
    name: tenant.name,
    status: tenant.status,
    timezone: tenant.timezone,
    currency: tenant.currency,
  });
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await request<TenantSummary>(
        `/platform/tenants/${tenant.id}/`,
        { method: "PATCH", body: JSON.stringify(form) },
        access,
      );
      await onSaved();
    } catch (rawError) {
      setError(apiErrorMessage(rawError, "Unable to update tenant."));
    }
  }

  return (
    <form onSubmit={submit} className="mb-5 rounded-lg border border-slate-200 bg-white p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-semibold">Edit {tenant.name}</h2>
        <button type="button" className="text-sm underline" onClick={onCancel}>Cancel</button>
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <InputField label="Name" value={form.name} onChange={(value) => setForm({ ...form, name: value })} required />
        <label className="block text-sm font-medium">
          Status
          <select className="input mt-1" value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>
            <option value="active">Active</option>
            <option value="suspended">Suspended</option>
          </select>
        </label>
        <InputField label="Timezone" value={form.timezone} onChange={(value) => setForm({ ...form, timezone: value })} required />
        <InputField label="Currency" value={form.currency} onChange={(value) => setForm({ ...form, currency: value.toUpperCase() })} required />
      </div>
      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      <button className="mt-4 rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white">Save changes</button>
    </form>
  );
}

function PlatformUsersPanel({ access }: { access: string }) {
  const [users, setUsers] = useState<PlatformUser[]>([]);
  const [tenants, setTenants] = useState<TenantSummary[]>([]);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [assigning, setAssigning] = useState<PlatformUser | null>(null);
  const [editing, setEditing] = useState<PlatformUser | null>(null);

  const load = useCallback(async () => {
    try {
      const [userData, tenantData] = await Promise.all([
        request<PlatformUser[]>("/platform/users/", {}, access),
        request<TenantSummary[]>("/platform/tenants/", {}, access),
      ]);
      setUsers(userData);
      setTenants(tenantData);
      setError("");
    } catch (rawError) {
      setError(apiErrorMessage(rawError, "Unable to load platform users."));
    }
  }, [access]);

  useEffect(() => {
    void load();
  }, [load]);

  async function toggleActive(user: PlatformUser) {
    try {
      await request<PlatformUser>(
        `/platform/users/${user.id}/`,
        { method: "PATCH", body: JSON.stringify({ is_active: !user.is_active }) },
        access,
      );
      await load();
    } catch (rawError) {
      setError(apiErrorMessage(rawError, "Unable to update user."));
    }
  }

  async function removeMembership(user: PlatformUser, tenantId: string) {
    try {
      await request<PlatformUser>(
        `/platform/users/${user.id}/remove-tenant/`,
        { method: "POST", body: JSON.stringify({ tenant_id: tenantId }) },
        access,
      );
      await load();
    } catch (rawError) {
      setError(apiErrorMessage(rawError, "Unable to remove tenant membership."));
    }
  }

  return (
    <div>
      <PanelHeader
        title="Users"
        description="Create platform-managed accounts and assign them to ISPs as Tenant Admins."
        actionLabel={showCreate ? "Cancel" : "Create user"}
        onAction={() => setShowCreate((value) => !value)}
      />
      {error && <ErrorBanner text={error} />}
      {showCreate && (
        <CreatePlatformUserForm
          access={access}
          onCreated={async () => {
            setShowCreate(false);
            await load();
          }}
        />
      )}
      {editing && (
        <EditPlatformUserForm
          access={access}
          user={editing}
          onCancel={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null);
            await load();
          }}
        />
      )}
      {assigning && (
        <AssignTenantForm
          access={access}
          user={assigning}
          tenants={tenants}
          onCancel={() => setAssigning(null)}
          onAssigned={async () => {
            setAssigning(null);
            await load();
          }}
        />
      )}

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full min-w-[900px] text-left text-sm">
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="px-4 py-3">User</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Tenant memberships</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => {
              const memberships = user.memberships.filter((membership) => membership.is_active);
              return (
                <tr key={user.id} className="border-t border-slate-100 align-top">
                  <td className="px-4 py-3">
                    <div className="font-medium">{user.name}</div>
                    <div className="text-xs text-slate-500">{user.email}</div>
                  </td>
                  <td className="px-4 py-3">
                    <StatusPill active={user.is_active} text={user.is_active ? "active" : "disabled"} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="space-y-2">
                      {memberships.map((membership) => (
                        <div key={membership.id} className="flex flex-wrap items-center gap-2 rounded bg-slate-50 px-2 py-1.5">
                          <span className="font-medium">{membership.tenant_name}</span>
                          <span className="text-xs text-slate-500">
                            {membership.roles.map((role) => role.name).join(", ") || "No role"}
                          </span>
                          <button className="ml-auto text-xs text-red-700 underline" onClick={() => void removeMembership(user, membership.tenant_id)}>
                            Remove
                          </button>
                        </div>
                      ))}
                      {memberships.length === 0 && <span className="text-slate-400">No active memberships</span>}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-2">
                      <button className="rounded border border-slate-300 px-3 py-1.5" onClick={() => setEditing(user)}>Edit</button>
                      <button className="rounded border border-slate-300 px-3 py-1.5" onClick={() => setAssigning(user)}>Assign tenant</button>
                      <button className="rounded border border-slate-300 px-3 py-1.5" onClick={() => void toggleActive(user)}>
                        {user.is_active ? "Disable" : "Enable"}
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
            {users.length === 0 && <EmptyRow columns={4} text="No regular users yet." />}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CreatePlatformUserForm({ access, onCreated }: { access: string; onCreated: () => Promise<void> }) {
  const [form, setForm] = useState({ email: "", name: "", password: "" });
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await request<PlatformUser>(
        "/platform/users/",
        { method: "POST", body: JSON.stringify(form) },
        access,
      );
      await onCreated();
    } catch (rawError) {
      setError(apiErrorMessage(rawError, "Unable to create user."));
    }
  }

  return (
    <form onSubmit={submit} className="mb-5 rounded-lg border border-slate-200 bg-white p-5">
      <h2 className="mb-4 font-semibold">Create user</h2>
      <div className="grid gap-4 md:grid-cols-3">
        <InputField label="Name" value={form.name} onChange={(value) => setForm({ ...form, name: value })} required />
        <InputField label="Email" type="email" value={form.email} onChange={(value) => setForm({ ...form, email: value })} required />
        <InputField label="Password" type="password" value={form.password} onChange={(value) => setForm({ ...form, password: value })} required />
      </div>
      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      <button className="mt-4 rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white">Create user</button>
    </form>
  );
}

function EditPlatformUserForm({
  access,
  user,
  onCancel,
  onSaved,
}: {
  access: string;
  user: PlatformUser;
  onCancel: () => void;
  onSaved: () => Promise<void>;
}) {
  const [name, setName] = useState(user.name);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await request<PlatformUser>(
        `/platform/users/${user.id}/`,
        { method: "PATCH", body: JSON.stringify({ name }) },
        access,
      );
      await onSaved();
    } catch (rawError) {
      setError(apiErrorMessage(rawError, "Unable to update user."));
    }
  }

  return (
    <form onSubmit={submit} className="mb-5 rounded-lg border border-slate-200 bg-white p-5">
      <div className="mb-4 flex justify-between">
        <h2 className="font-semibold">Edit {user.email}</h2>
        <button type="button" className="text-sm underline" onClick={onCancel}>Cancel</button>
      </div>
      <div className="max-w-md"><InputField label="Name" value={name} onChange={setName} required /></div>
      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      <button className="mt-4 rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white">Save</button>
    </form>
  );
}

function AssignTenantForm({
  access,
  user,
  tenants,
  onCancel,
  onAssigned,
}: {
  access: string;
  user: PlatformUser;
  tenants: TenantSummary[];
  onCancel: () => void;
  onAssigned: () => Promise<void>;
}) {
  const availableTenants = useMemo(
    () => tenants.filter((tenant) => tenant.status === "active"),
    [tenants],
  );
  const [tenantId, setTenantId] = useState(availableTenants[0]?.id || "");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!tenantId) {
      setError("Select a tenant.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await request<PlatformUser>(
        `/platform/users/${user.id}/assign-tenant/`,
        { method: "POST", body: JSON.stringify({ tenant_id: tenantId }) },
        access,
      );
      await onAssigned();
    } catch (rawError) {
      setError(apiErrorMessage(rawError, "Unable to assign tenant."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className="mb-5 rounded-lg border border-slate-200 bg-white p-5">
      <div className="mb-4 flex justify-between gap-3">
        <div>
          <h2 className="font-semibold">Assign {user.email} to tenant</h2>
          <p className="text-sm text-slate-500">
            PamirNet automatically assigns the built-in Tenant Admin role. Tenant Admins can create custom roles and manage their own team members.
          </p>
        </div>
        <button type="button" className="text-sm underline" onClick={onCancel}>Cancel</button>
      </div>
      <div className="max-w-md">
        <label className="block text-sm font-medium">
          Tenant
          <select className="input mt-1" value={tenantId} onChange={(event) => setTenantId(event.target.value)} required>
            <option value="">Select tenant</option>
            {availableTenants.map((tenant) => (
              <option key={tenant.id} value={tenant.id}>{tenant.name}</option>
            ))}
          </select>
        </label>
      </div>
      <div className="mt-3 rounded border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
        Role: <span className="font-semibold">Tenant Admin</span>
      </div>
      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      <button className="mt-4 rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60" disabled={submitting}>
        {submitting ? "Assigning…" : "Assign tenant"}
      </button>
    </form>
  );
}

function PlatformAuditPanel({ access }: { access: string }) {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [tenants, setTenants] = useState<TenantSummary[]>([]);
  const [tenantId, setTenantId] = useState("");
  const [actionName, setActionName] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (tenantId) params.set("tenant_id", tenantId);
      if (actionName.trim()) params.set("action", actionName.trim());
      const path = `/platform/audit/${params.size ? `?${params.toString()}` : ""}`;
      setLogs(await request<AuditLog[]>(path, {}, access));
      setError("");
    } catch (rawError) {
      setError(apiErrorMessage(rawError, "Unable to load audit logs."));
    }
  }, [access, actionName, tenantId]);

  useEffect(() => {
    request<TenantSummary[]>("/platform/tenants/", {}, access).then(setTenants).catch(() => undefined);
    void load();
  }, [access, load]);

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-xl font-semibold">Platform audit</h1>
        <p className="text-sm text-slate-500">Cross-tenant administrative and sensitive action history.</p>
      </div>
      <div className="mb-4 grid gap-3 rounded-lg border border-slate-200 bg-white p-4 md:grid-cols-[1fr_1fr_auto]">
        <label className="text-sm font-medium">
          Tenant
          <select className="input mt-1" value={tenantId} onChange={(event) => setTenantId(event.target.value)}>
            <option value="">All tenants</option>
            {tenants.map((tenant) => <option key={tenant.id} value={tenant.id}>{tenant.name}</option>)}
          </select>
        </label>
        <InputField label="Exact action" value={actionName} onChange={setActionName} placeholder="platform.tenant.created" />
        <button className="self-end rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white" onClick={() => void load()}>Apply</button>
      </div>
      {error && <ErrorBanner text={error} />}
      <AuditTable logs={logs} showTenant />
    </div>
  );
}

export function AuditTable({ logs, showTenant = false }: { logs: AuditLog[]; showTenant?: boolean }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="w-full min-w-[900px] text-left text-sm">
        <thead className="bg-slate-50 text-slate-500">
          <tr>
            <th className="px-4 py-3">Time</th>
            {showTenant && <th className="px-4 py-3">Tenant</th>}
            <th className="px-4 py-3">Actor</th>
            <th className="px-4 py-3">Action</th>
            <th className="px-4 py-3">Target</th>
            <th className="px-4 py-3">Source IP</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log) => (
            <tr key={log.id} className="border-t border-slate-100">
              <td className="whitespace-nowrap px-4 py-3">{formatDate(log.created_at)}</td>
              {showTenant && <td className="px-4 py-3">{log.tenant_name || "Platform"}</td>}
              <td className="px-4 py-3">{log.actor_email || "System"}</td>
              <td className="px-4 py-3 font-mono text-xs">{log.action}</td>
              <td className="px-4 py-3">{log.target_type}{log.target_id ? ` · ${log.target_id}` : ""}</td>
              <td className="px-4 py-3">{log.source_ip || "—"}</td>
            </tr>
          ))}
          {logs.length === 0 && <EmptyRow columns={showTenant ? 6 : 5} text="No audit entries found." />}
        </tbody>
      </table>
    </div>
  );
}

function PanelHeader({
  title,
  description,
  actionLabel,
  onAction,
}: {
  title: string;
  description: string;
  actionLabel: string;
  onAction: () => void;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold">{title}</h1>
        <p className="text-sm text-slate-500">{description}</p>
      </div>
      <button className="rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white" onClick={onAction}>
        {actionLabel}
      </button>
    </div>
  );
}

function InputField({
  label,
  value,
  onChange,
  type = "text",
  required = false,
  placeholder = "",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  required?: boolean;
  placeholder?: string;
}) {
  return (
    <label className="block text-sm font-medium">
      {label}
      <input
        className="input mt-1"
        type={type}
        value={value}
        placeholder={placeholder}
        required={required}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function StatusPill({ active, text }: { active: boolean; text: string }) {
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${active ? "bg-emerald-100 text-emerald-800" : "bg-slate-200 text-slate-700"}`}>
      {text}
    </span>
  );
}

function ErrorBanner({ text }: { text: string }) {
  return <div className="mb-4 rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{text}</div>;
}

function EmptyRow({ columns, text }: { columns: number; text: string }) {
  return <tr><td colSpan={columns} className="px-4 py-8 text-center text-slate-400">{text}</td></tr>;
}

function slugify(value: string) {
  return value.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

function formatDate(value: string) {
  return new Date(value).toLocaleString();
}
