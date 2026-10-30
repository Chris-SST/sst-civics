import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { get } from "../api";
import ErrorText from "../components/ErrorText";
import Pricing from "../components/Pricing";
import { MasteryBar } from "../components/QuestionCard";
import { TOPIC_SCOPES, learnUrl, practiseUrl, type StudyOverview, type TopicOverview } from "../study";

interface Usage {
  daily_used: number;
  daily_limit: number | null;
  monthly_used: number;
  monthly_limit: number | null;
  daily_exhausted: boolean;
  monthly_exhausted: boolean;
  near_monthly_limit: boolean;
}
interface TutorOverview {
  tutor_name: string;
  tutor_enabled: boolean;
  access: "full" | "none";
  usage: Usage;
}

const NOTICE_KEY = "sst.tutorNoticeSeen";

function noticeSeen(): boolean {
  try {
    return localStorage.getItem(NOTICE_KEY) === "1";
  } catch {
    return false;
  }
}

/** Learner home: readiness estimate, the three study areas (Learn, Practise, Mock test), mastery
 * per topic, the free-tier notice and the message count. The topic chat has no entry here any
 * more: Explain this, on every question in Learn and Practise, replaces it (task 1.10). */
export default function LearnerHome() {
  const { t } = useTranslation();
  const [showNotice, setShowNotice] = useState(() => !noticeSeen());
  const [tutor, setTutor] = useState<TutorOverview | null>(null);
  const [study, setStudy] = useState<StudyOverview | null | undefined>(undefined);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    get<TutorOverview>("/api/tutor/overview").then(setTutor).catch(setError);
    get<StudyOverview>("/api/study/overview")
      .then(setStudy)
      .catch(() => setStudy(null));
  }, []);

  if (!tutor) return error ? <ErrorText error={error} /> : <p className="muted">…</p>;

  const fullAccess = tutor.access === "full";
  const canChat = fullAccess && tutor.tutor_enabled;

  function acknowledge() {
    try {
      localStorage.setItem(NOTICE_KEY, "1");
    } catch {
      /* storage unavailable: the notice shows again next time */
    }
    setShowNotice(false);
  }

  return (
    <>
      <h1>{t("learner.welcome")}</h1>

      {showNotice && canChat && (
        <section className="card notice-card">
          <h2>{t("learner.noticeTitle", { name: tutor.tutor_name })}</h2>
          <p>{t("learner.noticeBody")}</p>
          <button type="button" className="btn btn-primary" onClick={acknowledge}>
            {t("learner.noticeOk")}
          </button>
        </section>
      )}

      {study?.free_tier && (
        <p className="alert alert-warn">
          {t("learner.freeTierNotice", { count: study.sample_size })}
        </p>
      )}
      {fullAccess && !tutor.tutor_enabled && <p className="alert alert-info">{t("learner.tutorOffline")}</p>}
      {error ? <ErrorText error={error} /> : null}

      {study === undefined && <p className="muted">…</p>}
      {study === null && <p className="muted">{t("learner.noTopics")}</p>}
      {study && <StudyAreas study={study} />}

      <Pricing />

      {study && study.topics.length > 0 && (
        <TopicsCard overview={study} />
      )}

      <section className="card">
        <h2>{t("learner.usage")}</h2>
        <p className="small">
          {t("learner.usageToday", { used: tutor.usage.daily_used, limit: tutor.usage.daily_limit ?? "∞" })}
          {tutor.usage.monthly_limit !== null && (
            <>
              <br />
              {t("learner.usageMonth", { used: tutor.usage.monthly_used, limit: tutor.usage.monthly_limit })}
            </>
          )}
        </p>
        {tutor.usage.near_monthly_limit && <p className="alert alert-warn small">{t("learner.nearLimit")}</p>}
        <p className="small muted">{t("learner.integrity")}</p>
      </section>
    </>
  );
}

function StudyAreas({ study }: { study: StudyOverview }) {
  const { t } = useTranslation();
  const m = study.mock;
  const canton = t(`cantons.${study.canton}`, { defaultValue: study.canton.toUpperCase() });
  const empty = study.questions_available === 0;
  return (
    <>
      <section className="card readiness-card">
        <div className="readiness">
          <b className="readiness-value">{study.readiness.value}%</b>
          <div>
            <h2>{t("learner.readinessTitle", { canton })}</h2>
            <p className="small muted">{t(study.readiness.label_key)}</p>
          </div>
        </div>
        <MasteryBar value={study.readiness.value} label={t("learner.readinessTitle", { canton })} />
        <p className="small muted">
          {t("learner.knownOf", {
            known: study.topics.reduce((n, tp) => n + tp.known, 0),
            total: study.questions_total,
          })}
          {study.due > 0 && ` · ${t("learner.dueCount", { count: study.due })}`}
        </p>
        {empty && <p className="small muted">{t("learner.noQuestionsYet")}</p>}
        <p className="small">
          <Link to="/glossary">{t("glossary.link")}</Link>
        </p>
      </section>

      <div className="study-areas">
        <section className="card area-card">
          <h2>{t("learn.title")}</h2>
          <p>{t("learner.learnBody")}</p>
          <Link to={learnUrl()} className={`btn btn-secondary${empty ? " disabled" : ""}`} aria-disabled={empty}>
            {t("learner.learnCta")}
          </Link>
        </section>
        <section className="card area-card">
          <h2>{t("practice.title")}</h2>
          <p>{t("learner.practiseBody")}</p>
          <Link to={practiseUrl()} className={`btn btn-primary${empty ? " disabled" : ""}`} aria-disabled={empty}>
            {study.due > 0 ? t("learner.practiseDue", { count: study.due }) : t("learner.practiseCta")}
          </Link>
        </section>
        <section className="card area-card">
          <h2>{t("mock.title")}</h2>
          <p>
            {m.configured && m.questions && m.minutes
              ? t("learner.mockBody", { questions: m.questions, minutes: m.minutes })
              : t("learner.mockSoon")}
          </p>
          {!m.paid && <p className="small muted">{m.free_mock_used ? t("learner.freeMockUsed") : t("learner.freeMockLeft")}</p>}
          <Link to={m.active_run_id ? `/mock/${m.active_run_id}` : "/mock"} className="btn btn-secondary">
            {m.active_run_id ? t("mock.continue") : t("learner.mockCta")}
          </Link>
        </section>
      </div>
    </>
  );
}

function TopicsCard({ overview }: { overview: StudyOverview }) {
  const { t } = useTranslation();
  const [selected, setSelected] = useState<string | null>(null);
  const canton = t(`cantons.${overview.canton}`, { defaultValue: overview.canton.toUpperCase() });

  const actions = (tp: TopicOverview) => (
    <div className="actions topic-actions">
      <Link className="btn btn-secondary btn-sm" to={learnUrl(tp.topic_code)} aria-disabled={tp.questions_available === 0}>
        {t("learn.title")}
      </Link>
      <Link className="btn btn-primary btn-sm" to={practiseUrl(tp.topic_code)} aria-disabled={tp.questions_available === 0}>
        {t("learner.practise")}
      </Link>
    </div>
  );

  return (
    <section className="card course-card">
      <h2 className="course-title">{t("learner.topicsTitle", { canton })}</h2>
      <p className="small muted">{t("learner.masteryHint")}</p>
      {TOPIC_SCOPES.map((scope) => {
        const group = overview.topics.filter((tp) => tp.scope === scope);
        if (group.length === 0) return null;
        return (
          <div key={scope} className="topic-group">
            <h3>{t(`topics.scope.${scope}`)}</h3>
            <ul className="topic-list">
              {group.map((tp) => (
                <li key={tp.topic_code} className={selected === tp.topic_code ? "open" : ""}>
                  <button
                    type="button"
                    className="topic-row"
                    aria-expanded={selected === tp.topic_code}
                    onClick={() => setSelected((s) => (s === tp.topic_code ? null : tp.topic_code))}
                  >
                    <span className="topic-name">
                      {tp.topic_name}
                      <span className="small muted">
                        {" · "}
                        {t("learner.topicCounts", { known: tp.known, understood: tp.understood, total: tp.questions_total })}
                      </span>
                    </span>
                    <MasteryBar value={tp.seen > 0 ? tp.mastery : null} label={tp.topic_name} />
                  </button>
                  {selected === tp.topic_code && actions(tp)}
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </section>
  );
}
