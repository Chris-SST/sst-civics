import { useTranslation } from "react-i18next";
import { Link, Navigate } from "react-router-dom";
import { homeFor, useAuth } from "../auth";
import Pricing from "../components/Pricing";

/** The information-first front door (D-042): what the service does, how it works in three steps,
 * the free sample questions, then the pricing panel. The footer with the independence notice
 * comes from the layout. */
export default function Landing() {
  const { t } = useTranslation();
  const { me, loading } = useAuth();

  if (!loading && me) return <Navigate to={homeFor(me.user.role)} replace />;

  const steps = [1, 2, 3] as const;

  return (
    <>
      <section className="hero">
        <h1>{t("landing.title")}</h1>
        <p>{t("landing.lead")}</p>
        <div className="actions">
          <Link className="btn btn-primary" to="/signup">
            {t("landing.cta")}
          </Link>
          <Link className="btn btn-secondary" to="/login">
            {t("nav.login")}
          </Link>
        </div>
      </section>

      <section className="landing-section" aria-labelledby="how-title">
        <h2 id="how-title">{t("landing.howTitle")}</h2>
        <ol className="steps">
          {steps.map((n) => (
            <li className="step" key={n}>
              <span className="step-n" aria-hidden="true">
                {n}
              </span>
              <h3>{t(`landing.step${n}Title`)}</h3>
              <p>{t(`landing.step${n}Body`)}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="landing-section free-card" aria-labelledby="free-title">
        <div>
          <h2 id="free-title">{t("landing.freeTitle")}</h2>
          <p>{t("landing.freeBody")}</p>
        </div>
        <Link className="btn btn-primary" to="/signup">
          {t("landing.cta")}
        </Link>
      </section>

      <div className="landing-section">
        <Pricing />
      </div>
    </>
  );
}
