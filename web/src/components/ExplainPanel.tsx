import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { post } from "../api";
import { ChatLog, streamMessage, type Msg, type Notice, type Usage } from "./ChatParts";
import ErrorText from "./ErrorText";

/** "Explain this": a short chat about one question, below the card. It opens the learner's
 * conversation for the question (or a new one), answers in the learner's language and shows how
 * many messages are left today. It is never mounted in the mock test. */

interface Started {
  id: string;
  status: "active" | "ended";
  messages: Msg[];
  tutor_enabled: boolean;
  usage: Usage;
}

const MAX_CHARS = 2000;

export default function ExplainPanel({ questionId, lang, onClose }: { questionId: string; lang: string; onClose: () => void }) {
  const { t } = useTranslation();
  const [conv, setConv] = useState<Started | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [ended, setEnded] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [error, setError] = useState<unknown>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    let cancelled = false;
    post<Started>("/api/explain/start", { question_id: questionId, lang })
      .then((c) => {
        if (cancelled) return;
        setConv(c);
        setMessages(c.messages);
        setUsage(c.usage);
        setEnded(c.status === "ended");
        setTimeout(() => inputRef.current?.focus(), 0);
      })
      .catch((e) => {
        if (!cancelled) setError(e);
      });
    return () => {
      cancelled = true;
    };
  }, [questionId, lang]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "nearest" });
  }, [messages.length, streaming]);

  const send = useCallback(
    async (e?: FormEvent) => {
      e?.preventDefault();
      const text = draft.trim();
      if (!conv || !text || busy) return;
      setBusy(true);
      setError(null);
      setNotice(null);
      setMessages((m) => [...m, { id: `tmp-${Date.now()}`, seq: 0, role: "user", content: text }]);
      setDraft("");
      setStreaming("");
      try {
        const result = await streamMessage(conv.id, text, {
          onDelta: setStreaming,
          onNotice: setNotice,
          onMessage: (m) => {
            setMessages((list) => [...list, { id: m.id, seq: list.length + 1, role: m.role, content: m.content }]);
            setStreaming(null);
          },
          onUsage: setUsage,
          onError: (err) => {
            setError(err);
            setStreaming(null);
          },
        });
        if (result.ended) setEnded(true);
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

  function onKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  }

  const limitReached = !!usage?.daily_exhausted;
  const left = usage && usage.daily_limit !== null ? Math.max(0, usage.daily_limit - usage.daily_used) : null;

  return (
    <section className="explain-panel" aria-label={t("explain.title")}>
      <div className="explain-head">
        <h3>{t("explain.title")}</h3>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
          {t("common.close")}
        </button>
      </div>
      <p className="small muted explain-note">{t("explain.note")}</p>

      {!conv && !error && <p className="muted">{t("common.working")}</p>}
      {error ? <ErrorText error={error} /> : null}

      {conv && (
        <>
          {!conv.tutor_enabled && <p className="alert alert-info small">{t("explain.offline")}</p>}
          <ChatLog
            messages={messages}
            streaming={streaming}
            notice={notice}
            intro={t("explain.intro")}
            bottomRef={bottomRef}
            className="chat-log explain-log"
          />
          {limitReached && <p className="alert alert-warn small">{t("explain.limitReached")}</p>}
          {ended ? (
            <p className="alert alert-info small">{t("chat.ended")}</p>
          ) : (
            <form className="chat-compose explain-compose" onSubmit={send}>
              <textarea
                ref={inputRef}
                value={draft}
                onChange={(e) => setDraft(e.target.value.slice(0, MAX_CHARS))}
                onKeyDown={onKey}
                placeholder={t("explain.placeholder")}
                aria-label={t("explain.placeholder")}
                rows={2}
                disabled={busy || limitReached || !conv.tutor_enabled}
              />
              <div className="chat-compose-row">
                <span className="small muted" aria-live="polite">
                  {left !== null && usage?.daily_limit != null ? t("explain.remaining", { left, limit: usage.daily_limit }) : ""}
                </span>
                <button className="btn btn-primary btn-sm" disabled={busy || !draft.trim() || limitReached || !conv.tutor_enabled}>
                  {busy ? t("common.working") : t("chat.send")}
                </button>
              </div>
            </form>
          )}
        </>
      )}
    </section>
  );
}
