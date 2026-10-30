import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import { get, post } from "../api";
import ErrorText from "../components/ErrorText";
import ModeStepper from "../components/ModeStepper";
import QuestionCard, { MasteryBar } from "../components/QuestionCard";
import { STUDY_MODES, TOPIC_SCOPES, learnUrl, practiseUrl, type LearnOut, type StudyMode, type StudyOverview } from "../study";

const MODE_KEY = "sst.learnMode";

function savedMode(): StudyMode {
  try {
    const m = localStorage.getItem(MODE_KEY);
    if (m && (STUDY_MODES as string[]).includes(m)) return m as StudyMode;
  } catch {
    /* storage unavailable */
  }
  return "own";
}

function saveMode(m: StudyMode) {
  try {
    localStorage.setItem(MODE_KEY, m);
  } catch {
    /* storage unavailable */
  }
}

/** Learn: the topics in catalogue order (Confederation, canton, commune); in a topic, one card
 * at a time with the question, the correct answer and the explanation in the chosen study mode.
 * No scoring; each card shown is marked as seen. */
export default function Learn() {
  const [params] = useSearchParams();
  const topic = params.get("topic");
  return topic ? <LearnTopic topicCode={topic} /> : <LearnTopics />;
}

function BackHome() {
  const { t } = useTranslation();
  return (
    <Link to="/learner" className="small">
      {"←"} {t("practice.back")}
    </Link>
  );
}

function LearnTopics() {
  const { t } = useTranslation();
  const [data, setData] = useState<StudyOverview | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    get<StudyOverview>("/api/study/overview").then(setData).catch(setError);
  }, []);

  if (!data) return error ? <ErrorText error={error} /> : <p className="muted">…</p>;

  return (
    <>
      <header className="page-head">
        <div>
          <BackHome />
          <h1>{t("learn.title")}</h1>
        </div>
      </header>
      <p>{t("learn.intro")}</p>
      {data.free_tier && <p className="alert alert-info">{t("learn.freeTier", { count: data.sample_size })}</p>}
      <section className="card">
        {TOPIC_SCOPES.map((scope) => {
          const group = data.topics.filter((tp) => tp.scope === scope);
          if (!group.length) return null;
          return (
            <div key={scope} className="topic-group">
              <h2>{t(`topics.scope.${scope}`)}</h2>
              <ul className="topic-list">
                {group.map((tp) => (
                  <li key={tp.topic_code}>
                    {tp.questions_available > 0 ? (
                      <Link className="topic-row" to={learnUrl(tp.topic_code)}>
                        <span className="topic-name">
                          {tp.topic_name}
                          <span className="small muted"> · {t("learn.seenOf", { seen: tp.seen, total: tp.questions_available })}</span>
                        </span>
                        <MasteryBar value={tp.seen > 0 ? tp.mastery : null} label={tp.topic_name} />
                      </Link>
                    ) : (
                      <div className="topic-row topic-empty">
                        <span className="topic-name">
                          {tp.topic_name}
                          <span className="small muted"> · {t("learn.noneYet")}</span>
                        </span>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </section>
    </>
  );
}

function LearnTopic({ topicCode }: { topicCode: string }) {
  const { t } = useTranslation();
  const [mode, setMode] = useState<StudyMode>(savedMode);
  const [data, setData] = useState<LearnOut | null>(null);
  const [index, setIndex] = useState(0);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(
    async (m: StudyMode) => {
      setError(null);
      try {
        setData(await get<LearnOut>(`/api/study/learn?topic_code=${encodeURIComponent(topicCode)}&mode=${m}`));
      } catch (e) {
        setError(e);
      }
    },
    [topicCode],
  );

  useEffect(() => {
    setIndex(0);
    void load(mode);
    // Reload only when the topic changes; a mode change reloads in changeMode.
  }, [topicCode]);

  const card = data?.cards[index] ?? null;

  useEffect(() => {
    if (card && !card.progress?.seen) {
      post(`/api/study/question/${card.id}/seen`).catch(() => {
        /* marking seen is best effort */
      });
    }
  }, [card]);

  function changeMode(m: StudyMode) {
    setMode(m);
    saveMode(m);
    void load(m);
  }

  function go(delta: number) {
    if (!data) return;
    setIndex((i) => Math.max(0, Math.min(data.cards.length - 1, i + delta)));
    window.scrollTo({ top: 0 });
  }

  const total = data?.cards.length ?? 0;
  const last = index >= total - 1;

  return (
    <>
      <header className="page-head">
        <div>
          <Link to={learnUrl()} className="small">
            {"←"} {t("learn.allTopics")}
          </Link>
          <h1>{data?.topic_name ?? t("learn.title")}</h1>
          {data && <p className="small muted">{t("learn.title")}</p>}
        </div>
      </header>
      {error ? <ErrorText error={error} /> : null}
      {data && total === 0 && (
        <section className="card">
          <p className="alert alert-info">{t("learn.noneYet")}</p>
          <BackHome />
        </section>
      )}
      {data && card && (
        <>
          <ModeStepper mode={mode} onChange={changeMode} />
          {data.free_tier && <p className="small muted">{t("learn.freeTierShort")}</p>}
          <p className="small muted progress-label">{t("learn.cardOf", { n: index + 1, total })}</p>
          <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={index + 1}>
            <span style={{ width: `${((index + 1) / total) * 100}%` }} />
          </div>
          <QuestionCard key={`${card.id}-${card.mode}`} question={card} reveal>
            <div className="actions">
              <button type="button" className="btn btn-ghost" disabled={index === 0} onClick={() => go(-1)}>
                {t("learn.previous")}
              </button>
              {last ? (
                <Link className="btn btn-primary" to={practiseUrl(topicCode)}>
                  {t("learn.practiseNow")}
                </Link>
              ) : (
                <button type="button" className="btn btn-primary" onClick={() => go(1)}>
                  {t("learn.next")}
                </button>
              )}
            </div>
          </QuestionCard>
        </>
      )}
      {!data && !error && <p className="muted">…</p>}
    </>
  );
}
