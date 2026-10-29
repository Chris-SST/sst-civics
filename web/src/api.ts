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

export interface UserOut {
  id: string;
  role: "parent" | "student" | "adult" | "tutor" | "admin";
  email: string | null;
  username: string | null;
  first_name: string;
  locale: string;
  email_verified: boolean;
  totp_enabled: boolean;
}

export interface FamilyOut {
  id: string;
  locale: string;
  plan_key: string | null;
  subscription_status: string | null;
  quantity: number;
  current_period_end: string | null;
  trial_end: string | null;
  cancel_at_period_end: boolean;
  payment_warning: boolean;
  free_access_until: string | null;
  tutor_credits: number;
  access: "full" | "read_only" | "none";
  has_stripe_customer: boolean;
  student_count: number;
}

export interface Me {
  user: UserOut;
  session: { mfa_pending: boolean; mfa_setup_required: boolean; impersonated_by: string | null };
  family: FamilyOut | null;
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

export interface StudentOut {
  id: string;
  first_name: string;
  year_of_birth: number | null;
  curriculum: string | null;
  courses: string[];
  locale: string;
  username: string | null;
  email: string | null;
  invite_pending: boolean;
  last_login_at: string | null;
}

export interface PublicConfig {
  tutor_name: string;
  main_site_url: string;
  terms_version: string;
  billing_enabled: boolean;
  env: string;
}
