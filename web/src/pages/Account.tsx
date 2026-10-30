import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import {
  CANTONS,
  LANGUAGE_CODES,
  LANGUAGE_ENDONYMS,
  STUDY_LANGUAGES,
  apiLocale,
  del,
  patch,
  post,
  type Me,
} from "../api";
import { useAuth } from "../auth";
import ErrorText from "../components/ErrorText";
import { switchInterface } from "../language";

/** Account settings: languages and canton, password (optional for learners), deletion. */
export default function Account() {
  const { t } = useTranslation();
  const { me, refresh } = useAuth();
  const navigate = useNavigate();
  if (!me) return null;

  return (
    <div className="narrow" style={{ display: "grid", gap: 16 }}>
      <h1>{t("account.title")}</h1>
      <p className="muted">{me.user.email}</p>
      <ProfileSection me={me} refresh={refresh} />
      <PasswordSection me={me} refresh={refresh} />
      <DeleteSection
        me={me}
        onDeleted={async () => {
          // Leave the guarded page first, then forget the (now deleted) session.
          navigate("/account/deleted", { replace: true });
          await refresh();
        }}
      />
    </div>
  );
}

interface SectionProps {
  me: Me;
  refresh: () => Promise<Me | null>;
}

function ProfileSection({ me, refresh }: SectionProps) {
  const { t, i18n } = useTranslation();
  const [locale, setLocale] = useState(me.user.locale);
  const [studyLanguage, setStudyLanguage] = useState(me.user.study_language);
  const [canton, setCanton] = useState(me.user.canton);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<unknown>(null);
  // Offer the learner's current canton even if it is not on the sign-up list.
  const cantons: string[] = (CANTONS as readonly string[]).includes(me.user.canton)
    ? [...CANTONS]
    : [...CANTONS, me.user.canton];

  async function save(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);
    setBusy(true);
    try {
      await patch("/api/me", { locale, study_language: studyLanguage, canton });
      switchInterface(locale, (lng) => i18n.changeLanguage(lng));
      await refresh();
      setSaved(true);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <h2>{t("account.profileTitle")}</h2>
      <form className="form" onSubmit={(e) => void save(e)}>
        <label className="field">
          <span>{t("fields.interfaceLanguage")}</span>
          <select value={locale} onChange={(e) => setLocale(e.target.value)}>
            {LANGUAGE_CODES.map((l) => (
              <option key={l} value={l}>
                {LANGUAGE_ENDONYMS[l]}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{t("fields.studyLanguage")}</span>
          <select value={studyLanguage} onChange={(e) => setStudyLanguage(e.target.value)}>
            {STUDY_LANGUAGES.map((l) => (
              <option key={l} value={l}>
                {t(`languages.${l}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{t("fields.canton")}</span>
          <select value={canton} onChange={(e) => setCanton(e.target.value)}>
            {cantons.map((c) => (
              <option key={c} value={c}>
                {t(`cantons.${c}`, { defaultValue: c.toUpperCase() })}
              </option>
            ))}
          </select>
          <span className="hint">{t("signup.cantonHint")}</span>
        </label>
        <ErrorText error={error} />
        {saved && <div className="alert alert-ok">{t("account.saved")}</div>}
        <div className="actions">
          <button className="btn btn-primary" disabled={busy}>
            {t("common.save")}
          </button>
        </div>
      </form>
    </section>
  );
}

function PasswordSection({ me, refresh }: SectionProps) {
  const { t } = useTranslation();
  const hasPassword = me.user.has_password;
  const isAdmin = me.user.role === "admin";
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [removeCurrent, setRemoveCurrent] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  async function run(action: () => Promise<unknown>, done: string) {
    setError(null);
    setMessage(null);
    setBusy(true);
    try {
      await action();
      await refresh();
      setCurrent("");
      setPassword("");
      setConfirm("");
      setRemoveCurrent("");
      setMessage(done);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  function setOrChange(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setMessage(null);
      setError({ code: "password_mismatch" });
      return;
    }
    const body = hasPassword
      ? { current_password: current, new_password: password }
      : { new_password: password };
    void run(() => post("/api/me/password", body), t("account.passwordSaved"));
  }

  function remove(e: FormEvent) {
    e.preventDefault();
    void run(
      () => post("/api/me/password/remove", { current_password: removeCurrent }),
      t("account.passwordRemoved"),
    );
  }

  const mismatch = (error as { code?: string } | null)?.code === "password_mismatch";

  return (
    <section className="card">
      <h2>{t("account.passwordTitle")}</h2>
      <p className="small">{hasPassword ? t("account.passwordOn") : t("account.passwordOff")}</p>
      <form className="form" onSubmit={setOrChange}>
        {hasPassword && (
          <label className="field">
            <span>{t("account.currentPassword")}</span>
            <input
              type="password"
              required
              autoComplete="current-password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
            />
          </label>
        )}
        <label className="field">
          <span>{t("fields.newPassword")}</span>
          <input
            type="password"
            required
            minLength={10}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <span className="hint">{t("fields.passwordHint")}</span>
        </label>
        <label className="field">
          <span>{t("fields.confirmPassword")}</span>
          <input
            type="password"
            required
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </label>
        <div className="actions">
          <button className="btn btn-primary" disabled={busy}>
            {hasPassword ? t("account.changePassword") : t("account.setPassword")}
          </button>
        </div>
      </form>
      {hasPassword && !isAdmin && (
        <form className="form" onSubmit={remove} style={{ marginTop: 16 }}>
          <p className="small">{t("account.removeIntro")}</p>
          <label className="field">
            <span>{t("account.currentPassword")}</span>
            <input
              type="password"
              required
              autoComplete="current-password"
              value={removeCurrent}
              onChange={(e) => setRemoveCurrent(e.target.value)}
            />
          </label>
          <div className="actions">
            <button className="btn btn-secondary" disabled={busy}>
              {t("account.removePassword")}
            </button>
          </div>
        </form>
      )}
      {mismatch ? (
        <div className="alert alert-error">{t("errors.password_mismatch")}</div>
      ) : (
        <ErrorText error={error} />
      )}
      {message && <div className="alert alert-ok">{message}</div>}
    </section>
  );
}

function DeleteSection({ me, onDeleted }: { me: Me; onDeleted: () => Promise<void> }) {
  const { t, i18n } = useTranslation();
  const hasPassword = me.user.has_password;
  const freshLink = me.session.reauth_seconds_left > 0;
  const [password, setPassword] = useState("");
  const [understood, setUnderstood] = useState(false);
  const [linkSent, setLinkSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  if (me.user.role !== "learner" || me.session.impersonated_by) return null;

  async function sendLink() {
    setError(null);
    setBusy(true);
    try {
      await post("/api/auth/link", {
        email: me.user.email,
        locale: apiLocale(i18n.language),
        next: "/account",
      });
      setLinkSent(true);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function remove(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await del("/api/me", freshLink && !password ? {} : { password });
      await onDeleted();
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  const canSubmit = understood && (freshLink || (hasPassword && password.length > 0));

  return (
    <section className="card">
      <h2>{t("account.deleteTitle")}</h2>
      <p className="small">{t("account.deleteIntro")}</p>
      <p className="small">{t("account.deleteKept")}</p>
      <form className="form" onSubmit={(e) => void remove(e)}>
        {freshLink ? (
          <div className="alert alert-ok">{t("account.reauthFresh")}</div>
        ) : (
          <>
            {hasPassword && (
              <label className="field">
                <span>{t("fields.password")}</span>
                <input
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </label>
            )}
            <p className="small">
              {hasPassword ? t("account.reauthEither") : t("account.reauthLink")}
            </p>
            {linkSent ? (
              <div className="alert alert-ok">{t("account.reauthLinkSent")}</div>
            ) : (
              <div className="actions">
                <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => void sendLink()}>
                  {t("login.sendLink")}
                </button>
              </div>
            )}
          </>
        )}
        <label className="check">
          <input type="checkbox" checked={understood} onChange={(e) => setUnderstood(e.target.checked)} />
          <span>{t("account.deleteConfirm")}</span>
        </label>
        <ErrorText error={error} />
        <div className="actions">
          <button className="btn btn-danger" disabled={busy || !canSubmit}>
            {t("account.deleteSubmit")}
          </button>
        </div>
      </form>
    </section>
  );
}
