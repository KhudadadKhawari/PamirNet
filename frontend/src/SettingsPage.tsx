import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import { apiErrorMessage, request, type TenantSummary } from "./api";

export function SettingsPage({
  access,
  canManage,
}: {
  access: string;
  canManage: boolean;
}) {
  const [tenant, setTenant] = useState<TenantSummary | null>(null);
  const [form, setForm] = useState({ name: "", timezone: "", currency: "" });
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    try {
      const data = await request<TenantSummary>("/tenant/", {}, access);
      setTenant(data);
      setForm({ name: data.name, timezone: data.timezone, currency: data.currency });
      setError("");
    } catch (rawError) {
      setError(apiErrorMessage(rawError, "Unable to load tenant settings."));
    }
  }, [access]);

  useEffect(() => {
    void load();
  }, [load]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    try {
      const data = await request<TenantSummary>(
        "/tenant/",
        {
          method: "PATCH",
          body: JSON.stringify({ ...form, currency: form.currency.toUpperCase() }),
        },
        access,
      );
      setTenant(data);
      setForm({ name: data.name, timezone: data.timezone, currency: data.currency });
      setMessage("Settings saved.");
      setError("");
    } catch (rawError) {
      setError(apiErrorMessage(rawError, "Unable to save tenant settings."));
    }
  }

  if (!tenant && !error) return <p className="text-sm text-slate-500">Loading settings…</p>;

  return (
    <div className="max-w-3xl">
      <div className="mb-5">
        <h2 className="text-xl font-semibold">Tenant Settings</h2>
        <p className="text-sm text-slate-500">Identity, timezone and default display currency.</p>
      </div>
      {error && (
        <div className="mb-4 rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}
      {message && (
        <div className="mb-4 rounded border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {message}
        </div>
      )}
      {tenant && (
        <form onSubmit={submit} className="rounded-lg border border-slate-200 bg-white p-5">
          <div className="mb-5 grid gap-4 md:grid-cols-2">
            <ReadOnlyField label="Slug" value={tenant.slug} />
            <ReadOnlyField label="Status" value={tenant.status} />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="block text-sm font-medium">
              <span className="mb-1 block">Tenant name</span>
              <input
                className="input"
                value={form.name}
                disabled={!canManage}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                required
              />
            </label>
            <label className="block text-sm font-medium">
              <span className="mb-1 block">Timezone</span>
              <input
                className="input"
                value={form.timezone}
                disabled={!canManage}
                placeholder="Asia/Kabul"
                onChange={(event) => setForm({ ...form, timezone: event.target.value })}
                required
              />
            </label>
            <label className="block text-sm font-medium">
              <span className="mb-1 block">Currency</span>
              <input
                className="input"
                maxLength={3}
                value={form.currency}
                disabled={!canManage}
                placeholder="AFN"
                onChange={(event) => setForm({ ...form, currency: event.target.value.toUpperCase() })}
                required
              />
            </label>
          </div>
          {canManage ? (
            <button className="mt-5 rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white">
              Save settings
            </button>
          ) : (
            <p className="mt-5 text-sm text-slate-500">You have read-only access to tenant settings.</p>
          )}
        </form>
      )}
    </div>
  );
}

function ReadOnlyField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="mb-1 text-sm font-medium">{label}</div>
      <div className="rounded border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
        {value}
      </div>
    </div>
  );
}
