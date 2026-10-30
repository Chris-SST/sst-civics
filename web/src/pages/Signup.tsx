import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { CANTONS, STUDY_LANGUAGES, post } from "../api";
import ErrorText from "../components/ErrorText";
import { shortLocale } from "../i18n";

const SITE = "https://swisssciencetutors.ch";

export default function Signup() {
  const { t, i18n } = useTranslation();
  const [email, setEmail] = useState("");
  const [canton, setCanton] = useState<string>("zh");
  const [studyLanguage, setStudyLanguage] = useState<string>("en");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [ageConfirmed, setAgeConfirmed] = useState(false);
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
        study_language: studyLanguage,
        canton,
        age_confirmed: ageConfirmed,
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
        <label className="field">
          <span>{t("fields.canton")}</span>
          <select value={canton} onChange={(e) => setCanton(e.target.value)}>
            {CANTONS.map((c) => (
              <option key={c} value={c}>
                {t(`cantons.${c}`)}
              </option>
            ))}
          </select>
          <span className="hint">{t("signup.cantonHint")}</span>
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
          <span className="hint">{t("signup.studyLanguageHint")}</span>
        </label>
        <label className="check">
          <input type="checkbox" checked={ageConfirmed} onChange={(e) => setAgeConfirmed(e.target.checked)} required />
          <span>{t("signup.ageConfirm")}</span>
        </label>
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
