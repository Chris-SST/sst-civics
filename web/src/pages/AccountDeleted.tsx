import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

/** Shown after a learner deleted their own account. */
export default function AccountDeleted() {
  const { t } = useTranslation();
  return (
    <div className="card narrow">
      <h1>{t("account.deletedTitle")}</h1>
      <p>{t("account.deletedBody")}</p>
      <Link className="btn btn-secondary" to="/">
        {t("common.home")}
      </Link>
    </div>
  );
}
