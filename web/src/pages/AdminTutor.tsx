import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { get, patch } from "../api";
import ErrorText from "../components/ErrorText";
import RichText from "../components/RichText";
import { formatChf, formatDate } from "../i18n";

interface Flag {
  id: string;
  kind: string;
  detail: string | null;
  status: "open" | "reviewed" | "dismissed";
  notes: string | null;
  created_at: string;
  student_first_name: string;
  course_key: string | null;
  topic_name: string | null;
}

interface FlagConversation {
  flagged_message_id: string | null;
  messages: { id: string; role: string; content: string; gate_label: string | null }[];
}

export function SafetyFlags() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<"open" | "reviewed" | "dismissed" | "">("open");
  const [flags, setFlags] = useState<Flag[] | null>(null);
  const [open, setOpen] = useState<{ flag: Flag; conv: FlagConversation } | null>(null);
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(() => {
    const q = status ? `?flag_status=${status}` : "";
    get<Flag[]>(`/api/admin/safety-flags${q}`).then(setFlags).catch(setError);
  }, [status]);
  useEffect(load, [load]);

  async function view(flag: Flag) {
    try {
      const conv = await get<FlagConversation>(`/api/admin/safety-flags/${flag.id}/conversation`);
      setOpen({ flag, conv });
      setNotes(flag.notes ?? "");
    } catch (e) {
      setError(e);
    }
  }

  async function update(newStatus: "reviewed" | "dismissed" | "open") {
    if (!open) return;
    try {
      await patch(`/api/admin/safety-flags/${open.flag.id}`, { status: newStatus, notes });
      setOpen(null);
      load();
    } catch (e) {
      setError(e);
    }
  }

  return (
    <>
      <p className="muted">{t("safety.intro")}</p>
      <label className="field" style={{ maxWidth: 260 }}>
        <span>{t("safety.filter")}</span>
        <select value={status} onChange={(e) => setStatus(e.target.value as typeof status)}>
          <option value="open">{t("safety.status.open")}</option>
          <option value="reviewed">{t("safety.status.reviewed")}</option>
          <option value="dismissed">{t("safety.status.dismissed")}</option>
          <option value="">{t("safety.all")}</option>
        </select>
      </label>
      {error ? <ErrorText error={error} /> : null}
      {flags === null ? (
        <p className="muted">…</p>
      ) : flags.length === 0 ? (
        <p className="muted">{t("safety.none")}</p>
      ) : (
        <div className="table-wrap card">
          <table className="table table-stack">
            <thead>
              <tr>
                <th>{t("safety.when")}</th>
                <th>{t("safety.student")}</th>
                <th>{t("safety.kind")}</th>
                <th>{t("safety.course")}</th>
                <th>{t("safety.statusLabel")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {flags.map((f) => (
                <tr key={f.id}>
                  <td data-label={t("safety.when")}>{formatDate(f.created_at)}</td>
                  <td data-label={t("safety.student")}>{f.student_first_name}</td>
                  <td data-label={t("safety.kind")}>
                    {t(`safety.kinds.${f.detail ?? f.kind}`, { defaultValue: f.detail ?? f.kind })}
                  </td>
                  <td data-label={t("safety.course")}>
                    {f.course_key ? t(`courses.${f.course_key}`, { defaultValue: f.course_key }) : ""}
                    {f.topic_name && <span className="small muted"> · {f.topic_name}</span>}
                  </td>
                  <td data-label={t("safety.statusLabel")}>{t(`safety.status.${f.status}`)}</td>
                  <td className="table-actions">
                    <button type="button" className="btn btn-sm" onClick={() => view(f)}>
                      {t("safety.review")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {open && (
        <section className="card" style={{ marginTop: 18 }}>
          <h2>
            {t("safety.reviewTitle", { name: open.flag.student_first_name })}{" "}
            <span className="small muted">({formatDate(open.flag.created_at)})</span>
          </h2>
          <p className="small muted">{t("safety.viewLogged")}</p>
          <div className="chat-log admin-transcript">
            {open.conv.messages.map((m) => (
              <div
                key={m.id}
                className={`bubble bubble-${m.role} ${m.id === open.conv.flagged_message_id ? "bubble-flagged" : ""}`}
              >
                {m.role === "user" ? <p>{m.content}</p> : <RichText text={m.content} />}
                {m.gate_label && m.gate_label !== "on_topic" && (
                  <span className="small muted">{m.gate_label}</span>
                )}
              </div>
            ))}
          </div>
          <label className="field">
            <span>{t("safety.notes")}</span>
            <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} />
          </label>
          <div className="actions">
            <button type="button" className="btn btn-primary" onClick={() => update("reviewed")}>
              {t("safety.markReviewed")}
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => update("dismissed")}>
              {t("safety.dismiss")}
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => setOpen(null)}>
              {t("common.close")}
            </button>
          </div>
        </section>
      )}
    </>
  );
}

interface UsageOut {
  period_start: string;
  calls: number;
  cost_chf: number;
  input_tokens: number;
  cache_read_tokens: number;
  output_tokens: number;
  student_messages: number;
  by_purpose: { purpose: string; calls: number; cost_chf: number; avg_latency_ms: number; errors: number }[];
  top_students: { student_id: string; first_name: string; calls: number; cost_chf: number }[];
}

export function AiUsage() {
  const { t } = useTranslation();
  const [data, setData] = useState<UsageOut | null>(null);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    get<UsageOut>("/api/admin/ai-usage").then(setData).catch(setError);
  }, []);
  if (error) return <ErrorText error={error} />;
  if (!data) return <p className="muted">…</p>;
  return (
    <>
      <p className="muted">{t("usage.intro", { date: formatDate(data.period_start) })}</p>
      <div className="kpis">
        <div className="kpi">
          <b>{formatChf(Math.round(data.cost_chf * 100))}</b>
          {t("usage.cost")}
        </div>
        <div className="kpi">
          <b>{data.student_messages}</b>
          {t("usage.messages")}
        </div>
        <div className="kpi">
          <b>{data.calls}</b>
          {t("usage.calls")}
        </div>
        <div className="kpi">
          <b>{data.student_messages ? formatChf(Math.round((data.cost_chf / data.student_messages) * 100)) : "–"}</b>
          {t("usage.perMessage")}
        </div>
        <div className="kpi">
          <b>{data.input_tokens ? Math.round((100 * data.cache_read_tokens) / (data.input_tokens + data.cache_read_tokens)) : 0}%</b>
          {t("usage.cacheRate")}
        </div>
      </div>
      <section className="card" style={{ marginTop: 18 }}>
        <h2>{t("usage.byPurpose")}</h2>
        <div className="table-wrap">
          <table className="table table-stack">
            <thead>
              <tr>
                <th>{t("usage.purpose")}</th>
                <th>{t("usage.calls")}</th>
                <th>{t("usage.cost")}</th>
                <th>{t("usage.latency")}</th>
                <th>{t("usage.errors")}</th>
              </tr>
            </thead>
            <tbody>
              {data.by_purpose.map((p) => (
                <tr key={p.purpose}>
                  <td data-label={t("usage.purpose")}>{t(`usage.purposes.${p.purpose}`, { defaultValue: p.purpose })}</td>
                  <td data-label={t("usage.calls")}>{p.calls}</td>
                  <td data-label={t("usage.cost")}>{formatChf(Math.round(p.cost_chf * 100))}</td>
                  <td data-label={t("usage.latency")}>{p.avg_latency_ms} ms</td>
                  <td data-label={t("usage.errors")}>{p.errors}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="card" style={{ marginTop: 18 }}>
        <h2>{t("usage.topStudents")}</h2>
        {data.top_students.length === 0 ? (
          <p className="muted">{t("usage.noStudents")}</p>
        ) : (
          <div className="table-wrap">
            <table className="table table-stack">
              <thead>
                <tr>
                  <th>{t("safety.student")}</th>
                  <th>{t("usage.calls")}</th>
                  <th>{t("usage.cost")}</th>
                </tr>
              </thead>
              <tbody>
                {data.top_students.map((s) => (
                  <tr key={s.student_id}>
                    <td data-label={t("safety.student")}>{s.first_name}</td>
                    <td data-label={t("usage.calls")}>{s.calls}</td>
                    <td data-label={t("usage.cost")}>{formatChf(Math.round(s.cost_chf * 100))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
