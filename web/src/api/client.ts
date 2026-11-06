/** Fetch wrapper for the FastAPI server (same origin; Vite proxies /api in dev). Who is acting = X-Reviewer header (dev until login exists). */
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message) }
}
export const reviewerName = () => localStorage.getItem("reviewer") || "dev"

export async function api<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const headers: Record<string, string> = { "X-Reviewer": reviewerName(), ...(init?.headers as Record<string, string> | undefined) }
  let body = init?.body
  if (init?.json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(init.json) }
  const res = await fetch(`/api${path}`, { ...init, headers, body })
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail ?? detail } catch { /* non-JSON error body */ }
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail))
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const qs = (params: Record<string, string | number | boolean | undefined | null>) => {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") p.set(k, String(v))
  const s = p.toString(); return s ? `?${s}` : ""
}
