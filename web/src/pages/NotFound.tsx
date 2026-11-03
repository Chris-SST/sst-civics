import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { guidePathFor, onAppHost } from "../guide";

export default function NotFound() {
  const { t } = useTranslation();
  // A guide-site address on the app host (app.viapunt.ch/en/fees/): go to that guide page.
  const guide = onAppHost() ? guidePathFor(window.location.pathname) : null;
  useEffect(() => {
    if (guide) window.location.replace(guide);
  }, [guide]);
  if (guide) return <p className="muted">…</p>;
  return (
    <div className="card narrow">
      <h1>{t("notFound.title")}</h1>
      <Link className="btn btn-secondary" to="/">
        {t("common.home")}
      </Link>
    </div>
  );
}
