import { useCallback, useEffect, useMemo, useState } from "react";

import { request } from "./api";

type Session = {
  id: string;
  router_name: string;
  identity_type: "subscriber" | "voucher";
  identity_name: string;
  username: string;
  package_name: string;
  framed_ip_address: string | null;
  calling_station_id: string;
  status: "active" | "stopped";
  started_at: string | null;
  last_update_at: string | null;
  input_bytes: number;
  output_bytes: number;
  total_bytes: number;
  session_seconds: number;
  last_rate_limit: string;
  last_control_action: string;
  last_control_error: string;
};

function formatBytes(value: number) {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value || 0;
  let index = 0;
  while (size >= 1000 && index < units.length - 1) {
    size /= 1000;
    index += 1;
  }
  return `${size.toFixed(index === 0 ? 0 : 2)} ${units[index]}`;
}

function formatDuration(seconds: number) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  return [hours, minutes, secs].map((value) => String(value).padStart(2, "0")).join(":");
}

export function SessionsPage({ access, canControl }: { access: string; canControl: boolean }) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [search, setSearch] = useState("");
  const [identityType, setIdentityType] = useState("");
  const [onlineOnly, setOnlineOnly] = useState(true);
  const [ordering, setOrdering] = useState("-total_bytes");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const query = useMemo(() => {
    const params = new URLSearchParams();
    if (search.trim()) params.set("search", search.trim());
    if (identityType) params.set("identity_type", identityType);
    if (onlineOnly) params.set("online", "true");
    params.set("ordering", ordering);
    return params.toString();
  }, [identityType, onlineOnly, ordering, search]);

  const load = useCallback(async () => {
    try {
      const rows = await request<Session[]>(`/sessions/?${query}`, {}, access);
      setSessions(rows);
      setError("");
    } catch {
      setError("Unable to load RADIUS sessions.");
    }
  }, [access, query]);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 15000);
    return () => window.clearInterval(timer);
  }, [load]);

  async function control(session: Session, action: "disconnect" | "refresh-policy") {
    setBusy(session.id);
    setError("");
    try {
      await request(
        `/sessions/${session.id}/${action}/`,
        { method: "POST", body: JSON.stringify({}) },
        access,
      );
      await load();
    } catch (rawError) {
      const apiError = rawError as Error & { payload?: { detail?: string } };
      setError(apiError.payload?.detail || `Unable to ${action.replace("-", " ")} session.`);
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-4 lg:flex-row lg:items-end">
        <label className="flex-1 text-sm">
          <span className="mb-1 block font-medium">Search</span>
          <input
            className="input"
            placeholder="Username, subscriber, IP or MAC"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block font-medium">Identity</span>
          <select className="input" value={identityType} onChange={(event) => setIdentityType(event.target.value)}>
            <option value="">All</option>
            <option value="subscriber">Subscribers</option>
            <option value="voucher">Vouchers</option>
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block font-medium">Sort</span>
          <select className="input" value={ordering} onChange={(event) => setOrdering(event.target.value)}>
            <option value="-total_bytes">Usage ↓</option>
            <option value="total_bytes">Usage ↑</option>
            <option value="-last_update_at">Latest update</option>
            <option value="username">Username</option>
            <option value="-session_seconds">Duration ↓</option>
          </select>
        </label>
        <label className="flex items-center gap-2 pb-2 text-sm">
          <input type="checkbox" checked={onlineOnly} onChange={(event) => setOnlineOnly(event.target.checked)} />
          Online only
        </label>
        <button className="rounded border border-slate-300 px-3 py-2 text-sm" onClick={() => void load()}>
          Refresh
        </button>
      </div>

      {error && <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Identity</th>
              <th className="px-4 py-3">Router / Address</th>
              <th className="px-4 py-3">Package</th>
              <th className="px-4 py-3">Usage</th>
              <th className="px-4 py-3">Duration</th>
              <th className="px-4 py-3">Rate</th>
              <th className="px-4 py-3">Status</th>
              {canControl && <th className="px-4 py-3 text-right">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {sessions.map((session) => (
              <tr key={session.id} className="border-t border-slate-100 align-top">
                <td className="px-4 py-3">
                  <div className="font-medium">{session.identity_name}</div>
                  <div className="font-mono text-xs text-slate-500">{session.username}</div>
                  <div className="mt-1 text-xs capitalize text-slate-400">{session.identity_type}</div>
                </td>
                <td className="px-4 py-3">
                  <div>{session.router_name}</div>
                  <div className="text-xs text-slate-500">{session.framed_ip_address || "—"}</div>
                  <div className="text-xs text-slate-400">{session.calling_station_id || "—"}</div>
                </td>
                <td className="px-4 py-3">{session.package_name || "—"}</td>
                <td className="px-4 py-3">
                  <div className="font-medium">{formatBytes(session.total_bytes)}</div>
                  <div className="text-xs text-slate-500">
                    ↓ {formatBytes(session.output_bytes)} · ↑ {formatBytes(session.input_bytes)}
                  </div>
                </td>
                <td className="px-4 py-3 font-mono text-xs">{formatDuration(session.session_seconds)}</td>
                <td className="px-4 py-3 font-mono text-xs">{session.last_rate_limit || "—"}</td>
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2 py-1 text-xs ${session.status === "active" ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>
                    {session.status}
                  </span>
                  {session.last_control_error && <div className="mt-1 max-w-48 text-xs text-red-600">Control error</div>}
                </td>
                {canControl && (
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-2">
                      <button
                        className="rounded border border-slate-300 px-2 py-1 text-xs disabled:opacity-50"
                        disabled={busy === session.id || session.status !== "active"}
                        onClick={() => void control(session, "refresh-policy")}
                      >
                        Apply policy
                      </button>
                      <button
                        className="rounded border border-red-200 px-2 py-1 text-xs text-red-700 disabled:opacity-50"
                        disabled={busy === session.id || session.status !== "active"}
                        onClick={() => void control(session, "disconnect")}
                      >
                        Disconnect
                      </button>
                    </div>
                  </td>
                )}
              </tr>
            ))}
            {sessions.length === 0 && (
              <tr><td className="px-4 py-8 text-center text-slate-500" colSpan={canControl ? 8 : 7}>No matching sessions.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
