import { useState, type FormEvent, type ReactNode } from "react";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import { post } from "../api";
import type { AnswerOut, StudyMode, StudyQuestion } from "../study";
import ErrorText from "./ErrorText";
import ExplainPanel from "./ExplainPanel";
import ModeStepper from "./ModeStepper";
import RichText from "./RichText";
import { ExplanationText, OptionText, QuestionText } from "./StudyText";

/** One question in its study mode with its four options. Three uses:
 * - Practise (and the check after a chat): pass `submit`; after the answer the result panel shows
 *   the correct answer and the explanation in the learner's language.
 * - Learn and the mock-test review: pass `reveal`; the correct answer (and `given`, if any) is
 *   marked and the explanation shown in the question's mode, with no scoring.
 * - Mock test: pass `onSelect` and `selected`; German only, no result, no help, no explanation,
 *   and never Explain this.
 * `explain` adds the "Explain this" button and chat panel (Learn and Practise only; in Practise the
 * button shows once the question is answered, because the chat knows the answer). It is never
 * passed in the mock test or its review.
 * Mount it with `key={question.id}` so the state resets for each new question. */

interface Props {
  question: StudyQuestion;
  submit?: (answer: string) => Promise<AnswerOut>;
  onResult?: (result: AnswerOut) => void;
  /** The result heading; when omitted a varied message is picked for the outcome. */
  headline?: (result: AnswerOut) => string;
  /** Shows the mode stepper; called with the mode the learner picks. */
  onModeChange?: (mode: StudyMode) => void;
  modeBusy?: boolean;
  reveal?: boolean;
  /** Offer "Explain this" (Learn and Practise). Ignored in the mock test. */
  explain?: boolean;
  selected?: string | null;
  onSelect?: (key: string) => void;
  /** Rendered under the result panel (or the revealed answer), typically a "Next" button. */
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
  result: AnswerOut,
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

function StateIcon({ ok }: { ok: boolean }) {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      {ok ? <path d="M4 10.5l4 4 8-9" /> : <path d="M10 4v7M10 15.5v.5" />}
    </svg>
  );
}

export function MasteryBar({ value, label }: { value: number | null; label?: string }) {
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
      <span className="mastery-value small">{value === null ? t("learner.notStarted") : `${value}%`}</span>
    </div>
  );
}

export function DifficultyDots({ level }: { level: number }) {
  const { t } = useTranslation();
  return (
    <span className="dots-difficulty" role="img" aria-label={t("question.difficulty", { level })} title={t("question.difficulty", { level })}>
      {[1, 2, 3].map((i) => (
        <i key={i} className={i <= level ? "on" : ""} />
      ))}
    </span>
  );
}

/** What the answer changed: understood, known, the next mode. */
function ProgressNote({ result }: { result: AnswerOut }) {
  const { t } = useTranslation();
  const p = result.progress;
  const notes: string[] = [];
  if (p.newly_known) notes.push(t("study.nowKnown"));
  else if (p.newly_understood) notes.push(t("study.nowUnderstood"));
  if (p.moved_forward) notes.push(t("study.nextMode", { mode: t(`study.mode.${p.mode}`) }));
  if (!notes.length) return null;
  return (
    <p className="progress-note small">
      {notes.map((n) => (
        <span key={n} className="chip">
          {n}
        </span>
      ))}
    </p>
  );
}

function optionLabel(q: StudyQuestion, key: string): string {
  const de = q.german.options.find((o) => o.key === key)?.text ?? "";
  return `${key.toUpperCase()}. ${de}`;
}

export default function QuestionCard({
  question: q,
  submit,
  onResult,
  headline,
  onModeChange,
  modeBusy,
  reveal,
  explain,
  selected,
  onSelect,
  children,
}: Props) {
  const { t } = useTranslation();
  const testMode = onSelect !== undefined;
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<AnswerOut | null>(null);
  const [heading, setHeading] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [showGerman, setShowGerman] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [reportText, setReportText] = useState("");
  const [reported, setReported] = useState(false);
  const [explaining, setExplaining] = useState(false);

  const chosen = testMode ? (selected ?? "") : reveal ? (q.given ?? "") : answer;
  const correctKey = result?.answer ?? (reveal ? q.answer : undefined);
  const locked = !!result || !!reveal;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!submit || !answer.trim() || busy || result) return;
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
      await post(`/api/questions/${q.id}/report`, { comment: reportText.trim() || null });
      setReported(true);
      setReporting(false);
    } catch (err) {
      setError(err);
    }
  }

  function choose(key: string) {
    if (testMode) onSelect?.(key);
    else if (!locked) setAnswer(key);
  }

  const canExplain = !!explain && !testMode && (!!reveal || !!result);
  const explainButton = canExplain ? (
    <button type="button" className="btn btn-secondary btn-sm" aria-expanded={explaining} onClick={() => setExplaining((e) => !e)}>
      {t("explain.button")}
    </button>
  ) : null;

  const report = reported ? (
    <span className="small muted">{t("question.reported")}</span>
  ) : (
    <button type="button" className="link-btn small" onClick={() => setReporting((r) => !r)}>
      {t("question.report")}
    </button>
  );

  return (
    <article className={`card question-card question-mode-${q.mode}`}>
      {!testMode && (
        <header className="question-meta">
          {q.difficulty > 0 && <DifficultyDots level={q.difficulty} />}
          <span className="tag">{t(`study.mode.${q.mode}`)}</span>
          {!q.reviewed && <span className="small muted">{t("question.unreviewed")}</span>}
        </header>
      )}
      {onModeChange && !locked && (
        <ModeStepper mode={q.mode} reached={q.progress?.mode_reached} fallback={q.fallback} disabled={modeBusy || busy} onChange={onModeChange} />
      )}

      <QuestionText q={q} />

      <form onSubmit={(e) => void onSubmit(e)} className="question-form">
        <div className="mcq" role="radiogroup" aria-label={t("question.yourAnswer")}>
          {q.german.options.map((o) => {
            const isCorrect = correctKey !== undefined && o.key === correctKey;
            const isWrong = correctKey !== undefined && chosen === o.key && !isCorrect;
            return (
              <button
                type="button"
                key={o.key}
                role="radio"
                aria-checked={chosen === o.key}
                className={`mcq-option${chosen === o.key ? " selected" : ""}${isCorrect ? " is-correct" : isWrong ? " is-wrong" : ""}`}
                onClick={() => choose(o.key)}
                disabled={locked}
              >
                <b>{o.key.toUpperCase()}</b>
                <OptionText q={q} optionKey={o.key} />
                {isCorrect ? (
                  <span className="opt-state">
                    <StateIcon ok />
                    {t("question.correct")}
                  </span>
                ) : isWrong ? (
                  <span className="opt-state">
                    <StateIcon ok={false} />
                    {reveal ? t("question.yourChoice") : t("question.incorrect")}
                  </span>
                ) : null}
              </button>
            );
          })}
        </div>
        {submit && !result && (
          <div className="actions">
            <button className="btn btn-primary" disabled={busy || !answer.trim()}>
              {busy ? t("common.working") : t("question.submit")}
            </button>
          </div>
        )}
      </form>
      {error ? <ErrorText error={error} /> : null}

      {reveal && (
        <section className="result result-reveal" aria-label={t("question.answerLabel")}>
          {q.given === null && <p className="small">{t("question.notAnswered")}</p>}
          <div className="result-answer">
            <b className="small">{t("question.answerLabel")}</b>
            <p>{q.answer ? optionLabel(q, q.answer) : null}</p>
          </div>
          <ExplanationText q={q} />
          <div className="question-footer">
            {children}
            {explainButton}
            {report}
          </div>
        </section>
      )}

      {result && (
        <section className={`result ${result.correct ? "result-ok" : "result-bad"}`} aria-live="polite">
          <h3>
            <StateIcon ok={result.correct} />
            {heading || (result.correct ? t("question.correct") : t("question.incorrect"))}
          </h3>
          <div className="result-answer">
            <b className="small">{t("question.answerLabel")}</b>
            <p lang="de">{result.answer_text ? `${result.answer.toUpperCase()}. ${result.answer_text}` : result.answer.toUpperCase()}</p>
            {result.answer_text_translated && <p className="small" lang={result.explanation.lang}>{result.answer_text_translated}</p>}
          </div>
          <ProgressNote result={result} />
          <div className="solution" lang={result.explanation.lang}>
            <RichText text={result.explanation.text} />
          </div>
          {result.explanation.lang !== "de" && (
            <>
              <button type="button" className="link-btn small" onClick={() => setShowGerman((s) => !s)} aria-expanded={showGerman}>
                {showGerman ? t("question.hideGerman") : t("question.showGerman")}
              </button>
              {showGerman && (
                <div className="solution" lang="de">
                  <RichText text={result.explanation_de} />
                </div>
              )}
            </>
          )}
          <div className="question-footer">
            {children}
            {explainButton}
            {report}
          </div>
        </section>
      )}

      {canExplain && explaining && <ExplainPanel questionId={q.id} lang={q.lang} onClose={() => setExplaining(false)} />}

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
    </article>
  );
}
