/**
 * Minimal API client. All requests go to the same origin (/api/v1/...),
 * proxied by Next.js to the backend. Authentication uses the httpOnly
 * session cookie; mutating requests echo the CSRF cookie in a header.
 */

export type FieldError = { field: string; message: string };

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;
  requestId: string | null;

  constructor(status: number, code: string, message: string, details: unknown, requestId: string | null) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }

  get fieldErrors(): FieldError[] {
    return Array.isArray(this.details)
      ? (this.details as FieldError[]).filter((d) => d && typeof d === "object" && "message" in d)
      : [];
  }
}

const BASE = "/api/v1";
const AUTH_PAGES = ["/login", "/signup", "/forgot-password", "/reset-password"];

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.split("; ").find((c) => c.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.split("=").slice(1).join("=")) : null;
}

type Query = Record<string, string | number | boolean | null | undefined | (string | number)[]>;

export function buildUrl(path: string, query?: Query): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => params.append(key, String(v)));
    else params.set(key, String(value));
  }
  const qs = params.toString();
  return `${BASE}${path}${qs ? `?${qs}` : ""}`;
}

type Options = { method?: string; body?: unknown; query?: Query; form?: FormData };

export async function api<T>(path: string, opts: Options = {}): Promise<T> {
  const method = opts.method ?? (opts.body !== undefined || opts.form ? "POST" : "GET");
  const headers: Record<string, string> = { Accept: "application/json" };
  let body: BodyInit | undefined;
  if (opts.form) {
    body = opts.form;
  } else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  if (method !== "GET") {
    const csrf = readCookie("iios_csrf");
    if (csrf) headers["X-CSRF-Token"] = csrf;
  }
  let res: Response;
  try {
    res = await fetch(buildUrl(path, opts.query), { method, headers, body, credentials: "same-origin" });
  } catch {
    throw new ApiError(0, "network_error", "No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.", null, null);
  }
  if (res.ok) {
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  }
  let payload: { error?: { code?: string; message?: string; details?: unknown; request_id?: string } } = {};
  try {
    payload = await res.json();
  } catch {
    /* non-JSON error (e.g. proxy) */
  }
  const err = new ApiError(
    res.status,
    payload.error?.code ?? `http_${res.status}`,
    payload.error?.message ?? (res.status >= 500 ? "El servidor no está disponible." : "Solicitud no válida."),
    payload.error?.details ?? null,
    payload.error?.request_id ?? res.headers.get("x-request-id"),
  );
  if (typeof window !== "undefined") {
    const here = window.location.pathname;
    if (res.status === 401 && !path.startsWith("/auth/login") && !AUTH_PAGES.includes(here)) {
      window.location.href = `/login?next=${encodeURIComponent(here + window.location.search)}`;
    } else if (err.code === "password_change_required" && here !== "/change-password") {
      window.location.href = "/change-password";
    }
  }
  throw err;
}

/** URL for GET downloads (the session cookie authenticates them). */
export function downloadUrl(path: string, query?: Query): string {
  return buildUrl(path, query);
}
