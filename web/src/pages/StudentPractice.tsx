import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, get, post } from "../api";
import ErrorText from "../components/ErrorText";
import QuestionCard, { MasteryBar, feedbackHeadline } from "../components/QuestionCard";
import type { AttemptOut, PracticeRound } from "../practice";

/** Practice on one topic in short rounds: the student sees how many questions are to go, gets a
 * varied word of feedback after each answer, and a summary with the mastery change at the end. */
export default function StudentPractice() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const courseKey = params.get("course_key") ?? "";
  const topicCode = params.get("topic_code") ?? "";
  const [round, setRound] = useState<PracticeRound | null>(null);
  const [roundNo, setRoundNo] = useState(0);
  const [index, setIndex] = useState(0);
  const [results, setResults] = useState<AttemptOut[]>([]);
  const [current, setCurrent] = useState<AttemptOut | null>(null);
  const [summary, setSummary] = useState(false);
  const [noQuestions, setNoQuestions] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setRound(null);
    setIndex(0);
    setResults([]);
    setCurrent(null);
    setSummary(false);
    setError(null);
    try {
      const r = await get<PracticeRound>(
        `/api/practice/round?course_key=${encodeURIComponent(courseKey)}&topic_code=${encodeURIComponent(topicCode)}`,
      );
      setRound(r);
    } catch (e) {
      if (e instanceof ApiError && e.code === "no_questions") setNoQuestions(true);
      else setError(e);
    }
  }, [courseKey, topicCode]);

  useEffect(() => {
    if (!courseKey || !topicCode) return;
    void load();
  }, [courseKey, topicCode, load]);

  async function askTutor() {
    setBusy(true);
    try {
      const conv = await post<{ id: string }>("/api/tutor/conversations", { course_key: courseKey, topic_code: topicCode });
      navigate(`/student/chat/${conv.id}`);
    } catch (e) {
      setError(e);
      setBusy(false);
    }
  }

  if (!courseKey || !topicCode) {
    return (
      <section className="card">
        <ErrorText error={new ApiError(400, "invalid_topic")} />
        <Link to="/student" className="btn btn-ghost">
          {t("practice.back")}
        </Link>
      </section>
    );
  }

  const total = round?.questions.length ?? 0;
  const question = round?.questions[index] ?? null;
  const last = index >= total - 1;
  const mastery = current?.mastery.mastery ?? results[results.length - 1]?.mastery.mastery ?? round?.mastery ?? null;
  const delta = current && current.mastery.previous !== undefined ? current.mastery.mastery - current.mastery.previous : null;

  function headline(r: AttemptOut): string {
    let streak = 0;
    for (let i = results.length - 1; i >= 0 && results[i].correct; i -= 1) streak += 1;
    const previousWrong = results.length > 0 && !results[results.length - 1].correct;
    return feedbackHeadline(t, r, { streak: r.correct ? streak + 1 : 0, previousWrong });
  }

  function advance() {
    if (!current) return;
    setResults([...results, current]);
    setCurrent(null);
    if (last) setSummary(true);
    else setIndex((i) => i + 1);
    window.scrollTo({ top: 0 });
  }

  function nextRound() {
    setRoundNo((n) => n + 1);
    void load();
    window.scrollTo({ top: 0 });
  }

  const header = (
    <header className="page-head">
      <div>
        <Link to="/student" className="small">
          {"←"} {t("chat.back")}
        </Link>
        <h1>{round?.topic_name || t("practice.title")}</h1>
        {round && <p className="small muted">{t("practice.title")}</p>}
      </div>
      <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => void askTutor()}>
        {t("student.askTutor")}
      </button>
    </header>
  );

  // --- Round summary --------------------------------------------------------------------------
  if (round && summary) {
    const right = results.filter((r) => r.correct).length;
    const ratio = total ? right / total : 0;
    const tone = ratio === 1 ? "Perfect" : ratio >= 0.8 ? "Great" : ratio >= 0.5 ? "Good" : "Keep";
    const from = round.mastery;
    const to = results[results.length - 1]?.mastery.mastery ?? from;
    return (
      <>
        {header}
        <section className={`card round-summary round-${tone.toLowerCase()}`} aria-live="polite">
          <h2>{t(`practice.round${tone}`)}</h2>
          <p className="round-score">{t("practice.roundScore", { correct: right, total })}</p>
          <div className="round-dots" aria-hidden="true">
            {results.map((r, i) => (
              <i key={i} className={r.correct ? "ok" : "bad"} />
            ))}
          </div>
          <p>{t(`practice.roundBody${tone}`)}</p>
          <div className="practice-mastery">
            <span className="small">{t("practice.masteryChange", { from, to })}</span>
            <MasteryBar value={to} label={t("practice.masteryTopic")} />
          </div>
          <div className="actions">
            <button type="button" className="btn btn-primary" onClick={nextRound}>
              {t("practice.anotherRound")}
            </button>
            <button type="button" className="btn btn-secondary" disabled={busy} onClick={() => void askTutor()}>
              {busy ? t("common.working") : t("student.askTutor")}
            </button>
            <Link to="/student" className="btn btn-ghost">
              {t("practice.back")}
            </Link>
          </div>
        </section>
      </>
    );
  }

  // --- A question -----------------------------------------------------------------------------
  return (
    <>
      {header}
      {error ? <ErrorText error={error} /> : null}

      {noQuestions && (
        <section className="card">
          <p className="alert alert-info">{t("practice.noQuestions")}</p>
          <div className="actions">
            <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void askTutor()}>
              {busy ? t("common.working") : t("practice.askInstead")}
            </button>
            <Link to="/student" className="btn btn-ghost">
              {t("practice.back")}
            </Link>
          </div>
        </section>
      )}

      {!noQuestions && !round && !error && <p className="muted">{"…"}</p>}

      {round && question && (
        <>
          <p className="small muted progress-label">{t("practice.progress", { n: index + 1, total })}</p>
          <div className="round-progress" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={index}>
            {round.questions.map((q, i) => {
              const r = results[i];
              const cls = r ? (r.correct ? "ok" : "bad") : i === index ? (current ? (current.correct ? "ok" : "bad") : "current") : "";
              return <span key={q.id} className={cls} />;
            })}
          </div>
          <div className="practice-mastery">
            <span className="small">
              {t("practice.masteryTopic")}
              {delta !== null && delta !== 0 && (
                <b className={`mastery-delta ${delta > 0 ? "up" : "down"}`}>{delta > 0 ? `+${delta}` : delta}</b>
              )}
            </span>
            <MasteryBar value={mastery} label={t("practice.masteryTopic")} />
          </div>
          {round.unseen === 0 && index === 0 && !current && <p className="alert alert-info">{t("practice.allSeen")}</p>}

          <QuestionCard
            key={`${roundNo}-${question.id}`}
            question={question}
            headline={headline}
            submit={(answer) =>
              post<AttemptOut>("/api/practice/attempts", {
                question_id: question.id,
                answer,
                mode: "practice",
                course_key: courseKey,
              })
            }
            onResult={setCurrent}
          >
            {current && (
              <button type="button" className="btn btn-primary" onClick={advance}>
                {last ? t("practice.seeResults") : t("practice.nextQuestion")}
              </button>
            )}
          </QuestionCard>
        </>
      )}
    </>
  );
}
