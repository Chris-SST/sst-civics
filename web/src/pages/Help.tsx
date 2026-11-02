import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { post } from "../api";
import { ChatLog, streamMessage, type Msg, type Notice, type Usage } from "../components/ChatParts";
import ErrorText from "../components/ErrorText";

/** The help chat (D-066): questions about the test, its topics and the naturalisation procedure,
 * answered from the Viapunt guide and the test checklist. One open conversation per learner;
 * "New conversation" ends it and starts a fresh one. Free learners get a small daily allowance. */

interface Started {
  id: string;
  status: "active" | "ended";
  messages: Msg[];
  tutor_enabled: boolean;
  paid: boolean;
  usage: Usage;
}

const MAX_CHARS = 2000;
const SUGGESTIONS = ["help.s1", "help.s2", "help.s3"];

export default function Help() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language.slice(0, 2);
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

  const open = useCallback(
    (fresh: boolean) => {
      setError(null);
      setNotice(null);
      return post<Started>("/api/help/start", { lang, new: fresh })
        .then((c) => {
          setConv(c);
          setMessages(c.messages);
          setUsage(c.usage);
          setEnded(c.status === "ended");
          setTimeout(() => inputRef.current?.focus(), 0);
        })
        .catch(setError);
    },
    [lang],
  );

  useEffect(() => {
    void open(false);
  }, [open]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "nearest" });
  }, [messages.length, streaming]);

  const send = useCallback(
    async (text: string) => {
      text = text.trim();
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
    [conv, busy],
  );

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void send(draft);
  }

  function onKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send(draft);
    }
  }

  const limitReached = !!usage?.daily_exhausted;
  const left = usage && usage.daily_limit !== null ? Math.max(0, usage.daily_limit - usage.daily_used) : null;
  const disabled = busy || limitReached || !conv?.tutor_enabled;

  return (
    <section className="card help-page">
      <div className="explain-head">
        <h1>{t("help.title")}</h1>
        {conv && messages.length > 0 && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => void open(true)} disabled={busy}>
            {t("help.newChat")}
          </button>
        )}
      </div>
      <p>{t("help.lead")}</p>
      <p className="small muted">{t("help.note")}</p>

      {!conv && !error && <p className="muted">{t("common.working")}</p>}
      {error ? <ErrorText error={error} /> : null}

      {conv && (
        <>
          {!conv.tutor_enabled && <p className="alert alert-info small">{t("explain.offline")}</p>}
          <ChatLog messages={messages} streaming={streaming} notice={notice} bottomRef={bottomRef} className="chat-log help-log" />
          {messages.length === 0 && streaming === null && (
            <div className="help-suggestions">
              <p className="small muted">{t("help.intro")}</p>
              {SUGGESTIONS.map((key) => (
                <button key={key} type="button" className="btn btn-secondary btn-sm" disabled={disabled} onClick={() => void send(t(key))}>
                  {t(key)}
                </button>
              ))}
            </div>
          )}
          {limitReached && <p className="alert alert-warn small">{t("help.limitReached")}</p>}
          {ended ? (
            <p className="alert alert-info small">
              {t("chat.ended")}{" "}
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => void open(true)}>
                {t("help.newChat")}
              </button>
            </p>
          ) : (
            <form className="chat-compose explain-compose" onSubmit={onSubmit}>
              <textarea
                ref={inputRef}
                value={draft}
                onChange={(e) => setDraft(e.target.value.slice(0, MAX_CHARS))}
                onKeyDown={onKey}
                placeholder={t("help.placeholder")}
                aria-label={t("help.placeholder")}
                rows={2}
                disabled={disabled}
              />
              <div className="chat-compose-row">
                <span className="small muted" aria-live="polite">
                  {left !== null && usage?.daily_limit != null ? t("explain.remaining", { left, limit: usage.daily_limit }) : ""}
                </span>
                <button className="btn btn-primary btn-sm" disabled={disabled || !draft.trim()}>
                  {busy ? t("common.working") : t("chat.send")}
                </button>
              </div>
            </form>
          )}
          {!conv.paid && (
            <p className="small muted">
              {t("help.free")} <Link to="/learner#pricing">{t("help.freeCta")}</Link>
            </p>
          )}
        </>
      )}
    </section>
  );
}
