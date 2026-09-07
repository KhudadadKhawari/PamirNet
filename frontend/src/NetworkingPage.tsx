import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import { request } from "./api";

type Router = {
  id: string;
  name: string;
  description: string;
  tunnel_ip: string;
  wireguard_public_key: string;
  api_protocol: "api" | "api_ssl" | "rest";
  api_port: number;
  api_username: string;
  api_tls_verify: boolean;
  enabled: boolean;
  status: "pending" | "online" | "offline" | "disabled";
  routeros_version: string;
  last_seen_at: string | null;
  latency_ms: number | null;
  packet_loss_percent: number | null;
  uptime_seconds: number | null;
  created_at: string;
  updated_at: string;
};

type Provisioning = {
  wireguard_private_key: string;
  wireguard_public_key: string;
  tunnel_ip: string;
  server_address: string;
  server_public_key: string;
  server_endpoint: string;
  server_port: number;
  radius_server: string;
  radius_secret: string;
  routeros_script: string;
  server_peer_config: string;
  server_apply_commands: string[];
  private_key_notice: string;
};

type CreateResult = { router: Router; provisioning: Provisioning };

type RotationResult = {
  radius_secret: string;
  routeros_command: string;
  notice: string;
};

export function NetworkingPage({ access, canManage }: { access: string; canManage: boolean }) {
  const [routers, setRouters] = useState<Router[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [provisioning, setProvisioning] = useState<Provisioning | null>(null);
  const [secretRotation, setSecretRotation] = useState<RotationResult | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRouters(await request<Router[]>("/network/routers/", {}, access));
      setError("");
    } catch {
      setError("Unable to load routers.");
    } finally {
      setLoading(false);
    }
  }, [access]);

  useEffect(() => {
    void load();
  }, [load]);

  async function testRouter(router: Router) {
    try {
      const updated = await request<Router & { test_error?: string }>(
        `/network/routers/${router.id}/test-connectivity/`,
        { method: "POST" },
        access,
      );
      setRouters((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      if (updated.test_error) setError(updated.test_error);
      else setError("");
    } catch (rawError) {
      setError(apiErrorMessage(rawError, "Connectivity test failed."));
    }
  }

  async function removeRouter(router: Router) {
    if (!window.confirm(`Delete ${router.name}?`)) return;
    try {
      await request<void>(`/network/routers/${router.id}/`, { method: "DELETE" }, access);
      setRouters((current) => current.filter((item) => item.id !== router.id));
    } catch (rawError) {
      setError(apiErrorMessage(rawError, "Unable to delete router."));
    }
  }

  async function rotateRadius(router: Router) {
    try {
      const result = await request<RotationResult>(
        `/network/routers/${router.id}/rotate-radius-secret/`,
        { method: "POST" },
        access,
      );
      setSecretRotation(result);
      setProvisioning(null);
    } catch (rawError) {
      setError(apiErrorMessage(rawError, "Unable to rotate RADIUS secret."));
    }
  }

  async function rotateWireGuard(router: Router) {
    if (!window.confirm(`Rotate the WireGuard key for ${router.name}? Existing tunnel access will stop until the new configuration is applied.`)) return;
    try {
      const result = await request<CreateResult>(
        `/network/routers/${router.id}/rotate-wireguard/`,
        { method: "POST" },
        access,
      );
      setRouters((current) => current.map((item) => (item.id === result.router.id ? result.router : item)));
      setProvisioning(result.provisioning);
      setSecretRotation(null);
    } catch (rawError) {
      setError(apiErrorMessage(rawError, "Unable to rotate WireGuard key."));
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Routers</h2>
          <p className="text-sm text-slate-500">MikroTik NAS devices connected to PamirNet over WireGuard.</p>
        </div>
        {canManage && (
          <button className="rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white" onClick={() => setShowCreate((value) => !value)}>
            {showCreate ? "Close" : "Add router"}
          </button>
        )}
      </div>

      {error && <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>}

      {showCreate && canManage && (
        <CreateRouterForm
          access={access}
          onCreated={(result) => {
            setRouters((current) => [...current, result.router].sort((a, b) => a.name.localeCompare(b.name)));
            setProvisioning(result.provisioning);
            setSecretRotation(null);
            setShowCreate(false);
          }}
          onError={setError}
        />
      )}

      {provisioning && <ProvisioningPanel provisioning={provisioning} onClose={() => setProvisioning(null)} />}
      {secretRotation && <RadiusRotationPanel result={secretRotation} onClose={() => setSecretRotation(null)} />}

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="min-w-[1000px] w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Router</th>
              <th className="px-4 py-3">Tunnel</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">RouterOS</th>
              <th className="px-4 py-3">Latency</th>
              <th className="px-4 py-3">Loss</th>
              <th className="px-4 py-3">Uptime</th>
              <th className="px-4 py-3">Last seen</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {routers.map((router) => (
              <tr key={router.id} className="border-t border-slate-100 align-top">
                <td className="px-4 py-3">
                  <div className="font-medium">{router.name}</div>
                  <div className="text-xs text-slate-500">{router.api_protocol}:{router.api_port}</div>
                </td>
                <td className="px-4 py-3 font-mono text-xs">{router.tunnel_ip}</td>
                <td className="px-4 py-3"><StatusBadge status={router.status} /></td>
                <td className="px-4 py-3">{router.routeros_version || "—"}</td>
                <td className="px-4 py-3">{router.latency_ms == null ? "—" : `${router.latency_ms.toFixed(1)} ms`}</td>
                <td className="px-4 py-3">{router.packet_loss_percent == null ? "—" : `${router.packet_loss_percent.toFixed(0)}%`}</td>
                <td className="px-4 py-3">{formatUptime(router.uptime_seconds)}</td>
                <td className="px-4 py-3 text-xs text-slate-500">{router.last_seen_at ? new Date(router.last_seen_at).toLocaleString() : "Never"}</td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-2">
                    <button className="rounded border border-slate-300 px-2.5 py-1.5 text-xs" onClick={() => testRouter(router)}>Test</button>
                    {canManage && (
                      <>
                        <button className="rounded border border-slate-300 px-2.5 py-1.5 text-xs" onClick={() => rotateRadius(router)}>RADIUS key</button>
                        <button className="rounded border border-slate-300 px-2.5 py-1.5 text-xs" onClick={() => rotateWireGuard(router)}>WG key</button>
                        <button className="rounded border border-red-200 px-2.5 py-1.5 text-xs text-red-700" onClick={() => removeRouter(router)}>Delete</button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {!loading && routers.length === 0 && (
              <tr><td colSpan={9} className="px-4 py-10 text-center text-slate-500">No routers registered yet.</td></tr>
            )}
            {loading && (
              <tr><td colSpan={9} className="px-4 py-10 text-center text-slate-500">Loading routers…</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CreateRouterForm({
  access,
  onCreated,
  onError,
}: {
  access: string;
  onCreated: (result: CreateResult) => void;
  onError: (message: string) => void;
}) {
  const [name, setName] = useState("");
  const [protocol, setProtocol] = useState<Router["api_protocol"]>("api");
  const [port, setPort] = useState("");
  const [username, setUsername] = useState("pamirnet");
  const [password, setPassword] = useState("");
  const [tlsVerify, setTlsVerify] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    onError("");
    try {
      const result = await request<CreateResult>(
        "/network/routers/",
        {
          method: "POST",
          body: JSON.stringify({
            name,
            api_protocol: protocol,
            api_username: username,
            api_password: password,
            api_tls_verify: tlsVerify,
            ...(port ? { api_port: Number(port) } : {}),
          }),
        },
        access,
      );
      onCreated(result);
    } catch (rawError) {
      onError(apiErrorMessage(rawError, "Unable to create router."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-4 rounded-lg border border-slate-200 bg-white p-5 md:grid-cols-2 lg:grid-cols-3">
      <Field label="Router name"><input className="input" required value={name} onChange={(event) => setName(event.target.value)} /></Field>
      <Field label="Management protocol">
        <select className="input" value={protocol} onChange={(event) => setProtocol(event.target.value as Router["api_protocol"])}>
          <option value="api">RouterOS API — 8728 (recommended over WireGuard)</option>
          <option value="api_ssl">RouterOS API SSL — 8729</option>
          <option value="rest">RouterOS REST — HTTPS</option>
        </select>
      </Field>
      <Field label="Custom port"><input className="input" type="number" min={1} max={65535} placeholder="Default" value={port} onChange={(event) => setPort(event.target.value)} /></Field>
      <Field label="RouterOS username"><input className="input" required value={username} onChange={(event) => setUsername(event.target.value)} /></Field>
      <Field label="RouterOS password"><input className="input" type="password" required value={password} onChange={(event) => setPassword(event.target.value)} /></Field>
      <label className="flex items-center gap-2 self-end pb-2 text-sm"><input type="checkbox" checked={tlsVerify} onChange={(event) => setTlsVerify(event.target.checked)} /> Verify router TLS certificate</label>
      <div className="md:col-span-2 lg:col-span-3 flex justify-end">
        <button disabled={submitting} className="rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">{submitting ? "Creating…" : "Create and generate configuration"}</button>
      </div>
    </form>
  );
}

function ProvisioningPanel({ provisioning, onClose }: { provisioning: Provisioning; onClose: () => void }) {
  return (
    <div className="rounded-lg border border-amber-300 bg-amber-50 p-5">
      <div className="flex items-start justify-between gap-4">
        <div><h3 className="font-semibold">One-time router provisioning</h3><p className="mt-1 text-sm text-amber-900">{provisioning.private_key_notice}</p></div>
        <button className="text-sm underline" onClick={onClose}>Close</button>
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <CodeBlock title="1. Apply on PamirNet VPS" value={provisioning.server_apply_commands.join("\n")} />
        <CodeBlock title="2. Paste into MikroTik terminal" value={provisioning.routeros_script} />
      </div>
    </div>
  );
}

function RadiusRotationPanel({ result, onClose }: { result: RotationResult; onClose: () => void }) {
  return (
    <div className="rounded-lg border border-amber-300 bg-amber-50 p-5">
      <div className="flex items-start justify-between gap-4"><div><h3 className="font-semibold">RADIUS secret rotated</h3><p className="mt-1 text-sm text-amber-900">{result.notice}</p></div><button className="text-sm underline" onClick={onClose}>Close</button></div>
      <div className="mt-4"><CodeBlock title="Apply on MikroTik" value={result.routeros_command} /></div>
    </div>
  );
}

function CodeBlock({ title, value }: { title: string; value: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }
  return (
    <div>
      <div className="mb-2 flex items-center justify-between"><span className="text-sm font-medium">{title}</span><button className="text-xs underline" onClick={copy}>{copied ? "Copied" : "Copy"}</button></div>
      <pre className="max-h-80 overflow-auto rounded-md bg-slate-950 p-4 text-xs text-slate-100 whitespace-pre-wrap">{value}</pre>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block"><span className="mb-1 block text-sm font-medium">{label}</span>{children}</label>;
}

function StatusBadge({ status }: { status: Router["status"] }) {
  const classes = {
    online: "bg-emerald-100 text-emerald-800",
    offline: "bg-red-100 text-red-800",
    pending: "bg-amber-100 text-amber-800",
    disabled: "bg-slate-200 text-slate-700",
  }[status];
  return <span className={`rounded-full px-2 py-1 text-xs font-medium ${classes}`}>{status}</span>;
}

function formatUptime(seconds: number | null) {
  if (seconds == null) return "—";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  return days ? `${days}d ${hours}h` : `${hours}h`;
}

function apiErrorMessage(rawError: unknown, fallback: string) {
  const error = rawError as Error & { payload?: { detail?: string } };
  return error.payload?.detail || fallback;
}
