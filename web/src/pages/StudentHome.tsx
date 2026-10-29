import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { get, post } from "../api";
import { useAuth } from "../auth";
import ErrorText from "../components/ErrorText";
import { MasteryBar } from "../components/QuestionCard";
import { formatDate } from "../i18n";
import { estimateDiagnosticSize, type PracticeOverview, type TopicOverview } from "../practice";

interface Topic {
  code: string;
  name: string;
}
interface Course {
  key: string;
  name: string;
  level: string;
  topics: Topic[];
}
interface Recent {
  id: string;
  course_name: string;
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
  access: "full" | "read_only" | "none";
  notice_seen: boolean;
  courses: Course[];
  usage: Usage;
  recent: Recent[];
}

export default function StudentHome() {
  const { t } = useTranslation();
  const { me } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState<Overview | null>(null);
  const [practice, setPractice] = useState<Record<string, PracticeOverview | null>>({});
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [hiddenDiag, setHiddenDiag] = useState<Set<string>>(new Set());

  useEffect(() => {
    get<Overview>("/api/tutor/overview")
      .then((d) => {
        setData(d);
        for (const c of d.courses) {
          get<PracticeOverview>(`/api/practice/overview?course_key=${encodeURIComponent(c.key)}`)
            .then((p) => setPractice((m) => ({ ...m, [c.key]: p })))
            .catch(() => setPractice((m) => ({ ...m, [c.key]: null })));
        }
      })
      .catch(setError);
  }, []);

  if (!data) return error ? <ErrorText error={error} /> : <p className="muted">…</p>;

  const fullAccess = data.access === "full";
  const canChat = fullAccess && data.tutor_enabled;

  async function acknowledge() {
    try {
      await post("/api/tutor/notice-seen");
      setData((d) => (d ? { ...d, notice_seen: true } : d));
    } catch (e) {
      setError(e);
    }
  }

  async function askTutor(courseKey: string, topicCode: string) {
    setBusy(`chat:${courseKey}:${topicCode}`);
    setError(null);
    try {
      const conv = await post<{ id: string }>("/api/tutor/conversations", {
        course_key: courseKey,
        topic_code: topicCode,
      });
      navigate(`/student/chat/${conv.id}`);
    } catch (e) {
      setError(e);
      setBusy(null);
    }
  }

  function practise(courseKey: string, topicCode: string) {
    navigate(`/student/practice?course_key=${encodeURIComponent(courseKey)}&topic_code=${encodeURIComponent(topicCode)}`);
  }

  async function startDiagnostic(courseKey: string) {
    setBusy(`diag:${courseKey}`);
    setError(null);
    try {
      const run = await post<{ id: string }>("/api/practice/diagnostic/start", { course_key: courseKey });
      navigate(`/student/diagnostic/${run.id}`);
    } catch (e) {
      setError(e);
      setBusy(null);
    }
  }

  return (
    <>
      <h1>{t("student.hello", { name: me?.user.first_name || me?.user.email || "" })}</h1>

      {!data.notice_seen && canChat && (
        <section className="card notice-card">
          <h2>{t("student.noticeTitle", { name: data.tutor_name })}</h2>
          <p>{t("student.noticeBody")}</p>
          <button type="button" className="btn btn-primary" onClick={acknowledge}>
            {t("student.noticeOk")}
          </button>
        </section>
      )}

      {data.access !== "full" && (
        <p className="alert alert-warn">
          <span className={`status status-${data.access}`}>{t(`access.${data.access}`)}</span> {t("student.askParent")}
        </p>
      )}
      {fullAccess && !data.tutor_enabled && <p className="alert alert-info">{t("student.tutorOffline")}</p>}
      {error ? <ErrorText error={error} /> : null}

      {data.courses.length === 0 && (
        <section className="card">
          <p className="muted">{t("student.noCourses")}</p>
        </section>
      )}

      {data.courses.map((course) => {
        const p = practice[course.key];
        const loading = !(course.key in practice);
        const showDiag =
          !!p &&
          p.questions_available > 0 &&
          (p.diagnostic === null || p.diagnostic.status !== "done") &&
          !hiddenDiag.has(course.key);
        return (
          <CourseCard
            key={course.key}
            course={course}
            overview={loading ? undefined : p}
            showDiag={showDiag}
            fullAccess={fullAccess}
            canChat={canChat}
            busy={busy}
            onAsk={(code) => void askTutor(course.key, code)}
            onPractise={(code) => practise(course.key, code)}
            onStartDiag={() => void startDiagnostic(course.key)}
            onSkipDiag={() => setHiddenDiag((s) => new Set(s).add(course.key))}
          />
        );
      })}

      <section className="card">
        <h2>{t("student.recent")}</h2>
        {data.recent.length === 0 ? (
          <p className="muted">{t("student.noRecent")}</p>
        ) : (
          <ul className="recent-list">
            {data.recent.map((r) => (
              <li key={r.id}>
                <Link to={`/student/chat/${r.id}`}>
                  <b>{r.topic_name}</b>
                  <span className="small muted">
                    {r.course_name} · {formatDate(r.last_activity_at)}
                    {r.status === "ended" && ` · ${t("student.endedTag")}`}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
        <h3>{t("student.usage")}</h3>
        <p className="small">
          {t("student.usageToday", { used: data.usage.daily_used, limit: data.usage.daily_limit ?? "∞" })}
          <br />
          {t("student.usageMonth", { used: data.usage.monthly_used, limit: data.usage.monthly_limit ?? "∞" })}
        </p>
        {data.usage.near_monthly_limit && <p className="alert alert-warn small">{t("student.nearLimit")}</p>}
        <p className="small muted">{t("student.integrity")}</p>
      </section>
    </>
  );
}

interface CourseCardProps {
  course: Course;
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

function CourseCard({ course, overview, showDiag, fullAccess, canChat, busy, onAsk, onPractise, onStartDiag, onSkipDiag }: CourseCardProps) {
  const { t } = useTranslation();
  const [showAll, setShowAll] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [pickerTopic, setPickerTopic] = useState("");

  const title = (
    <h2 className="course-title">
      {course.name} {course.level && <span className="small muted">({course.level})</span>}
    </h2>
  );

  if (overview === undefined) {
    return (
      <section className="card course-card">
        {title}
        <p className="muted">…</p>
      </section>
    );
  }

  // No question bank for this course yet (or the overview failed): plain topic picker.
  if (!overview || overview.questions_available === 0) {
    return (
      <section className="card course-card">
        {title}
        {overview && <p className="small muted">{t("student.noQuestionsYet")}</p>}
        <label className="field">
          <span>{t("student.topic")}</span>
          <select value={pickerTopic} onChange={(e) => setPickerTopic(e.target.value)} disabled={!canChat}>
            <option value="">{t("student.chooseTopic")}</option>
            {course.topics.map((tp) => (
              <option key={tp.code} value={tp.code}>
                {tp.name}
              </option>
            ))}
          </select>
        </label>
        <div className="actions">
          <button
            type="button"
            className="btn btn-primary"
            disabled={!canChat || !pickerTopic || busy !== null}
            onClick={() => onAsk(pickerTopic)}
          >
            {busy === `chat:${course.key}:${pickerTopic}` ? t("common.working") : t("student.askTutor")}
          </button>
        </div>
      </section>
    );
  }

  const tested = overview.topics.filter((tp) => tp.mastery !== null).length;
  const inProgress = overview.diagnostic?.status === "in_progress";
  const estimate = estimateDiagnosticSize(overview.topics);

  const actions = (tp: TopicOverview) => (
    <div className="actions topic-actions">
      <button
        type="button"
        className="btn btn-primary btn-sm"
        disabled={!fullAccess || tp.questions_available === 0}
        onClick={() => onPractise(tp.topic_code)}
      >
        {t("student.practise")}
      </button>
      <button
        type="button"
        className="btn btn-secondary btn-sm"
        disabled={!canChat || busy !== null}
        onClick={() => onAsk(tp.topic_code)}
      >
        {busy === `chat:${course.key}:${tp.topic_code}` ? t("common.working") : t("student.askTutor")}
      </button>
    </div>
  );

  return (
    <section className="card course-card">
      <header className="course-head">
        {title}
        <div className="overall" aria-label={t("student.overall")}>
          <b>{overview.overall === null ? "–" : `${overview.overall}%`}</b>
          <span className="small muted">{t("student.overall")}</span>
        </div>
      </header>
      <p className="small muted">{t("student.testedOf", { tested, total: overview.topics.length })}</p>

      {showDiag && (
        <div className="diag-cta">
          <h3>{t("student.diagTitle")}</h3>
          <p>{t("student.diagBody", { count: estimate })}</p>
          <div className="actions">
            <button type="button" className="btn btn-primary" disabled={!fullAccess || busy !== null} onClick={onStartDiag}>
              {busy === `diag:${course.key}` ? t("common.working") : inProgress ? t("student.diagContinue") : t("student.diagStart")}
            </button>
            <button type="button" className="btn btn-ghost" onClick={onSkipDiag}>
              {t("student.diagSkip")}
            </button>
          </div>
        </div>
      )}

      {overview.next.length > 0 && (
        <>
          <h3>{t("student.workNext")}</h3>
          <ul className="next-list">
            {overview.next.map((tp) => (
              <li key={tp.topic_code}>
                <div className="next-head">
                  <b>{tp.topic_name}</b>
                  <span className="small muted">
                    {tp.mastery === null ? t("student.notTested") : `${tp.mastery}%`}
                    {tp.due && <span className="status status-due">{t("student.due")}</span>}
                  </span>
                </div>
                {actions(tp)}
              </li>
            ))}
          </ul>
        </>
      )}

      <button type="button" className="link-btn" aria-expanded={showAll} onClick={() => setShowAll((s) => !s)}>
        {showAll ? t("student.hideTopics") : t("student.showTopics", { count: overview.topics.length })}
      </button>
      {showAll && (
        <ul className="topic-list">
          {overview.topics.map((tp) => (
            <li key={tp.topic_code} className={selected === tp.topic_code ? "open" : ""}>
              <button
                type="button"
                className="topic-row"
                aria-expanded={selected === tp.topic_code}
                onClick={() => setSelected((s) => (s === tp.topic_code ? null : tp.topic_code))}
              >
                <span className="topic-name">{tp.topic_name}</span>
                <MasteryBar value={tp.mastery} due={tp.due} label={tp.topic_name} />
              </button>
              {selected === tp.topic_code && actions(tp)}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
