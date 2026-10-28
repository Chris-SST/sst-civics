import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import { post } from "../api";
import ErrorText from "../components/ErrorText";

export default function VerifyEmail() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [state, setState] = useState<"working" | "ok" | "error">("working");
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!token) {
      setState("error");
      return;
    }
    post("/api/auth/verify-email", { token })
      .then(() => setState("ok"))
      .catch((e) => {
        setError(e);
        setState("error");
      });
  }, [token]);

  return (
    <div className="card narrow">
      <h1>{t("verify.title")}</h1>
      {state === "working" && <p className="muted">{t("common.working")}</p>}
      {state === "ok" && (
        <>
          <div className="alert alert-ok">{t("verify.ok")}</div>
          <Link className="btn btn-primary" to="/login">
            {t("nav.login")}
          </Link>
        </>
      )}
      {state === "error" && (
        <>
          <ErrorText error={error ?? { code: "invalid_token" }} />
          <p className="small">{t("verify.retryHint")}</p>
          <Link className="btn btn-secondary" to="/login">
            {t("nav.login")}
          </Link>
        </>
      )}
    </div>
  );
}
