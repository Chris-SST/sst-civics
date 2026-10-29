import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, get, post } from "../api";
import ErrorText from "../components/ErrorText";
import QuestionCard, { MasteryBar } from "../components/QuestionCard";
import type { AttemptOut, PracticeOverview, QuestionPublic } from "../practice";

/** Practice on one topic: a question, the result, the next question. */
export default function StudentPractice() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const courseKey = params.get("course_key") ?? "";
  const topicCode = params.get("topic_code") ?? "";
  const [question, setQuestion] = useState<QuestionPublic | null>(null);
  const [noQuestions, setNoQuestions] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [result, setResult] = useState<AttemptOut | null>(null);
  const [mastery, setMastery] = useState<number | null>(null);
  const [topicName, setTopicName] = useState("");
  const [busy, setBusy] = useState(false);
  const [count, setCount] = useState(0);

  const load = useCallback(async () => {
    setResult(null);
    setQuestion(null);
    setError(null);
    try {
      const q = await get<QuestionPublic>(
        `/api/practice/next?course_key=${encodeURIComponent(courseKey)}&topic_code=${encodeURIComponent(topicCode)}`,
      );
      setQuestion(q);
    } catch (e) {
      if (e instanceof ApiError && e.code === "no_questions") setNoQuestions(true);
      else setError(e);
    }
  }, [courseKey, topicCode]);

  useEffect(() => {
    if (!courseKey || !topicCode) return;
    void load();
    get<PracticeOverview>(`/api/practice/overview?course_key=${encodeURIComponent(courseKey)}`)
      .then((o) => {
        const tp = o.topics.find((x) => x.topic_code === topicCode);
        if (tp) {
          setTopicName(tp.topic_name);
          setMastery(tp.mastery);
        }
      })
      .catch(() => undefined);
  }, [courseKey, topicCode, load]);

  async function askTutor() {
    setBusy(true);
    try {
      const conv = await post<{ id: string }>("/api/tutor/conversations", { course_key: courseKey, topic_code: topicCode });
      navigate(`/student/chat/${conv.id}`);
    } catch (e) {
      setError(e);
      setBusy(false);
    }
  }

  if (!courseKey || !topicCode) {
    return (
      <section className="card">
        <ErrorText error={new ApiError(400, "invalid_topic")} />
        <Link to="/student" className="btn btn-ghost">
          {t("practice.back")}
        </Link>
      </section>
    );
  }

  return (
    <>
      <header className="page-head">
        <div>
          <Link to="/student" className="small">
            ← {t("chat.back")}
          </Link>
          <h1>{topicName || t("practice.title")}</h1>
          {topicName && <p className="small muted">{t("practice.title")}</p>}
        </div>
        <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => void askTutor()}>
          {t("student.askTutor")}
        </button>
      </header>
      <div className="practice-mastery">
        <span className="small">{t("practice.mastery")}</span>
        <MasteryBar value={mastery} label={t("practice.mastery")} />
      </div>
      {error ? <ErrorText error={error} /> : null}

      {noQuestions && (
        <section className="card">
          <p className="alert alert-info">{t("practice.noQuestions")}</p>
          <div className="actions">
            <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void askTutor()}>
              {busy ? t("common.working") : t("practice.askInstead")}
            </button>
            <Link to="/student" className="btn btn-ghost">
              {t("practice.back")}
            </Link>
          </div>
        </section>
      )}

      {!noQuestions && !question && !error && <p className="muted">…</p>}

      {question && (
        <QuestionCard
          key={`${question.id}-${count}`}
          question={question}
          submit={(answer) =>
            post<AttemptOut>("/api/practice/attempts", {
              question_id: question.id,
              answer,
              mode: "practice",
              course_key: courseKey,
            })
          }
          onResult={(r) => {
            setResult(r);
            setMastery(r.mastery.mastery);
          }}
        >
          {result && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                setCount((c) => c + 1);
                void load();
                window.scrollTo({ top: 0 });
              }}
            >
              {t("practice.nextQuestion")}
            </button>
          )}
        </QuestionCard>
      )}
    </>
  );
}
