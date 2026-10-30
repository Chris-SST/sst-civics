import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, get, post } from "../api";
import Countdown from "../components/Countdown";
import ErrorText from "../components/ErrorText";
import QuestionCard from "../components/QuestionCard";
import { mockQuestion, type MockInfo, type MockRunOut } from "../study";

/** Mock test: German only, the canton's number of questions and time limit, a countdown to the
 * deadline the server set, no help and no explanations while it runs. Afterwards the score,
 * pass or fail against the pass mark (labelled unconfirmed), and every wrong answer in the
 * learner's language with its explanation. There is no "Explain this" in a mock test. */
export default function Mock() {
  const { id } = useParams();
  return id ? <MockRun runId={id} /> : <MockIntro />;
}

function BackHome() {
  const { t } = useTranslation();
  return (
    <Link to="/learner" className="small">
      {"←"} {t("practice.back")}
    </Link>
  );
}

function MockIntro() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [info, setInfo] = useState<MockInfo | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    get<MockInfo>("/api/mock").then(setInfo).catch(setError);
  }, []);

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const run = await post<MockRunOut>("/api/mock/start");
      navigate(`/mock/${run.id}`);
    } catch (e) {
      setError(e);
      setBusy(false);
    }
  }

  if (!info) return error ? <ErrorText error={error} /> : <p className="muted">…</p>;

  return (
    <>
      <header className="page-head">
        <div>
          <BackHome />
          <h1>{t("mock.title")}</h1>
        </div>
      </header>
      <section className="card">
        {!info.configured ? (
          <p className="alert alert-info">{t("learner.mockSoon")}</p>
        ) : (
          <>
            <p className="mock-format">{t("mock.format", { questions: info.questions, minutes: info.minutes })}</p>
            <ul className="mock-rules">
              <li>{t("mock.ruleGerman")}</li>
              <li>{t("mock.ruleNoHelp")}</li>
              <li>{t("mock.ruleTimer")}</li>
              <li>{t("mock.ruleReview")}</li>
            </ul>
            {info.pass_mark !== null && (
              <p className="small">
                {t("mock.passMark", { mark: info.pass_mark, total: info.questions })}{" "}
                {!info.pass_mark_confirmed && <span className="muted">({t(info.pass_mark_label_key)})</span>}
              </p>
            )}
            {!info.paid && (
              <p className={`alert ${info.free_mock_used ? "alert-warn" : "alert-info"}`}>
                {info.free_mock_used ? t("mock.freeUsed") : t("mock.freeOne")}
              </p>
            )}
            {!info.enough_questions && <p className="alert alert-info">{t("mock.notEnough")}</p>}
            {error ? <ErrorText error={error} /> : null}
            <div className="actions">
              {info.active_run_id ? (
                <Link className="btn btn-primary" to={`/mock/${info.active_run_id}`}>
                  {t("mock.continue")}
                </Link>
              ) : (
                <button type="button" className="btn btn-primary" disabled={busy || !info.can_start || !info.enough_questions} onClick={() => void start()}>
                  {busy ? t("common.working") : t("mock.start")}
                </button>
              )}
            </div>
          </>
        )}
      </section>
      {info.recent.length > 0 && (
        <section className="card">
          <h2>{t("mock.recent")}</h2>
          <ul className="recent-list">
            {info.recent.map((r) => (
              <li key={r.id}>
                <Link to={`/mock/${r.id}`}>
                  <b className="mono">{t("mock.scoreShort", { score: r.score ?? 0, total: r.total })}</b>
                  <span className="small muted">
                    {r.passed === null ? "" : r.passed ? t("mock.passed") : t("mock.failed")}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

function MockRun({ runId }: { runId: string }) {
  const { t } = useTranslation();
  const [run, setRun] = useState<MockRunOut | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [index, setIndex] = useState(0);
  const [error, setError] = useState<unknown>(null);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await get<MockRunOut>(`/api/mock/${runId}`);
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
      await post(`/api/mock/${runId}/answer`, { question_id: questionId, answer: key });
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
      setRun(await post<MockRunOut>(`/api/mock/${runId}/finish`));
      window.scrollTo({ top: 0 });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  }

  if (!run) return error ? <ErrorText error={error} /> : <p className="muted">…</p>;
  if (run.status !== "in_progress") return <MockResult run={run} />;

  const questions = run.questions ?? [];
  const q = questions[index];
  const answered = questions.filter((x) => answers[x.id]).length;
  const unanswered = questions.length - answered;

  return (
    <>
      <header className="page-head mock-head">
        <div>
          <h1>{t("mock.title")}</h1>
          <p className="small muted">{t("mock.answeredOf", { n: answered, total: questions.length })}</p>
        </div>
        <Countdown deadline={run.deadline_at} serverNow={run.now} onExpire={() => void load()} />
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
          {t("mock.handIn")}
        </button>
      </div>

      {confirming && (
        <section className="card confirm-card" role="alertdialog" aria-label={t("mock.handIn")}>
          <p>{unanswered > 0 ? t("mock.confirmUnanswered", { count: unanswered }) : t("mock.confirm")}</p>
          <div className="actions">
            <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void handIn()}>
              {busy ? t("common.working") : t("mock.handInNow")}
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

function MockResult({ run }: { run: MockRunOut }) {
  const { t } = useTranslation();
  const review = run.review ?? [];
  const tone = run.passed === null ? "" : run.passed ? "result-ok" : "result-bad";
  return (
    <>
      <header className="page-head">
        <div>
          <BackHome />
          <h1>{t("mock.resultTitle")}</h1>
        </div>
      </header>
      <section className={`card mock-score ${tone}`} aria-live="polite">
        {run.status === "expired" && <p className="small">{t("mock.expired")}</p>}
        <p className="mock-score-value">{t("mock.scoreShort", { score: run.score ?? 0, total: run.total })}</p>
        {run.passed !== null && <h2>{run.passed ? t("mock.passed") : t("mock.failed")}</h2>}
        {run.pass_mark !== null && (
          <p className="small">
            {t("mock.passMark", { mark: run.pass_mark, total: run.total })}{" "}
            {!run.pass_mark_confirmed && <span>({t(run.pass_mark_label_key)})</span>}
          </p>
        )}
        <p className="small muted">{t("mock.estimateNote")}</p>
        <div className="actions">
          <Link className="btn btn-primary" to="/practise">
            {t("learner.practiseCta")}
          </Link>
          <Link className="btn btn-ghost" to="/mock">
            {t("mock.backToMock")}
          </Link>
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
