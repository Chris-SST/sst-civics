/** Fetch wrapper for the SST API. Same-origin cookies carry the session; the CSRF
 * cookie is echoed in a header on state-changing requests. */

export class ApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string) {
    super(code);
    this.status = status;
    this.code = code;
  }
}

function readCookie(name: string): string | null {
  const m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
  return m ? decodeURIComponent(m[1]) : null;
}

export async function ensureCsrf(): Promise<string> {
  const existing = readCookie("sst_csrf");
  if (existing) return existing;
  const r = await fetch("/api/auth/csrf", { credentials: "same-origin" });
  const data = (await r.json()) as { csrf_token: string };
  return data.csrf_token;
}

export async function api<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") headers["X-CSRF-Token"] = await ensureCsrf();
  const r = await fetch(path, {
    method,
    headers,
    credentials: "same-origin",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (r.status === 204) return undefined as T;
  let data: unknown = null;
  try {
    data = await r.json();
  } catch {
    data = null;
  }
  if (!r.ok) {
    const detail = (data as { detail?: unknown } | null)?.detail;
    let code = "unknown_error";
    if (typeof detail === "string") code = detail;
    else if (Array.isArray(detail) && detail.length) code = "validation_error";
    else if (r.status === 429) code = "rate_limited";
    throw new ApiError(r.status, code);
  }
  return data as T;
}

export const get = <T,>(path: string) => api<T>("GET", path);
export const post = <T,>(path: string, body?: unknown) => api<T>("POST", path, body);
export const patch = <T,>(path: string, body?: unknown) => api<T>("PATCH", path, body);
export const del = <T,>(path: string) => api<T>("DELETE", path);

export type Role = "learner" | "admin";

export interface UserOut {
  id: string;
  role: Role;
  email: string | null;
  locale: string;
  study_language: string;
  canton: string;
  email_verified: boolean;
  totp_enabled: boolean;
}

export interface EntitlementOut {
  id: string;
  canton: string;
  starts_at: string;
  expires_at: string;
  source: "stripe" | "admin" | "trial";
  active: boolean;
}

export interface AccessOut {
  /** Access for the learner's own canton. */
  access: "full" | "none";
  canton: string;
  entitlements: EntitlementOut[];
  has_stripe_customer: boolean;
}

export interface Me {
  user: UserOut;
  session: { mfa_pending: boolean; mfa_setup_required: boolean; impersonated_by: string | null };
  access: AccessOut;
  csrf_token: string;
}

export interface PlanOut {
  key: string;
  kind: "subscription" | "addon";
  amount_cents: number | null;
  currency: string;
  interval: string | null;
  monthly_message_limit: number | null;
  daily_message_limit: number | null;
}

export interface PublicConfig {
  tutor_name: string;
  terms_version: string;
  billing_enabled: boolean;
  env: string;
}

/** Cantons a learner can choose at sign-up and an admin can grant access for. */
export const CANTONS = ["zh", "ag"] as const;
/** Languages a learner can study the questions in. */
export const STUDY_LANGUAGES = ["en", "de", "fr"] as const;
