import { useCallback, useEffect, useMemo, useState } from "react";

import { request } from "./api";

type UsagePoint = {
  period_start: string;
  input_bytes: number;
  output_bytes: number;
  total_bytes: number;
  session_seconds: number;
};

type IdentityUsage = {
  identity_type: "subscriber" | "voucher";
  identity_key: string;
  identity_name: string;
  username: string;
  input_bytes: number;
  output_bytes: number;
  total_bytes: number;
  session_seconds: number;
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
  return `${hours}h ${minutes}m`;
}

function toLocalInput(value: Date) {
  const offset = value.getTimezoneOffset() * 60000;
  return new Date(value.getTime() - offset).toISOString().slice(0, 16);
}

export function AnalyticsPage({ access }: { access: string }) {
  const [start, setStart] = useState(() => toLocalInput(new Date(Date.now() - 7 * 86400000)));
  const [end, setEnd] = useState(() => toLocalInput(new Date()));
  const [granularity, setGranularity] = useState<"hour" | "day">("hour");
  const [identityType, setIdentityType] = useState("");
  const [ordering, setOrdering] = useState("-total_bytes");
  const [series, setSeries] = useState<UsagePoint[]>([]);
  const [identities, setIdentities] = useState<IdentityUsage[]>([]);
  const [error, setError] = useState("");

  const params = useMemo(() => {
    const startIso = new Date(start).toISOString();
    const endIso = new Date(end).toISOString();
    return { startIso, endIso };
  }, [end, start]);

  const load = useCallback(async () => {
    setError("");
    const seriesParams = new URLSearchParams({
      start: params.startIso,
      end: params.endIso,
      granularity,
    });
    const identityParams = new URLSearchParams({
      start: params.startIso,
      end: params.endIso,
      ordering,
      limit: "200",
    });
    if (identityType) {
      seriesParams.set("identity_type", identityType);
      identityParams.set("identity_type", identityType);
    }
    try {
      const [points, rows] = await Promise.all([
        request<UsagePoint[]>(`/analytics/usage/?${seriesParams.toString()}`, {}, access),
        request<IdentityUsage[]>(`/analytics/identities/?${identityParams.toString()}`, {}, access),
      ]);
      setSeries(points);
      setIdentities(rows);
    } catch {
      setError("Unable to load analytics for this range.");
    }
  }, [access, granularity, identityType, ordering, params]);

  useEffect(() => {
    void load();
  }, [load]);

  const totals = useMemo(
    () =>
      series.reduce(
        (result, point) => ({
          input: result.input + point.input_bytes,
          output: result.output + point.output_bytes,
          total: result.total + point.total_bytes,
        }),
        { input: 0, output: 0, total: 0 },
      ),
    [series],
  );

  const maxTraffic = useMemo(
    () => Math.max(1, ...series.map((point) => point.total_bytes)),
    [series],
  );

  function preset(days: number) {
    const now = new Date();
    setEnd(toLocalInput(now));
    setStart(toLocalInput(new Date(now.getTime() - days * 86400000)));
    setGranularity(days > 7 ? "day" : "hour");
  }

  return (
    <div className="space-y-5">
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm">
            <span className="mb-1 block font-medium">From</span>
            <input className="input" type="datetime-local" value={start} onChange={(event) => setStart(event.target.value)} />
          </label>
          <label className="text-sm">
            <span className="mb-1 block font-medium">To</span>
            <input className="input" type="datetime-local" value={end} onChange={(event) => setEnd(event.target.value)} />
          </label>
          <label className="text-sm">
            <span className="mb-1 block font-medium">Granularity</span>
            <select className="input" value={granularity} onChange={(event) => setGranularity(event.target.value as "hour" | "day")}>
              <option value="hour">Hourly</option>
              <option value="day">Daily</option>
            </select>
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
            <span className="mb-1 block font-medium">Sort users</span>
            <select className="input" value={ordering} onChange={(event) => setOrdering(event.target.value)}>
              <option value="-total_bytes">Total usage ↓</option>
              <option value="total_bytes">Total usage ↑</option>
              <option value="-output_bytes">Download ↓</option>
              <option value="-input_bytes">Upload ↓</option>
              <option value="-session_seconds">Session time ↓</option>
              <option value="username">Username</option>
            </select>
          </label>
          <button className="rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white" onClick={() => void load()}>
            Apply
          </button>
        </div>
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          <button className="rounded border border-slate-300 px-2 py-1" onClick={() => preset(1)}>24 hours</button>
          <button className="rounded border border-slate-300 px-2 py-1" onClick={() => preset(7)}>7 days</button>
          <button className="rounded border border-slate-300 px-2 py-1" onClick={() => preset(30)}>30 days</button>
          <button className="rounded border border-slate-300 px-2 py-1" onClick={() => preset(90)}>Quarter</button>
        </div>
      </div>

      {error && <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <div className="grid gap-4 sm:grid-cols-3">
        <Metric label="Total" value={formatBytes(totals.total)} />
        <Metric label="Download" value={formatBytes(totals.output)} />
        <Metric label="Upload" value={formatBytes(totals.input)} />
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="font-semibold">Traffic over time</h2>
        <div className="mt-4 flex h-48 items-end gap-1 overflow-hidden border-b border-slate-200 pb-1">
          {series.map((point) => {
            const height = Math.max(3, Math.round((point.total_bytes / maxTraffic) * 100));
            return (
              <div
                key={point.period_start}
                className="min-w-1 flex-1 rounded-t bg-slate-700"
                style={{ height: `${height}%` }}
                title={`${new Date(point.period_start).toLocaleString()} — ${formatBytes(point.total_bytes)}`}
              />
            );
          })}
          {series.length === 0 && <p className="self-center text-sm text-slate-500">No traffic in this range.</p>}
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Identity</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Download</th>
              <th className="px-4 py-3">Upload</th>
              <th className="px-4 py-3">Total</th>
              <th className="px-4 py-3">Session time</th>
            </tr>
          </thead>
          <tbody>
            {identities.map((row) => (
              <tr key={row.identity_key} className="border-t border-slate-100">
                <td className="px-4 py-3">
                  <div className="font-medium">{row.identity_name}</div>
                  <div className="font-mono text-xs text-slate-500">{row.username}</div>
                </td>
                <td className="px-4 py-3 capitalize">{row.identity_type}</td>
                <td className="px-4 py-3">{formatBytes(row.output_bytes)}</td>
                <td className="px-4 py-3">{formatBytes(row.input_bytes)}</td>
                <td className="px-4 py-3 font-medium">{formatBytes(row.total_bytes)}</td>
                <td className="px-4 py-3">{formatDuration(row.session_seconds)}</td>
              </tr>
            ))}
            {identities.length === 0 && (
              <tr><td className="px-4 py-8 text-center text-slate-500" colSpan={6}>No matching usage data.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value}</div>
    </div>
  );
}
