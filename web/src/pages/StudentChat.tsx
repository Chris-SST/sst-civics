import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, ensureCsrf, get, post } from "../api";
import ErrorText from "../components/ErrorText";
import RichText from "../components/RichText";

interface Msg {
  id: string;
  seq: number;
  role: "user" | "assistant" | "notice";
  content: string;
}

interface Conversation {
  id: string;
  course_key: string;
  course_name: string;
  topic_code: string;
  topic_name: string;
  language: string;
  title: string;
  status: "active" | "ended";
  messages: Msg[];
}

interface Usage {
  daily_used: number;
  daily_limit: number | null;
  monthly_used: number;
  monthly_limit: number | null;
  daily_exhausted: boolean;
  monthly_exhausted: boolean;
  near_monthly_limit: boolean;
}

type Notice = "off_topic" | "override" | "wellbeing" | "ended" | "refusal";

const MAX_CHARS = 2000;

export default function StudentChat() {
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
        const r = await fetch(`/api/tutor/conversations/${conv.id}/messages`, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            Accept: "text/event-stream",
            "X-CSRF-Token": await ensureCsrf(),
          },
          body: JSON.stringify({ content: text }),
        });
        if (!r.ok || !r.body) {
          let code = "unknown_error";
          try {
            const data = (await r.json()) as { detail?: string };
            if (typeof data.detail === "string") code = data.detail;
          } catch {
            /* no body */
          }
          throw new ApiError(r.status, code);
        }
        const reader = r.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let collected = "";
        let ended = false;
        const handle = (event: string, data: Record<string, unknown>) => {
          switch (event) {
            case "delta":
              collected += String(data.text ?? "");
              setStreaming(collected);
              break;
            case "notice":
              setNotice(data.kind as Notice);
              if (data.kind === "ended") ended = true;
              break;
            case "message":
              setConv((c) =>
                c
                  ? {
                      ...c,
                      messages: [
                        ...c.messages,
                        {
                          id: String(data.id),
                          seq: c.messages.length + 1,
                          role: data.role as Msg["role"],
                          content: String(data.content),
                        },
                      ],
                    }
                  : c,
              );
              setStreaming(null);
              break;
            case "usage":
              setUsage(data as unknown as Usage);
              break;
            case "error":
              setError(new ApiError(502, String(data.code ?? "unknown_error")));
              setStreaming(null);
              break;
            default:
              break;
          }
        };
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          let idx: number;
          while ((idx = buffer.indexOf("\n\n")) >= 0) {
            const chunk = buffer.slice(0, idx);
            buffer = buffer.slice(idx + 2);
            let event = "message";
            let data = "{}";
            for (const line of chunk.split("\n")) {
              if (line.startsWith("event: ")) event = line.slice(7);
              else if (line.startsWith("data: ")) data = line.slice(6);
            }
            try {
              handle(event, JSON.parse(data) as Record<string, unknown>);
            } catch {
              /* ignore malformed chunk */
            }
          }
        }
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
      navigate("/student");
    } catch (e) {
      setError(e);
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
          <Link to="/student" className="small">
            ← {t("chat.back")}
          </Link>
          <h1 className="chat-title">{conv.topic_name}</h1>
          <p className="small muted">{conv.course_name}</p>
        </div>
        {!ended && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={endSession}>
            {t("chat.end")}
          </button>
        )}
      </header>

      <div className="chat-log" role="log" aria-live="polite">
        {conv.messages.length === 0 && <p className="chat-intro muted">{t("chat.intro")}</p>}
        {conv.messages.map((m) => (
          <div key={m.id} className={`bubble bubble-${m.role}`}>
            {m.role === "user" ? <p>{m.content}</p> : <RichText text={m.content} />}
          </div>
        ))}
        {streaming !== null && (
          <div className="bubble bubble-assistant bubble-streaming">
            {streaming ? <RichText text={streaming} /> : <span className="dots">…</span>}
          </div>
        )}
        {notice === "wellbeing" && (
          <div className="alert alert-info helpline">
            <b>{t("chat.helplineTitle")}</b>
            <p>{t("chat.helplineBody")}</p>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

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
          {t("chat.ended")} <Link to="/student">{t("chat.newSession")}</Link>
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
    </div>
  );
}
