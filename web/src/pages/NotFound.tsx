import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

export default function NotFound() {
  const { t } = useTranslation();
  return (
    <div className="card narrow">
      <h1>{t("notFound.title")}</h1>
      <Link className="btn btn-secondary" to="/">
        {t("common.home")}
      </Link>
    </div>
  );
}
