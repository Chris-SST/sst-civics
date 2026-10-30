import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ApiError, apiLocale, post, type LoginOut } from "../api";
import { pathAfterSignIn, useAuth } from "../auth";
import ErrorText from "../components/ErrorText";

/** Sign-in: an email link first, a password as the second option. */
export default function Login() {
  const { t, i18n } = useTranslation();
  const { refresh } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mode, setMode] = useState<"link" | "password">("link");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [linkSent, setLinkSent] = useState(false);
  const [resent, setResent] = useState(false);

  async function sendLink(e?: FormEvent) {
    e?.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await post("/api/auth/link", { email, locale: apiLocale(i18n.language) });
      setLinkSent(true);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function submitPassword(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const out = await post<LoginOut>("/api/auth/login", { email, password });
      await refresh();
      navigate(pathAfterSignIn(out, (location.state as { from?: string } | null)?.from));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    await post("/api/auth/resend-verification", { email });
    setResent(true);
  }

  const notVerified = error instanceof ApiError && error.code === "email_not_verified";

  if (linkSent) {
    return (
      <div className="card narrow">
        <h1>{t("login.checkEmailTitle")}</h1>
        <p>{t("login.checkEmailBody", { email })}</p>
        <p className="small">{t("login.checkEmailHint")}</p>
        <ErrorText error={error} />
        <div className="actions">
          <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => void sendLink()}>
            {t("login.sendAgain")}
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => {
              setLinkSent(false);
              setError(null);
            }}
          >
            {t("login.otherAddress")}
          </button>
        </div>
        <p className="small" style={{ marginTop: 16 }}>
          {t("login.noAccount")} <Link to="/signup">{t("nav.signup")}</Link>
        </p>
      </div>
    );
  }

  const emailField = (
    <label className="field">
      <span>{t("fields.email")}</span>
      <input
        type="email"
        required
        autoComplete="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
    </label>
  );

  return (
    <div className="card narrow">
      <h1>{t("login.title")}</h1>
      {mode === "link" ? (
        <form className="form" onSubmit={(e) => void sendLink(e)}>
          <p className="small">{t("login.linkIntro")}</p>
          {emailField}
          <ErrorText error={error} />
          <div className="actions">
            <button className="btn btn-primary" disabled={busy}>
              {t("login.sendLink")}
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => {
                setMode("password");
                setError(null);
              }}
            >
              {t("login.usePassword")}
            </button>
          </div>
        </form>
      ) : (
        <form className="form" onSubmit={(e) => void submitPassword(e)}>
          {emailField}
          <label className="field">
            <span>{t("fields.password")}</span>
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <ErrorText error={error} />
          {notVerified && !resent && (
            <button type="button" className="btn btn-secondary" onClick={() => void resend()}>
              {t("login.resend")}
            </button>
          )}
          {resent && <div className="alert alert-ok">{t("login.resent")}</div>}
          <div className="actions">
            <button className="btn btn-primary" disabled={busy}>
              {t("login.submit")}
            </button>
            <Link to="/forgot-password" className="small">
              {t("login.forgot")}
            </Link>
          </div>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => {
              setMode("link");
              setError(null);
            }}
          >
            {t("login.useLink")}
          </button>
        </form>
      )}
      <p className="small" style={{ marginTop: 16 }}>
        {t("login.noAccount")} <Link to="/signup">{t("nav.signup")}</Link>
      </p>
    </div>
  );
}
