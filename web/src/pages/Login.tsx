import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ApiError, post, type Me } from "../api";
import { homeFor, useAuth } from "../auth";
import ErrorText from "../components/ErrorText";

interface LoginOut {
  status: "ok" | "mfa_required" | "mfa_setup_required";
  me: Me | null;
}

export default function Login() {
  const { t } = useTranslation();
  const { refresh } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [resent, setResent] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const out = await post<LoginOut>("/api/auth/login", { email, password });
      await refresh();
      if (out.status === "mfa_required") navigate("/2fa");
      else if (out.status === "mfa_setup_required") navigate("/2fa/setup");
      else {
        const from = (location.state as { from?: string } | null)?.from;
        navigate(from && from !== "/login" ? from : homeFor(out.me?.user.role ?? ""));
      }
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

  return (
    <div className="card narrow">
      <h1>{t("login.title")}</h1>
      <form className="form" onSubmit={(e) => void submit(e)}>
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
      </form>
      <p className="small" style={{ marginTop: 16 }}>
        {t("login.noAccount")} <Link to="/signup">{t("nav.signup")}</Link>
      </p>
    </div>
  );
}
