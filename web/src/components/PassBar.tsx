import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { get, post, type ProductOut } from "../api";
import { useAuth } from "../auth";
import { formatChf } from "../i18n";

/** The Viapunt Pass, one tap away while a visitor or a free learner practises (Chris, 2 November
 * 2026): a slim bar fixed to the bottom of the screen. A signed-in learner goes straight to
 * Stripe checkout; a visitor goes to sign-up, which remembers the wish and opens the pass on the
 * learner home afterwards. Hidden for learners who already have access. */

export const BUY_AFTER_SIGNUP = "viapunt.buyPass";

export default function PassBar({ canton = "zh" }: { canton?: string }) {
  const { t, i18n } = useTranslation();
  const { me, config } = useAuth();
  const learner = me?.user.role === "learner" ? me : null;
  const myCanton = learner?.access.canton || canton;
  const [pass, setPass] = useState<ProductOut | null>(null);
  const [busy, setBusy] = useState(false);
  const hidden = (!!me && !learner) || (!!learner && !learner.access.free_tier) || config?.billing_enabled === false;

  useEffect(() => {
    if (hidden) return;
    get<ProductOut[]>("/api/billing/products")
      .then((list) => setPass(list.find((p) => p.kind === "pass" && p.canton === myCanton && p.available) ?? null))
      .catch(() => setPass(null));
  }, [hidden, myCanton]);

  if (hidden || !pass) return null;
  const price = formatChf(pass.amount_cents, pass.currency);
  const label = t("passBar.cta", { price });

  async function buy() {
    if (!pass) return;
    setBusy(true);
    try {
      const out = await post<{ url: string }>("/api/billing/checkout", { product: pass.key });
      window.location.assign(out.url);
    } catch {
      setBusy(false);
      window.location.assign("/learner#pricing");
    }
  }

  return (
    <>
      <div className="pass-bar-spacer" aria-hidden="true" />
      <aside className="pass-bar" aria-label={t("pricing.title")}>
        <div className="pass-bar-inner">
          <p className="small">
            <b>{t("pricing.passName", { canton: t(`cantons.${myCanton}`, { defaultValue: myCanton.toUpperCase() }) })}</b>{" "}
            <span className="pass-bar-text">{t("passBar.text", { months: pass.months })}</span>
          </p>
          {learner ? (
            <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={() => void buy()}>
              {busy ? t("common.working") : label}
            </button>
          ) : (
            <Link
              className="btn btn-primary btn-sm"
              to={`/signup?lang=${encodeURIComponent(i18n.language.slice(0, 2))}&canton=${myCanton}&pass=1`}
            >
              {label}
            </Link>
          )}
        </div>
      </aside>
    </>
  );
}
