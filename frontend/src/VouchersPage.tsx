import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { downloadFile, request } from "./api";

type Package = {
  id: string;
  name: string;
  enabled: boolean;
};

type VoucherBatch = {
  id: string;
  name: string;
  package: string;
  package_name: string;
  quantity: number;
  simultaneous_sessions: number | null;
  enabled: boolean;
  generated_count: number;
  active_count: number;
  expired_count: number;
  consumed_count: number;
  disabled_count: number;
  created_at: string;
};

export function VouchersPage({
  access,
  canGenerate,
  canExport,
  canDisable,
}: {
  access: string;
  canGenerate: boolean;
  canExport: boolean;
  canDisable: boolean;
}) {
  const [batches, setBatches] = useState<VoucherBatch[]>([]);
  const [packages, setPackages] = useState<Package[]>([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState("");
  const [packageId, setPackageId] = useState("");
  const [quantity, setQuantity] = useState("100");
  const [sessions, setSessions] = useState("1");

  async function load() {
    try {
      const [batchRows, packageRows] = await Promise.all([
        request<VoucherBatch[]>("/voucher-batches/", {}, access),
        request<Package[]>("/packages/", {}, access),
      ]);
      setBatches(batchRows);
      setPackages(packageRows.filter((item) => item.enabled));
      if (!packageId && packageRows.length) {
        const first = packageRows.find((item) => item.enabled);
        if (first) setPackageId(first.id);
      }
      setError("");
    } catch {
      setError("Unable to load voucher batches.");
    }
  }

  useEffect(() => {
    void load();
  }, [access]);

  async function createBatch(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      await request<VoucherBatch>(
        "/voucher-batches/",
        {
          method: "POST",
          body: JSON.stringify({
            name,
            package_id: packageId,
            quantity: Number(quantity),
            simultaneous_sessions: sessions === "unlimited" ? null : Number(sessions),
          }),
        },
        access,
      );
      setName("");
      await load();
    } catch (rawError) {
      const apiError = rawError as Error & { payload?: { detail?: string; name?: string[] } };
      setError(apiError.payload?.detail || apiError.payload?.name?.[0] || "Unable to generate vouchers.");
    } finally {
      setSaving(false);
    }
  }

  async function disableBatch(batch: VoucherBatch) {
    if (!window.confirm(`Disable all active/unused vouchers in ${batch.name}?`)) return;
    await request(`/voucher-batches/${batch.id}/disable/`, { method: "POST" }, access);
    await load();
  }

  async function deleteBatch(batch: VoucherBatch) {
    if (!window.confirm(`Delete unused batch ${batch.name}?`)) return;
    try {
      await request(`/voucher-batches/${batch.id}/`, { method: "DELETE" }, access);
      await load();
    } catch {
      setError("Only completely unused batches can be deleted. Disable used batches instead.");
    }
  }

  return (
    <div className="space-y-5">
      {canGenerate && (
        <form onSubmit={createBatch} className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="mb-4">
            <h2 className="font-semibold">Generate voucher batch</h2>
            <p className="text-xs text-slate-500">8-digit usernames, 6-digit passwords, activation on first successful login.</p>
          </div>
          <div className="grid gap-3 md:grid-cols-5">
            <input className="input md:col-span-2" placeholder="Batch name" value={name} onChange={(event) => setName(event.target.value)} required />
            <select className="input" value={packageId} onChange={(event) => setPackageId(event.target.value)} required>
              <option value="">Select package</option>
              {packages.map((pkg) => <option key={pkg.id} value={pkg.id}>{pkg.name}</option>)}
            </select>
            <input className="input" type="number" min="1" value={quantity} onChange={(event) => setQuantity(event.target.value)} required />
            <select className="input" value={sessions} onChange={(event) => setSessions(event.target.value)}>
              <option value="1">1 device</option>
              <option value="2">2 devices</option>
              <option value="3">3 devices</option>
              <option value="unlimited">Unlimited</option>
            </select>
          </div>
          <div className="mt-3 flex justify-end">
            <button className="rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50" disabled={saving || !packageId}>
              {saving ? "Generating…" : "Generate"}
            </button>
          </div>
        </form>
      )}

      {error && <p className="text-sm text-red-700">{error}</p>}

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full min-w-[980px] text-left text-sm">
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="px-4 py-3">Batch</th>
              <th>Package</th>
              <th>Total</th>
              <th>Unused</th>
              <th>Active</th>
              <th>Expired</th>
              <th>Consumed</th>
              <th>Sessions</th>
              <th>Status</th>
              <th className="px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {batches.map((batch) => (
              <tr key={batch.id} className="border-t border-slate-100">
                <td className="px-4 py-3"><div className="font-medium">{batch.name}</div><div className="text-xs text-slate-500">{new Date(batch.created_at).toLocaleString()}</div></td>
                <td>{batch.package_name}</td>
                <td>{batch.quantity}</td>
                <td>{batch.generated_count}</td>
                <td>{batch.active_count}</td>
                <td>{batch.expired_count}</td>
                <td>{batch.consumed_count}</td>
                <td>{batch.simultaneous_sessions ?? "Unlimited"}</td>
                <td><span className={`rounded-full px-2 py-1 text-xs ${batch.enabled ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>{batch.enabled ? "Enabled" : "Disabled"}</span></td>
                <td className="px-4 text-right">
                  <div className="flex justify-end gap-2">
                    {canExport && <button className="rounded border border-slate-300 px-2 py-1.5" onClick={() => void downloadFile(`/voucher-batches/${batch.id}/export/`, `${batch.name}.csv`, access)}>CSV</button>}
                    {canDisable && batch.enabled && <button className="rounded border border-slate-300 px-2 py-1.5" onClick={() => void disableBatch(batch)}>Disable</button>}
                    {canDisable && batch.generated_count === batch.quantity && <button className="rounded border border-red-200 px-2 py-1.5 text-red-700" onClick={() => void deleteBatch(batch)}>Delete</button>}
                  </div>
                </td>
              </tr>
            ))}
            {batches.length === 0 && <tr><td className="px-4 py-8 text-center text-slate-500" colSpan={10}>No voucher batches yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
