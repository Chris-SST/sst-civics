import { useState, type FormEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { post } from "../api";
import type { AttemptOut, QuestionPublic } from "../practice";
import ErrorText from "./ErrorText";
import RichText from "./RichText";

/** One question with its answer input and, after submitting, the result panel. Mount it with
 * `key={question.id}` so the state resets for each new question. */

interface Props {
  question: QuestionPublic;
  submit: (answer: string) => Promise<AttemptOut>;
  onResult?: (result: AttemptOut) => void;
  /** Rendered under the result panel, typically a "Next" button. */
  children?: ReactNode;
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
        {value === null ? t("student.notTested") : `${value}%`}
        {due && <span className="status status-due">{t("student.due")}</span>}
      </span>
    </div>
  );
}

export function DifficultyDots({ level }: { level: number }) {
  const { t } = useTranslation();
  return (
    <span className="dots-difficulty" aria-label={t("question.difficulty", { level })} title={t("question.difficulty", { level })}>
      {[1, 2, 3, 4, 5].map((i) => (
        <i key={i} className={i <= level ? "on" : ""} />
      ))}
    </span>
  );
}

export default function QuestionCard({ question: q, submit, onResult, children }: Props) {
  const { t } = useTranslation();
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<AttemptOut | null>(null);
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

  const structured = q.qtype === "structured";
  const percent = result ? Math.round(result.score * 100) : 0;
  const markingUnavailable = !!result && structured && !result.ai_marked;

  return (
    <article className="card question-card">
      <header className="question-meta">
        <span className={`tag ${q.calculator_allowed ? "tag-calc" : "tag-nocalc"}`}>
          {q.calculator_allowed ? t("question.calculator") : t("question.noCalculator")}
        </span>
        <DifficultyDots level={q.difficulty} />
        <span className="small muted">{t("question.marks", { count: q.marks })}</span>
        {!q.reviewed && <span className="small muted">{t("question.unreviewed")}</span>}
      </header>

      <RichText className="question-text" text={q.question_text} />

      <form onSubmit={(e) => void onSubmit(e)} className="question-form">
        {q.qtype === "mcq" && (
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
                <b>{o.key}</b>
                <RichText text={o.text} />
              </button>
            ))}
          </div>
        )}
        {q.qtype === "numeric" && (
          <label className="field">
            <span>{t("question.yourAnswer")}</span>
            <div className="answer-row">
              <input
                type="text"
                inputMode="decimal"
                autoComplete="off"
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                disabled={!!result}
                placeholder="0.0"
              />
              {q.unit && <span className="unit">{q.unit}</span>}
            </div>
            <span className="hint">{t("question.numericHint")}</span>
          </label>
        )}
        {q.qtype === "short" && (
          <label className="field">
            <span>{t("question.yourAnswer")}</span>
            <input
              type="text"
              autoComplete="off"
              autoCapitalize="off"
              spellCheck={false}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              disabled={!!result}
            />
            <span className="hint">{t("question.shortHint")}</span>
          </label>
        )}
        {structured && (
          <label className="field">
            <span>{t("question.yourAnswer")}</span>
            <textarea
              rows={5}
              value={answer}
              onChange={(e) => setAnswer(e.target.value.slice(0, 4000))}
              disabled={!!result}
            />
            <span className="hint">{t("question.structuredNote")}</span>
          </label>
        )}
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
            {markingUnavailable
              ? t("question.markingUnavailable")
              : structured
                ? t("question.score", { percent })
                : result.correct
                  ? t("question.correct")
                  : t("question.incorrect")}
          </h3>
          {result.feedback && (
            <div className="result-feedback">
              <b className="small">{t("question.feedback")}</b>
              <RichText text={result.feedback} />
            </div>
          )}
          <div className="result-answer">
            <b className="small">{t("question.answerLabel")}</b>
            <RichText text={q.qtype === "numeric" && q.unit ? `${result.answer} ${q.unit}` : result.answer} />
          </div>
          {result.worked_solution && (
            <>
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => setShowSolution((s) => !s)} aria-expanded={showSolution}>
                {showSolution ? t("question.hideSolution") : t("question.showSolution")}
              </button>
              {showSolution && <RichText className="solution" text={result.worked_solution} />}
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
