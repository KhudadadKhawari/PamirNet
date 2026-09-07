import { useCallback, useEffect, useMemo, useState } from "react";

import { request } from "./api";

type TrafficPoint = {
  period_start: string;
  input_bytes: number;
  output_bytes: number;
};

type RouterSummary = {
  id: string;
  name: string;
  status: string;
  latency_ms: number | null;
  packet_loss_percent: number | null;
  uptime_seconds: number | null;
  last_seen_at: string | null;
};

type Dashboard = {
  online_sessions: number;
  active_subscribers: number;
  active_vouchers: number;
  today_input_bytes: number;
  today_output_bytes: number;
  today_total_bytes: number;
  traffic_24h: TrafficPoint[];
  routers: RouterSummary[];
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

function formatUptime(seconds: number | null) {
  if (seconds == null) return "—";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  return `${days}d ${hours}h`;
}

export function DashboardPage({ access }: { access: string }) {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setDashboard(await request<Dashboard>("/dashboard/", {}, access));
      setError("");
    } catch {
      setError("Unable to load dashboard data.");
    }
  }, [access]);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 30000);
    return () => window.clearInterval(timer);
  }, [load]);

  const maxTraffic = useMemo(() => {
    if (!dashboard?.traffic_24h.length) return 1;
    return Math.max(
      1,
      ...dashboard.traffic_24h.map((point) => point.input_bytes + point.output_bytes),
    );
  }, [dashboard]);

  if (error) return <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>;
  if (!dashboard) return <p className="text-sm text-slate-500">Loading dashboard…</p>;

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Online sessions" value={String(dashboard.online_sessions)} />
        <Metric label="Active subscribers" value={String(dashboard.active_subscribers)} />
        <Metric label="Active vouchers" value={String(dashboard.active_vouchers)} />
        <Metric label="Today's traffic" value={formatBytes(dashboard.today_total_bytes)} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[2fr_1fr]">
        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="font-semibold">Traffic — last 24 hours</h2>
              <p className="text-xs text-slate-500">
                ↓ {formatBytes(dashboard.today_output_bytes)} · ↑ {formatBytes(dashboard.today_input_bytes)} today
              </p>
            </div>
            <button className="rounded border border-slate-300 px-3 py-1.5 text-xs" onClick={() => void load()}>
              Refresh
            </button>
          </div>
          <div className="flex h-44 items-end gap-1 overflow-hidden border-b border-slate-200 pb-1">
            {dashboard.traffic_24h.map((point) => {
              const total = point.input_bytes + point.output_bytes;
              const height = Math.max(3, Math.round((total / maxTraffic) * 100));
              return (
                <div
                  key={point.period_start}
                  className="group relative min-w-2 flex-1 rounded-t bg-slate-700"
                  style={{ height: `${height}%` }}
                  title={`${new Date(point.period_start).toLocaleString()} — ${formatBytes(total)}`}
                >
                  <span className="sr-only">{formatBytes(total)}</span>
                </div>
              );
            })}
            {dashboard.traffic_24h.length === 0 && (
              <div className="self-center text-sm text-slate-500">No accounting traffic yet.</div>
            )}
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="font-semibold">Network health</h2>
          <div className="mt-3 space-y-3">
            {dashboard.routers.map((router) => (
              <div key={router.id} className="rounded border border-slate-100 p-3 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{router.name}</span>
                  <span className={`text-xs font-semibold uppercase ${router.status === "online" ? "text-emerald-600" : "text-red-600"}`}>
                    {router.status}
                  </span>
                </div>
                <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-slate-500">
                  <span>{router.latency_ms == null ? "—" : `${router.latency_ms.toFixed(1)} ms`}</span>
                  <span>{router.packet_loss_percent == null ? "—" : `${router.packet_loss_percent}% loss`}</span>
                  <span>{formatUptime(router.uptime_seconds)}</span>
                </div>
              </div>
            ))}
            {dashboard.routers.length === 0 && <p className="text-sm text-slate-500">No routers registered.</p>}
          </div>
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-xl font-semibold">{value}</div>
    </div>
  );
}
