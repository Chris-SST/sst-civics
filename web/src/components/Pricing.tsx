import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { get, post, type EntitlementOut, type ProductKey, type ProductOut, type RefundEligibility } from "../api";
import { useAuth } from "../auth";
import { formatChf, formatDate } from "../i18n";
import ErrorText from "./ErrorText";
import { SITE } from "./Layout";

/** Entitlement sources that count as a pass (the server's PASS_SOURCES). */
const PASS_SOURCES = ["stripe", "admin"];
/** An extension may be bought up to this many days after a pass ended (EXTENSION_GRACE_DAYS). */
const GRACE_DAYS = 90;
const DAY_MS = 24 * 60 * 60 * 1000;

interface CantonStatus {
  /** Longest-running access of any kind (pass, admin grant or trial) active now. */
  activeUntil: string | null;
  /** The latest pass, when it has ended. */
  endedOn: string | null;
  passActive: boolean;
  canExtend: boolean;
}

function cantonStatus(entitlements: EntitlementOut[], canton: string, now = Date.now()): CantonStatus {
  const mine = entitlements.filter((e) => e.canton === canton);
  const active = mine.filter((e) => e.active).sort((a, b) => b.expires_at.localeCompare(a.expires_at))[0];
  const pass = mine
    .filter((e) => PASS_SOURCES.includes(e.source))
    .sort((a, b) => b.expires_at.localeCompare(a.expires_at))[0];
  const passEnds = pass ? Date.parse(pass.expires_at) : 0;
  const passStarted = pass ? Date.parse(pass.starts_at) <= now : false;
  return {
    activeUntil: active ? active.expires_at : null,
    endedOn: pass && !pass.active && passEnds <= now ? pass.expires_at : null,
    passActive: !!pass && pass.active,
    canExtend: !!pass && passStarted && passEnds > now - GRACE_DAYS * DAY_MS,
  };
}

/** The Civics Pass products for sale, with access status, Buy and Extend buttons, and the
 * refund rule for the learner's latest payment. Used on the landing page and learner home. */
export default function Pricing() {
  const { t } = useTranslation();
  const { me, config } = useAuth();
  const [products, setProducts] = useState<ProductOut[] | null>(null);
  const [refund, setRefund] = useState<RefundEligibility | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const learner = me?.user.role === "learner" ? me : null;
  const isLearner = learner !== null;
  // Refetch the refund rule whenever the latest payment changes (bought, refunded).
  const paymentKey = learner
    ? `${learner.access.latest_payment?.checkout_session_id ?? ""}:${learner.access.latest_payment?.refunded ?? ""}`
    : "";

  useEffect(() => {
    get<ProductOut[]>("/api/billing/products")
      .then(setProducts)
      .catch(() => setProducts([]));
  }, []);

  useEffect(() => {
    if (!isLearner || paymentKey.startsWith(":")) {
      setRefund(null);
      return;
    }
    get<RefundEligibility>("/api/billing/refund-eligibility")
      .then(setRefund)
      .catch(() => setRefund(null));
  }, [isLearner, paymentKey]);

  async function checkout(product: ProductKey, canton?: string) {
    setBusy(`${product}:${canton ?? ""}`);
    setError(null);
    try {
      const out = await post<{ url: string }>("/api/billing/checkout", { product, canton });
      window.location.assign(out.url);
    } catch (e) {
      setError(e);
      setBusy(null);
    }
  }

  const passes = (products ?? []).filter((p) => p.kind === "pass");
  const extension = (products ?? []).find((p) => p.kind === "extension" && p.available);
  const billingOn = config?.billing_enabled !== false;

  return (
    <section className="card">
      <h2>{t("pricing.title")}</h2>
      <p className="small">{t("pricing.intro")}</p>
      <ErrorText error={error} />
      {products === null && <p className="muted">…</p>}
      {products !== null && passes.length === 0 && <p className="muted">{t("pricing.unavailable")}</p>}
      <div className="plans">
        {passes.map((p) => {
          const canton = p.canton ?? "";
          const name = t(`cantons.${canton}`, { defaultValue: canton.toUpperCase() });
          const status = learner ? cantonStatus(learner.access.entitlements, canton) : null;
          const buyable = p.available && billingOn && !status?.passActive;
          return (
            <div key={p.key} className={`plan ${status?.activeUntil ? "featured" : ""}`}>
              <h3>{t("pricing.passName", { canton: name })}</h3>
              <div className="price">
                {p.available ? formatChf(p.amount_cents, p.currency) : "–"}{" "}
                <small>{t("pricing.period", { months: p.months })}</small>
              </div>
              <p className="small">{t("pricing.passIncludes")}</p>
              {status && (
                <p className="small">
                  {status.activeUntil ? (
                    <span className="status status-full">
                      {t("pricing.activeUntil", { date: formatDate(status.activeUntil) })}
                    </span>
                  ) : status.endedOn ? (
                    <span className="status status-none">
                      {t("pricing.endedOn", { date: formatDate(status.endedOn) })}
                    </span>
                  ) : (
                    <span className="muted">{t("pricing.freeTier")}</span>
                  )}
                </p>
              )}
              <div className="actions">
                {!learner && (
                  <Link className="btn btn-primary" to="/signup">
                    {t("pricing.signUpToBuy")}
                  </Link>
                )}
                {learner && buyable && (
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={busy !== null}
                    onClick={() => void checkout(p.key)}
                  >
                    {busy === `${p.key}:` ? t("common.working") : t("pricing.buy")}
                  </button>
                )}
                {learner && extension && billingOn && status?.canExtend && (
                  <button
                    type="button"
                    className={`btn ${buyable ? "btn-secondary" : "btn-primary"}`}
                    disabled={busy !== null}
                    onClick={() => void checkout(extension.key, canton)}
                  >
                    {busy === `${extension.key}:${canton}`
                      ? t("common.working")
                      : t("pricing.extend", {
                          months: extension.months,
                          price: formatChf(extension.amount_cents, extension.currency),
                        })}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {extension && (
        <p className="hint" style={{ marginTop: 12 }}>
          {t("pricing.extensionNote", {
            months: extension.months,
            price: formatChf(extension.amount_cents, extension.currency),
          })}
        </p>
      )}
      <p className="hint">{t("pricing.priceNote")}</p>
      {refund && refund.reason !== "no_payment" && (
        <p className="small">
          {refund.eligible
            ? t("pricing.refundEligible", {
                date: formatDate(refund.deadline),
                max: refund.max_questions,
                count: refund.questions_studied,
              })
            : refund.reason === "refunded"
              ? t("pricing.refundDone")
              : refund.reason === "too_late"
                ? t("pricing.refundTooLate", { date: formatDate(refund.deadline) })
                : t("pricing.refundTooMany", { max: refund.max_questions, count: refund.questions_studied })}{" "}
          {refund.eligible && <a href={`${SITE}/contact/`}>{t("pricing.writeToSupport")}</a>}
        </p>
      )}
    </section>
  );
}
