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
export const del = <T,>(path: string, body?: unknown) => api<T>("DELETE", path, body);

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
  has_password: boolean;
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
  /** No active entitlement for the learner's canton: free practice only, no "Explain this". */
  free_tier: boolean;
  latest_payment: {
    product: string;
    canton: string;
    paid_at: string;
    refunded: boolean;
    checkout_session_id: string;
  } | null;
}

export interface Me {
  user: UserOut;
  session: {
    mfa_pending: boolean;
    mfa_setup_required: boolean;
    impersonated_by: string | null;
    /** Seconds left in which a sign-in link counts as re-authentication (account deletion). */
    reauth_seconds_left: number;
  };
  access: AccessOut;
  csrf_token: string;
}

export type ProductKey = "civics_pass_zh" | "civics_pass_ag" | "civics_extension";

/** A Civics Pass or the extension, priced from Stripe by lookup key. */
export interface ProductOut {
  key: ProductKey;
  kind: "pass" | "extension";
  /** The canton a pass is for; null for the extension. */
  canton: string | null;
  amount_cents: number | null;
  currency: string;
  months: number;
  /** False when Stripe has no price for the key right now. */
  available: boolean;
}

export interface RefundEligibility {
  eligible: boolean;
  reason: "no_payment" | "refunded" | "too_late" | "too_many_questions" | null;
  payment_id: string | null;
  product: string | null;
  canton: string | null;
  paid_at: string | null;
  deadline: string | null;
  questions_studied: number;
  max_questions: number;
  window_days: number;
}

export interface PublicConfig {
  tutor_name: string;
  terms_version: string;
  billing_enabled: boolean;
  env: string;
}

/** Cantons a learner can choose at sign-up and an admin can grant access for. */
export const CANTONS = ["zh", "ag"] as const;
/** Interface and study languages the API accepts (launch languages, D-014). */
export const LANGUAGE_CODES = ["de", "en", "fr", "it", "pt", "es", "sq", "tr"] as const;
export type LanguageCode = (typeof LANGUAGE_CODES)[number];
/** Languages a learner can study the questions in. */
export const STUDY_LANGUAGES = LANGUAGE_CODES;
/** Each language in its own name, for the interface-language choice. */
export const LANGUAGE_ENDONYMS: Record<LanguageCode, string> = {
  de: "Deutsch",
  en: "English",
  fr: "Français",
  it: "Italiano",
  pt: "Português",
  es: "Español",
  sq: "Shqip",
  tr: "Türkçe",
};

/** Two-letter code the API stores for an i18next language such as "it-CH". Unknown
 * languages map to English. */
export function apiLocale(lng: string): LanguageCode {
  const short = lng.slice(0, 2).toLowerCase();
  return (LANGUAGE_CODES as readonly string[]).includes(short) ? (short as LanguageCode) : "en";
}

export interface LoginOut {
  status: "ok" | "mfa_required" | "mfa_setup_required";
  me: Me | null;
}
