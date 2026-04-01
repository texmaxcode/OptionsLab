import { getToken, removeToken } from "./auth";

/**
 * Base URL for the backend API. When running in the browser, uses the same
 * host as the page and port 8000 so the app works from any device on the
 * network (e.g. http://192.168.1.16:3000 → API at http://192.168.1.16:8000).
 * Override with NEXT_PUBLIC_API_URL if needed.
 */
export function getApiBase(): string {
  if (typeof window !== "undefined") {
    const env = process.env.NEXT_PUBLIC_API_URL;
    if (env) return env;
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

export async function fetchApi<T>(
  path: string,
  options?: RequestInit & { allowEmpty?: boolean; skipAuth?: boolean }
): Promise<T> {
  const { allowEmpty, skipAuth, ...init } = options ?? {};

  const authHeaders: Record<string, string> = {};
  if (!skipAuth) {
    const token = getToken();
    if (token) authHeaders["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${getApiBase()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...init.headers,
    },
  });

  if (res.status === 401 && !skipAuth) {
    // Token expired or invalid — clear it and redirect to login
    removeToken();
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new Error("Session expired. Please log in again.");
  }

  if (!res.ok) {
    // Try to surface structured FastAPI error messages ({"detail": ...})
    let message = `HTTP ${res.status}`;
    try {
      const contentType = res.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        const data = (await res.json()) as unknown;
        if (data && typeof data === "object" && "detail" in data) {
          const detail = (data as { detail?: unknown }).detail;
          if (typeof detail === "string" && detail.trim()) {
            message = detail;
          } else if (Array.isArray(detail) && detail.length > 0) {
            // Validation-style errors: show first message
            const first = detail[0] as { msg?: string };
            if (first?.msg) message = first.msg;
          }
        }
      } else {
        const text = await res.text();
        if (text.trim()) message = text;
      }
    } catch {
      // fall back to generic message
    }
    throw new Error(message);
  }
  if (allowEmpty) {
    if (res.status === 204) return undefined as T;
    const text = await res.text();
    if (!text.trim()) return undefined as T;
    return JSON.parse(text) as T;
  }
  return (await res.json()) as Promise<T>;
}
