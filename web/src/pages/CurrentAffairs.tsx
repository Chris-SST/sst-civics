import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { get, post } from "../api";
import ErrorText from "../components/ErrorText";
import { formatDate } from "../i18n";
import type { OptionOut } from "../study";

interface Block {
  lang: string;
  question: string;
  options: OptionOut[];
}

export interface CurrentAffairsQuestion {
  id: string;
  refers_to: string;
  page_kind: "roundup" | "vote";
  page_url: string | null;
  german: Block;
  translation: Block | null;
}

export interface CurrentAffairsOut {
  canton: string;
  count: number;
  questions: CurrentAffairsQuestion[];
}

interface Checked extends CurrentAffairsQuestion {
  correct: boolean;
  answer: string;
  explanation: { lang: string; text: string };
  explanation_de: string;
}

/** The optional "Current affairs" topic (D-074): questions made from the guide's politics
 * pages, free for everyone, in German with the learner's translation beneath. Answers are
 * checked by the server and not recorded: they never count towards the mock test, the free
 * sample set or readiness. Each question shows the date it refers to and links to its page. */
export default function CurrentAffairs() {
  const { t } = useTranslation();
  const [data, setData] = useState<CurrentAffairsOut | null>(null);
  const [index, setIndex] = useState(0);
  const [choice, setChoice] = useState<string | null>(null);
  const [result, setResult] = useState<Checked | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    get<CurrentAffairsOut>("/api/study/current-affairs").then(setData).catch(setError);
  }, []);

  const question = data?.questions[index] ?? null;
  const total = data?.questions.length ?? 0;

  async function check() {
    if (!question || !choice) return;
    setError(null);
    try {
      setResult(await post<Checked>("/api/study/current-affairs/answer", { question_id: question.id, answer: choice }));
    } catch (e) {
      setError(e);
    }
  }

  function next() {
    setResult(null);
    setChoice(null);
    setIndex((i) => i + 1);
    window.scrollTo({ top: 0 });
  }

  const optionText = (key: string) => question?.german.options.find((o) => o.key === key)?.text ?? key;

  return (
    <>
      <header className="page-head">
        <div>
          <Link to="/learner" className="small">
            {"←"} {t("currentAffairs.back")}
          </Link>
          <h1>{t("currentAffairs.title")}</h1>
          <p className="small muted">{t("currentAffairs.body")}</p>
        </div>
      </header>
      {error ? <ErrorText error={error} /> : null}
      {!data && !error && <p className="muted">{"…"}</p>}
      {data && total === 0 && <p className="alert alert-info">{t("currentAffairs.none")}</p>}
      {data && total > 0 && !question && (
        <section className="card">
          <p>{t("currentAffairs.done")}</p>
          <Link to="/learner" className="btn btn-ghost">
            {t("currentAffairs.back")}
          </Link>
        </section>
      )}
      {question && (
        <section className="card" aria-live="polite">
          <p className="small muted">
            {t("currentAffairs.progress", { n: index + 1, total })} · {t("currentAffairs.refersTo", { date: formatDate(question.refers_to) })}
          </p>
          <h2 lang="de">{question.german.question}</h2>
          {question.translation && (
            <p className="small muted" lang={question.translation.lang}>
              {question.translation.question}
            </p>
          )}
          <div className="mcq" role="radiogroup" aria-label={question.german.question}>
            {question.german.options.map((o) => {
              const tr = question.translation?.options.find((x) => x.key === o.key)?.text;
              const isCorrect = result !== null && o.key === result.answer;
              const isWrong = result !== null && o.key === choice && !isCorrect;
              return (
                <button
                  key={o.key}
                  type="button"
                  role="radio"
                  aria-checked={choice === o.key}
                  className={`mcq-option${choice === o.key ? " selected" : ""}${isCorrect ? " is-correct" : isWrong ? " is-wrong" : ""}`}
                  disabled={result !== null}
                  onClick={() => setChoice(o.key)}
                >
                  <b>{o.key.toUpperCase()}</b>
                  <span>
                    <span lang="de">{o.text}</span>
                    {tr && (
                      <span className="small muted" lang={question.translation?.lang}>
                        {" "}
                        ({tr})
                      </span>
                    )}
                  </span>
                </button>
              );
            })}
          </div>
          {result ? (
            <>
              <p className={`alert ${result.correct ? "alert-ok" : "alert-info"}`}>
                {result.correct ? t("currentAffairs.correct") : t("currentAffairs.wrong", { answer: optionText(result.answer) })}
              </p>
              <p lang={result.explanation.lang}>{result.explanation.text}</p>
              <div className="actions">
                <button type="button" className="btn btn-primary" onClick={next}>
                  {t("currentAffairs.next")}
                </button>
                {question.page_url && (
                  <a className="btn btn-ghost" href={question.page_url} target="_blank" rel="noopener">
                    {t("currentAffairs.readPage")}
                  </a>
                )}
              </div>
            </>
          ) : (
            <div className="actions">
              <button type="button" className="btn btn-primary" disabled={!choice} onClick={() => void check()}>
                {t("currentAffairs.check")}
              </button>
            </div>
          )}
        </section>
      )}
    </>
  );
}
