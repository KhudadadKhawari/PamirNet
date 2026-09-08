import { useCallback, useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";

import { AnalyticsPage } from "./AnalyticsPage";
import { AuditPage } from "./AuditPage";
import { request } from "./api";
import type { Me } from "./api";
import { DashboardPage } from "./DashboardPage";
import { NetworkingPage } from "./NetworkingPage";
import { PackagesPage } from "./PackagesPage";
import { PlatformPage } from "./PlatformPage";
import { SessionsPage } from "./SessionsPage";
import { SettingsPage } from "./SettingsPage";
import { SubscribersPage } from "./SubscribersPage";
import { UsersRolesPage } from "./UsersRolesPage";
import { VouchersPage } from "./VouchersPage";

type LoginResult = { access: string };
type TenantChoice = { id: string; name: string; slug: string };
type LoginConflict = { detail?: string; tenants?: TenantChoice[] };
type AuthState = "loading" | "anonymous" | "authenticated";

export default function App() {
  const [access, setAccess] = useState<string | null>(() => sessionStorage.getItem("pamirnet_access"));
  const [me, setMe] = useState<Me | null>(null);
  const [state, setState] = useState<AuthState>("loading");

  const storeAccess = useCallback((token: string | null) => {
    setAccess(token);
    if (token) sessionStorage.setItem("pamirnet_access", token);
    else sessionStorage.removeItem("pamirnet_access");
  }, []);

  const loadMe = useCallback(async (token: string) => {
    const profile = await request<Me>("/auth/me/", {}, token);
    setMe(profile);
    setState("authenticated");
  }, []);

  const refresh = useCallback(async () => {
    try {
      const result = await request<LoginResult>("/auth/refresh/", { method: "POST" });
      storeAccess(result.access);
      await loadMe(result.access);
      return result.access;
    } catch {
      storeAccess(null);
      setMe(null);
      setState("anonymous");
      return null;
    }
  }, [loadMe, storeAccess]);

  useEffect(() => {
    if (access) loadMe(access).catch(() => refresh());
    else void refresh();
  }, []);

  if (state === "loading") return <CenteredMessage text="Loading PamirNet…" />;
  if (state === "anonymous") {
    return (
      <LoginScreen
        onAuthenticated={async (token) => {
          storeAccess(token);
          await loadMe(token);
        }}
      />
    );
  }
  if (!me || !access) return <CenteredMessage text="Loading account…" />;

  return (
    <AppShell
      access={access}
      me={me}
      onAccessChanged={async (token) => {
        storeAccess(token);
        await loadMe(token);
      }}
      onExitImpersonation={async () => {
        await request<void>(
          "/platform/impersonation/stop/",
          { method: "POST" },
          access,
        );
        await refresh();
      }}
      onLogout={async () => {
        await request<void>("/auth/logout/", { method: "POST" }).catch(() => undefined);
        storeAccess(null);
        setMe(null);
        setState("anonymous");
      }}
    />
  );
}

function LoginScreen({
  onAuthenticated,
}: {
  onAuthenticated: (access: string) => Promise<void>;
}) {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [tenantId, setTenantId] = useState("");
  const [tenantChoices, setTenantChoices] = useState<TenantChoice[]>([]);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const result = await request<LoginResult>("/auth/login/", {
        method: "POST",
        body: JSON.stringify({
          identifier,
          password,
          ...(tenantId ? { tenant_id: tenantId } : {}),
        }),
      });
      await onAuthenticated(result.access);
    } catch (rawError) {
      const apiError = rawError as Error & { status?: number; payload?: LoginConflict };
      if (apiError.status === 409 && apiError.payload?.tenants?.length) {
        setTenantChoices(apiError.payload.tenants);
        setTenantId(apiError.payload.tenants[0].id);
        setError("Select the ISP account to continue.");
      } else {
        setError(apiError.payload?.detail || "Login failed.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 text-slate-900">
      <form
        onSubmit={submit}
        className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
      >
        <div className="mb-6">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
            ISP Operations
          </p>
          <h1 className="mt-1 text-2xl font-bold">PamirNet</h1>
        </div>
        <Field label="Username or email">
          <input
            className="input"
            type="text"
            autoComplete="username"
            value={identifier}
            onChange={(event) => setIdentifier(event.target.value)}
            required
          />
        </Field>
        <Field label="Password">
          <input
            className="input"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </Field>
        {tenantChoices.length > 0 && (
          <Field label="ISP">
            <select
              className="input"
              value={tenantId}
              onChange={(event) => setTenantId(event.target.value)}
            >
              {tenantChoices.map((tenant) => (
                <option key={tenant.id} value={tenant.id}>
                  {tenant.name}
                </option>
              ))}
            </select>
          </Field>
        )}
        {error && <p className="mb-4 text-sm text-red-700">{error}</p>}
        <button
          className="w-full rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
          disabled={submitting}
        >
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </main>
  );
}

function AppShell({
  access,
  me,
  onAccessChanged,
  onExitImpersonation,
  onLogout,
}: {
  access: string;
  me: Me;
  onAccessChanged: (access: string) => Promise<void>;
  onExitImpersonation: () => Promise<void>;
  onLogout: () => Promise<void>;
}) {
  if (me.is_platform_admin && !me.tenant) {
    return (
      <PlatformPage
        access={access}
        me={me}
        onAccessChanged={onAccessChanged}
        onLogout={onLogout}
      />
    );
  }

  const permitted = (code: string) =>
    me.permissions.includes("*") || me.permissions.includes(code);
  const navigation = [
    { label: "Dashboard", visible: permitted("dashboard.view") },
    { label: "Networking", visible: permitted("router.view") || permitted("router.manage") },
    { label: "Sessions", visible: permitted("session.view") || permitted("session.disconnect") },
    {
      label: "Subscribers",
      visible:
        permitted("subscriber.view") ||
        permitted("subscriber.create") ||
        permitted("subscriber.edit"),
    },
    { label: "Packages", visible: permitted("package.view") || permitted("package.manage") },
    {
      label: "Vouchers",
      visible:
        permitted("voucher.view") ||
        permitted("voucher.generate") ||
        permitted("voucher.export") ||
        permitted("voucher.disable"),
    },
    { label: "Analytics", visible: permitted("analytics.view") },
    {
      label: "Users & Roles",
      visible: permitted("user.manage") || permitted("role.manage"),
    },
    { label: "Audit", visible: permitted("audit.view") },
    { label: "Settings", visible: true },
  ].filter((item) => item.visible);

  const [activePage, setActivePage] = useState(navigation[0]?.label || "Settings");

  useEffect(() => {
    if (!navigation.some((item) => item.label === activePage)) {
      setActivePage(navigation[0]?.label || "Settings");
    }
  }, [activePage, navigation.map((item) => item.label).join("|")]);

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      {me.impersonating && (
        <div className="flex items-center justify-between bg-amber-100 px-4 py-2 text-sm text-amber-950">
          <span>Platform administrator is viewing {me.tenant?.name}.</span>
          <button className="font-semibold underline" onClick={onExitImpersonation}>
            Exit impersonation
          </button>
        </div>
      )}
      <div className="flex min-h-screen">
        <aside className="hidden w-56 shrink-0 border-r border-slate-200 bg-slate-900 text-slate-100 md:block">
          <div className="border-b border-slate-800 px-5 py-5">
            <div className="font-bold">PamirNet</div>
            <div className="mt-1 truncate text-xs text-slate-400">{me.tenant?.name}</div>
          </div>
          <nav className="p-3">
            {navigation.map((item) => (
              <button
                key={item.label}
                onClick={() => setActivePage(item.label)}
                className={`mb-1 w-full rounded px-3 py-2 text-left text-sm ${
                  activePage === item.label
                    ? "bg-slate-800 text-white"
                    : "text-slate-300 hover:bg-slate-800"
                }`}
              >
                {item.label}
              </button>
            ))}
          </nav>
        </aside>
        <main className="min-w-0 flex-1">
          <header className="border-b border-slate-200 bg-white px-5 py-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h1 className="font-semibold">{activePage}</h1>
                <p className="text-xs text-slate-500">PamirNet ISP operations</p>
              </div>
              <div className="flex items-center gap-3 text-sm">
                <span className="hidden text-slate-500 sm:inline">{me.email}</span>
                <button className="rounded border border-slate-300 px-3 py-1.5" onClick={onLogout}>
                  Sign out
                </button>
              </div>
            </div>
            <select
              className="input mt-3 md:hidden"
              value={activePage}
              onChange={(event) => setActivePage(event.target.value)}
            >
              {navigation.map((item) => (
                <option key={item.label} value={item.label}>
                  {item.label}
                </option>
              ))}
            </select>
          </header>
          <section className="p-5">
            {activePage === "Dashboard" && <DashboardPage access={access} />}
            {activePage === "Networking" && (
              <NetworkingPage access={access} canManage={permitted("router.manage")} />
            )}
            {activePage === "Sessions" && (
              <SessionsPage access={access} canControl={permitted("session.disconnect")} />
            )}
            {activePage === "Packages" && (
              <PackagesPage access={access} canManage={permitted("package.manage")} />
            )}
            {activePage === "Subscribers" && (
              <SubscribersPage
                access={access}
                canCreate={permitted("subscriber.create")}
                canEdit={permitted("subscriber.edit")}
              />
            )}
            {activePage === "Vouchers" && (
              <VouchersPage
                access={access}
                canGenerate={permitted("voucher.generate")}
                canExport={permitted("voucher.export")}
                canDisable={permitted("voucher.disable")}
              />
            )}
            {activePage === "Analytics" && <AnalyticsPage access={access} />}
            {activePage === "Users & Roles" && (
              <UsersRolesPage
                access={access}
                canManageUsers={permitted("user.manage")}
                canManageRoles={permitted("role.manage")}
              />
            )}
            {activePage === "Audit" && <AuditPage access={access} />}
            {activePage === "Settings" && (
              <SettingsPage access={access} canManage={permitted("settings.manage")} />
            )}
          </section>
        </main>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="mb-4 block">
      <span className="mb-1 block text-sm font-medium">{label}</span>
      {children}
    </label>
  );
}

function CenteredMessage({ text }: { text: string }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-100 text-sm text-slate-500">
      {text}
    </main>
  );
}
