import { useCallback, useEffect, useState } from "react";

import { apiErrorMessage, request, type AuditLog } from "./api";
import { AuditTable } from "./PlatformPage";

export function AuditPage({ access }: { access: string }) {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [actionName, setActionName] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const query = actionName.trim()
        ? `?action=${encodeURIComponent(actionName.trim())}`
        : "";
      setLogs(await request<AuditLog[]>(`/audit/${query}`, {}, access));
      setError("");
    } catch (rawError) {
      setError(apiErrorMessage(rawError, "Unable to load audit logs."));
    }
  }, [access, actionName]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Audit Log</h2>
          <p className="text-sm text-slate-500">Append-only history of sensitive tenant actions.</p>
        </div>
        <div className="flex gap-2">
          <input
            className="input w-64"
            placeholder="Exact action, e.g. role.updated"
            value={actionName}
            onChange={(event) => setActionName(event.target.value)}
          />
          <button
            className="rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white"
            onClick={() => void load()}
          >
            Apply
          </button>
        </div>
      </div>
      {error && (
        <div className="mb-4 rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}
      <AuditTable logs={logs} />
    </div>
  );
}
