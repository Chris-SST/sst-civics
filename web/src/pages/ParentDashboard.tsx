import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { del, get, patch, post, type PlanOut, type StudentOut } from "../api";
import { useAuth } from "../auth";
import ErrorText from "../components/ErrorText";
import { formatChf, formatDate, shortLocale } from "../i18n";

interface Options {
  curricula: string[];
  courses: string[];
}

export default function ParentDashboard() {
  const { t, i18n } = useTranslation();
  const { me, config, refresh } = useAuth();
  const [students, setStudents] = useState<StudentOut[]>([]);
  const [plans, setPlans] = useState<PlanOut[]>([]);
  const [options, setOptions] = useState<Options>({ curricula: [], courses: [] });
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [showAdd, setShowAdd] = useState(false);

  const isParent = me?.user.role === "parent";
  const family = me?.family;

  const load = useCallback(async () => {
    const [s, p, o] = await Promise.all([
      get<StudentOut[]>("/api/family/students"),
      get<PlanOut[]>("/api/billing/plans"),
      get<Options>("/api/family/options"),
    ]);
    setStudents(s);
    setPlans(p);
    setOptions(o);
  }, []);

  useEffect(() => {
    load().catch(setError);
  }, [load]);

  async function checkout(planKey: string, quantity = 1) {
    setError(null);
    setBusy(true);
    try {
      const out = await post<{ url: string }>("/api/billing/checkout", { plan_key: planKey, quantity });
      window.location.assign(out.url);
    } catch (e) {
      setError(e);
      setBusy(false);
    }
  }

  async function portal() {
    setError(null);
    setBusy(true);
    try {
      const out = await post<{ url: string }>("/api/billing/portal");
      window.location.assign(out.url);
    } catch (e) {
      setError(e);
      setBusy(false);
    }
  }

  async function removeStudent(s: StudentOut) {
    if (!window.confirm(t("parent.confirmRemove", { name: s.first_name }))) return;
    await del(`/api/family/students/${s.id}`);
    await load();
    await refresh();
  }

  async function resetStudentPassword(s: StudentOut) {
    const pw = window.prompt(t("parent.newStudentPassword", { name: s.first_name }));
    if (!pw) return;
    try {
      await patch(`/api/family/students/${s.id}`, { password: pw });
      window.alert(t("parent.passwordChanged"));
    } catch (e) {
      setError(e);
    }
  }

  async function changeLanguage(lng: string) {
    await i18n.changeLanguage(lng);
    try {
      await patch("/api/family/settings", { locale: shortLocale(lng) });
    } catch {
      /* non-critical */
    }
  }

  if (!me || !family) return <p className="muted">…</p>;

  const subscribed = ["trialing", "active", "past_due"].includes(family.subscription_status ?? "");
  const subscriptionPlans = plans.filter((p) => p.kind === "subscription");
  const addons = plans.filter((p) => p.kind === "addon");

  return (
    <>
      <h1>{t("parent.title")}</h1>
      {config && !config.billing_enabled && <div className="alert alert-warn">{t("parent.billingDisabled")}</div>}
      {family.payment_warning && (
        <div className="alert alert-warn">
          {t("parent.paymentWarning")}{" "}
          <button className="btn btn-sm btn-secondary" onClick={() => void portal()} disabled={busy}>
            {t("parent.updatePayment")}
          </button>
        </div>
      )}
      <ErrorText error={error} />

      <div className="grid-2">
        <section className="card">
          <h2>{t("parent.subscription")}</h2>
          <p>
            <span className={`status status-${family.access}`}>{t(`access.${family.access}`)}</span>
          </p>
          {family.free_access_until && new Date(family.free_access_until) > new Date() && (
            <p className="small">{t("parent.freeAccess", { date: formatDate(family.free_access_until) })}</p>
          )}
          {family.plan_key && (
            <ul className="small">
              <li>
                {t("parent.plan")}: <b>{t(`plans.${family.plan_key}.name`)}</b>
              </li>
              <li>
                {t("parent.status")}: {t(`subStatus.${family.subscription_status ?? "none"}`)}
              </li>
              <li>
                {t("parent.students")}: {family.quantity}
              </li>
              {family.trial_end && family.subscription_status === "trialing" && (
                <li>{t("parent.trialEnds", { date: formatDate(family.trial_end) })}</li>
              )}
              {family.current_period_end && (
                <li>
                  {family.cancel_at_period_end
                    ? t("parent.endsOn", { date: formatDate(family.current_period_end) })
                    : t("parent.renewsOn", { date: formatDate(family.current_period_end) })}
                </li>
              )}
            </ul>
          )}
          <p className="small">{t("parent.tutorCredits", { count: family.tutor_credits })}</p>
          <div className="actions">
            {family.has_stripe_customer && (
              <button className="btn btn-secondary" onClick={() => void portal()} disabled={busy}>
                {t("parent.manageBilling")}
              </button>
            )}
            {!isParent && (
              <Link className="btn btn-primary" to="/student">
                {t("parent.goToTutor")}
              </Link>
            )}
          </div>
        </section>

        {isParent ? (
          <section className="card">
            <h2>{t("parent.students")}</h2>
            {students.length === 0 && <p className="muted">{t("parent.noStudents")}</p>}
            {students.map((s) => (
              <div key={s.id} style={{ borderTop: "1px solid var(--line)", padding: "10px 0" }}>
                <b style={{ color: "var(--ink)" }}>{s.first_name}</b>{" "}
                <span className="small muted">
                  {s.year_of_birth} · {s.curriculum ? t(`curricula.${s.curriculum}`) : ""}
                </span>
                <div className="small">
                  {s.courses.map((c) => t(`courses.${c}`, { defaultValue: c })).join(", ") || t("student.noCourses")}
                </div>
                <div className="small">
                  {s.username
                    ? t("parent.loginUsername", { username: s.username })
                    : s.invite_pending
                      ? t("parent.invitePending", { email: s.email })
                      : t("parent.loginEmail", { email: s.email })}
                </div>
                <div className="actions" style={{ marginTop: 6 }}>
                  {s.username && (
                    <button className="btn btn-sm btn-secondary" onClick={() => void resetStudentPassword(s)}>
                      {t("parent.resetPassword")}
                    </button>
                  )}
                  <button className="btn btn-sm btn-danger" onClick={() => void removeStudent(s)}>
                    {t("parent.remove")}
                  </button>
                </div>
              </div>
            ))}
            {showAdd ? (
              <AddStudentForm
                options={options}
                onDone={async () => {
                  setShowAdd(false);
                  await load();
                  await refresh();
                }}
                onCancel={() => setShowAdd(false)}
              />
            ) : (
              <button className="btn btn-primary" onClick={() => setShowAdd(true)} style={{ marginTop: 10 }}>
                {t("parent.addStudent")}
              </button>
            )}
          </section>
        ) : (
          <section className="card">
            <h2>{t("parent.adultTitle")}</h2>
            <p className="small">{t("parent.adultBody")}</p>
          </section>
        )}
      </div>

      {!subscribed && (
        <section className="card">
          <h2>{t("parent.choosePlan")}</h2>
          <p className="small">{t("landing.trialNote")}</p>
          {isParent && students.length === 0 && <div className="alert alert-info">{t("parent.addStudentFirst")}</div>}
          <div className="plans">
            {subscriptionPlans.map((p) => (
              <div key={p.key} className={`plan ${p.key === "hybrid_monthly" ? "featured" : ""}`}>
                <h3>{t(`plans.${p.key}.name`)}</h3>
                <div className="price">
                  {formatChf(p.amount_cents, p.currency)} <small>{p.interval ? t(`plans.per_${p.interval}`) : ""}</small>
                </div>
                <p className="small">{t(`plans.${p.key}.blurb`)}</p>
                <p className="hint">
                  {t("plans.limits", { monthly: p.monthly_message_limit, daily: p.daily_message_limit })}
                </p>
                <button
                  className="btn btn-primary"
                  disabled={busy || (isParent && students.length === 0) || !config?.billing_enabled}
                  onClick={() => void checkout(p.key)}
                >
                  {t("parent.startTrial")}
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="card">
        <h2>{t("parent.addons")}</h2>
        <div className="plans">
          {addons.map((p) => (
            <div key={p.key} className="plan">
              <h3>{t(`plans.${p.key}.name`)}</h3>
              <div className="price">{formatChf(p.amount_cents, p.currency)}</div>
              <p className="small">{t(`plans.${p.key}.blurb`)}</p>
              <button
                className="btn btn-secondary"
                disabled={busy || !config?.billing_enabled}
                onClick={() => void checkout(p.key, 1)}
              >
                {t("parent.buy")}
              </button>
            </div>
          ))}
        </div>
      </section>

      <section className="card">
        <h2>{t("parent.settings")}</h2>
        <div className="grid-2">
          <label className="field">
            <span>{t("nav.language")}</span>
            <select value={i18n.language} onChange={(e) => void changeLanguage(e.target.value)}>
              <option value="en-GB">English</option>
              <option value="de-CH">Deutsch</option>
              <option value="fr-CH">Français</option>
            </select>
          </label>
          <div className="field">
            <span>{t("parent.security")}</span>
            {me.user.totp_enabled ? (
              <p className="small">{t("parent.twofaOn")}</p>
            ) : (
              <Link className="btn btn-secondary" to="/2fa/setup">
                {t("parent.enable2fa")}
              </Link>
            )}
          </div>
        </div>
        <p className="hint">{t("parent.dataRights")}</p>
      </section>
    </>
  );
}

function AddStudentForm({
  options,
  onDone,
  onCancel,
}: {
  options: Options;
  onDone: () => Promise<void>;
  onCancel: () => void;
}) {
  const { t, i18n } = useTranslation();
  const thisYear = new Date().getFullYear();
  const [firstName, setFirstName] = useState("");
  const [year, setYear] = useState(thisYear - 15);
  const [curriculum, setCurriculum] = useState("ib_dp");
  const [courses, setCourses] = useState<string[]>([]);
  const [method, setMethod] = useState<"username" | "invite">("username");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  function toggleCourse(c: string) {
    setCourses((cs) => (cs.includes(c) ? cs.filter((x) => x !== c) : [...cs, c]));
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await post("/api/family/students", {
        first_name: firstName,
        year_of_birth: year,
        curriculum,
        courses,
        locale: shortLocale(i18n.language),
        ...(method === "username" ? { username, password } : { invite_email: inviteEmail }),
      });
      await onDone();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const years = Array.from({ length: 16 }, (_, i) => thisYear - 5 - i);
  const visibleCourses = options.courses.filter((c) => c.startsWith(curriculum.split("_")[0]) || c === "other");

  return (
    <form className="form" onSubmit={(e) => void submit(e)} style={{ marginTop: 12 }}>
      <h3>{t("parent.addStudent")}</h3>
      <label className="field">
        <span>{t("fields.firstName")}</span>
        <input required maxLength={80} value={firstName} onChange={(e) => setFirstName(e.target.value)} />
        <span className="hint">{t("parent.firstNameHint")}</span>
      </label>
      <label className="field">
        <span>{t("fields.yearOfBirth")}</span>
        <select value={year} onChange={(e) => setYear(Number(e.target.value))}>
          {years.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>{t("fields.curriculum")}</span>
        <select value={curriculum} onChange={(e) => setCurriculum(e.target.value)}>
          {options.curricula.map((c) => (
            <option key={c} value={c}>
              {t(`curricula.${c}`)}
            </option>
          ))}
        </select>
      </label>
      <div className="field">
        <span>{t("fields.courses")}</span>
        <div style={{ display: "grid", gap: 4 }}>
          {visibleCourses.map((c) => (
            <label key={c} className="check small">
              <input type="checkbox" checked={courses.includes(c)} onChange={() => toggleCourse(c)} />
              <span>{t(`courses.${c}`, { defaultValue: c })}</span>
            </label>
          ))}
        </div>
      </div>
      <label className="field">
        <span>{t("parent.loginMethod")}</span>
        <select value={method} onChange={(e) => setMethod(e.target.value as "username" | "invite")}>
          <option value="username">{t("parent.methodUsername")}</option>
          <option value="invite">{t("parent.methodInvite")}</option>
        </select>
      </label>
      {method === "username" ? (
        <>
          <label className="field">
            <span>{t("fields.username")}</span>
            <input
              required
              minLength={3}
              maxLength={40}
              pattern="[A-Za-z0-9][A-Za-z0-9._-]*"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
            <span className="hint">{t("fields.usernameHint")}</span>
          </label>
          <label className="field">
            <span>{t("fields.password")}</span>
            <input
              type="text"
              required
              minLength={10}
              autoComplete="off"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <span className="hint">{t("fields.passwordHint")}</span>
          </label>
        </>
      ) : (
        <label className="field">
          <span>{t("fields.studentEmail")}</span>
          <input type="email" required value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} />
        </label>
      )}
      <ErrorText error={error} />
      <div className="actions">
        <button className="btn btn-primary" disabled={busy}>
          {t("common.save")}
        </button>
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          {t("common.cancel")}
        </button>
      </div>
    </form>
  );
}
