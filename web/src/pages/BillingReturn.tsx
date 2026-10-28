import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth";

export default function BillingReturn() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const status = params.get("status");
  const { me, refresh } = useAuth();
  const [tries, setTries] = useState(0);

  const active = me?.family?.access === "full";

  useEffect(() => {
    if (status !== "success" || active || tries >= 15) return;
    const id = setTimeout(async () => {
      await refresh();
      setTries((n) => n + 1);
    }, 2000);
    return () => clearTimeout(id);
  }, [status, active, tries, refresh]);

  return (
    <div className="card narrow">
      <h1>{t("billingReturn.title")}</h1>
      {status === "cancelled" && <div className="alert alert-info">{t("billingReturn.cancelled")}</div>}
      {status === "success" && active && <div className="alert alert-ok">{t("billingReturn.active")}</div>}
      {status === "success" && !active && tries < 15 && (
        <div className="alert alert-info">{t("billingReturn.waiting")}</div>
      )}
      {status === "success" && !active && tries >= 15 && (
        <div className="alert alert-warn">{t("billingReturn.slow")}</div>
      )}
      <Link className="btn btn-primary" to="/parent">
        {t("billingReturn.toDashboard")}
      </Link>
    </div>
  );
}
