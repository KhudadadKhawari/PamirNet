import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { request } from "./api";

type Package = {
  id: string;
  name: string;
  description: string;
  duration_value: number;
  duration_unit: "day" | "week" | "month";
  download_speed_mbps: number;
  upload_speed_mbps: number;
  price: string | null;
  currency: string;
  simultaneous_sessions: number;
  enabled: boolean;
};

export function PackagesPage({ access, canManage }: { access: string; canManage: boolean }) {
  const [packages, setPackages] = useState<Package[]>([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState("");
  const [download, setDownload] = useState("10");
  const [upload, setUpload] = useState("5");
  const [durationValue, setDurationValue] = useState("1");
  const [durationUnit, setDurationUnit] = useState<Package["duration_unit"]>("month");
  const [price, setPrice] = useState("");

  async function load() {
    try {
      setPackages(await request<Package[]>("/packages/", {}, access));
      setError("");
    } catch {
      setError("Unable to load packages.");
    }
  }

  useEffect(() => {
    void load();
  }, [access]);

  async function createPackage(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await request<Package>(
        "/packages/",
        {
          method: "POST",
          body: JSON.stringify({
            name,
            duration_value: Number(durationValue),
            duration_unit: durationUnit,
            download_speed_mbps: Number(download),
            upload_speed_mbps: Number(upload),
            price: price || null,
            simultaneous_sessions: 1,
          }),
        },
        access,
      );
      setName("");
      setPrice("");
      await load();
    } catch (rawError) {
      const apiError = rawError as Error & { payload?: { detail?: string } };
      setError(apiError.payload?.detail || "Unable to create package.");
    } finally {
      setSaving(false);
    }
  }

  async function togglePackage(pkg: Package) {
    await request<Package>(
      `/packages/${pkg.id}/`,
      { method: "PATCH", body: JSON.stringify({ enabled: !pkg.enabled }) },
      access,
    );
    await load();
  }

  return (
    <div className="space-y-5">
      {canManage && (
        <form onSubmit={createPackage} className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="font-semibold">Create package</h2>
              <p className="text-xs text-slate-500">Speed and calendar duration for subscriber access.</p>
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-6">
            <input className="input md:col-span-2" placeholder="Package name" value={name} onChange={(event) => setName(event.target.value)} required />
            <input className="input" type="number" min="1" placeholder="Download Mbps" value={download} onChange={(event) => setDownload(event.target.value)} required />
            <input className="input" type="number" min="1" placeholder="Upload Mbps" value={upload} onChange={(event) => setUpload(event.target.value)} required />
            <div className="flex gap-2">
              <input className="input min-w-0" type="number" min="1" value={durationValue} onChange={(event) => setDurationValue(event.target.value)} required />
              <select className="input" value={durationUnit} onChange={(event) => setDurationUnit(event.target.value as Package["duration_unit"])}>
                <option value="day">Day</option>
                <option value="week">Week</option>
                <option value="month">Month</option>
              </select>
            </div>
            <input className="input" type="number" min="0" step="0.01" placeholder="Price (optional)" value={price} onChange={(event) => setPrice(event.target.value)} />
          </div>
          <div className="mt-3 flex justify-end">
            <button className="rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50" disabled={saving}>{saving ? "Creating…" : "Create package"}</button>
          </div>
        </form>
      )}

      {error && <p className="text-sm text-red-700">{error}</p>}
      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="px-4 py-3">Package</th>
              <th>Speed</th>
              <th>Duration</th>
              <th>Price</th>
              <th>Status</th>
              <th className="px-4 text-right">Action</th>
            </tr>
          </thead>
          <tbody>
            {packages.map((pkg) => (
              <tr key={pkg.id} className="border-t border-slate-100">
                <td className="px-4 py-3 font-medium">{pkg.name}</td>
                <td>{pkg.download_speed_mbps}↓ / {pkg.upload_speed_mbps}↑ Mbps</td>
                <td>{pkg.duration_value} {pkg.duration_unit}{pkg.duration_value === 1 ? "" : "s"}</td>
                <td>{pkg.price ? `${pkg.price} ${pkg.currency}` : "—"}</td>
                <td><span className={`rounded-full px-2 py-1 text-xs ${pkg.enabled ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>{pkg.enabled ? "Enabled" : "Disabled"}</span></td>
                <td className="px-4 text-right">
                  {canManage && <button className="rounded border border-slate-300 px-3 py-1.5" onClick={() => void togglePackage(pkg)}>{pkg.enabled ? "Disable" : "Enable"}</button>}
                </td>
              </tr>
            ))}
            {packages.length === 0 && <tr><td className="px-4 py-8 text-center text-slate-500" colSpan={6}>No packages yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
