const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

export type TenantSummary = {
  id: string;
  name: string;
  slug: string;
  status: "active" | "suspended" | string;
  timezone: string;
  currency: string;
  created_at?: string;
  updated_at?: string;
};

export type Permission = {
  code: string;
  name: string;
  category: string;
};

export type Role = {
  id: string;
  name: string;
  is_system: boolean;
  is_owner: boolean;
  permissions: Permission[];
  created_at?: string;
  updated_at?: string;
};

export type TenantMembership = {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
  roles: Role[];
  created_at: string;
  updated_at: string;
};

export type AuditLog = {
  id: number;
  tenant_id: string | null;
  tenant_name: string | null;
  action: string;
  actor_email: string | null;
  target_type: string;
  target_id: string;
  source_ip: string | null;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type PlatformMembership = {
  id: string;
  tenant_id: string;
  tenant_name: string;
  tenant_slug: string;
  tenant_status: string;
  is_active: boolean;
  roles: Array<{ id: string; name: string; is_owner: boolean }>;
};

export type PlatformUser = {
  id: number;
  email: string;
  name: string;
  is_active: boolean;
  memberships: PlatformMembership[];
  date_joined: string;
};

export type Me = {
  id: number;
  email: string;
  name: string;
  is_platform_admin: boolean;
  tenant: TenantSummary | null;
  permissions: string[];
  impersonating: boolean;
};

function headersFor(options: RequestInit, access?: string | null) {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body) headers.set("Content-Type", "application/json");
  if (access) headers.set("Authorization", `Bearer ${access}`);
  return headers;
}

async function apiFetch(path: string, options: RequestInit = {}, access?: string | null) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: headersFor(options, access),
    credentials: "include",
  });
  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    const error = new Error(`Request failed with ${response.status}`) as Error & {
      status?: number;
      payload?: unknown;
    };
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return response;
}

export function apiErrorMessage(error: unknown, fallback = "Request failed."): string {
  const payload = (error as { payload?: unknown } | undefined)?.payload;
  if (payload && typeof payload === "object") {
    const record = payload as Record<string, unknown>;
    if (typeof record.detail === "string") return record.detail;
    for (const value of Object.values(record)) {
      if (typeof value === "string") return value;
      if (Array.isArray(value) && value.length > 0) return String(value[0]);
      if (value && typeof value === "object") {
        const nested = Object.values(value as Record<string, unknown>)[0];
        if (typeof nested === "string") return nested;
        if (Array.isArray(nested) && nested.length > 0) return String(nested[0]);
      }
    }
  }
  return fallback;
}

export async function request<T>(
  path: string,
  options: RequestInit = {},
  access?: string | null,
): Promise<T> {
  const response = await apiFetch(path, options, access);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function downloadFile(
  path: string,
  fallbackName: string,
  access?: string | null,
): Promise<void> {
  const response = await apiFetch(path, {}, access);
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^";]+)"?/i);
  const filename = match?.[1] || fallbackName;
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
