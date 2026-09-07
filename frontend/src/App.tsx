import { useCallback, useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";

import { request } from "./api";
import type { Me, TenantSummary } from "./api";
import { NetworkingPage } from "./NetworkingPage";
import { PackagesPage } from "./PackagesPage";
import { SubscribersPage } from "./SubscribersPage";

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
    return <LoginScreen onAuthenticated={async (token) => { storeAccess(token); await loadMe(token); }} />;
  }
  if (!me || !access) return <CenteredMessage text="Loading account…" />;

  return (
    <AppShell
      access={access}
      me={me}
      onAccessChanged={async (token) => { storeAccess(token); await loadMe(token); }}
      onExitImpersonation={async () => { await request<void>("/platform/impersonation/stop/", { method: "POST" }, access); await refresh(); }}
      onLogout={async () => {
        await request<void>("/auth/logout/", { method: "POST" }).catch(() => undefined);
        storeAccess(null);
        setMe(null);
        setState("anonymous");
      }}
    />
  );
}

function LoginScreen({ onAuthenticated }: { onAuthenticated: (access: string) => Promise<void> }) {
  const [email, setEmail] = useState("");
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
        body: JSON.stringify({ email, password, ...(tenantId ? { tenant_id: tenantId } : {}) }),
      });
      await onAuthenticated(result.access);
    } catch (rawError) {
      const apiError = rawError as Error & { status?: number; payload?: LoginConflict };
      if (apiError.status === 409 && apiError.payload?.tenants?.length) {
        setTenantChoices(apiError.payload.tenants);
        setTenantId(apiError.payload.tenants[0].id);
        setError("Select the ISP account to continue.");
      } else setError(apiError.payload?.detail || "Login failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 text-slate-900">
      <form onSubmit={submit} className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-6"><p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">ISP Operations</p><h1 className="mt-1 text-2xl font-bold">PamirNet</h1></div>
        <Field label="Email"><input className="input" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></Field>
        <Field label="Password"><input className="input" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required /></Field>
        {tenantChoices.length > 0 && <Field label="ISP"><select className="input" value={tenantId} onChange={(event) => setTenantId(event.target.value)}>{tenantChoices.map((tenant) => <option key={tenant.id} value={tenant.id}>{tenant.name}</option>)}</select></Field>}
        {error && <p className="mb-4 text-sm text-red-700">{error}</p>}
        <button className="w-full rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60" disabled={submitting}>{submitting ? "Signing in…" : "Sign in"}</button>
      </form>
    </main>
  );
}

function AppShell({ access, me, onAccessChanged, onExitImpersonation, onLogout }: {
  access: string;
  me: Me;
  onAccessChanged: (access: string) => Promise<void>;
  onExitImpersonation: () => Promise<void>;
  onLogout: () => Promise<void>;
}) {
  if (me.is_platform_admin && !me.tenant) {
    return <PlatformHome access={access} me={me} onAccessChanged={onAccessChanged} onLogout={onLogout} />;
  }

  const navigation = ["Dashboard", "Networking", "Subscribers", "Packages", "Vouchers", "Analytics", "Users & Roles", "Audit", "Settings"];
  const [activePage, setActivePage] = useState("Dashboard");
  const permitted = (code: string) => me.permissions.includes("*") || me.permissions.includes(code);

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      {me.impersonating && <div className="flex items-center justify-between bg-amber-100 px-4 py-2 text-sm text-amber-950"><span>Platform administrator is viewing {me.tenant?.name}.</span><button className="font-semibold underline" onClick={onExitImpersonation}>Exit impersonation</button></div>}
      <div className="flex min-h-screen">
        <aside className="hidden w-56 shrink-0 border-r border-slate-200 bg-slate-900 text-slate-100 md:block">
          <div className="border-b border-slate-800 px-5 py-5"><div className="font-bold">PamirNet</div><div className="mt-1 truncate text-xs text-slate-400">{me.tenant?.name}</div></div>
          <nav className="p-3">{navigation.map((item) => <button key={item} onClick={() => setActivePage(item)} className={`mb-1 w-full rounded px-3 py-2 text-left text-sm ${activePage === item ? "bg-slate-800 text-white" : "text-slate-300 hover:bg-slate-800"}`}>{item}</button>)}</nav>
        </aside>
        <main className="min-w-0 flex-1">
          <header className="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-3">
            <div><h1 className="font-semibold">{activePage}</h1><p className="text-xs text-slate-500">PamirNet ISP operations</p></div>
            <div className="flex items-center gap-3 text-sm"><span className="hidden text-slate-500 sm:inline">{me.email}</span><button className="rounded border border-slate-300 px-3 py-1.5" onClick={onLogout}>Sign out</button></div>
          </header>
          <section className="p-5">
            {activePage === "Dashboard" && <Dashboard me={me} />}
            {activePage === "Networking" && <NetworkingPage access={access} canManage={permitted("router.manage")} />}
            {activePage === "Packages" && <PackagesPage access={access} canManage={permitted("package.manage")} />}
            {activePage === "Subscribers" && <SubscribersPage access={access} canCreate={permitted("subscriber.create")} canEdit={permitted("subscriber.edit")} />}
            {!['Dashboard', 'Networking', 'Packages', 'Subscribers'].includes(activePage) && <Placeholder page={activePage} />}
          </section>
        </main>
      </div>
    </div>
  );
}

function Dashboard({ me }: { me: Me }) {
  return <><div className="grid gap-4 md:grid-cols-3"><InfoCard label="Tenant" value={me.tenant?.name || "—"} /><InfoCard label="Role access" value={`${me.permissions.length} permissions`} /><InfoCard label="AAA" value="Phase 3 active" /></div><div className="mt-5 rounded-lg border border-slate-200 bg-white p-5"><h2 className="font-semibold">PamirNet control plane</h2><p className="mt-2 text-sm text-slate-600">MikroTik networking and FreeRADIUS are active. Phase 3 adds packages, subscribers, subscription periods and tenant-aware RADIUS authorization.</p></div></>;
}

function Placeholder({ page }: { page: string }) {
  return <div className="rounded-lg border border-slate-200 bg-white p-5"><h2 className="font-semibold">{page}</h2><p className="mt-2 text-sm text-slate-500">This operational module is scheduled for a later PamirNet phase.</p></div>;
}

function PlatformHome({ access, me, onAccessChanged, onLogout }: { access: string; me: Me; onAccessChanged: (access: string) => Promise<void>; onLogout: () => Promise<void> }) {
  const [tenants, setTenants] = useState<TenantSummary[]>([]);
  const [error, setError] = useState("");
  useEffect(() => { request<TenantSummary[]>("/platform/tenants/", {}, access).then(setTenants).catch(() => setError("Unable to load tenants.")); }, [access]);
  async function impersonate(tenant: TenantSummary) {
    const result = await request<{ access: string }>(`/platform/tenants/${tenant.id}/impersonate/`, { method: "POST", body: JSON.stringify({ reason: "Support session" }) }, access);
    await onAccessChanged(result.access);
  }
  return <main className="min-h-screen bg-slate-100 text-slate-900"><header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-4"><div><div className="font-bold">PamirNet Platform</div><div className="text-xs text-slate-500">{me.email}</div></div><button className="rounded border border-slate-300 px-3 py-1.5 text-sm" onClick={onLogout}>Sign out</button></header><section className="mx-auto max-w-6xl p-6"><div className="mb-4 flex items-center justify-between"><h1 className="text-xl font-semibold">Tenants</h1><span className="text-sm text-slate-500">{tenants.length} total</span></div>{error && <p className="mb-4 text-sm text-red-700">{error}</p>}<div className="overflow-hidden rounded-lg border border-slate-200 bg-white"><table className="w-full text-left text-sm"><thead className="bg-slate-50 text-slate-500"><tr><th className="px-4 py-3">ISP</th><th>Status</th><th>Currency</th><th className="px-4 text-right">Action</th></tr></thead><tbody>{tenants.map((tenant) => <tr key={tenant.id} className="border-t border-slate-100"><td className="px-4 py-3"><div className="font-medium">{tenant.name}</div><div className="text-xs text-slate-500">{tenant.slug}</div></td><td>{tenant.status}</td><td>{tenant.currency}</td><td className="px-4 text-right"><button className="rounded border border-slate-300 px-3 py-1.5 disabled:opacity-50" disabled={tenant.status !== "active"} onClick={() => impersonate(tenant)}>Impersonate</button></td></tr>)}</tbody></table></div></section></main>;
}

function Field({ label, children }: { label: string; children: ReactNode }) { return <label className="mb-4 block"><span className="mb-1 block text-sm font-medium">{label}</span>{children}</label>; }
function InfoCard({ label, value }: { label: string; value: string }) { return <div className="rounded-lg border border-slate-200 bg-white p-4"><div className="text-xs uppercase tracking-wide text-slate-500">{label}</div><div className="mt-1 font-semibold">{value}</div></div>; }
function CenteredMessage({ text }: { text: string }) { return <main className="flex min-h-screen items-center justify-center bg-slate-100 text-sm text-slate-500">{text}</main>; }
