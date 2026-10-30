import { useTranslation } from "react-i18next";
import type { RefObject } from "react";
import { ApiError, ensureCsrf } from "../api";
import RichText from "./RichText";

/** The parts of a chat that the general chat (LearnerChat) and Explain this share: the message
 * types, the log with its bubbles, and the call that streams one reply. */

export interface Msg {
  id: string;
  seq: number;
  role: "user" | "assistant" | "notice";
  content: string;
}

export interface Usage {
  daily_used: number;
  daily_limit: number | null;
  monthly_used: number;
  monthly_limit: number | null;
  daily_exhausted: boolean;
  monthly_exhausted: boolean;
  near_monthly_limit: boolean;
}

export type Notice = "off_topic" | "override" | "wellbeing" | "ended" | "refusal";

export interface StreamHandlers {
  /** The reply so far. */
  onDelta: (collected: string) => void;
  onNotice: (kind: Notice) => void;
  onMessage: (message: { id: string; role: Msg["role"]; content: string }) => void;
  onUsage: (usage: Usage) => void;
  onError: (error: ApiError) => void;
}

/** Send one learner message and read the server-sent events of the reply. Throws an ApiError
 * when the request is refused (limit reached, no access, ...). Resolves with `ended: true` when
 * the server closed the conversation. */
export async function streamMessage(
  conversationId: string,
  text: string,
  handlers: StreamHandlers,
): Promise<{ ended: boolean }> {
  const r = await fetch(`/api/tutor/conversations/${conversationId}/messages`, {
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
        handlers.onDelta(collected);
        break;
      case "notice":
        handlers.onNotice(data.kind as Notice);
        if (data.kind === "ended") ended = true;
        break;
      case "message":
        handlers.onMessage({ id: String(data.id), role: data.role as Msg["role"], content: String(data.content) });
        break;
      case "usage":
        handlers.onUsage(data as unknown as Usage);
        break;
      case "error":
        handlers.onError(new ApiError(502, String(data.code ?? "unknown_error")));
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
  return { ended };
}

interface LogProps {
  messages: Msg[];
  /** The reply being streamed, "" before the first word, null when none. */
  streaming: string | null;
  notice: Notice | null;
  intro?: string;
  bottomRef?: RefObject<HTMLDivElement | null>;
  className?: string;
}

/** The message bubbles, the streaming reply and, after a wellbeing notice, the helpline. */
export function ChatLog({ messages, streaming, notice, intro, bottomRef, className = "chat-log" }: LogProps) {
  const { t } = useTranslation();
  return (
    <div className={className} role="log" aria-live="polite">
      {messages.length === 0 && intro && <p className="chat-intro muted">{intro}</p>}
      {messages.map((m) => (
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
  );
}
