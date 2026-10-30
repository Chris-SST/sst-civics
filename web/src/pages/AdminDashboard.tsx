import { useCallback, useEffect, useState, type FormEvent } from "react";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes, useNavigate } from "react-router-dom";
import { CANTONS, get, patch, post, type EntitlementOut, type RefundEligibility } from "../api";
import { homeFor, useAuth } from "../auth";
import ErrorText from "../components/ErrorText";
import { formatChf, formatDate } from "../i18n";
import { AiUsage } from "./AdminTutor";
import AdminQuestions from "./AdminQuestions";

/** Staging and development only: open the app as a learner. The server refuses it in production. */
function useViewAs(setError: (e: unknown) => void) {
  const { refresh, config } = useAuth();
  const navigate = useNavigate();
  const enabled = !!config && config.env !== "production";
  async function viewAs(userId: string) {
    try {
      const out = await post<{ role: string }>(`/api/admin/impersonate/${userId}`);
      await refresh();
      navigate(homeFor(out.role));
    } catch (e) {
      setError(e);
    }
  }
  return { enabled, viewAs };
}

export default function AdminDashboard() {
  const { t } = useTranslation();
  return (
    <>
      <h1>{t("admin.title")}</h1>
      <nav className="tabs">
        <NavLink to="/admin" end>
          {t("admin.overview")}
        </NavLink>
        <NavLink to="/admin/learners">{t("admin.learners")}</NavLink>
        <NavLink to="/admin/staff">{t("admin.staff")}</NavLink>
        <NavLink to="/admin/usage">{t("admin.usage")}</NavLink>
        <NavLink to="/admin/questions">{t("qbank.tab")}</NavLink>
      </nav>
      <Routes>
        <Route index element={<Overview />} />
        <Route path="learners" element={<Learners />} />
        <Route path="staff" element={<Staff />} />
        <Route path="usage" element={<AiUsage />} />
        <Route path="questions/*" element={<AdminQuestions />} />
      </Routes>
    </>
  );
}

interface OverviewOut {
  learners: number;
  users_by_role: Record<string, number>;
  active_entitlements: number;
  recent_stripe_events: {
    id: string;
    type: string;
    received_at: string;
    processed_at: string | null;
    error: string | null;
  }[];
}

function Overview() {
  const { t } = useTranslation();
  const [data, setData] = useState<OverviewOut | null>(null);
  useEffect(() => {
    get<OverviewOut>("/api/admin/overview").then(setData).catch(() => setData(null));
  }, []);
  if (!data) return <p className="muted">…</p>;
  return (
    <>
      <div className="kpis">
        <div className="kpi">
          <b>{data.learners}</b>
          {t("admin.learners")}
        </div>
        <div className="kpi">
          <b>{data.active_entitlements}</b>
          {t("admin.activeEntitlements")}
        </div>
        <div className="kpi">
          <b>{data.users_by_role.admin ?? 0}</b>
          {t("roles.admin")}
        </div>
      </div>
      <section className="card" style={{ marginTop: 18 }}>
        <h2>{t("admin.stripeEvents")}</h2>
        {data.recent_stripe_events.length === 0 && <p className="muted">{t("admin.noEvents")}</p>}
        <div className="table-wrap">
          <table className="table table-stack">
            <tbody>
              {data.recent_stripe_events.map((e) => (
                <tr key={e.id}>
                  <td data-label={t("admin.eventType")}>{e.type}</td>
                  <td className="small" data-label={t("admin.received")}>
                    {formatDate(e.received_at)}
                  </td>
                  <td className="small" data-label={t("admin.status")}>
                    {e.processed_at ? t("admin.processed") : t("admin.pending")}
                  </td>
                  {e.error && (
                    <td className="small" data-label={t("admin.error")} style={{ color: "var(--red)" }}>
                      {e.error}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

interface LearnerRow {
  id: string;
  email: string | null;
  email_verified: boolean;
  is_active: boolean;
  locale: string;
  study_language: string;
  canton: string;
  created_at: string;
  last_login_at: string | null;
  access: "full" | "none";
  entitlements: EntitlementOut[];
}

interface LearnerDetail extends LearnerRow {
  age_confirmed_at: string | null;
  terms_version: string | null;
  terms_accepted_at: string | null;
  has_stripe_customer: boolean;
  payments: AdminPayment[];
}

interface AdminPayment {
  id: string;
  product: string;
  canton: string;
  amount_cents: number;
  currency: string;
  paid_at: string;
  refunded_at: string | null;
  refund: RefundEligibility;
}

/** Default expiry for a manual grant: six months from today, as yyyy-mm-dd. */
function defaultExpiry(): string {
  const d = new Date();
  d.setMonth(d.getMonth() + 6);
  return d.toISOString().slice(0, 10);
}

function cantonName(t: TFunction, code: string): string {
  return t(`cantons.${code}`, { defaultValue: code.toUpperCase() });
}

function Learners() {
  const { t } = useTranslation();
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<LearnerRow[]>([]);
  const [detail, setDetail] = useState<LearnerDetail | null>(null);
  const [canton, setCanton] = useState<string>(CANTONS[0]);
  const [expires, setExpires] = useState(defaultExpiry());
  const [source, setSource] = useState<"admin" | "trial">("admin");
  const [ok, setOk] = useState("");
  const [error, setError] = useState<unknown>(null);
  const { enabled: viewAsEnabled, viewAs } = useViewAs(setError);

  const load = useCallback(async () => {
    setRows(await get<LearnerRow[]>(`/api/admin/learners?q=${encodeURIComponent(q)}`));
  }, [q]);

  useEffect(() => {
    load().catch(setError);
  }, [load]);

  async function open(id: string) {
    setOk("");
    try {
      const d = await get<LearnerDetail>(`/api/admin/learners/${id}`);
      setDetail(d);
      setCanton(d.canton || CANTONS[0]);
    } catch (err) {
      setError(err);
    }
  }

  async function refund(p: AdminPayment) {
    if (!detail) return;
    const question = p.refund.eligible ? t("admin.refundConfirm") : t("admin.refundOverrideConfirm");
    if (!window.confirm(question)) return;
    setError(null);
    setOk("");
    try {
      await post(`/api/admin/payments/${p.id}/refund`, { override: !p.refund.eligible });
      await open(detail.id);
      setOk(t("admin.refundRequested"));
    } catch (err) {
      setError(err);
    }
  }

  async function grant(e: FormEvent) {
    e.preventDefault();
    if (!detail || !expires) return;
    setError(null);
    setOk("");
    try {
      const until = new Date(`${expires}T23:59:59`).toISOString();
      await post<EntitlementOut>(`/api/admin/users/${detail.id}/entitlements`, {
        canton,
        expires_at: until,
        source,
      });
      setOk(t("admin.granted", { canton: cantonName(t, canton), date: formatDate(until) }));
      await open(detail.id);
      await load();
    } catch (err) {
      setError(err);
    }
  }

  return (
    <>
      <ErrorText error={error} />
      <div className="field" style={{ maxWidth: 360, marginBottom: 12 }}>
        <input placeholder={t("admin.searchEmail")} value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <div className="table-wrap card">
        <table className="table table-stack">
          <thead>
            <tr>
              <th>{t("fields.email")}</th>
              <th>{t("fields.canton")}</th>
              <th>{t("admin.access")}</th>
              <th>{t("admin.lastLogin")}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} style={{ opacity: r.is_active ? 1 : 0.5 }}>
                <td data-label={t("fields.email")}>
                  {r.email} {!r.email_verified && <span className="hint">({t("admin.unverified")})</span>}
                </td>
                <td data-label={t("fields.canton")}>{cantonName(t, r.canton)}</td>
                <td data-label={t("admin.access")}>
                  <span className={`status status-${r.access}`}>{t(`access.${r.access}`)}</span>
                </td>
                <td className="small" data-label={t("admin.lastLogin")}>
                  {formatDate(r.last_login_at)}
                </td>
                <td className="table-actions">
                  <button className="btn btn-sm btn-secondary" onClick={() => void open(r.id)}>
                    {t("common.open")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <p className="muted">{t("admin.noLearners")}</p>}
      </div>
      {detail && (
        <section className="card">
          <h2>{detail.email}</h2>
          <ul className="small">
            <li>
              {t("fields.canton")}: {cantonName(t, detail.canton)}
            </li>
            <li>
              {t("fields.studyLanguage")}: {t(`languages.${detail.study_language}`, { defaultValue: detail.study_language })}
            </li>
            <li>
              {t("admin.ageConfirmed")}: {formatDate(detail.age_confirmed_at)}
            </li>
            <li>
              {t("admin.termsAccepted")}: {formatDate(detail.terms_accepted_at)}{" "}
              {detail.terms_version && `(${detail.terms_version})`}
            </li>
            <li>
              {t("admin.stripeCustomer")}: {detail.has_stripe_customer ? t("common.yes") : t("common.no")}
            </li>
          </ul>
          {viewAsEnabled && detail.is_active && (
            <div className="actions">
              <button className="btn btn-sm btn-secondary" onClick={() => void viewAs(detail.id)}>
                {t("admin.viewAs")}
              </button>
            </div>
          )}

          <h3>{t("admin.entitlements")}</h3>
          {detail.entitlements.length === 0 ? (
            <p className="muted small">{t("admin.noEntitlements")}</p>
          ) : (
            <ul className="small">
              {detail.entitlements.map((en) => (
                <li key={en.id}>
                  {cantonName(t, en.canton)}: {formatDate(en.starts_at)} – {formatDate(en.expires_at)} ·{" "}
                  {t(`admin.source.${en.source}`)}{" "}
                  <span className={`status status-${en.active ? "full" : "none"}`}>
                    {en.active ? t("access.full") : t("admin.expired")}
                  </span>
                </li>
              ))}
            </ul>
          )}

          <h3>{t("admin.payments")}</h3>
          {detail.payments.length === 0 ? (
            <p className="muted small">{t("admin.noPayments")}</p>
          ) : (
            <ul className="small">
              {detail.payments.map((p) => (
                <li key={p.id}>
                  {formatDate(p.paid_at)} · {formatChf(p.amount_cents, p.currency.toUpperCase())} ·{" "}
                  {t(`admin.product.${p.product}`, { defaultValue: p.product })} ({cantonName(t, p.canton)})
                  {p.refunded_at ? (
                    <> · <span className="status status-none">{t("admin.refundedOn", { date: formatDate(p.refunded_at) })}</span></>
                  ) : (
                    <>
                      {" "}
                      <button type="button" className="btn btn-sm btn-secondary" onClick={() => void refund(p)}>
                        {p.refund.eligible ? t("admin.refund") : t("admin.refundAnyway")}
                      </button>
                      {!p.refund.eligible && (
                        <span className="hint"> {t(`admin.refundRule.${p.refund.reason}`, { count: p.refund.questions_studied })}</span>
                      )}
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}

          <h3>{t("admin.grantAccess")}</h3>
          {ok && <div className="alert alert-ok">{ok}</div>}
          <form className="form" onSubmit={(e) => void grant(e)} style={{ maxWidth: 420 }}>
            <label className="field">
              <span>{t("fields.canton")}</span>
              <select value={canton} onChange={(e) => setCanton(e.target.value)}>
                {CANTONS.map((c) => (
                  <option key={c} value={c}>
                    {cantonName(t, c)}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>{t("admin.until")}</span>
              <input type="date" required value={expires} onChange={(e) => setExpires(e.target.value)} />
            </label>
            <label className="field">
              <span>{t("admin.sourceLabel")}</span>
              <select value={source} onChange={(e) => setSource(e.target.value as "admin" | "trial")}>
                <option value="admin">{t("admin.source.admin")}</option>
                <option value="trial">{t("admin.source.trial")}</option>
              </select>
            </label>
            <div className="actions">
              <button className="btn btn-primary">{t("admin.grant")}</button>
              <button type="button" className="btn btn-ghost" onClick={() => setDetail(null)}>
                {t("common.close")}
              </button>
            </div>
          </form>
        </section>
      )}
    </>
  );
}

interface StaffRow {
  id: string;
  role: string;
  email: string | null;
  locale: string;
  is_active: boolean;
  totp_enabled: boolean;
  last_login_at: string | null;
}

function Staff() {
  const { t } = useTranslation();
  const { me } = useAuth();
  const [rows, setRows] = useState<StaffRow[]>([]);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => setRows(await get<StaffRow[]>("/api/admin/users")), []);
  useEffect(() => {
    load().catch(setError);
  }, [load]);

  async function action(id: string, what: "reset-2fa" | "deactivate" | "activate") {
    setError(null);
    try {
      if (what === "deactivate" || what === "activate") {
        await patch(`/api/admin/users/${id}`, { is_active: what === "activate" });
      } else {
        await post(`/api/admin/users/${id}/${what}`);
      }
      await load();
    } catch (err) {
      setError(err);
    }
  }

  return (
    <>
      <ErrorText error={error} />
      <p className="small muted">{t("admin.staffIntro")}</p>
      <div className="table-wrap card">
        <table className="table table-stack">
          <thead>
            <tr>
              <th>{t("fields.email")}</th>
              <th>{t("admin.role")}</th>
              <th>2FA</th>
              <th>{t("admin.lastLogin")}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((u) => (
              <tr key={u.id} style={{ opacity: u.is_active ? 1 : 0.5 }}>
                <td data-label={t("fields.email")}>{u.email}</td>
                <td data-label={t("admin.role")}>{t(`roles.${u.role}`)}</td>
                <td data-label="2FA">{u.totp_enabled ? t("common.yes") : t("common.no")}</td>
                <td className="small" data-label={t("admin.lastLogin")}>
                  {formatDate(u.last_login_at)}
                </td>
                <td className="table-actions">
                  <div className="actions">
                    {u.totp_enabled && (
                      <button className="btn btn-sm btn-secondary" onClick={() => void action(u.id, "reset-2fa")}>
                        {t("admin.reset2fa")}
                      </button>
                    )}
                    {u.id !== me?.user.id && (
                      <button
                        className="btn btn-sm btn-danger"
                        onClick={() => void action(u.id, u.is_active ? "deactivate" : "activate")}
                      >
                        {u.is_active ? t("admin.deactivate") : t("admin.activate")}
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
