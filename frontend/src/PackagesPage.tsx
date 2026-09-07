import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import { request } from "./api";

type PolicyScope = "daily" | "weekly" | "monthly" | "subscription";
type PolicyAction = "throttle" | "block";

type PolicyStage = {
  id: string;
  threshold_gb: string;
  action: PolicyAction;
  download_speed_mbps: number | null;
  upload_speed_mbps: number | null;
};

type UsagePolicy = {
  id: string;
  scope: PolicyScope;
  enabled: boolean;
  stages: PolicyStage[];
};

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
  usage_policies: UsagePolicy[];
};

type StageDraft = {
  threshold_gb: string;
  action: PolicyAction;
  download_speed_mbps: string;
  upload_speed_mbps: string;
};

type PolicyDraft = {
  scope: PolicyScope;
  enabled: boolean;
  stages: StageDraft[];
};

const scopeLabels: Record<PolicyScope, string> = {
  daily: "Daily",
  weekly: "Weekly",
  monthly: "Monthly",
  subscription: "Subscription",
};

const scopeOrder: PolicyScope[] = ["daily", "weekly", "monthly", "subscription"];

function toDrafts(pkg: Package): PolicyDraft[] {
  return pkg.usage_policies
    .map((policy) => ({
      scope: policy.scope,
      enabled: policy.enabled,
      stages: policy.stages.map((stage) => ({
        threshold_gb: stage.threshold_gb,
        action: stage.action,
        download_speed_mbps: stage.download_speed_mbps?.toString() || "",
        upload_speed_mbps: stage.upload_speed_mbps?.toString() || "",
      })),
    }))
    .sort((a, b) => scopeOrder.indexOf(a.scope) - scopeOrder.indexOf(b.scope));
}

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
  const [selectedPackageId, setSelectedPackageId] = useState("");
  const [policyDrafts, setPolicyDrafts] = useState<PolicyDraft[]>([]);

  const selectedPackage = useMemo(
    () => packages.find((pkg) => pkg.id === selectedPackageId) || null,
    [packages, selectedPackageId],
  );

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
    try {
      await request<Package>(
        `/packages/${pkg.id}/`,
        { method: "PATCH", body: JSON.stringify({ enabled: !pkg.enabled }) },
        access,
      );
      await load();
    } catch {
      setError("Unable to update package.");
    }
  }

  function editPolicies(pkg: Package) {
    setSelectedPackageId(pkg.id);
    setPolicyDrafts(toDrafts(pkg));
    setError("");
  }

  function addPolicy(scope: PolicyScope) {
    if (policyDrafts.some((policy) => policy.scope === scope)) return;
    setPolicyDrafts((current) => [
      ...current,
      { scope, enabled: true, stages: [] },
    ].sort((a, b) => scopeOrder.indexOf(a.scope) - scopeOrder.indexOf(b.scope)));
  }

  function updatePolicy(index: number, patch: Partial<PolicyDraft>) {
    setPolicyDrafts((current) => current.map((policy, itemIndex) => (
      itemIndex === index ? { ...policy, ...patch } : policy
    )));
  }

  function addStage(policyIndex: number) {
    if (!selectedPackage) return;
    const stage: StageDraft = {
      threshold_gb: "10",
      action: "throttle",
      download_speed_mbps: Math.max(1, Math.floor(selectedPackage.download_speed_mbps / 2)).toString(),
      upload_speed_mbps: Math.max(1, Math.floor(selectedPackage.upload_speed_mbps / 2)).toString(),
    };
    setPolicyDrafts((current) => current.map((policy, index) => (
      index === policyIndex ? { ...policy, stages: [...policy.stages, stage] } : policy
    )));
  }

  function updateStage(policyIndex: number, stageIndex: number, patch: Partial<StageDraft>) {
    setPolicyDrafts((current) => current.map((policy, index) => {
      if (index !== policyIndex) return policy;
      return {
        ...policy,
        stages: policy.stages.map((stage, itemIndex) => (
          itemIndex === stageIndex ? { ...stage, ...patch } : stage
        )),
      };
    }));
  }

  function removeStage(policyIndex: number, stageIndex: number) {
    setPolicyDrafts((current) => current.map((policy, index) => (
      index === policyIndex
        ? { ...policy, stages: policy.stages.filter((_, itemIndex) => itemIndex !== stageIndex) }
        : policy
    )));
  }

  async function savePolicies() {
    if (!selectedPackage) return;
    if (policyDrafts.some((policy) => policy.stages.length === 0)) {
      setError("Every enabled policy definition needs at least one stage.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const payload = policyDrafts.map((policy) => ({
        scope: policy.scope,
        enabled: policy.enabled,
        stages: policy.stages.map((stage) => ({
          threshold_gb: stage.threshold_gb,
          action: stage.action,
          download_speed_mbps: stage.action === "throttle" ? Number(stage.download_speed_mbps) : null,
          upload_speed_mbps: stage.action === "throttle" ? Number(stage.upload_speed_mbps) : null,
        })),
      }));
      const updated = await request<Package>(
        `/packages/${selectedPackage.id}/`,
        { method: "PATCH", body: JSON.stringify({ usage_policies: payload }) },
        access,
      );
      await load();
      setPolicyDrafts(toDrafts(updated));
    } catch (rawError) {
      const apiError = rawError as Error & { payload?: { detail?: string } };
      setError(apiError.payload?.detail || "Unable to save FUP policies. Check stage values and speeds.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      {canManage && (
        <form onSubmit={createPackage} className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="font-semibold">Create package</h2>
              <p className="text-xs text-slate-500">Base speed and calendar duration. Configure quota/FUP after creation.</p>
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
        <table className="w-full min-w-[880px] text-left text-sm">
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="px-4 py-3">Package</th>
              <th>Speed</th>
              <th>Duration</th>
              <th>Price</th>
              <th>FUP</th>
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
                <td>{pkg.usage_policies.length ? `${pkg.usage_policies.length} polic${pkg.usage_policies.length === 1 ? "y" : "ies"}` : "None"}</td>
                <td><span className={`rounded-full px-2 py-1 text-xs ${pkg.enabled ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>{pkg.enabled ? "Enabled" : "Disabled"}</span></td>
                <td className="px-4 text-right">
                  {canManage && (
                    <div className="flex justify-end gap-2">
                      <button className="rounded border border-slate-300 px-3 py-1.5" onClick={() => editPolicies(pkg)}>FUP / quota</button>
                      <button className="rounded border border-slate-300 px-3 py-1.5" onClick={() => void togglePackage(pkg)}>{pkg.enabled ? "Disable" : "Enable"}</button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {packages.length === 0 && <tr><td className="px-4 py-8 text-center text-slate-500" colSpan={7}>No packages yet.</td></tr>}
          </tbody>
        </table>
      </div>

      {canManage && selectedPackage && (
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="font-semibold">FUP & quota — {selectedPackage.name}</h2>
              <p className="text-xs text-slate-500">Usage is upload + download combined. The most restrictive active stage wins.</p>
            </div>
            <button className="rounded border border-slate-300 px-3 py-1.5 text-sm" onClick={() => setSelectedPackageId("")}>Close</button>
          </div>

          <div className="mb-4 flex flex-wrap gap-2">
            {scopeOrder.filter((scope) => !policyDrafts.some((policy) => policy.scope === scope)).map((scope) => (
              <button key={scope} className="rounded border border-slate-300 px-3 py-1.5 text-sm" onClick={() => addPolicy(scope)}>+ {scopeLabels[scope]}</button>
            ))}
          </div>

          <div className="space-y-4">
            {policyDrafts.map((policy, policyIndex) => (
              <div key={policy.scope} className="rounded border border-slate-200 p-3">
                <div className="mb-3 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <strong>{scopeLabels[policy.scope]}</strong>
                    <label className="flex items-center gap-2 text-xs text-slate-600">
                      <input type="checkbox" checked={policy.enabled} onChange={(event) => updatePolicy(policyIndex, { enabled: event.target.checked })} />
                      Enabled
                    </label>
                  </div>
                  <button className="text-xs text-red-700" onClick={() => setPolicyDrafts((current) => current.filter((_, index) => index !== policyIndex))}>Remove policy</button>
                </div>

                <div className="space-y-2">
                  {policy.stages.map((stage, stageIndex) => (
                    <div key={`${policy.scope}-${stageIndex}`} className="grid gap-2 md:grid-cols-[1.2fr_1.2fr_1fr_1fr_auto]">
                      <input className="input" type="number" min="0.001" step="0.001" value={stage.threshold_gb} onChange={(event) => updateStage(policyIndex, stageIndex, { threshold_gb: event.target.value })} placeholder="Threshold GB" />
                      <select className="input" value={stage.action} onChange={(event) => updateStage(policyIndex, stageIndex, { action: event.target.value as PolicyAction })}>
                        <option value="throttle">Throttle</option>
                        <option value="block">Block</option>
                      </select>
                      <input className="input" type="number" min="1" max={selectedPackage.download_speed_mbps} disabled={stage.action === "block"} value={stage.download_speed_mbps} onChange={(event) => updateStage(policyIndex, stageIndex, { download_speed_mbps: event.target.value })} placeholder="Down Mbps" />
                      <input className="input" type="number" min="1" max={selectedPackage.upload_speed_mbps} disabled={stage.action === "block"} value={stage.upload_speed_mbps} onChange={(event) => updateStage(policyIndex, stageIndex, { upload_speed_mbps: event.target.value })} placeholder="Up Mbps" />
                      <button className="rounded border border-slate-300 px-3 text-sm" onClick={() => removeStage(policyIndex, stageIndex)}>×</button>
                    </div>
                  ))}
                </div>
                <button className="mt-3 rounded border border-slate-300 px-3 py-1.5 text-sm" onClick={() => addStage(policyIndex)}>+ Add stage</button>
              </div>
            ))}
          </div>

          <div className="mt-4 flex justify-end">
            <button className="rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50" disabled={saving} onClick={() => void savePolicies()}>{saving ? "Saving…" : "Save FUP policies"}</button>
          </div>
        </section>
      )}
    </div>
  );
}
