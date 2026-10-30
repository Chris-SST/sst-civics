import { useState, type FormEvent, type ReactNode } from "react";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import { post } from "../api";
import type { AttemptOut, QuestionPublic } from "../practice";
import ErrorText from "./ErrorText";
import RichText from "./RichText";

/** One question in German with its four options and, after submitting, the result panel with
 * the explanation. Mount it with `key={question.id}` so the state resets for each new question.
 * The study modes (own language, side by side, German with help) arrive in task 1.7. */

interface Props {
  question: QuestionPublic;
  submit: (answer: string) => Promise<AttemptOut>;
  onResult?: (result: AttemptOut) => void;
  /** The result heading; when omitted a varied message is picked for the outcome. */
  headline?: (result: AttemptOut) => string;
  /** Rendered under the result panel, typically a "Next" button. */
  children?: ReactNode;
}

function pick(list: unknown, seed: number): string | null {
  if (!Array.isArray(list) || list.length === 0) return null;
  return String(list[Math.abs(seed) % list.length]);
}

/** A short, varied heading for a result. Streaks and recoveries get their own line so a run of
 * answers reads like a coach, not a form. */
export function feedbackHeadline(
  t: TFunction,
  result: AttemptOut,
  context: { streak?: number; previousWrong?: boolean } = {},
): string {
  const seed = Math.floor(Math.random() * 1000);
  const streak = context.streak ?? 0;
  if (result.correct) {
    if (streak >= 3) return t("question.streak", { count: streak });
    if (context.previousWrong) return t("question.backOnTrack");
    return pick(t("question.praise", { returnObjects: true }), seed) ?? t("question.correct");
  }
  if (context.previousWrong) return t("question.tricky");
  return pick(t("question.encourage", { returnObjects: true }), seed) ?? t("question.incorrect");
}

export function MasteryBar({ value, due, label }: { value: number | null; due?: boolean; label?: string }) {
  const { t } = useTranslation();
  const pct = value === null ? 0 : Math.max(0, Math.min(100, value));
  return (
    <div className="mastery">
      <div
        className={`mastery-bar${value === null ? " mastery-untested" : ""}`}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value ?? undefined}
        aria-label={label ?? t("practice.mastery")}
      >
        <span style={{ width: `${pct}%` }} />
      </div>
      <span className="mastery-value small">
        {value === null ? t("learner.notTested") : `${value}%`}
        {due && <span className="status status-due">{t("learner.due")}</span>}
      </span>
    </div>
  );
}

export function DifficultyDots({ level }: { level: number }) {
  const { t } = useTranslation();
  return (
    <span className="dots-difficulty" aria-label={t("question.difficulty", { level })} title={t("question.difficulty", { level })}>
      {[1, 2, 3].map((i) => (
        <i key={i} className={i <= level ? "on" : ""} />
      ))}
    </span>
  );
}

export default function QuestionCard({ question: q, submit, onResult, headline, children }: Props) {
  const { t } = useTranslation();
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<AttemptOut | null>(null);
  const [heading, setHeading] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [showSolution, setShowSolution] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [reportText, setReportText] = useState("");
  const [reported, setReported] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!answer.trim() || busy || result) return;
    setBusy(true);
    setError(null);
    try {
      const r = await submit(answer.trim());
      setHeading(headline ? headline(r) : feedbackHeadline(t, r));
      setResult(r);
      onResult?.(r);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function sendReport(e: FormEvent) {
    e.preventDefault();
    try {
      await post(`/api/practice/questions/${q.id}/report`, { comment: reportText.trim() || null });
      setReported(true);
      setReporting(false);
    } catch (err) {
      setError(err);
    }
  }

  return (
    <article className="card question-card">
      <header className="question-meta">
        <DifficultyDots level={q.difficulty} />
        {!q.reviewed && <span className="small muted">{t("question.unreviewed")}</span>}
      </header>

      <RichText className="question-text" text={q.question_text} />

      <form onSubmit={(e) => void onSubmit(e)} className="question-form">
        <div className="mcq" role="radiogroup" aria-label={t("question.yourAnswer")}>
          {(q.options ?? []).map((o) => (
            <button
              type="button"
              key={o.key}
              role="radio"
              aria-checked={answer === o.key}
              className={`mcq-option${answer === o.key ? " selected" : ""}${
                result ? (o.key.trim().toLowerCase() === result.answer.trim().toLowerCase() ? " is-correct" : answer === o.key ? " is-wrong" : "") : ""
              }`}
              onClick={() => !result && setAnswer(o.key)}
              disabled={!!result}
            >
              <b>{o.key.toUpperCase()}</b>
              <RichText text={o.text} />
            </button>
          ))}
        </div>
        {!result && (
          <div className="actions">
            <button className="btn btn-primary" disabled={busy || !answer.trim()}>
              {busy ? t("common.working") : t("question.submit")}
            </button>
          </div>
        )}
      </form>
      {error ? <ErrorText error={error} /> : null}

      {result && (
        <section className={`result ${result.correct ? "result-ok" : "result-bad"}`} aria-live="polite">
          <h3>
            {heading || (result.correct ? t("question.correct") : t("question.incorrect"))}
          </h3>
          <div className="result-answer">
            <b className="small">{t("question.answerLabel")}</b>
            <RichText text={result.answer_text ? `${result.answer.toUpperCase()}. ${result.answer_text}` : result.answer.toUpperCase()} />
          </div>
          {result.explanation && (
            <>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => setShowSolution((s) => !s)} aria-expanded={showSolution}>
                {showSolution ? t("question.hideExplanation") : t("question.showExplanation")}
              </button>
              {showSolution && <RichText className="solution" text={result.explanation} />}
            </>
          )}
          <div className="question-footer">
            {children}
            {reported ? (
              <span className="small muted">{t("question.reported")}</span>
            ) : (
              <button type="button" className="link-btn small" onClick={() => setReporting((r) => !r)}>
                {t("question.report")}
              </button>
            )}
          </div>
          {reporting && !reported && (
            <form className="form report-form" onSubmit={(e) => void sendReport(e)}>
              <label className="field">
                <span>{t("question.reportHint")}</span>
                <input value={reportText} onChange={(e) => setReportText(e.target.value.slice(0, 1000))} />
              </label>
              <div className="actions">
                <button className="btn btn-secondary btn-sm">{t("question.reportSend")}</button>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setReporting(false)}>
                  {t("common.cancel")}
                </button>
              </div>
            </form>
          )}
        </section>
      )}
    </article>
  );
}
