import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import { request } from "./api";

type Package = {
  id: string;
  name: string;
  enabled: boolean;
  download_speed_mbps: number;
  upload_speed_mbps: number;
};

type Subscription = {
  id: string;
  package: string;
  package_name: string;
  duration_value: number;
  duration_unit: string;
  started_at: string;
  expires_at: string;
  status: string;
};

type Subscriber = {
  id: string;
  name: string;
  phone: string;
  address: string;
  notes: string;
  status: string;
  mac_lock_mode: string;
  mac_address: string;
  last_mac_address: string;
  last_authenticated_at: string | null;
  username: string;
  active_subscription: Subscription | null;
};

type CreateResult = { subscriber: Subscriber; generated_password?: string };

type SecretNotice = { title: string; username?: string; password: string } | null;

export function SubscribersPage({
  access,
  canCreate,
  canEdit,
}: {
  access: string;
  canCreate: boolean;
  canEdit: boolean;
}) {
  const [subscribers, setSubscribers] = useState<Subscriber[]>([]);
  const [packages, setPackages] = useState<Package[]>([]);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [packageId, setPackageId] = useState("");
  const [macMode, setMacMode] = useState("none");
  const [macAddress, setMacAddress] = useState("");
  const [saving, setSaving] = useState(false);
  const [selectedPackages, setSelectedPackages] = useState<Record<string, string>>({});
  const [secretNotice, setSecretNotice] = useState<SecretNotice>(null);

  async function load() {
    try {
      const [subscriberRows, packageRows] = await Promise.all([
        request<Subscriber[]>("/subscribers/", {}, access),
        request<Package[]>("/packages/", {}, access),
      ]);
      setSubscribers(subscriberRows);
      setPackages(packageRows);
      setSelectedPackages((current) => {
        const next = { ...current };
        subscriberRows.forEach((subscriber) => {
          if (!next[subscriber.id]) {
            next[subscriber.id] = subscriber.active_subscription?.package || "";
          }
        });
        return next;
      });
      setError("");
    } catch {
      setError("Unable to load subscribers.");
    }
  }

  useEffect(() => {
    void load();
  }, [access]);

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return subscribers;
    return subscribers.filter((subscriber) =>
      `${subscriber.name} ${subscriber.username} ${subscriber.phone}`.toLowerCase().includes(needle),
    );
  }, [search, subscribers]);

  async function createSubscriber(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const result = await request<CreateResult>(
        "/subscribers/",
        {
          method: "POST",
          body: JSON.stringify({
            name,
            phone,
            username,
            password,
            package_id: packageId || null,
            mac_lock_mode: macMode,
            mac_address: macAddress,
          }),
        },
        access,
      );
      if (result.generated_password) {
        setSecretNotice({
          title: "Generated subscriber credentials",
          username: result.subscriber.username,
          password: result.generated_password,
        });
      }
      setName("");
      setPhone("");
      setUsername("");
      setPassword("");
      setMacAddress("");
      await load();
    } catch (rawError) {
      const apiError = rawError as Error & { payload?: { detail?: string } };
      setError(apiError.payload?.detail || "Unable to create subscriber.");
    } finally {
      setSaving(false);
    }
  }

  async function updateStatus(subscriber: Subscriber, newStatus: string) {
    await request<Subscriber>(
      `/subscribers/${subscriber.id}/`,
      { method: "PATCH", body: JSON.stringify({ status: newStatus }) },
      access,
    );
    await load();
  }

  async function assignPackage(subscriber: Subscriber) {
    const selected = selectedPackages[subscriber.id];
    if (!selected) return;
    await request<Subscriber>(
      `/subscribers/${subscriber.id}/assign-package/`,
      { method: "POST", body: JSON.stringify({ package_id: selected }) },
      access,
    );
    await load();
  }

  async function renew(subscriber: Subscriber) {
    await request<Subscriber>(
      `/subscribers/${subscriber.id}/renew/`,
      { method: "POST", body: "{}" },
      access,
    );
    await load();
  }

  async function generateNewPassword(subscriber: Subscriber) {
    const result = await request<{ password: string }>(
      `/subscribers/${subscriber.id}/change-password/`,
      { method: "POST", body: "{}" },
      access,
    );
    setSecretNotice({
      title: `New password for ${subscriber.name}`,
      username: subscriber.username,
      password: result.password,
    });
  }

  return (
    <div className="space-y-5">
      {secretNotice && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="font-semibold">{secretNotice.title}</div>
              <div className="mt-2 font-mono">Username: {secretNotice.username}</div>
              <div className="font-mono">Password: {secretNotice.password}</div>
              <div className="mt-1 text-xs">Save it now. PamirNet will not display this password again.</div>
            </div>
            <button className="font-semibold underline" onClick={() => setSecretNotice(null)}>Dismiss</button>
          </div>
        </div>
      )}

      {canCreate && (
        <form onSubmit={createSubscriber} className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="mb-4">
            <h2 className="font-semibold">Add subscriber</h2>
            <p className="text-xs text-slate-500">Leave username/password empty to generate credentials automatically.</p>
          </div>
          <div className="grid gap-3 md:grid-cols-4">
            <input className="input" placeholder="Name *" value={name} onChange={(event) => setName(event.target.value)} required />
            <input className="input" placeholder="Phone" value={phone} onChange={(event) => setPhone(event.target.value)} />
            <input className="input" placeholder="Username (auto if empty)" value={username} onChange={(event) => setUsername(event.target.value)} />
            <input className="input" type="password" placeholder="Password (auto if empty)" value={password} onChange={(event) => setPassword(event.target.value)} />
            <select className="input" value={packageId} onChange={(event) => setPackageId(event.target.value)}>
              <option value="">No package yet</option>
              {packages.filter((pkg) => pkg.enabled).map((pkg) => <option key={pkg.id} value={pkg.id}>{pkg.name}</option>)}
            </select>
            <select className="input" value={macMode} onChange={(event) => setMacMode(event.target.value)}>
              <option value="none">No MAC lock</option>
              <option value="manual">Manual MAC</option>
              <option value="first_login">Bind on first login</option>
            </select>
            <input className="input md:col-span-2" placeholder="MAC address" value={macAddress} onChange={(event) => setMacAddress(event.target.value)} disabled={macMode === "none"} />
          </div>
          <div className="mt-3 flex justify-end">
            <button className="rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50" disabled={saving}>{saving ? "Creating…" : "Add subscriber"}</button>
          </div>
        </form>
      )}

      <div className="flex items-center justify-between gap-3">
        <input className="input max-w-sm" placeholder="Search name, username or phone" value={search} onChange={(event) => setSearch(event.target.value)} />
        <span className="text-sm text-slate-500">{filtered.length} subscribers</span>
      </div>
      {error && <p className="text-sm text-red-700">{error}</p>}

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full min-w-[1100px] text-left text-sm">
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="px-4 py-3">Subscriber</th>
              <th>Username</th>
              <th>Status</th>
              <th>Package</th>
              <th>Expires</th>
              <th>MAC</th>
              <th className="px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((subscriber) => (
              <tr key={subscriber.id} className="border-t border-slate-100 align-top">
                <td className="px-4 py-3"><div className="font-medium">{subscriber.name}</div><div className="text-xs text-slate-500">{subscriber.phone || "No phone"}</div></td>
                <td className="font-mono">{subscriber.username}</td>
                <td>
                  {canEdit ? (
                    <select className="rounded border border-slate-300 bg-white px-2 py-1" value={subscriber.status} onChange={(event) => void updateStatus(subscriber, event.target.value)}>
                      <option value="active">Active</option>
                      <option value="disabled">Disabled</option>
                      <option value="expired">Expired</option>
                      <option value="suspended">Suspended</option>
                      <option value="quota_exhausted">Quota exhausted</option>
                    </select>
                  ) : subscriber.status}
                </td>
                <td>
                  <div className="font-medium">{subscriber.active_subscription?.package_name || "—"}</div>
                  {canEdit && <div className="mt-2 flex gap-2"><select className="rounded border border-slate-300 bg-white px-2 py-1" value={selectedPackages[subscriber.id] || ""} onChange={(event) => setSelectedPackages((current) => ({ ...current, [subscriber.id]: event.target.value }))}><option value="">Choose package</option>{packages.filter((pkg) => pkg.enabled).map((pkg) => <option key={pkg.id} value={pkg.id}>{pkg.name}</option>)}</select><button className="rounded border border-slate-300 px-2 py-1" onClick={() => void assignPackage(subscriber)}>Apply</button></div>}
                </td>
                <td>{subscriber.active_subscription ? new Date(subscriber.active_subscription.expires_at).toLocaleString() : "—"}</td>
                <td><div>{subscriber.mac_lock_mode}</div><div className="font-mono text-xs text-slate-500">{subscriber.mac_address || "—"}</div></td>
                <td className="px-4 text-right">
                  {canEdit && <div className="flex justify-end gap-2"><button className="rounded border border-slate-300 px-2 py-1 disabled:opacity-40" disabled={!subscriber.active_subscription} onClick={() => void renew(subscriber)}>Renew</button><button className="rounded border border-slate-300 px-2 py-1" onClick={() => void generateNewPassword(subscriber)}>New password</button></div>}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && <tr><td className="px-4 py-8 text-center text-slate-500" colSpan={7}>No subscribers found.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
