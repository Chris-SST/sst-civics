import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, useNavigate } from "react-router-dom";
import QRCode from "qrcode";
import { post } from "../api";
import { homeFor, useAuth } from "../auth";
import ErrorText from "../components/ErrorText";

interface SetupOut {
  secret: string;
  otpauth_uri: string;
}

export default function TwoFactor({ mode }: { mode: "verify" | "setup" }) {
  const { t } = useTranslation();
  const { me, loading, refresh } = useAuth();
  const navigate = useNavigate();
  const [setup, setSetup] = useState<SetupOut | null>(null);
  const [qr, setQr] = useState<string>("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (mode !== "setup" || !me || me.user.totp_enabled) return;
    post<SetupOut>("/api/auth/totp/setup")
      .then(async (s) => {
        setSetup(s);
        setQr(await QRCode.toDataURL(s.otpauth_uri, { margin: 1, width: 200 }));
      })
      .catch(setError);
  }, [mode, me]);

  if (loading) return <p className="muted">…</p>;
  if (!me) return <Navigate to="/login" replace />;
  if (mode === "verify" && !me.session.mfa_pending) return <Navigate to={homeFor(me.user.role)} replace />;
  if (mode === "setup" && me.user.totp_enabled) return <Navigate to={homeFor(me.user.role)} replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await post(mode === "setup" ? "/api/auth/totp/enable" : "/api/auth/totp/verify", { code });
      const fresh = await refresh();
      navigate(homeFor(fresh?.user.role ?? me!.user.role));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card narrow">
      <h1>{mode === "setup" ? t("twofa.setupTitle") : t("twofa.verifyTitle")}</h1>
      {mode === "setup" && (
        <>
          <p className="small">{me.user.role === "admin" ? t("twofa.requiredStaff") : t("twofa.optional")}</p>
          <p className="small">{t("twofa.setupSteps")}</p>
          {qr && <img className="qr" src={qr} alt={t("twofa.qrAlt")} />}
          {setup && <code className="secret">{setup.secret}</code>}
        </>
      )}
      {mode === "verify" && <p className="small">{t("twofa.verifyIntro")}</p>}
      <form className="form" onSubmit={(e) => void submit(e)} style={{ marginTop: 12 }}>
        <label className="field">
          <span>{t("twofa.code")}</span>
          <input
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9 ]*"
            required
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
        </label>
        <ErrorText error={error} />
        <button className="btn btn-primary" disabled={busy}>
          {mode === "setup" ? t("twofa.enable") : t("twofa.confirm")}
        </button>
      </form>
    </div>
  );
}
