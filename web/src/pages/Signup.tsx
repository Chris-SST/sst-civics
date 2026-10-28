import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { post } from "../api";
import ErrorText from "../components/ErrorText";
import { shortLocale } from "../i18n";

const SITE = "https://swisssciencetutors.ch";

export default function Signup() {
  const { t, i18n } = useTranslation();
  const [accountType, setAccountType] = useState<"parent" | "adult">("parent");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [guardian, setGuardian] = useState(false);
  const [terms, setTerms] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [done, setDone] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError({ code: "password_mismatch" });
      return;
    }
    setBusy(true);
    try {
      await post("/api/auth/signup", {
        email,
        password,
        locale: shortLocale(i18n.language),
        account_type: accountType,
        guardian_confirmed: accountType === "parent" ? guardian : false,
        accept_terms: terms,
      });
      setDone(true);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <div className="card narrow">
        <h1>{t("signup.checkEmailTitle")}</h1>
        <p>{t("signup.checkEmailBody", { email })}</p>
        <Link className="btn btn-secondary" to="/login">
          {t("nav.login")}
        </Link>
      </div>
    );
  }

  const mismatch = (error as { code?: string } | null)?.code === "password_mismatch";

  return (
    <div className="card narrow">
      <h1>{t("signup.title")}</h1>
      <p className="small">{t("signup.intro")}</p>
      <form className="form" onSubmit={(e) => void submit(e)}>
        <label className="field">
          <span>{t("signup.accountType")}</span>
          <select value={accountType} onChange={(e) => setAccountType(e.target.value as "parent" | "adult")}>
            <option value="parent">{t("signup.typeParent")}</option>
            <option value="adult">{t("signup.typeAdult")}</option>
          </select>
        </label>
        <label className="field">
          <span>{t("fields.email")}</span>
          <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="field">
          <span>{t("fields.password")}</span>
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
        {accountType === "parent" && (
          <label className="check">
            <input type="checkbox" checked={guardian} onChange={(e) => setGuardian(e.target.checked)} required />
            <span>{t("signup.guardian")}</span>
          </label>
        )}
        <label className="check">
          <input type="checkbox" checked={terms} onChange={(e) => setTerms(e.target.checked)} required />
          <span>
            {t("signup.terms")} <a href={`${SITE}/terms/`}>{t("footer.terms")}</a>,{" "}
            <a href={`${SITE}/privacy/`}>{t("footer.privacy")}</a>
          </span>
        </label>
        {mismatch ? (
          <div className="alert alert-error">{t("errors.password_mismatch")}</div>
        ) : (
          <ErrorText error={error} />
        )}
        <div className="actions">
          <button className="btn btn-primary" disabled={busy}>
            {t("signup.submit")}
          </button>
          <Link to="/login" className="small">
            {t("signup.haveAccount")}
          </Link>
        </div>
      </form>
    </div>
  );
}
