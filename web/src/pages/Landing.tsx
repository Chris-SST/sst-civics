import { useTranslation } from "react-i18next";
import { Link, Navigate } from "react-router-dom";
import { homeFor, useAuth } from "../auth";
import Pricing from "../components/Pricing";

export default function Landing() {
  const { t } = useTranslation();
  const { me, loading, config } = useAuth();

  if (!loading && me) return <Navigate to={homeFor(me.user.role)} replace />;

  return (
    <>
      <section className="hero">
        <h1>{t("landing.title", { name: config?.tutor_name ?? "Civics Trainer" })}</h1>
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

      <Pricing />
    </>
  );
}
