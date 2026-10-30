import { Fragment, useState } from "react";
import { useTranslation } from "react-i18next";
import type { StudyQuestion, Term } from "../study";
import RichText from "./RichText";

/** Renders a question's text, options and explanation as its study mode says
 * (app/study/modes.py): own language first with the German small underneath, both side by side,
 * German with the key terms explained, or German only. */

function escapeRe(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Splits `text` at whole-word occurrences of the terms. */
function splitTerms(text: string, terms: Term[]): Array<string | Term> {
  const usable = terms.filter((t) => t.term.trim());
  if (!usable.length) return [text];
  const sorted = [...usable].sort((a, b) => b.term.length - a.term.length);
  const re = new RegExp(`(?<![\\p{L}\\p{N}])(${sorted.map((t) => escapeRe(t.term)).join("|")})(?![\\p{L}\\p{N}])`, "giu");
  const out: Array<string | Term> = [];
  let last = 0;
  for (const m of text.matchAll(re)) {
    const at = m.index ?? 0;
    if (at > last) out.push(text.slice(last, at));
    const term = sorted.find((t) => t.term.toLowerCase() === m[0].toLowerCase());
    out.push(term ? { ...term, term: m[0] } : m[0]);
    last = at + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/** German text with key terms underlined; in the question a tap on a term shows its
 * translation and note. Options are buttons themselves, so there the terms are only underlined
 * and the list under the question explains them. */
function HelpText({ text, terms, interactive }: { text: string; terms: Term[]; interactive: boolean }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState<number | null>(null);
  return (
    <span lang="de">
      {splitTerms(text, terms).map((p, i) => {
        if (typeof p === "string") return <Fragment key={i}>{p}</Fragment>;
        if (!interactive) {
          return (
            <span key={i} className="term">
              {p.term}
            </span>
          );
        }
        return (
          <span key={i} className="term-wrap">
            <button
              type="button"
              className="term"
              aria-expanded={open === i}
              aria-label={t("study.termLabel", { term: p.term })}
              onClick={() => setOpen((o) => (o === i ? null : i))}
            >
              {p.term}
            </button>
            {open === i && (
              <span className="term-pop" role="note">
                <b>{p.translation}</b>
                {p.note ? <span className="small"> {p.note}</span> : null}
              </span>
            )}
          </span>
        );
      })}
    </span>
  );
}

export function TermList({ terms }: { terms: Term[] }) {
  const { t } = useTranslation();
  if (!terms.length) return null;
  return (
    <details className="term-list">
      <summary className="small">{t("study.keyTerms", { count: terms.length })}</summary>
      <dl>
        {terms.map((term) => (
          <Fragment key={term.term}>
            <dt lang="de">{term.term}</dt>
            <dd>
              {term.translation}
              {term.note ? <span className="small muted"> {term.note}</span> : null}
            </dd>
          </Fragment>
        ))}
      </dl>
    </details>
  );
}

/** The question text in its mode. */
export function QuestionText({ q }: { q: StudyQuestion }) {
  const tr = q.translation;
  if (q.mode === "own" && tr) {
    return (
      <div className="study-own">
        <div lang={tr.lang}>
          <RichText className="question-text" text={tr.question} />
        </div>
        <div lang="de" className="study-de-small">
          <RichText text={q.german.question} />
        </div>
      </div>
    );
  }
  if (q.mode === "side" && tr) {
    return (
      <div className="study-side">
        <div lang="de">
          <RichText className="question-text" text={q.german.question} />
        </div>
        <div lang={tr.lang}>
          <RichText className="question-text" text={tr.question} />
        </div>
      </div>
    );
  }
  if (q.mode === "help") {
    return (
      <>
        <p className="question-text">
          <HelpText text={q.german.question} terms={q.terms} interactive />
        </p>
        <TermList terms={q.terms} />
      </>
    );
  }
  return (
    <div lang="de">
      <RichText className="question-text" text={q.german.question} />
    </div>
  );
}

/** One option's text in the question's mode. */
export function OptionText({ q, optionKey }: { q: StudyQuestion; optionKey: string }) {
  const de = q.german.options.find((o) => o.key === optionKey)?.text ?? "";
  const tr = q.translation?.options.find((o) => o.key === optionKey)?.text;
  if (q.mode === "own" && tr) {
    return (
      <span className="opt-text">
        <span lang={q.translation?.lang}>{tr}</span>
        <span lang="de" className="study-de-small">
          {de}
        </span>
      </span>
    );
  }
  if (q.mode === "side" && tr) {
    return (
      <span className="opt-text opt-side">
        <span lang="de">{de}</span>
        <span lang={q.translation?.lang}>{tr}</span>
      </span>
    );
  }
  if (q.mode === "help") {
    return (
      <span className="opt-text">
        <HelpText text={de} terms={q.terms} interactive={false} />
      </span>
    );
  }
  return (
    <span className="opt-text" lang="de">
      {de}
    </span>
  );
}

/** The explanation of a revealed question in its mode (Learn cards and the mock-test review). */
export function ExplanationText({ q }: { q: StudyQuestion }) {
  const tr = q.translation;
  const de = q.german.explanation ?? "";
  if (q.mode === "own" && tr?.explanation) {
    return (
      <div className="solution">
        <div lang={tr.lang}>
          <RichText text={tr.explanation} />
        </div>
        <div lang="de" className="study-de-small">
          <RichText text={de} />
        </div>
      </div>
    );
  }
  if (q.mode === "side" && tr?.explanation) {
    return (
      <div className="solution study-side">
        <div lang="de">
          <RichText text={de} />
        </div>
        <div lang={tr.lang}>
          <RichText text={tr.explanation} />
        </div>
      </div>
    );
  }
  return (
    <div className="solution" lang="de">
      <RichText text={de} />
    </div>
  );
}
