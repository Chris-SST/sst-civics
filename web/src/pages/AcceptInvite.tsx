import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import { post } from "../api";
import ErrorText from "../components/ErrorText";

export default function AcceptInvite() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError({ code: "password_mismatch" });
      return;
    }
    try {
      await post("/api/auth/accept-invite", { token, password });
      setDone(true);
    } catch (err) {
      setError(err);
    }
  }

  return (
    <div className="card narrow">
      <h1>{t("invite.title")}</h1>
      {done ? (
        <>
          <div className="alert alert-ok">{t("invite.ok")}</div>
          <Link className="btn btn-primary" to="/login">
            {t("nav.login")}
          </Link>
        </>
      ) : (
        <form className="form" onSubmit={(e) => void submit(e)}>
          <p className="small">{t("invite.intro")}</p>
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
          {(error as { code?: string } | null)?.code === "password_mismatch" ? (
            <div className="alert alert-error">{t("errors.password_mismatch")}</div>
          ) : (
            <ErrorText error={error} />
          )}
          <button className="btn btn-primary">{t("invite.submit")}</button>
        </form>
      )}
    </div>
  );
}
