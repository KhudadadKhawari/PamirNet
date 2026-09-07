import { useEffect, useState } from "react";

type Health = {
  status: string;
  service: string;
};

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const apiBase = import.meta.env.VITE_API_BASE_URL || "/api";

    fetch(`${apiBase}/health/`)
      .then((response) => {
        if (!response.ok) throw new Error("Backend health check failed");
        return response.json() as Promise<Health>;
      })
      .then(setHealth)
      .catch(() => setError(true));
  }, []);

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-5xl items-center px-6 py-16">
        <section className="w-full rounded-xl border border-slate-800 bg-slate-900 p-8 shadow-2xl">
          <div className="mb-8 flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-400">
                ISP Operations Platform
              </p>
              <h1 className="mt-2 text-4xl font-bold tracking-tight">PamirNet</h1>
            </div>
            <span className="rounded-md border border-slate-700 px-3 py-1 text-sm text-slate-300">
              Phase 0
            </span>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <StatusCard label="Frontend" value="Ready" />
            <StatusCard
              label="Backend"
              value={health?.status === "ok" ? "Connected" : error ? "Unavailable" : "Checking..."}
            />
            <StatusCard label="Next" value="Tenancy + RBAC" />
          </div>
        </section>
      </div>
    </main>
  );
}

function StatusCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-5">
      <div className="text-sm text-slate-500">{label}</div>
      <div className="mt-1 font-semibold text-slate-200">{value}</div>
    </div>
  );
}
