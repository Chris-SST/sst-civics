import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import { get, type LatestPaymentOut, type Me } from "../api";
import { useAuth } from "../auth";
import { formatDate } from "../i18n";

/** Polls every two seconds for this long before showing the "taking longer" message. */
const POLL_MS = 2000;
const MAX_TRIES = 15;

/** The purchase is confirmed when the latest payment is this Checkout Session (the webhook has
 * granted or extended the entitlement). Without a session id, any active access for the canton
 * counts. */
function confirmed(
  me: Me | null,
  payment: LatestPaymentOut | null,
  sessionId: string | null,
  canton: string | null,
): boolean {
  if (!me) return false;
  if (sessionId) return payment?.checkout_session_id === sessionId;
  return me.access.entitlements.some((e) => e.active && (!canton || e.canton === canton));
}

export default function BillingReturn() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const status = params.get("status");
  const sessionId = params.get("session_id");
  const canton = params.get("canton");
  const { me, refresh } = useAuth();
  const [tries, setTries] = useState(0);
  const [payment, setPayment] = useState<LatestPaymentOut | null>(null);

  const done = status === "success" && confirmed(me, payment, sessionId, canton);
  const until = me?.access.entitlements
    .filter((e) => e.active && e.canton === (canton ?? payment?.canton))
    .map((e) => e.expires_at)
    .sort()
    .pop();
  const cantonCode = canton ?? payment?.canton ?? "";
  const cantonName = t(`cantons.${cantonCode}`, { defaultValue: cantonCode.toUpperCase() });

  useEffect(() => {
    if (status !== "success" || done || tries >= MAX_TRIES) return;
    const id = setTimeout(async () => {
      // The payment is read from its own endpoint; /me is refreshed for the entitlements.
      setPayment(await get<LatestPaymentOut | null>("/api/billing/payments/latest").catch(() => null));
      await refresh();
      setTries((n) => n + 1);
    }, POLL_MS);
    return () => clearTimeout(id);
  }, [status, done, tries, refresh]);

  return (
    <div className="card narrow">
      <h1>{t("billingReturn.title")}</h1>
      {status === "cancelled" && <div className="alert alert-info">{t("billingReturn.cancelled")}</div>}
      {done && (
        <div className="alert alert-ok">
          {until
            ? t("billingReturn.activeUntil", { canton: cantonName, date: formatDate(until) })
            : t("billingReturn.active")}
        </div>
      )}
      {status === "success" && !done && tries < MAX_TRIES && (
        <div className="alert alert-info">{t("billingReturn.waiting")}</div>
      )}
      {status === "success" && !done && tries >= MAX_TRIES && (
        <div className="alert alert-warn">{t("billingReturn.slow")}</div>
      )}
      <Link className="btn btn-primary" to="/learner">
        {t("billingReturn.toDashboard")}
      </Link>
    </div>
  );
}
