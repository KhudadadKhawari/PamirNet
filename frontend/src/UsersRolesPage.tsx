import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import {
  apiErrorMessage,
  request,
  type Permission,
  type Role,
  type TenantMembership,
} from "./api";

type Tab = "users" | "roles";

export function UsersRolesPage({
  access,
  canManageUsers,
  canManageRoles,
}: {
  access: string;
  canManageUsers: boolean;
  canManageRoles: boolean;
}) {
  const [tab, setTab] = useState<Tab>(canManageUsers ? "users" : "roles");
  const [users, setUsers] = useState<TenantMembership[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [error, setError] = useState("");
  const [showCreateUser, setShowCreateUser] = useState(false);
  const [editingUser, setEditingUser] = useState<TenantMembership | null>(null);
  const [editingRole, setEditingRole] = useState<Role | "new" | null>(null);

  const load = useCallback(async () => {
    try {
      const tasks: Promise<unknown>[] = [];
      if (canManageUsers) {
        tasks.push(request<TenantMembership[]>("/users/", {}, access).then(setUsers));
      }
      if (canManageUsers || canManageRoles) {
        tasks.push(request<Role[]>("/roles/", {}, access).then(setRoles));
      }
      if (canManageRoles) {
        tasks.push(request<Permission[]>("/permissions/", {}, access).then(setPermissions));
      }
      await Promise.all(tasks);
      setError("");
    } catch (rawError) {
      setError(apiErrorMessage(rawError, "Unable to load access-control data."));
    }
  }, [access, canManageRoles, canManageUsers]);

  useEffect(() => {
    void load();
  }, [load]);

  async function disableUser(user: TenantMembership) {
    try {
      if (user.is_active) {
        await request<void>(`/users/${user.id}/`, { method: "DELETE" }, access);
      } else {
        await request<TenantMembership>(
          `/users/${user.id}/`,
          { method: "PATCH", body: JSON.stringify({ is_active: true }) },
          access,
        );
      }
      await load();
    } catch (rawError) {
      setError(apiErrorMessage(rawError, "Unable to update user."));
    }
  }

  async function deleteRole(role: Role) {
    if (role.is_system) return;
    try {
      await request<void>(`/roles/${role.id}/`, { method: "DELETE" }, access);
      await load();
    } catch (rawError) {
      setError(apiErrorMessage(rawError, "Unable to delete role."));
    }
  }

  if (!canManageUsers && !canManageRoles) {
    return <Notice text="You do not have permission to manage tenant users or roles." />;
  }

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Users & Roles</h2>
          <p className="text-sm text-slate-500">Manage tenant access without sharing accounts.</p>
        </div>
        <div className="flex gap-2">
          {canManageUsers && (
            <button
              className="rounded border border-slate-300 px-3 py-2 text-sm"
              onClick={() => setTab("users")}
            >
              Users
            </button>
          )}
          {canManageRoles && (
            <button
              className="rounded border border-slate-300 px-3 py-2 text-sm"
              onClick={() => setTab("roles")}
            >
              Roles
            </button>
          )}
        </div>
      </div>

      {error && <ErrorBanner text={error} />}

      {tab === "users" && canManageUsers && (
        <div>
          <div className="mb-4 flex justify-end">
            <button
              className="rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white"
              onClick={() => {
                setShowCreateUser((value) => !value);
                setEditingUser(null);
              }}
            >
              {showCreateUser ? "Cancel" : "Add user"}
            </button>
          </div>
          {showCreateUser && (
            <CreateTenantUserForm
              access={access}
              roles={roles}
              onCreated={async () => {
                setShowCreateUser(false);
                await load();
              }}
            />
          )}
          {editingUser && (
            <EditTenantUserForm
              access={access}
              user={editingUser}
              roles={roles}
              onCancel={() => setEditingUser(null)}
              onSaved={async () => {
                setEditingUser(null);
                await load();
              }}
            />
          )}
          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th className="px-4 py-3">User</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Roles</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id} className="border-t border-slate-100">
                    <td className="px-4 py-3">
                      <div className="font-medium">{user.name}</div>
                      <div className="text-xs text-slate-500">{user.email}</div>
                    </td>
                    <td className="px-4 py-3">
                      <StatusPill active={user.is_active} />
                    </td>
                    <td className="px-4 py-3">
                      {user.roles.map((role) => role.name).join(", ") || "No role"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-2">
                        <button
                          className="rounded border border-slate-300 px-3 py-1.5"
                          onClick={() => {
                            setEditingUser(user);
                            setShowCreateUser(false);
                          }}
                        >
                          Edit
                        </button>
                        <button
                          className="rounded border border-slate-300 px-3 py-1.5"
                          onClick={() => void disableUser(user)}
                        >
                          {user.is_active ? "Disable" : "Enable"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {users.length === 0 && <EmptyRow columns={4} text="No tenant users found." />}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "roles" && canManageRoles && (
        <div>
          <div className="mb-4 flex justify-end">
            <button
              className="rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white"
              onClick={() => setEditingRole("new")}
            >
              Create role
            </button>
          </div>
          {editingRole && (
            <RoleForm
              access={access}
              role={editingRole}
              permissions={permissions}
              onCancel={() => setEditingRole(null)}
              onSaved={async () => {
                setEditingRole(null);
                await load();
              }}
            />
          )}
          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th className="px-4 py-3">Role</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Permissions</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {roles.map((role) => (
                  <tr key={role.id} className="border-t border-slate-100 align-top">
                    <td className="px-4 py-3 font-medium">{role.name}</td>
                    <td className="px-4 py-3">
                      {role.is_owner ? "Owner" : role.is_system ? "System" : "Custom"}
                    </td>
                    <td className="max-w-xl px-4 py-3 text-xs text-slate-600">
                      {role.permissions.length === 0
                        ? "No permissions"
                        : role.permissions.map((permission) => permission.name).join(", ")}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-2">
                        <button
                          className="rounded border border-slate-300 px-3 py-1.5 disabled:opacity-50"
                          disabled={role.is_system}
                          onClick={() => setEditingRole(role)}
                        >
                          Edit
                        </button>
                        <button
                          className="rounded border border-slate-300 px-3 py-1.5 text-red-700 disabled:opacity-50"
                          disabled={role.is_system}
                          onClick={() => void deleteRole(role)}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {roles.length === 0 && <EmptyRow columns={4} text="No roles found." />}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function CreateTenantUserForm({
  access,
  roles,
  onCreated,
}: {
  access: string;
  roles: Role[];
  onCreated: () => Promise<void>;
}) {
  const [form, setForm] = useState({ email: "", name: "", password: "" });
  const [roleIds, setRoleIds] = useState<string[]>([]);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (roleIds.length === 0) {
      setError("Select at least one role.");
      return;
    }
    try {
      await request<TenantMembership>(
        "/users/",
        {
          method: "POST",
          body: JSON.stringify({ ...form, role_ids: roleIds }),
        },
        access,
      );
      await onCreated();
    } catch (rawError) {
      setError(apiErrorMessage(rawError, "Unable to add user."));
    }
  }

  return (
    <form onSubmit={submit} className="mb-5 rounded-lg border border-slate-200 bg-white p-5">
      <h3 className="font-semibold">Add user</h3>
      <p className="mb-4 text-sm text-slate-500">
        For an existing PamirNet account, only email and roles are required. New accounts require name and password.
      </p>
      <div className="grid gap-4 md:grid-cols-3">
        <Field label="Email"><input className="input" type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} required /></Field>
        <Field label="Name (new account)"><input className="input" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></Field>
        <Field label="Password (new account)"><input className="input" type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /></Field>
      </div>
      <RoleSelector roles={roles} selected={roleIds} onChange={setRoleIds} />
      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      <button className="mt-4 rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white">Add user</button>
    </form>
  );
}

function EditTenantUserForm({
  access,
  user,
  roles,
  onCancel,
  onSaved,
}: {
  access: string;
  user: TenantMembership;
  roles: Role[];
  onCancel: () => void;
  onSaved: () => Promise<void>;
}) {
  const [name, setName] = useState(user.name);
  const [active, setActive] = useState(user.is_active);
  const [roleIds, setRoleIds] = useState(user.roles.map((role) => role.id));
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (roleIds.length === 0) {
      setError("Select at least one role.");
      return;
    }
    try {
      await request<TenantMembership>(
        `/users/${user.id}/`,
        {
          method: "PATCH",
          body: JSON.stringify({ name, is_active: active, role_ids: roleIds }),
        },
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
        <div><h3 className="font-semibold">Edit user</h3><p className="text-sm text-slate-500">{user.email}</p></div>
        <button type="button" className="text-sm underline" onClick={onCancel}>Cancel</button>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Name"><input className="input" value={name} onChange={(event) => setName(event.target.value)} required /></Field>
        <label className="flex items-center gap-2 self-end pb-3 text-sm font-medium"><input type="checkbox" checked={active} onChange={(event) => setActive(event.target.checked)} />Active membership</label>
      </div>
      <RoleSelector roles={roles} selected={roleIds} onChange={setRoleIds} />
      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      <button className="mt-4 rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white">Save user</button>
    </form>
  );
}

function RoleForm({
  access,
  role,
  permissions,
  onCancel,
  onSaved,
}: {
  access: string;
  role: Role | "new";
  permissions: Permission[];
  onCancel: () => void;
  onSaved: () => Promise<void>;
}) {
  const existing = role === "new" ? null : role;
  const [name, setName] = useState(existing?.name || "");
  const [selected, setSelected] = useState(existing?.permissions.map((item) => item.code) || []);
  const [error, setError] = useState("");
  const groups = useMemo(() => groupPermissions(permissions), [permissions]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      if (existing) {
        await request<Role>(
          `/roles/${existing.id}/`,
          { method: "PATCH", body: JSON.stringify({ name, permission_codes: selected }) },
          access,
        );
      } else {
        await request<Role>(
          "/roles/",
          { method: "POST", body: JSON.stringify({ name, permission_codes: selected }) },
          access,
        );
      }
      await onSaved();
    } catch (rawError) {
      setError(apiErrorMessage(rawError, "Unable to save role."));
    }
  }

  return (
    <form onSubmit={submit} className="mb-5 rounded-lg border border-slate-200 bg-white p-5">
      <div className="mb-4 flex justify-between">
        <h3 className="font-semibold">{existing ? `Edit ${existing.name}` : "Create role"}</h3>
        <button type="button" className="text-sm underline" onClick={onCancel}>Cancel</button>
      </div>
      <div className="max-w-md"><Field label="Role name"><input className="input" value={name} onChange={(event) => setName(event.target.value)} required /></Field></div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {Object.entries(groups).map(([category, items]) => (
          <fieldset key={category} className="rounded border border-slate-200 p-3">
            <legend className="px-1 text-sm font-semibold">{category}</legend>
            <div className="grid gap-2">
              {items.map((permission) => (
                <label key={permission.code} className="flex items-start gap-2 text-sm">
                  <input
                    className="mt-1"
                    type="checkbox"
                    checked={selected.includes(permission.code)}
                    onChange={() => setSelected((codes) => codes.includes(permission.code) ? codes.filter((code) => code !== permission.code) : [...codes, permission.code])}
                  />
                  <span><span className="font-medium">{permission.name}</span><span className="block font-mono text-xs text-slate-400">{permission.code}</span></span>
                </label>
              ))}
            </div>
          </fieldset>
        ))}
      </div>
      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      <button className="mt-4 rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white">Save role</button>
    </form>
  );
}

function RoleSelector({ roles, selected, onChange }: { roles: Role[]; selected: string[]; onChange: (roles: string[]) => void }) {
  return <div className="mt-4"><div className="mb-2 text-sm font-medium">Roles</div><div className="flex flex-wrap gap-3 rounded border border-slate-200 p-3">{roles.map((role) => <label key={role.id} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={selected.includes(role.id)} onChange={() => onChange(selected.includes(role.id) ? selected.filter((id) => id !== role.id) : [...selected, role.id])} />{role.name}{role.is_owner && <span className="text-xs text-amber-700">Owner</span>}</label>)}</div></div>;
}

function groupPermissions(permissions: Permission[]) {
  return permissions.reduce<Record<string, Permission[]>>((groups, permission) => {
    (groups[permission.category] ||= []).push(permission);
    return groups;
  }, {});
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block text-sm font-medium"><span className="mb-1 block">{label}</span>{children}</label>;
}

function StatusPill({ active }: { active: boolean }) {
  return <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${active ? "bg-emerald-100 text-emerald-800" : "bg-slate-200 text-slate-700"}`}>{active ? "active" : "disabled"}</span>;
}

function ErrorBanner({ text }: { text: string }) {
  return <div className="mb-4 rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{text}</div>;
}

function Notice({ text }: { text: string }) {
  return <div className="rounded border border-slate-200 bg-white p-5 text-sm text-slate-600">{text}</div>;
}

function EmptyRow({ columns, text }: { columns: number; text: string }) {
  return <tr><td colSpan={columns} className="px-4 py-8 text-center text-slate-400">{text}</td></tr>;
}
