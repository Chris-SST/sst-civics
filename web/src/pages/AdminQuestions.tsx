import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink, Route, Routes, useParams } from "react-router-dom";
import { get } from "../api";
import ErrorText from "../components/ErrorText";
import QuestionReview, {
  StatsKpis,
  TranslationStatusTable,
  scopeLabel,
  useTopicName,
  type ReviewMeta,
  type ReviewStats,
  type TranslationStatus,
} from "../components/QuestionReview";
import { formatDate } from "../i18n";

/** Admin: question bank overview (counts, translation status, open reports) and the review
 * queue. Questions come from content/ and are imported on deploy; there is no generation here
 * (the content pipeline runs as scripts, task 1.5). */
export default function AdminQuestions() {
  const { t } = useTranslation();
  return (
    <>
      <nav className="tabs tabs-sub">
        <NavLink to="/admin/questions" end>
          {t("qbank.overview")}
        </NavLink>
        <NavLink to="/admin/questions/review">{t("qbank.reviewQueue")}</NavLink>
      </nav>
      <Routes>
        <Route index element={<Bank />} />
        <Route path="review" element={<QuestionReview />} />
        <Route path="review/:id" element={<ReviewById />} />
      </Routes>
    </>
  );
}

function ReviewById() {
  const { id } = useParams();
  return <QuestionReview initialQuestionId={id} />;
}

interface Report {
  id: string;
  question_id: string;
  scope: string;
  topic_code: string;
  lang: string | null;
  comment: string | null;
  created_at: string;
  question_status: string;
}

function Bank() {
  const { t } = useTranslation();
  const [meta, setMeta] = useState<ReviewMeta | null>(null);
  const [stats, setStats] = useState<ReviewStats | null>(null);
  const [translations, setTranslations] = useState<TranslationStatus | null>(null);
  const [reports, setReports] = useState<Report[]>([]);
  const [canton, setCanton] = useState("");
  const [error, setError] = useState<unknown>(null);
  const topicName = useTopicName(meta);

  useEffect(() => {
    Promise.all([get<ReviewMeta>("/api/review/meta"), get<ReviewStats>("/api/review/stats"), get<Report[]>("/api/review/reports")])
      .then(([m, s, r]) => {
        setMeta(m);
        setStats(s);
        setReports(r);
      })
      .catch(setError);
  }, []);

  useEffect(() => {
    const qs = canton ? `?canton=${encodeURIComponent(canton)}` : "";
    get<TranslationStatus>(`/api/review/translations${qs}`).then(setTranslations).catch(setError);
  }, [canton]);

  return (
    <>
      {error ? <ErrorText error={error} /> : null}
      <p className="small muted">{t("qbank.importNote")}</p>
      {stats && <StatsKpis stats={stats} />}

      <section className="card">
        <h2>{t("qbank.translationsTitle")}</h2>
        <div className="filters">
          <label className="field">
            <span>{t("review.canton")}</span>
            <select value={canton} onChange={(e) => setCanton(e.target.value)}>
              <option value="">{t("review.allCantons")}</option>
              <option value="federal">{t("review.federal")}</option>
              {(meta?.cantons ?? []).map((c) => (
                <option key={c} value={c}>
                  {t(`cantons.${c}`, { defaultValue: c.toUpperCase() })}
                </option>
              ))}
            </select>
          </label>
        </div>
        {translations ? <TranslationStatusTable data={translations} /> : <p className="muted">…</p>}
      </section>

      <section className="card">
        <h2>{t("qbank.reports")}</h2>
        {reports.length === 0 ? (
          <p className="muted">{t("qbank.noReports")}</p>
        ) : (
          <div className="table-wrap">
            <table className="table table-stack">
              <thead>
                <tr>
                  <th>{t("admin.received")}</th>
                  <th>{t("review.topic")}</th>
                  <th>{t("qbank.comment")}</th>
                  <th>{t("review.statusLabel")}</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {reports.map((r) => (
                  <tr key={r.id}>
                    <td data-label={t("admin.received")} className="small">
                      {formatDate(r.created_at)}
                    </td>
                    <td data-label={t("review.topic")} className="small">
                      {scopeLabel(t, r.scope)} · {topicName(r.topic_code)}
                      {r.lang && <span className="chip">{t(`languages.${r.lang}`, { defaultValue: r.lang })}</span>}
                    </td>
                    <td data-label={t("qbank.comment")}>{r.comment || <span className="muted">{t("qbank.noComment")}</span>}</td>
                    <td data-label={t("review.statusLabel")}>
                      <span className={`status status-${r.question_status}`}>{t(`review.status.${r.question_status}`, { defaultValue: r.question_status })}</span>
                    </td>
                    <td className="table-actions">
                      <Link to={`/admin/questions/review/${encodeURIComponent(r.question_id)}`} className="btn btn-sm btn-secondary">
                        {t("common.open")}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
