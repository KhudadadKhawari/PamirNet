const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

export type TenantSummary = {
  id: string;
  name: string;
  slug: string;
  status: string;
  timezone: string;
  currency: string;
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
