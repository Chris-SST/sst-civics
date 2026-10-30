import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError, post, type LoginOut } from "../api";
import { pathAfterSignIn, useAuth } from "../auth";
import ErrorText from "../components/ErrorText";

/** Confirms the address. The confirmation link also signs the person in. */
export default function VerifyEmail() {
  const { t } = useTranslation();
  const { refresh } = useAuth();
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [state, setState] = useState<"working" | "ok" | "error">("working");
  const [next, setNext] = useState("/");
  const [error, setError] = useState<unknown>(null);
  // The token works once; React may run effects twice in development.
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    if (!token) {
      setState("error");
      return;
    }
    post<LoginOut>("/api/auth/verify-email", { token })
      .then(async (out) => {
        await refresh();
        setNext(pathAfterSignIn(out));
        setState("ok");
      })
      .catch((e) => {
        setError(e);
        setState("error");
      });
  }, [token, refresh]);

  return (
    <div className="card narrow">
      <h1>{t("verify.title")}</h1>
      {state === "working" && <p className="muted">{t("common.working")}</p>}
      {state === "ok" && (
        <>
          <div className="alert alert-ok">{t("verify.signedIn")}</div>
          <Link className="btn btn-primary" to={next}>
            {t("verify.continue")}
          </Link>
        </>
      )}
      {state === "error" && (
        <>
          <ErrorText error={error ?? new ApiError(400, "invalid_token")} />
          <p className="small">{t("verify.retryHint")}</p>
          <Link className="btn btn-secondary" to="/login">
            {t("nav.login")}
          </Link>
        </>
      )}
    </div>
  );
}
