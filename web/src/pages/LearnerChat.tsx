import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";
import { get, post } from "../api";
import { ChatLog, streamMessage, type Msg, type Notice, type Usage } from "../components/ChatParts";
import ErrorText from "../components/ErrorText";
import QuestionCard from "../components/QuestionCard";
import type { AnswerOut, StudyQuestion } from "../study";

interface Conversation {
  id: string;
  canton: string;
  topic_code: string;
  topic_name: string;
  language: string;
  title: string;
  status: "active" | "ended";
  messages: Msg[];
}

interface CheckOut {
  conversation_id: string;
  topic_code: string;
  questions: StudyQuestion[];
}

const MAX_CHARS = 2000;

export default function LearnerChat() {
  const { t } = useTranslation();
  const { id } = useParams();
  const navigate = useNavigate();
  const [conv, setConv] = useState<Conversation | null>(null);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [check, setCheck] = useState<CheckOut | null>(null);
  const [checkBusy, setCheckBusy] = useState(false);
  const [checkError, setCheckError] = useState<unknown>(null);
  const [checkMastery, setCheckMastery] = useState<number | null>(null);
  const checkRef = useRef<HTMLElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!id) return;
    get<Conversation>(`/api/tutor/conversations/${id}`)
      .then(setConv)
      .catch((e) => setError(e));
  }, [id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [conv?.messages.length, streaming]);

  const send = useCallback(
    async (e?: FormEvent) => {
      e?.preventDefault();
      const text = draft.trim();
      if (!conv || !text || busy) return;
      setBusy(true);
      setError(null);
      setNotice(null);
      const optimistic: Msg = { id: `tmp-${Date.now()}`, seq: 0, role: "user", content: text };
      setConv({ ...conv, messages: [...conv.messages, optimistic] });
      setDraft("");
      setStreaming("");
      try {
        const { ended } = await streamMessage(conv.id, text, {
          onDelta: setStreaming,
          onNotice: setNotice,
          onMessage: (m) => {
            setConv((c) =>
              c ? { ...c, messages: [...c.messages, { id: m.id, seq: c.messages.length + 1, role: m.role, content: m.content }] } : c,
            );
            setStreaming(null);
          },
          onUsage: setUsage,
          onError: (e) => {
            setError(e);
            setStreaming(null);
          },
        });
        if (ended) setConv((c) => (c ? { ...c, status: "ended" } : c));
      } catch (err) {
        setError(err);
        setStreaming(null);
      } finally {
        setBusy(false);
        setTimeout(() => inputRef.current?.focus(), 0);
      }
    },
    [conv, draft, busy],
  );

  async function endSession() {
    if (!conv) return;
    try {
      await post(`/api/tutor/conversations/${conv.id}/end`);
      navigate("/learner");
    } catch (e) {
      setError(e);
    }
  }

  async function loadCheck() {
    if (!conv) return;
    setCheckBusy(true);
    setCheckError(null);
    try {
      setCheck(await get<CheckOut>(`/api/study/check?conversation_id=${conv.id}`));
      setTimeout(() => checkRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
    } catch (e) {
      setCheckError(e);
    } finally {
      setCheckBusy(false);
    }
  }

  function onKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  }

  if (!conv) {
    return error ? <ErrorText error={error} /> : <p className="muted">…</p>;
  }
  const ended = conv.status === "ended";
  const limitReached = usage?.daily_exhausted || usage?.monthly_exhausted;

  return (
    <div className="chat">
      <header className="chat-head">
        <div>
          <Link to="/learner" className="small">
            ← {t("chat.back")}
          </Link>
          <h1 className="chat-title">{conv.topic_name}</h1>
          <p className="small muted">{t(`cantons.${conv.canton}`, { defaultValue: conv.canton.toUpperCase() })}</p>
        </div>
        {!ended && (
          <div className="chat-head-actions">
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={checkBusy || busy}
              onClick={() => void loadCheck()}
            >
              {checkBusy ? t("common.working") : t("chat.check")}
            </button>
            <button type="button" className="btn btn-ghost btn-sm" onClick={endSession}>
              {t("chat.end")}
            </button>
          </div>
        )}
      </header>

      <ChatLog messages={conv.messages} streaming={streaming} notice={notice} intro={t("chat.intro")} bottomRef={bottomRef} />

      {usage?.near_monthly_limit && !limitReached && (
        <p className="alert alert-warn small">
          {t("chat.nearLimit", { used: usage.monthly_used, limit: usage.monthly_limit })}
        </p>
      )}
      {limitReached && (
        <p className="alert alert-warn small">
          {t(usage?.monthly_exhausted ? "chat.monthlyLimit" : "chat.dailyLimit")}
        </p>
      )}
      {error ? <ErrorText error={error} /> : null}

      {ended ? (
        <p className="alert alert-info">
          {t("chat.ended")} <Link to="/learner">{t("chat.newSession")}</Link>
        </p>
      ) : (
        <form className="chat-compose" onSubmit={send}>
          <textarea
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value.slice(0, MAX_CHARS))}
            onKeyDown={onKey}
            placeholder={t("chat.placeholder")}
            rows={2}
            disabled={busy || !!limitReached}
            aria-label={t("chat.placeholder")}
          />
          <div className="chat-compose-row">
            <span className="small muted">
              {draft.length}/{MAX_CHARS}
            </span>
            <button className="btn btn-primary" disabled={busy || !draft.trim() || !!limitReached}>
              {busy ? t("common.working") : t("chat.send")}
            </button>
          </div>
        </form>
      )}

      {checkError ? <ErrorText error={checkError} /> : null}
      {check && (
        <section className="check-panel" ref={checkRef} aria-label={t("chat.checkTitle")}>
          <div className="check-head">
            <h2>{t("chat.checkTitle")}</h2>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setCheck(null)}>
              {t("common.close")}
            </button>
          </div>
          {check.questions.length === 0 ? (
            <p className="alert alert-info">{t("chat.checkEmpty")}</p>
          ) : (
            <>
              <p className="small muted">{t("chat.checkIntro")}</p>
              {check.questions.map((q) => (
                <QuestionCard
                  key={q.id}
                  question={q}
                  submit={(answer) =>
                    post<AnswerOut>("/api/study/answer", {
                      question_id: q.id,
                      answer,
                      mode: q.mode,
                      context: "check",
                      conversation_id: conv.id,
                    })
                  }
                  onResult={(r) => setCheckMastery(r.mastery.mastery)}
                />
              ))}
              {checkMastery !== null && (
                <p className="alert alert-ok">{t("chat.masteryNow", { topic: conv.topic_name, value: checkMastery })}</p>
              )}
            </>
          )}
        </section>
      )}
    </div>
  );
}
