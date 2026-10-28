import { useTranslation } from "react-i18next";
import { ApiError } from "../api";

export function errorCode(e: unknown): string {
  if (e instanceof ApiError) return e.code;
  return "network_error";
}

export default function ErrorText({ error }: { error: unknown }) {
  const { t } = useTranslation();
  if (!error) return null;
  const code = errorCode(error);
  return (
    <div className="alert alert-error" role="alert">
      {t(`errors.${code}`, { defaultValue: t("errors.unknown_error") })}
    </div>
  );
}
