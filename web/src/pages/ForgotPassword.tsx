import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { post } from "../api";
import ErrorText from "../components/ErrorText";

export default function ForgotPassword() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await post("/api/auth/forgot-password", { email });
      setDone(true);
    } catch (err) {
      setError(err);
    }
  }

  return (
    <div className="card narrow">
      <h1>{t("forgot.title")}</h1>
      {done ? (
        <>
          <div className="alert alert-ok">{t("forgot.sent")}</div>
          <Link className="btn btn-secondary" to="/login">
            {t("nav.login")}
          </Link>
        </>
      ) : (
        <form className="form" onSubmit={(e) => void submit(e)}>
          <p className="small">{t("forgot.intro")}</p>
          <label className="field">
            <span>{t("fields.email")}</span>
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <ErrorText error={error} />
          <div className="actions">
            <button className="btn btn-primary">{t("forgot.submit")}</button>
            <Link to="/login" className="small">
              {t("common.back")}
            </Link>
          </div>
        </form>
      )}
    </div>
  );
}
