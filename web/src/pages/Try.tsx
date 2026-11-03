import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import { get } from "../api";
import ErrorText from "../components/ErrorText";
import PassBar from "../components/PassBar";
import QuestionCard from "../components/QuestionCard";
import type { AnswerOut, StudyQuestion } from "../study";

/** Free practice without an account: the 30 sample questions of Zurich or of the rest of
 * Switzerland (`?canton=ch`; Zurich when the link names none), German and the visitor's language
 * side by side, checked in the browser. The guide site's "Try 30 free questions" lands here.
 * Where the visitor is is kept in this browser only; a free account keeps real progress. */

/** The choices on this page: Zurich, and "ch" (Rest of Switzerland). */
const TRY_CANTONS = ["zh", "ch"] as const;
type TryCanton = (typeof TRY_CANTONS)[number];

function asCanton(value: string | null): TryCanton {
  return value === "ch" ? "ch" : "zh";
}

interface SampleOut {
  canton: string;
  lang: string;
  questions: StudyQuestion[];
}

interface Saved {
  lang: string;
  canton?: string;
  index: number;
  score: number;
}

const KEY = "viapunt.try";

function load(lang: string, canton: TryCanton): Saved {
  try {
    const s = JSON.parse(localStorage.getItem(KEY) || "null") as Saved | null;
    if (s && s.lang === lang && (s.canton ?? "zh") === canton) return s;
  } catch {
    /* storage unavailable */
  }
  return { lang, canton, index: 0, score: 0 };
}

function save(s: Saved) {
  try {
    localStorage.setItem(KEY, JSON.stringify(s));
  } catch {
    /* storage unavailable */
  }
}

/** The result panel's data, built from the question itself (nothing is sent anywhere). */
function check(q: StudyQuestion, given: string): AnswerOut {
  const key = q.answer ?? "";
  const de = q.german.options.find((o) => o.key === key)?.text ?? null;
  const tr = q.translation?.options.find((o) => o.key === key)?.text ?? null;
  return {
    attempt_id: "",
    correct: given === key,
    score: given === key ? 1 : 0,
    mode: q.mode,
    answer: key,
    answer_text: de,
    answer_text_translated: tr && tr !== de ? tr : null,
    explanation: q.explanation ?? { lang: "de", text: q.german.explanation ?? "" },
    explanation_de: q.german.explanation ?? "",
    progress: {
      mode: q.mode,
      previous_mode: q.mode,
      moved_forward: false,
      mode_reached: q.mode,
      understood: false,
      known: false,
      newly_understood: false,
      newly_known: false,
      box: 0,
      due_at: null,
    },
    mastery: { topic_code: q.topic_code, mastery: 0 },
    readiness: { value: 0, label_key: "" },
  };
}

export default function Try() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language.slice(0, 2);
  const [params, setParams] = useSearchParams();
  const canton = asCanton(params.get("canton"));
  const [data, setData] = useState<SampleOut | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [state, setState] = useState<Saved>(() => load(lang, canton));
  const [answered, setAnswered] = useState(false);

  useEffect(() => {
    setData(null);
    setError(null);
    setAnswered(false);
    setState(load(lang, canton));
    let current = true; // a quick switch of canton must not show the earlier answer
    get<SampleOut>(`/api/public/sample-questions?canton=${canton}&lang=${encodeURIComponent(lang)}`)
      .then((d) => current && setData(d))
      .catch((e) => current && setError(e));
    return () => {
      current = false;
    };
  }, [lang, canton]);

  const choose = (c: TryCanton) => {
    const next = new URLSearchParams(params);
    next.set("canton", c);
    setParams(next, { replace: true });
  };

  const update = (s: Saved) => {
    setState(s);
    save(s);
  };

  const signup = `/signup?lang=${encodeURIComponent(lang)}&canton=${canton}`;
  const total = data?.questions.length ?? 0;
  const done = data !== null && state.index >= total;
  const q = data && !done ? data.questions[state.index] : null;

  return (
    <div className="try-page">
      <h1>{t("try.title")}</h1>
      <div className="try-cantons" role="group" aria-label={t("fields.canton")}>
        {TRY_CANTONS.map((c) => (
          <button key={c} type="button" aria-pressed={c === canton} onClick={() => choose(c)}>
            {t(`cantons.${c}`)}
          </button>
        ))}
      </div>
      <p>{t("try.intro", { language: t(`languages.${lang}`) })}</p>
      {error ? <ErrorText error={error} /> : null}
      {!data && !error && <p className="muted">{t("common.working")}</p>}
      {data && total === 0 && <p className="muted">{t("try.none")}</p>}

      {q && (
        <>
          <p className="small muted try-progress" aria-live="polite">
            {t("try.progress", { n: state.index + 1, total, score: state.score })}
          </p>
          {q.fallback && <p className="alert alert-info small">{t("try.germanOnly")}</p>}
          <QuestionCard
            key={q.id}
            question={q}
            noReport
            submit={async (given) => check(q, given)}
            onResult={(r) => {
              setAnswered(true);
              if (r.correct) update({ ...state, score: state.score + 1 });
            }}
          >
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                setAnswered(false);
                update({ ...state, index: state.index + 1, score: state.score });
                window.scrollTo({ top: 0, behavior: "smooth" });
              }}
            >
              {state.index + 1 < total ? t("try.next") : t("try.finish")}
            </button>
          </QuestionCard>
          {answered && (
            <p className="small try-nudge">
              {t("try.nudge")} <Link to={signup}>{t("try.signup")}</Link>
            </p>
          )}
        </>
      )}

      {done && total > 0 && (
        <section className="card try-done">
          <h2>{t("try.doneTitle")}</h2>
          <p className="try-score">{t("try.doneScore", { score: state.score, total })}</p>
          <p>{t("try.doneText")}</p>
          <div className="actions">
            <Link to={signup} className="btn btn-primary">
              {t("try.signup")}
            </Link>
            <button type="button" className="btn btn-secondary" onClick={() => update({ lang, canton, index: 0, score: 0 })}>
              {t("try.again")}
            </button>
          </div>
        </section>
      )}
      <PassBar canton={canton} />
    </div>
  );
}
