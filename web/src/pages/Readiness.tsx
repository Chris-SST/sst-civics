import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, get, post } from "../api";
import { useAuth } from "../auth";
import ErrorText from "../components/ErrorText";
import QuestionCard, { MasteryBar } from "../components/QuestionCard";
import { mockQuestion, type ReadinessInfo, type ReadinessRunOut } from "../study";

/** Readiness check (app/study/readiness_check.py): 20 questions from the whole bank of the
 * learner's canton, German only, no time limit, answers checked at the end. The result shows the
 * share right overall and per topic area, a "where you stand" line, the wrong answers explained
 * and, for free learners, the Viapunt Pass. One check a day without a pass. No Explain this here:
 * the run is a measurement. */
export default function Readiness() {
  const { id } = useParams();
  return id ? <CheckRun runId={id} /> : <CheckIntro />;
}

const API = "/api/readiness-check";

function BackHome() {
  const { t } = useTranslation();
  return (
    <Link to="/learner" className="small">
      {"←"} {t("practice.back")}
    </Link>
  );
}

function CheckIntro() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [info, setInfo] = useState<ReadinessInfo | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    get<ReadinessInfo>(API).then(setInfo).catch(setError);
  }, []);

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const run = await post<ReadinessRunOut>(`${API}/start`);
      navigate(`/readiness/${run.id}`);
    } catch (e) {
      setError(e);
      setBusy(false);
    }
  }

  if (!info) return error ? <ErrorText error={error} /> : <p className="muted">…</p>;
  const usedUp = !info.can_start && !info.active_run_id;

  return (
    <>
      <header className="page-head">
        <div>
          <BackHome />
          <h1>{t("readinessCheck.title")}</h1>
        </div>
      </header>
      <section className="card">
        <p className="mock-format">{t("readinessCheck.intro", { questions: info.questions })}</p>
        <ul className="mock-rules">
          <li>{t("readinessCheck.ruleGerman")}</li>
          <li>{t("readinessCheck.ruleNoTimer")}</li>
          <li>{t("readinessCheck.ruleEnd")}</li>
        </ul>
        {!info.paid && (
          <p className={`alert ${usedUp ? "alert-warn" : "alert-info"}`}>
            {usedUp ? t("readinessCheck.usedToday") : t("readinessCheck.freeOne")}
          </p>
        )}
        {!info.enough_questions && <p className="alert alert-info">{t("readinessCheck.notEnough")}</p>}
        {error ? <ErrorText error={error} /> : null}
        <div className="actions">
          {info.active_run_id ? (
            <Link className="btn btn-primary" to={`/readiness/${info.active_run_id}`}>
              {t("readinessCheck.continue")}
            </Link>
          ) : (
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy || !info.can_start || !info.enough_questions}
              onClick={() => void start()}
            >
              {busy ? t("common.working") : t("readinessCheck.start")}
            </button>
          )}
          {info.last && (
            <Link className="btn btn-ghost" to={`/readiness/${info.last.id}`}>
              {t("readinessCheck.seeLast")}
            </Link>
          )}
        </div>
      </section>
    </>
  );
}

function CheckRun({ runId }: { runId: string }) {
  const { t } = useTranslation();
  const [run, setRun] = useState<ReadinessRunOut | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [index, setIndex] = useState(0);
  const [error, setError] = useState<unknown>(null);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await get<ReadinessRunOut>(`${API}/${runId}`);
      setRun(r);
      setAnswers(r.answers ?? {});
    } catch (e) {
      setError(e);
    }
  }, [runId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function choose(questionId: string, key: string) {
    const before = answers[questionId];
    setAnswers((a) => ({ ...a, [questionId]: key }));
    setError(null);
    try {
      await post(`${API}/${runId}/answer`, { question_id: questionId, answer: key });
    } catch (e) {
      setAnswers((a) => {
        const next = { ...a };
        if (before) next[questionId] = before;
        else delete next[questionId];
        return next;
      });
      if (e instanceof ApiError && (e.code === "deadline_passed" || e.code === "mock_finished")) void load();
      else setError(e);
    }
  }

  async function handIn() {
    setBusy(true);
    try {
      setRun(await post<ReadinessRunOut>(`${API}/${runId}/finish`));
      window.scrollTo({ top: 0 });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  }

  if (!run) return error ? <ErrorText error={error} /> : <p className="muted">…</p>;
  if (run.status !== "in_progress") return <CheckResult run={run} />;

  const questions = run.questions ?? [];
  const q = questions[index];
  const answered = questions.filter((x) => answers[x.id]).length;
  const unanswered = questions.length - answered;

  return (
    <>
      <header className="page-head mock-head">
        <div>
          <h1>{t("readinessCheck.title")}</h1>
          <p className="small muted">{t("mock.answeredOf", { n: answered, total: questions.length })}</p>
        </div>
      </header>
      {error ? <ErrorText error={error} /> : null}

      <nav className="mock-nav" aria-label={t("mock.navigator")}>
        {questions.map((x, i) => (
          <button
            type="button"
            key={x.id}
            className={`mock-nav-item${i === index ? " current" : ""}${answers[x.id] ? " answered" : ""}`}
            aria-current={i === index ? "step" : undefined}
            aria-label={t("mock.goTo", { n: i + 1 })}
            onClick={() => setIndex(i)}
          >
            {i + 1}
          </button>
        ))}
      </nav>

      {q && (
        <>
          <p className="small muted progress-label">{t("practice.progress", { n: index + 1, total: questions.length })}</p>
          <QuestionCard key={q.id} question={mockQuestion(q, index)} selected={answers[q.id] ?? null} onSelect={(key) => void choose(q.id, key)} />
        </>
      )}

      <div className="actions mock-actions">
        <button type="button" className="btn btn-ghost" disabled={index === 0} onClick={() => setIndex((i) => i - 1)}>
          {t("learn.previous")}
        </button>
        {index < questions.length - 1 && (
          <button type="button" className="btn btn-secondary" onClick={() => setIndex((i) => i + 1)}>
            {t("learn.next")}
          </button>
        )}
        <button type="button" className="btn btn-primary" disabled={busy} onClick={() => setConfirming(true)}>
          {t("readinessCheck.handIn")}
        </button>
      </div>

      {confirming && (
        <section className="card confirm-card" role="alertdialog" aria-label={t("readinessCheck.handIn")}>
          <p>{unanswered > 0 ? t("readinessCheck.confirmUnanswered", { count: unanswered }) : t("readinessCheck.confirm")}</p>
          <div className="actions">
            <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void handIn()}>
              {busy ? t("common.working") : t("readinessCheck.handInNow")}
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => setConfirming(false)}>
              {t("mock.keepGoing")}
            </button>
          </div>
        </section>
      )}
    </>
  );
}

function CheckResult({ run }: { run: ReadinessRunOut }) {
  const { t } = useTranslation();
  const { me } = useAuth();
  const free = !!me?.access.free_tier;
  const review = run.review ?? [];
  const percent = run.percent ?? 0;
  return (
    <>
      <header className="page-head">
        <div>
          <BackHome />
          <h1>{t("readinessCheck.resultTitle")}</h1>
        </div>
      </header>
      <section className="card mock-score" aria-live="polite">
        {run.status === "expired" && <p className="small">{t("readinessCheck.expired")}</p>}
        <p className="mock-score-value">{t("readinessCheck.score", { score: run.score ?? 0, total: run.total, percent })}</p>
        {run.level && <p>{t(`readinessCheck.level.${run.level}`)}</p>}
        <p className="small muted">{t("mock.estimateNote")}</p>
      </section>

      {run.areas && run.areas.length > 0 && (
        <section className="card">
          <h2>{t("readinessCheck.areasTitle")}</h2>
          <ul className="topic-list readiness-areas">
            {run.areas.map((a) => (
              <li key={a.area}>
                <div className="topic-row">
                  <span className="topic-name">
                    {t(`readinessCheck.area.${a.area}`)}
                    <span className="small muted">
                      {" · "}
                      {t("readinessCheck.areaScore", { correct: a.correct, total: a.total })}
                    </span>
                  </span>
                  <MasteryBar value={a.percent} label={t(`readinessCheck.area.${a.area}`)} />
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="card">
        {free && (
          <p>
            {t("pricing.passIncludes")} <Link to="/learner#pricing">{t("help.freeCta")}</Link>
          </p>
        )}
        <div className="actions">
          <Link className="btn btn-primary" to="/practise">
            {t("learner.practiseCta")}
          </Link>
          <Link className="btn btn-secondary" to="/mock">
            {t("learner.mockCta")}
          </Link>
          {free ? null : (
            <Link className="btn btn-ghost" to="/readiness">
              {t("readinessCheck.again")}
            </Link>
          )}
        </div>
      </section>

      <h2>{t("mock.reviewTitle")}</h2>
      {review.length === 0 ? (
        <p className="alert alert-ok">{t("mock.allRight")}</p>
      ) : (
        <>
          <p className="small muted">{t("mock.reviewIntro", { count: review.length })}</p>
          {review.map((q) => (
            <QuestionCard key={q.id} question={q} reveal />
          ))}
        </>
      )}
    </>
  );
}
