import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";
import { get, post } from "../api";
import ErrorText from "../components/ErrorText";
import QuestionCard, { MasteryBar } from "../components/QuestionCard";
import type { AttemptOut, DiagnosticOut, TopicOverview } from "../practice";

/** The short check that finds a student's gaps: one question at a time, then a results screen. */
export default function StudentDiagnostic() {
  const { t } = useTranslation();
  const { id } = useParams();
  const navigate = useNavigate();
  const [run, setRun] = useState<DiagnosticOut | null>(null);
  const [answered, setAnswered] = useState<AttemptOut | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!id) return;
    get<DiagnosticOut>(`/api/practice/diagnostic/${id}`).then(setRun).catch(setError);
  }, [id]);

  if (!run) return error ? <ErrorText error={error} /> : <p className="muted">…</p>;

  async function askTutor(topicCode: string) {
    if (!run) return;
    setBusy(true);
    try {
      const conv = await post<{ id: string }>("/api/tutor/conversations", {
        course_key: run.course_key,
        topic_code: topicCode,
      });
      navigate(`/student/chat/${conv.id}`);
    } catch (e) {
      setError(e);
      setBusy(false);
    }
  }

  function practise(topicCode: string) {
    if (!run) return;
    navigate(`/student/practice?course_key=${encodeURIComponent(run.course_key)}&topic_code=${encodeURIComponent(topicCode)}`);
  }

  async function stop() {
    if (!run) return;
    try {
      await post(`/api/practice/diagnostic/${run.id}/skip`);
      navigate("/student");
    } catch (e) {
      setError(e);
    }
  }

  // --- Results --------------------------------------------------------------------------------
  if (run.status === "done" && run.summary) {
    const weakest: TopicOverview | undefined = run.next?.[0];
    return (
      <>
        <h1>{t("diagnostic.doneTitle")}</h1>
        <section className="card">
          <p>{t("diagnostic.doneBody")}</p>
          <ul className="topic-list">
            {run.summary.map((tp) => (
              <li key={tp.topic_code}>
                <div className="topic-row">
                  <span className="topic-name">{tp.topic_name}</span>
                  <MasteryBar value={tp.mastery} due={tp.due} label={tp.topic_name} />
                </div>
              </li>
            ))}
          </ul>
          {weakest && (
            <>
              <h3>{t("diagnostic.weakest", { topic: weakest.topic_name })}</h3>
              <div className="actions">
                <button type="button" className="btn btn-primary" onClick={() => practise(weakest.topic_code)}>
                  {t("student.practise")}
                </button>
                <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => void askTutor(weakest.topic_code)}>
                  {busy ? t("common.working") : t("student.askTutor")}
                </button>
              </div>
            </>
          )}
          {error ? <ErrorText error={error} /> : null}
          <p style={{ marginTop: 16 }}>
            <Link to="/student" className="btn btn-ghost">
              {t("diagnostic.backHome")}
            </Link>
          </p>
        </section>
      </>
    );
  }

  if (run.status !== "in_progress" || !run.question) {
    return (
      <>
        <h1>{t("diagnostic.title")}</h1>
        <section className="card">
          <p className="alert alert-info">{run.total === 0 ? t("diagnostic.empty") : t("diagnostic.alreadyDone")}</p>
          <Link to="/student" className="btn btn-ghost">
            {t("diagnostic.backHome")}
          </Link>
        </section>
      </>
    );
  }

  // --- A question -----------------------------------------------------------------------------
  const q = run.question;
  const pct = Math.round((run.position / Math.max(run.total, 1)) * 100);
  return (
    <>
      <header className="page-head">
        <div>
          <Link to="/student" className="small">
            ← {t("chat.back")}
          </Link>
          <h1>{t("diagnostic.title")}</h1>
        </div>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => void stop()}>
          {t("diagnostic.stop")}
        </button>
      </header>
      <p className="small muted progress-label">{t("diagnostic.progress", { n: run.position + 1, total: run.total })}</p>
      <div className="progress" aria-hidden="true">
        <span style={{ width: `${pct}%` }} />
      </div>
      {error ? <ErrorText error={error} /> : null}
      <QuestionCard
        key={q.id}
        question={q}
        submit={(answer) =>
          post<AttemptOut>("/api/practice/attempts", {
            question_id: q.id,
            answer,
            mode: "diagnostic",
            diagnostic_id: run.id,
          })
        }
        onResult={setAnswered}
      >
        {answered?.diagnostic && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              setRun(answered.diagnostic ?? null);
              setAnswered(null);
              window.scrollTo({ top: 0 });
            }}
          >
            {answered.diagnostic.status === "done" ? t("diagnostic.seeResults") : t("diagnostic.next")}
          </button>
        )}
      </QuestionCard>
    </>
  );
}
