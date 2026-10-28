import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, Navigate } from "react-router-dom";
import { get, type PlanOut } from "../api";
import { homeFor, useAuth } from "../auth";
import { formatChf } from "../i18n";

export default function Landing() {
  const { t } = useTranslation();
  const { me, loading, config } = useAuth();
  const [plans, setPlans] = useState<PlanOut[]>([]);

  useEffect(() => {
    get<PlanOut[]>("/api/billing/plans")
      .then((p) => setPlans(p.filter((x) => x.kind === "subscription")))
      .catch(() => setPlans([]));
  }, []);

  if (!loading && me) return <Navigate to={homeFor(me.user.role)} replace />;

  return (
    <>
      <section className="hero">
        <h1>{t("landing.title", { name: config?.tutor_name ?? "SST Virtual Tutor" })}</h1>
        <p>{t("landing.lead")}</p>
        <div className="actions" style={{ justifyContent: "center" }}>
          <Link className="btn btn-primary" to="/signup">
            {t("landing.cta")}
          </Link>
          <Link className="btn btn-secondary" to="/login">
            {t("nav.login")}
          </Link>
        </div>
      </section>

      <section className="card">
        <h2>{t("landing.plansTitle")}</h2>
        <div className="plans">
          {plans.map((p) => (
            <div key={p.key} className={`plan ${p.key === "hybrid_monthly" ? "featured" : ""}`}>
              <h3>{t(`plans.${p.key}.name`)}</h3>
              <div className="price">
                {formatChf(p.amount_cents, p.currency)}{" "}
                <small>{p.interval ? t(`plans.per_${p.interval}`) : ""}</small>
              </div>
              <p className="small">{t(`plans.${p.key}.blurb`)}</p>
              <p className="hint">
                {t("plans.limits", { monthly: p.monthly_message_limit, daily: p.daily_message_limit })}
              </p>
            </div>
          ))}
          {plans.length === 0 && <p className="muted">{t("plans.unavailable")}</p>}
        </div>
        <p className="hint" style={{ marginTop: 12 }}>
          {t("landing.trialNote")}{" "}
          <a href="https://swisssciencetutors.ch/virtual-tutor/">{t("landing.learnMore")}</a>
        </p>
      </section>
    </>
  );
}
