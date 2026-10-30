import { createHmac } from "node:crypto";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, request, type APIRequestContext, type Page } from "@playwright/test";

const here = fileURLToPath(new URL(".", import.meta.url));
const PORT = Number(process.env.E2E_PORT ?? 8100);
export const BASE_URL = `http://127.0.0.1:${PORT}`;
const OUTBOX = resolve(here, "../../var/e2e/outbox");

// Must match tests/e2e/start_server.py.
export const ADMIN_EMAIL = "e2e-admin@example.ch";
export const ADMIN_PASSWORD = "E2e-admin-password-1";
const ADMIN_TOTP_SECRET = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP";
const WEBHOOK_SECRET = "whsec_e2e_test_secret";

let counter = 0;
export function freshEmail(prefix: string): string {
  counter += 1;
  return `${prefix}-${Date.now().toString(36)}${counter}@example.ch`;
}

// --- Email (EMAIL_BACKEND=console writes .eml files) ---------------------------------------

function decodeQuotedPrintable(s: string): string {
  return s.replace(/=\r?\n/g, "").replace(/=([0-9A-F]{2})/g, (_, h: string) => String.fromCharCode(parseInt(h, 16)));
}

function messagesFor(email: string): string[] {
  if (!existsSync(OUTBOX)) return [];
  return readdirSync(OUTBOX)
    .filter((f) => f.endsWith(".eml"))
    .sort()
    .map((f) => readFileSync(resolve(OUTBOX, f), "utf8"))
    .filter((raw) => new RegExp(`^To:.*${email.replace(/[.+]/g, "\$&")}`, "im").test(raw));
}

export function emailCount(email: string): number {
  return messagesFor(email).length;
}

/** The link in the newest message to `email`, once there are more than `seen` messages. */
export async function linkFromEmail(email: string, seen = 0): Promise<string> {
  let link = "";
  await expect
    .poll(
      () => {
        const all = messagesFor(email);
        if (all.length <= seen) return "";
        let raw = all[all.length - 1];
        if (/quoted-printable/i.test(raw)) raw = decodeQuotedPrintable(raw);
        const m = raw.match(/https?:\/\/[^\s"'<>]+token=[^\s"'<>]+/);
        link = m ? m[0].replace(/&amp;/g, "&") : "";
        return link;
      },
      { message: `an email with a link to ${email}`, timeout: 15_000 },
    )
    .not.toBe("");
  return link;
}

// --- Learners ---------------------------------------------------------------------------------

/** Sign up through the form, follow the verification link; the learner ends up signed in. */
export async function signUpAndVerify(page: Page, email: string): Promise<void> {
  await page.goto("/signup");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("I am 16 or older").check();
  await page.getByLabel(/I accept the/).check();
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("heading", { name: "Check your email" })).toBeVisible();
  await page.goto(await linkFromEmail(email));
  await expect(page.getByText("Your email address is confirmed and you are signed in.")).toBeVisible();
  await page.getByRole("link", { name: "Continue" }).click();
  await expect(page.getByRole("heading", { name: "Welcome" })).toBeVisible();
}

// --- Admin (API session with the authenticator code) ---------------------------------------

function base32(s: string): Buffer {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const c of s.replace(/=+$/, "")) bits += alphabet.indexOf(c).toString(2).padStart(5, "0");
  const bytes: number[] = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) bytes.push(parseInt(bits.slice(i, i + 8), 2));
  return Buffer.from(bytes);
}

export function adminCode(now = Date.now()): string {
  const counterBuf = Buffer.alloc(8);
  counterBuf.writeBigUInt64BE(BigInt(Math.floor(now / 30_000)));
  const h = createHmac("sha1", base32(ADMIN_TOTP_SECRET)).update(counterBuf).digest();
  const o = h[h.length - 1] & 0xf;
  const n = ((h[o] & 0x7f) << 24) | (h[o + 1] << 16) | (h[o + 2] << 8) | h[o + 3];
  return String(n % 1_000_000).padStart(6, "0");
}

/** Sign in through the log-in form with password and authenticator code. */
export async function adminLoginUi(page: Page): Promise<void> {
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in with a password instead" }).click();
  await page.getByLabel("Email address").fill(ADMIN_EMAIL);
  await page.getByLabel("Password").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await page.locator("input[autocomplete=one-time-code]").fill(adminCode());
  await page.locator("form .btn-primary").click();
  await expect(page.getByRole("heading", { name: "Admin", exact: true })).toBeVisible();
}

export interface AdminApi {
  api: APIRequestContext;
  post: (url: string, data: unknown) => Promise<{ status: number; body: any }>;
  get: (url: string) => Promise<any>;
}

export async function adminApi(): Promise<AdminApi> {
  const api = await request.newContext({ baseURL: BASE_URL });
  const csrf = async () => ((await (await api.get("/api/auth/csrf")).json()) as { csrf_token: string }).csrf_token;
  const login = await api.post("/api/auth/login", {
    data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD },
    headers: { "X-CSRF-Token": await csrf() },
  });
  expect(login.ok()).toBeTruthy();
  const verify = await api.post("/api/auth/totp/verify", {
    data: { code: adminCode() },
    headers: { "X-CSRF-Token": await csrf() },
  });
  expect(verify.ok()).toBeTruthy();
  return {
    api,
    get: async (url) => (await api.get(url)).json(),
    post: async (url, data) => {
      const r = await api.post(url, { data, headers: { "X-CSRF-Token": await csrf() } });
      return { status: r.status(), body: await r.json().catch(() => null) };
    },
  };
}

export async function learnerId(admin: AdminApi, email: string): Promise<string> {
  const rows = (await admin.get(`/api/admin/learners?q=${encodeURIComponent(email)}`)) as { id: string; email: string }[];
  const row = rows.find((r) => r.email === email);
  expect(row, `learner ${email} in the admin list`).toBeTruthy();
  return row!.id;
}

// --- Stripe webhook ------------------------------------------------------------------------

/** Post a signed event the way Stripe does: t=<time>,v1=HMAC-SHA256(secret, "<t>.<payload>"). */
export async function postStripeEvent(event: object): Promise<number> {
  const payload = JSON.stringify(event);
  const t = Math.floor(Date.now() / 1000);
  const v1 = createHmac("sha256", WEBHOOK_SECRET).update(`${t}.${payload}`).digest("hex");
  const api = await request.newContext({ baseURL: BASE_URL });
  const r = await api.post("/api/billing/webhook", {
    data: payload,
    headers: { "content-type": "application/json", "stripe-signature": `t=${t},v1=${v1}` },
  });
  const status = r.status();
  await api.dispose();
  return status;
}
