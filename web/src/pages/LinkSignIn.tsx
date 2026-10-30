import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, post, type LoginOut } from "../api";
import { pathAfterSignIn, useAuth } from "../auth";
import ErrorText from "../components/ErrorText";

/** Pages a sign-in link may return to (mirrors the API's fixed list). */
const ALLOWED_NEXT = ["/account"];

/** Opens a one-time sign-in link: /auth/link?token=… (optionally next=/account). */
export default function LinkSignIn() {
  const { t } = useTranslation();
  const { refresh } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const nextParam = params.get("next");
  const next = nextParam && ALLOWED_NEXT.includes(nextParam) ? nextParam : null;
  const [error, setError] = useState<unknown>(null);
  // The token works once; React may run effects twice in development.
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    if (!token) {
      setError(new ApiError(400, "invalid_token"));
      return;
    }
    post<LoginOut>("/api/auth/link/consume", { token })
      .then(async (out) => {
        await refresh();
        navigate(pathAfterSignIn(out, next), { replace: true });
      })
      .catch((e) => setError(e));
  }, [token, next, refresh, navigate]);

  return (
    <div className="card narrow">
      <h1>{t("linkSignIn.title")}</h1>
      {error ? (
        <>
          <ErrorText error={error} />
          <p className="small">{t("linkSignIn.retryHint")}</p>
          <Link className="btn btn-secondary" to="/login">
            {t("linkSignIn.newLink")}
          </Link>
        </>
      ) : (
        <p className="muted">{t("common.working")}</p>
      )}
    </div>
  );
}
