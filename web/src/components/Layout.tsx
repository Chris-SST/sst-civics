import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { post } from "../api";
import { homeFor, useAuth } from "../auth";
import { LANGUAGES } from "../i18n";

const SITE = "https://swisssciencetutors.ch";

export default function Layout({ children }: { children: ReactNode }) {
  const { t, i18n } = useTranslation();
  const { me, config, logout, refresh } = useAuth();
  const navigate = useNavigate();

  async function onLogout() {
    await logout();
    navigate("/login");
  }

  async function stopImpersonation() {
    await post("/api/auth/stop-impersonation");
    await refresh();
    navigate("/admin");
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="container topbar-inner">
          <Link to={me ? homeFor(me.user.role) : "/"} className="brand" aria-label="SST Virtual Tutor">
            <img src="/brand/logo-green-black.png" alt="Swiss Science Tutors" className="brand-logo" />
            <span className="brand-sub">{config?.tutor_name ?? "Virtual Tutor"}</span>
          </Link>
          <nav className="topnav">
            <label className="lang">
              <span className="visually-hidden">{t("nav.language")}</span>
              <select
                value={i18n.language}
                onChange={(e) => void i18n.changeLanguage(e.target.value)}
                aria-label={t("nav.language")}
              >
                {LANGUAGES.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.label}
                  </option>
                ))}
              </select>
            </label>
            {me ? (
              <>
                <span className="who">
                  <span className="who-name">{me.user.first_name || me.user.email || me.user.username}</span>
                  <span className="role-pill">{t(`roles.${me.user.role}`)}</span>
                </span>
                <button className="btn btn-ghost" onClick={() => void onLogout()}>
                  {t("nav.logout")}
                </button>
              </>
            ) : (
              <>
                <Link className="btn btn-ghost" to="/login">
                  {t("nav.login")}
                </Link>
                <Link className="btn btn-primary" to="/signup">
                  {t("nav.signup")}
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>

      {config?.env && config.env !== "production" && (
        <div className="env-banner">{t("env.banner", { env: config.env })}</div>
      )}
      {me?.session.impersonated_by && (
        <div className="impersonation-banner">
          <span>
            {t("impersonation.banner", {
              name: me.user.first_name || me.user.email || me.user.username,
              role: t(`roles.${me.user.role}`),
              admin: me.session.impersonated_by,
            })}
          </span>
          <button className="btn btn-sm btn-secondary" onClick={() => void stopImpersonation()}>
            {t("impersonation.back")}
          </button>
        </div>
      )}

      <main className="container main">{children}</main>

      <footer className="footer">
        <div className="container footer-inner">
          <ul className="footer-links">
            <li>
              <a href={`${SITE}/`}>{t("footer.home")}</a>
            </li>
            <li>
              <a href={`${SITE}/book-a-consultation/`}>{t("footer.consultation")}</a>
            </li>
            <li>
              <a href={`${SITE}/how-we-operate/`}>{t("footer.lessons")}</a>
            </li>
            <li>
              <a href={`${SITE}/frequently-asked-questions/`}>{t("footer.faq")}</a>
            </li>
            <li>
              <a href={`${SITE}/contact/`}>{t("footer.contact")}</a>
            </li>
            <li>
              <a href={`${SITE}/about-us/`}>{t("footer.about")}</a>
            </li>
            <li>
              <a href={`${SITE}/terms/`}>{t("footer.terms")}</a>
            </li>
            <li>
              <a href={`${SITE}/privacy/`}>{t("footer.privacy")}</a>
            </li>
            <li>
              <a href={`${SITE}/ai-safety/`}>{t("footer.aiSafety")}</a>
            </li>
          </ul>
          <p className="muted small">{t("footer.trademark")}</p>
        </div>
      </footer>
    </div>
  );
}
