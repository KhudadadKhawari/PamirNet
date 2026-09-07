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

export async function request<T>(
  path: string,
  options: RequestInit = {},
  access?: string | null,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body) headers.set("Content-Type", "application/json");
  if (access) headers.set("Authorization", `Bearer ${access}`);

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
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

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
