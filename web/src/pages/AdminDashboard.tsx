import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes, useNavigate } from "react-router-dom";
import { get, patch, post } from "../api";
import { homeFor, useAuth } from "../auth";
import ErrorText from "../components/ErrorText";
import { formatDate } from "../i18n";
import { AiUsage, SafetyFlags } from "./AdminTutor";

/** Staging and development only: open the app as another user. The server refuses it in production. */
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
        <NavLink to="/admin/families">{t("admin.families")}</NavLink>
        <NavLink to="/admin/staff">{t("admin.staff")}</NavLink>
        <NavLink to="/admin/plans">{t("admin.plans")}</NavLink>
        <NavLink to="/admin/safety">{t("admin.safety")}</NavLink>
        <NavLink to="/admin/usage">{t("admin.usage")}</NavLink>
      </nav>
      <Routes>
        <Route index element={<Overview />} />
        <Route path="families" element={<Families />} />
        <Route path="staff" element={<Staff />} />
        <Route path="plans" element={<Plans />} />
        <Route path="safety" element={<SafetyFlags />} />
        <Route path="usage" element={<AiUsage />} />
      </Routes>
    </>
  );
}

interface OverviewOut {
  families: number;
  users_by_role: Record<string, number>;
  subscriptions_by_status: Record<string, number>;
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
          <b>{data.families}</b>
          {t("admin.families")}
        </div>
        {["parent", "student", "adult", "tutor", "admin"].map((r) => (
          <div className="kpi" key={r}>
            <b>{data.users_by_role[r] ?? 0}</b>
            {t(`roles.${r}`)}
          </div>
        ))}
        {Object.entries(data.subscriptions_by_status).map(([s, n]) => (
          <div className="kpi" key={s}>
            <b>{n}</b>
            {t(`subStatus.${s}`, { defaultValue: s })}
          </div>
        ))}
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
                  <td className="small" data-label={t("parent.status")}>
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

interface FamilyRow {
  id: string;
  created_at: string;
  payer_email: string | null;
  payer_verified: boolean;
  plan_key: string | null;
  subscription_status: string | null;
  quantity: number;
  access: string;
  student_count: number;
  free_access_until: string | null;
  payment_warning: boolean;
}

interface FamilyDetail extends FamilyRow {
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
  free_access_reason: string | null;
  tutor_credits: number;
  users: { id: string; role: string; email: string | null; username: string | null; first_name: string; totp_enabled: boolean; is_active: boolean }[];
  payments: { id: string; amount_cents: number; currency: string; paid_at: string }[];
}

function Families() {
  const { t } = useTranslation();
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<FamilyRow[]>([]);
  const [detail, setDetail] = useState<FamilyDetail | null>(null);
  const [until, setUntil] = useState("");
  const [reason, setReason] = useState("SST lesson family");
  const [error, setError] = useState<unknown>(null);
  const { enabled: viewAsEnabled, viewAs } = useViewAs(setError);

  const load = useCallback(async () => {
    setRows(await get<FamilyRow[]>(`/api/admin/families?q=${encodeURIComponent(q)}`));
  }, [q]);

  useEffect(() => {
    load().catch(setError);
  }, [load]);

  async function open(id: string) {
    setDetail(await get<FamilyDetail>(`/api/admin/families/${id}`));
  }

  async function grant(e: FormEvent) {
    e.preventDefault();
    if (!detail) return;
    try {
      await post(`/api/admin/families/${detail.id}/free-access`, {
        until: until ? new Date(until).toISOString() : null,
        reason,
      });
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
              <th>{t("parent.plan")}</th>
              <th>{t("parent.status")}</th>
              <th>{t("admin.access")}</th>
              <th>{t("parent.students")}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td data-label={t("fields.email")}>
                  {r.payer_email} {!r.payer_verified && <span className="hint">({t("admin.unverified")})</span>}
                </td>
                <td data-label={t("parent.plan")}>{r.plan_key ? t(`plans.${r.plan_key}.name`) : "–"}</td>
                <td data-label={t("parent.status")}>{t(`subStatus.${r.subscription_status ?? "none"}`)}</td>
                <td data-label={t("admin.access")}>
                  <span className={`status status-${r.access}`}>{t(`access.${r.access}`)}</span>
                </td>
                <td data-label={t("parent.students")}>{r.student_count}</td>
                <td className="table-actions">
                  <button className="btn btn-sm btn-secondary" onClick={() => void open(r.id)}>
                    {t("common.open")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {detail && (
        <section className="card">
          <h2>{detail.payer_email}</h2>
          <ul className="small">
            <li>Stripe customer: {detail.stripe_customer_id ?? "–"}</li>
            <li>Stripe subscription: {detail.stripe_subscription_id ?? "–"}</li>
            <li>
              {t("parent.tutorCredits", { count: detail.tutor_credits })}
            </li>
            <li>
              {t("admin.freeAccessUntil")}: {formatDate(detail.free_access_until)} {detail.free_access_reason && `(${detail.free_access_reason})`}
            </li>
          </ul>
          <h3>{t("admin.members")}</h3>
          <ul className="small">
            {detail.users.map((u) => (
              <li key={u.id} style={{ marginBottom: 6 }}>
                {t(`roles.${u.role}`)}: {u.first_name || u.email || u.username} {u.email && `· ${u.email}`} {u.username && `· ${u.username}`}
                {!u.is_active && ` · ${t("admin.inactive")}`}{" "}
                {viewAsEnabled && u.is_active && (
                  <button className="btn btn-sm btn-secondary" onClick={() => void viewAs(u.id)}>
                    {t("admin.viewAs")}
                  </button>
                )}
              </li>
            ))}
          </ul>
          <h3>{t("admin.grantFreeAccess")}</h3>
          <form className="form" onSubmit={(e) => void grant(e)} style={{ maxWidth: 420 }}>
            <label className="field">
              <span>{t("admin.until")}</span>
              <input type="date" value={until} onChange={(e) => setUntil(e.target.value)} />
              <span className="hint">{t("admin.untilHint")}</span>
            </label>
            <label className="field">
              <span>{t("admin.reason")}</span>
              <input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={200} />
            </label>
            <div className="actions">
              <button className="btn btn-primary">{t("common.save")}</button>
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
  email: string;
  first_name: string;
  locale: string;
  is_active: boolean;
  totp_enabled: boolean;
  invite_pending: boolean;
  tagged_courses: string[];
  last_login_at: string | null;
}

function Staff() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<StaffRow[]>([]);
  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [role, setRole] = useState<"tutor" | "admin">("tutor");
  const [locale, setLocale] = useState<"en" | "de" | "fr">("en");
  const [courses, setCourses] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [ok, setOk] = useState("");
  const { enabled: viewAsEnabled, viewAs } = useViewAs(setError);

  const load = useCallback(async () => setRows(await get<StaffRow[]>("/api/admin/users")), []);
  useEffect(() => {
    load().catch(setError);
  }, [load]);

  async function create(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setOk("");
    try {
      await post("/api/admin/users", {
        email,
        first_name: firstName,
        role,
        locale,
        tagged_courses: courses
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      });
      setOk(t("admin.invited", { email }));
      setEmail("");
      setFirstName("");
      setCourses("");
      await load();
    } catch (err) {
      setError(err);
    }
  }

  async function action(id: string, what: "reset-2fa" | "resend-invite" | "deactivate" | "activate") {
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
      {ok && <div className="alert alert-ok">{ok}</div>}
      <div className="table-wrap card">
        <table className="table table-stack">
          <thead>
            <tr>
              <th>{t("fields.firstName")}</th>
              <th>{t("fields.email")}</th>
              <th>{t("admin.role")}</th>
              <th>2FA</th>
              <th>{t("tutor.courses")}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((u) => (
              <tr key={u.id} style={{ opacity: u.is_active ? 1 : 0.5 }}>
                <td data-label={t("fields.firstName")}>{u.first_name}</td>
                <td data-label={t("fields.email")}>{u.email}</td>
                <td data-label={t("admin.role")}>{t(`roles.${u.role}`)}</td>
                <td data-label="2FA">
                  {u.invite_pending ? t("admin.invitePending") : u.totp_enabled ? t("common.yes") : t("common.no")}
                </td>
                <td className="small" data-label={t("tutor.courses")}>
                  {u.tagged_courses.join(", ")}
                </td>
                <td className="table-actions">
                  <div className="actions">
                    {viewAsEnabled && u.is_active && u.role === "tutor" && (
                      <button className="btn btn-sm btn-secondary" onClick={() => void viewAs(u.id)}>
                        {t("admin.viewAs")}
                      </button>
                    )}
                    {u.invite_pending && (
                      <button className="btn btn-sm btn-secondary" onClick={() => void action(u.id, "resend-invite")}>
                        {t("admin.resendInvite")}
                      </button>
                    )}
                    {u.totp_enabled && (
                      <button className="btn btn-sm btn-secondary" onClick={() => void action(u.id, "reset-2fa")}>
                        {t("admin.reset2fa")}
                      </button>
                    )}
                    <button
                      className="btn btn-sm btn-danger"
                      onClick={() => void action(u.id, u.is_active ? "deactivate" : "activate")}
                    >
                      {u.is_active ? t("admin.deactivate") : t("admin.activate")}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <section className="card">
        <h2>{t("admin.inviteStaff")}</h2>
        <form className="form" onSubmit={(e) => void create(e)} style={{ maxWidth: 480 }}>
          <label className="field">
            <span>{t("fields.firstName")}</span>
            <input required value={firstName} onChange={(e) => setFirstName(e.target.value)} />
          </label>
          <label className="field">
            <span>{t("fields.email")}</span>
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label className="field">
            <span>{t("admin.role")}</span>
            <select value={role} onChange={(e) => setRole(e.target.value as "tutor" | "admin")}>
              <option value="tutor">{t("roles.tutor")}</option>
              <option value="admin">{t("roles.admin")}</option>
            </select>
          </label>
          <label className="field">
            <span>{t("nav.language")}</span>
            <select value={locale} onChange={(e) => setLocale(e.target.value as "en" | "de" | "fr")}>
              <option value="en">English</option>
              <option value="de">Deutsch</option>
              <option value="fr">Français</option>
            </select>
          </label>
          <label className="field">
            <span>{t("admin.taggedCourses")}</span>
            <input value={courses} onChange={(e) => setCourses(e.target.value)} placeholder="ib_maths_aa_hl, ib_physics_sl" />
          </label>
          <button className="btn btn-primary">{t("admin.sendInvite")}</button>
        </form>
      </section>
    </>
  );
}

interface PlanRow {
  key: string;
  kind: string;
  monthly_message_limit: number | null;
  daily_message_limit: number | null;
  is_active: boolean;
}

function Plans() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<PlanRow[]>([]);
  const [error, setError] = useState<unknown>(null);
  const load = useCallback(async () => setRows(await get<PlanRow[]>("/api/admin/plans")), []);
  useEffect(() => {
    load().catch(setError);
  }, [load]);

  async function save(p: PlanRow) {
    try {
      await patch(`/api/admin/plans/${p.key}`, {
        monthly_message_limit: p.monthly_message_limit,
        daily_message_limit: p.daily_message_limit,
        is_active: p.is_active,
      });
      await load();
    } catch (err) {
      setError(err);
    }
  }

  function update(key: string, field: keyof PlanRow, value: number | boolean | null) {
    setRows((rs) => rs.map((r) => (r.key === key ? { ...r, [field]: value } : r)));
  }

  return (
    <div className="card">
      <ErrorText error={error} />
      <p className="small">{t("admin.plansIntro")}</p>
      <div className="table-wrap">
        <table className="table table-stack">
          <thead>
            <tr>
              <th>{t("parent.plan")}</th>
              <th>{t("admin.monthlyLimit")}</th>
              <th>{t("admin.dailyLimit")}</th>
              <th>{t("admin.active")}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.key}>
                <td data-label={t("parent.plan")}>
                  {t(`plans.${p.key}.name`)} <span className="hint">({p.key})</span>
                </td>
                <td data-label={t("admin.monthlyLimit")}>
                  {p.kind === "subscription" ? (
                    <input
                      type="number"
                      min={0}
                      value={p.monthly_message_limit ?? 0}
                      onChange={(e) => update(p.key, "monthly_message_limit", Number(e.target.value))}
                    />
                  ) : (
                    "–"
                  )}
                </td>
                <td data-label={t("admin.dailyLimit")}>
                  {p.kind === "subscription" ? (
                    <input
                      type="number"
                      min={0}
                      value={p.daily_message_limit ?? 0}
                      onChange={(e) => update(p.key, "daily_message_limit", Number(e.target.value))}
                    />
                  ) : (
                    "–"
                  )}
                </td>
                <td data-label={t("admin.active")}>
                  <label className="check">
                    <input
                      type="checkbox"
                      checked={p.is_active}
                      onChange={(e) => update(p.key, "is_active", e.target.checked)}
                    />
                    <span className="visually-hidden">{t("admin.active")}</span>
                  </label>
                </td>
                <td className="table-actions">
                  <button className="btn btn-sm btn-secondary" onClick={() => void save(p)}>
                    {t("common.save")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
