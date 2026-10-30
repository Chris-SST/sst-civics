import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { get, post } from "../api";
import ErrorText from "../components/ErrorText";
import Pricing from "../components/Pricing";
import { MasteryBar } from "../components/QuestionCard";
import { formatDate } from "../i18n";
import { TOPIC_SCOPES, practiceUrl, type PracticeOverview, type TopicOverview } from "../practice";

interface Recent {
  id: string;
  topic_name: string;
  status: "active" | "ended";
  last_activity_at: string;
}
interface Usage {
  daily_used: number;
  daily_limit: number | null;
  monthly_used: number;
  monthly_limit: number | null;
  daily_exhausted: boolean;
  monthly_exhausted: boolean;
  near_monthly_limit: boolean;
}
interface Overview {
  tutor_name: string;
  tutor_enabled: boolean;
  access: "full" | "none";
  usage: Usage;
  recent: Recent[];
}

const NOTICE_KEY = "sst.tutorNoticeSeen";

function noticeSeen(): boolean {
  try {
    return localStorage.getItem(NOTICE_KEY) === "1";
  } catch {
    return false;
  }
}

/** Learner home: the topics of the learner's canton with mastery, the diagnostic, recent chats. */
export default function LearnerHome() {
  const { t } = useTranslation();
  const [showNotice, setShowNotice] = useState(() => !noticeSeen());
  const navigate = useNavigate();
  const [data, setData] = useState<Overview | null>(null);
  const [practice, setPractice] = useState<PracticeOverview | null | undefined>(undefined);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [hideDiag, setHideDiag] = useState(false);

  useEffect(() => {
    get<Overview>("/api/tutor/overview").then(setData).catch(setError);
    get<PracticeOverview>("/api/practice/overview")
      .then(setPractice)
      .catch(() => setPractice(null));
  }, []);

  if (!data) return error ? <ErrorText error={error} /> : <p className="muted">…</p>;

  const fullAccess = data.access === "full";
  const canChat = fullAccess && data.tutor_enabled;

  function acknowledge() {
    try {
      localStorage.setItem(NOTICE_KEY, "1");
    } catch {
      /* storage unavailable: the notice shows again next time */
    }
    setShowNotice(false);
  }

  async function askTutor(topicCode: string) {
    setBusy(`chat:${topicCode}`);
    setError(null);
    try {
      const conv = await post<{ id: string }>("/api/tutor/conversations", { topic_code: topicCode });
      navigate(`/learner/chat/${conv.id}`);
    } catch (e) {
      setError(e);
      setBusy(null);
    }
  }

  async function startDiagnostic() {
    setBusy("diag");
    setError(null);
    try {
      const run = await post<{ id: string }>("/api/practice/diagnostic/start");
      navigate(`/learner/diagnostic/${run.id}`);
    } catch (e) {
      setError(e);
      setBusy(null);
    }
  }

  return (
    <>
      <h1>{t("learner.welcome")}</h1>

      {showNotice && canChat && (
        <section className="card notice-card">
          <h2>{t("learner.noticeTitle", { name: data.tutor_name })}</h2>
          <p>{t("learner.noticeBody")}</p>
          <button type="button" className="btn btn-primary" onClick={acknowledge}>
            {t("learner.noticeOk")}
          </button>
        </section>
      )}

      {data.access !== "full" && (
        <p className="alert alert-warn">
          <span className={`status status-${data.access}`}>{t(`access.${data.access}`)}</span> {t("learner.noAccess")}
        </p>
      )}
      {fullAccess && !data.tutor_enabled && <p className="alert alert-info">{t("learner.tutorOffline")}</p>}
      {error ? <ErrorText error={error} /> : null}

      <Pricing />

      <TopicsCard
        overview={practice}
        showDiag={!hideDiag}
        fullAccess={fullAccess}
        canChat={canChat}
        busy={busy}
        onAsk={(code) => void askTutor(code)}
        onPractise={(code) => navigate(practiceUrl(code))}
        onStartDiag={() => void startDiagnostic()}
        onSkipDiag={() => setHideDiag(true)}
      />

      <section className="card">
        <h2>{t("learner.recent")}</h2>
        {data.recent.length === 0 ? (
          <p className="muted">{t("learner.noRecent")}</p>
        ) : (
          <ul className="recent-list">
            {data.recent.map((r) => (
              <li key={r.id}>
                <Link to={`/learner/chat/${r.id}`}>
                  <b>{r.topic_name}</b>
                  <span className="small muted">
                    {formatDate(r.last_activity_at)}
                    {r.status === "ended" && ` · ${t("learner.endedTag")}`}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
        <h3>{t("learner.usage")}</h3>
        <p className="small">
          {t("learner.usageToday", { used: data.usage.daily_used, limit: data.usage.daily_limit ?? "∞" })}
          {data.usage.monthly_limit !== null && (
            <>
              <br />
              {t("learner.usageMonth", { used: data.usage.monthly_used, limit: data.usage.monthly_limit })}
            </>
          )}
        </p>
        {data.usage.near_monthly_limit && <p className="alert alert-warn small">{t("learner.nearLimit")}</p>}
        <p className="small muted">{t("learner.integrity")}</p>
      </section>
    </>
  );
}

interface TopicsCardProps {
  /** undefined while loading, null when the practice overview could not be loaded */
  overview: PracticeOverview | null | undefined;
  showDiag: boolean;
  fullAccess: boolean;
  canChat: boolean;
  busy: string | null;
  onAsk: (topicCode: string) => void;
  onPractise: (topicCode: string) => void;
  onStartDiag: () => void;
  onSkipDiag: () => void;
}

function TopicsCard({ overview, showDiag, fullAccess, canChat, busy, onAsk, onPractise, onStartDiag, onSkipDiag }: TopicsCardProps) {
  const { t } = useTranslation();
  const [showAll, setShowAll] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  if (overview === undefined) {
    return (
      <section className="card course-card">
        <p className="muted">…</p>
      </section>
    );
  }
  if (overview === null || overview.topics.length === 0) {
    return (
      <section className="card course-card">
        <p className="muted">{t("learner.noTopics")}</p>
      </section>
    );
  }

  const canton = t(`cantons.${overview.canton}`, { defaultValue: overview.canton.toUpperCase() });
  const tested = overview.topics.filter((tp) => tp.mastery !== null).length;
  const inProgress = overview.diagnostic?.status === "in_progress";
  const diagVisible =
    showDiag && overview.questions_available > 0 && (overview.diagnostic === null || overview.diagnostic.status !== "done");

  const actions = (tp: TopicOverview) => (
    <div className="actions topic-actions">
      <button
        type="button"
        className="btn btn-primary btn-sm"
        disabled={!fullAccess || tp.questions_available === 0}
        onClick={() => onPractise(tp.topic_code)}
      >
        {t("learner.practise")}
      </button>
      <button type="button" className="btn btn-secondary btn-sm" disabled={!canChat || busy !== null} onClick={() => onAsk(tp.topic_code)}>
        {busy === `chat:${tp.topic_code}` ? t("common.working") : t("learner.askTutor")}
      </button>
    </div>
  );

  return (
    <section className="card course-card">
      <header className="course-head">
        <h2 className="course-title">{t("learner.topicsTitle", { canton })}</h2>
        <div className="overall" aria-label={t("learner.overall")}>
          <b>{overview.overall === null ? "–" : `${overview.overall}%`}</b>
          <span className="small muted">{t("learner.overall")}</span>
        </div>
      </header>
      <p className="small muted">{t("learner.testedOf", { tested, total: overview.topics.length })}</p>
      {overview.questions_available === 0 && <p className="small muted">{t("learner.noQuestionsYet")}</p>}

      {diagVisible && (
        <div className="diag-cta">
          <h3>{t("learner.diagTitle")}</h3>
          <p>{t("learner.diagBody", { count: overview.diagnostic_total_estimate })}</p>
          <div className="actions">
            <button type="button" className="btn btn-primary" disabled={!fullAccess || busy !== null} onClick={onStartDiag}>
              {busy === "diag" ? t("common.working") : inProgress ? t("learner.diagContinue") : t("learner.diagStart")}
            </button>
            <button type="button" className="btn btn-ghost" onClick={onSkipDiag}>
              {t("learner.diagSkip")}
            </button>
          </div>
        </div>
      )}

      {overview.next.length > 0 && (
        <>
          <h3>{t("learner.workNext")}</h3>
          <ul className="next-list">
            {overview.next.map((tp) => (
              <li key={tp.topic_code}>
                <div className="next-head">
                  <b>{tp.topic_name}</b>
                  <span className="small muted">
                    {tp.mastery === null ? t("learner.notTested") : `${tp.mastery}%`}
                    {tp.due && <span className="status status-due">{t("learner.due")}</span>}
                  </span>
                </div>
                {actions(tp)}
              </li>
            ))}
          </ul>
        </>
      )}

      <button type="button" className="link-btn" aria-expanded={showAll} onClick={() => setShowAll((s) => !s)}>
        {showAll ? t("learner.hideTopics") : t("learner.showTopics", { count: overview.topics.length })}
      </button>
      {showAll &&
        TOPIC_SCOPES.map((scope) => {
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
                        <span className="small muted"> · {t("learner.questionsCount", { count: tp.questions_available })}</span>
                      </span>
                      <MasteryBar value={tp.mastery} due={tp.due} label={tp.topic_name} />
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
