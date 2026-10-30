import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError, get, post } from "../api";
import ErrorText from "../components/ErrorText";
import QuestionCard, { MasteryBar, feedbackHeadline } from "../components/QuestionCard";
import type { AnswerOut, PractiseRound, StudyMode, StudyQuestion } from "../study";

/** Practise in short rounds chosen by spaced repetition and weighted towards weak topics (all
 * topics, or one with ?topic=). Each correct answer moves the question one study mode on; the
 * mode stepper on the card steps back (or on) at any time. Feedback shows the explanation in the
 * learner's language, the topic's mastery and the readiness estimate. */
export default function Practise() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const topicCode = params.get("topic") ?? "";
  const [round, setRound] = useState<PractiseRound | null>(null);
  const [questions, setQuestions] = useState<StudyQuestion[]>([]);
  const [roundNo, setRoundNo] = useState(0);
  const [index, setIndex] = useState(0);
  const [results, setResults] = useState<AnswerOut[]>([]);
  const [current, setCurrent] = useState<AnswerOut | null>(null);
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
    setNoQuestions(false);
    try {
      const query = topicCode ? `?topic_code=${encodeURIComponent(topicCode)}` : "";
      const r = await get<PractiseRound>(`/api/study/practise${query}`);
      setRound(r);
      setQuestions(r.questions);
    } catch (e) {
      if (e instanceof ApiError && e.code === "no_questions") setNoQuestions(true);
      else setError(e);
    }
  }, [topicCode]);

  useEffect(() => {
    void load();
  }, [load]);

  async function changeMode(q: StudyQuestion, mode: StudyMode) {
    setBusy(true);
    setError(null);
    try {
      const updated = await post<StudyQuestion>(`/api/study/question/${q.id}/mode`, { mode });
      setQuestions((list) => list.map((x) => (x.id === q.id ? { ...updated, topic_mastery: x.topic_mastery } : x)));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  const total = questions.length;
  const question = questions[index] ?? null;
  const last = index >= total - 1;
  const lastResult = current ?? results[results.length - 1] ?? null;
  const delta = current && current.mastery.previous !== undefined ? current.mastery.mastery - current.mastery.previous : null;
  const readiness = lastResult?.readiness ?? round?.readiness ?? null;

  function headline(r: AnswerOut): string {
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

  const title = round?.topic_name ?? t("practice.allTopics");
  const header = (
    <header className="page-head">
      <div>
        <Link to="/learner" className="small">
          {"←"} {t("practice.back")}
        </Link>
        <h1>{title}</h1>
        <p className="small muted">{t("practice.title")}</p>
      </div>
    </header>
  );

  const readinessLine = readiness && (
    <div className="practice-mastery">
      <span className="small">
        {t("practice.readiness")}
        <span className="muted"> ({t(readiness.label_key)})</span>
      </span>
      <MasteryBar value={readiness.value} label={t("practice.readiness")} />
    </div>
  );

  // --- Round summary --------------------------------------------------------------------------
  if (round && summary) {
    const right = results.filter((r) => r.correct).length;
    const ratio = total ? right / total : 0;
    const tone = ratio === 1 ? "Perfect" : ratio >= 0.8 ? "Great" : ratio >= 0.5 ? "Good" : "Keep";
    const moved = results.filter((r) => r.progress.moved_forward).length;
    const known = results.filter((r) => r.progress.newly_known).length;
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
          {(moved > 0 || known > 0) && <p className="small">{t("practice.roundModes", { moved, known })}</p>}
          {readinessLine}
          <div className="actions">
            <button type="button" className="btn btn-primary" onClick={nextRound}>
              {t("practice.anotherRound")}
            </button>
            <Link to="/learner" className="btn btn-ghost">
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
            <Link to="/learner" className="btn btn-ghost">
              {t("practice.back")}
            </Link>
          </div>
        </section>
      )}

      {!noQuestions && !round && !error && <p className="muted">{"…"}</p>}

      {round && question && (
        <>
          {round.free_tier && index === 0 && !current && <p className="small muted">{t("practice.freeTier")}</p>}
          <p className="small muted progress-label">{t("practice.progress", { n: index + 1, total })}</p>
          <div className="round-progress" role="progressbar" aria-label={t("practice.progress", { n: index + 1, total })} aria-valuemin={0} aria-valuemax={total} aria-valuenow={index}>
            {questions.map((q, i) => {
              const r = results[i];
              const cls = r ? (r.correct ? "ok" : "bad") : i === index ? (current ? (current.correct ? "ok" : "bad") : "current") : "";
              return <span key={q.id} className={cls} />;
            })}
          </div>
          <div className="practice-mastery">
            <span className="small">
              {t("practice.masteryOf", { topic: question.topic_name })}
              {delta !== null && delta !== 0 && (
                <b className={`mastery-delta ${delta > 0 ? "up" : "down"}`}>{delta > 0 ? `+${delta}` : delta}</b>
              )}
            </span>
            <MasteryBar value={current ? current.mastery.mastery : (question.topic_mastery ?? null)} label={t("practice.masteryTopic")} />
          </div>
          {round.unseen === 0 && index === 0 && !current && <p className="alert alert-info">{t("practice.allSeen")}</p>}

          <QuestionCard
            key={`${roundNo}-${question.id}-${question.mode}`}
            question={question}
            headline={headline}
            onModeChange={(m) => void changeMode(question, m)}
            modeBusy={busy}
            explain
            submit={(answer) =>
              post<AnswerOut>("/api/study/answer", {
                question_id: question.id,
                answer,
                mode: question.mode,
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
          {current && readinessLine}
        </>
      )}
    </>
  );
}
