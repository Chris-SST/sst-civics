import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { get, patch } from "../api";
import ErrorText from "./ErrorText";
import { DifficultyDots } from "./QuestionCard";
import RichText from "./RichText";

/** Review queue and review panel for tutors and admins (/api/review). */

export interface ReviewModule {
  module_key: string;
  name: string;
  topics: { code: string; name: string; levels: string[] }[];
}

export interface QuestionFull {
  id: string;
  module_key: string;
  level: "sl" | "hl" | "both";
  topic_code: string;
  difficulty: number;
  language: string;
  question_text: string;
  options: { key: string; text: string }[] | null;
  answer: string;
  worked_solution: string;
  status: string;
  spot_check: boolean;
  source: string;
  prompt_version: string;
  check_results: { issues?: string[]; max_similarity?: number } | null;
  solve_answer: string | null;
  review_note: string | null;
  reviewed_at: string | null;
  report_count: number;
  created_at: string;
}

export interface ReviewStats {
  modules: { module_key: string; by_status: Record<string, number>; topics: Record<string, Record<string, number>> }[];
  open_reports: number;
  my_review_minutes: number;
}

export const QUESTION_STATUSES = ["draft", "auto_verified", "needs_review", "approved", "retired"] as const;

export function IssueChips({ issues }: { issues: string[] | undefined }) {
  const { t } = useTranslation();
  if (!issues || issues.length === 0) return <span className="small muted">–</span>;
  return (
    <span className="chips">
      {issues.map((i) => (
        <span key={i} className="chip chip-warn">
          {t(`review.issues.${i}`, { defaultValue: i })}
        </span>
      ))}
    </span>
  );
}

export function StatsKpis({ stats, modules }: { stats: ReviewStats; modules: ReviewModule[] }) {
  const { t } = useTranslation();
  const name = (key: string) => modules.find((m) => m.module_key === key)?.name ?? key;
  return (
    <div className="kpis review-kpis">
      {stats.modules.map((m) => (
        <div className="kpi" key={m.module_key}>
          <b>{Object.values(m.by_status).reduce((a, b) => a + b, 0)}</b>
          {name(m.module_key)}
          <div className="small muted kpi-breakdown">
            {QUESTION_STATUSES.filter((s) => m.by_status[s]).map((s) => (
              <span key={s}>
                {t(`review.status.${s}`)}: {m.by_status[s]}
              </span>
            ))}
          </div>
        </div>
      ))}
      <div className="kpi">
        <b>{stats.open_reports}</b>
        {t("review.openReports")}
      </div>
      <div className="kpi">
        <b>{stats.my_review_minutes}</b>
        {t("review.myMinutes")}
      </div>
    </div>
  );
}

export default function QuestionReview({ initialQuestionId }: { initialQuestionId?: string }) {
  const { t } = useTranslation();
  const [modules, setModules] = useState<ReviewModule[]>([]);
  const [stats, setStats] = useState<ReviewStats | null>(null);
  const [moduleKey, setModuleKey] = useState("");
  const [qStatus, setQStatus] = useState("");
  const [rows, setRows] = useState<QuestionFull[] | null>(null);
  const [current, setCurrent] = useState<QuestionFull | null>(null);
  const [error, setError] = useState<unknown>(null);

  const loadStats = useCallback(() => get<ReviewStats>("/api/review/stats").then(setStats).catch(setError), []);

  useEffect(() => {
    get<ReviewModule[]>("/api/review/modules").then(setModules).catch(setError);
    void loadStats();
  }, [loadStats]);

  const loadQueue = useCallback(async () => {
    const qs = new URLSearchParams();
    if (moduleKey) qs.set("module_key", moduleKey);
    if (qStatus) qs.set("q_status", qStatus);
    try {
      setRows(await get<QuestionFull[]>(`/api/review/queue?${qs.toString()}`));
    } catch (e) {
      setError(e);
    }
  }, [moduleKey, qStatus]);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  useEffect(() => {
    if (initialQuestionId) get<QuestionFull>(`/api/review/questions/${initialQuestionId}`).then(setCurrent).catch(setError);
  }, [initialQuestionId]);

  async function open(id: string) {
    setError(null);
    try {
      setCurrent(await get<QuestionFull>(`/api/review/questions/${id}`));
      window.scrollTo({ top: 0 });
    } catch (e) {
      setError(e);
    }
  }

  const topicName = (mod: string, code: string) =>
    modules.find((m) => m.module_key === mod)?.topics.find((tp) => tp.code === code)?.name ?? code;

  return (
    <>
      {error ? <ErrorText error={error} /> : null}
      {stats && <StatsKpis stats={stats} modules={modules} />}

      {current && (
        <ReviewPanel
          key={current.id}
          q={current}
          modules={modules}
          onClose={() => setCurrent(null)}
          onSaved={(updated) => {
            setCurrent(null);
            setRows((rs) => (rs ? rs.filter((r) => r.id !== updated.id || !!qStatus) : rs));
            void loadQueue();
            void loadStats();
          }}
        />
      )}

      <section className="card">
        <h2>{t("review.queue")}</h2>
        <div className="filters">
          <label className="field">
            <span>{t("review.module")}</span>
            <select value={moduleKey} onChange={(e) => setModuleKey(e.target.value)}>
              <option value="">{t("review.allModules")}</option>
              {modules.map((m) => (
                <option key={m.module_key} value={m.module_key}>
                  {m.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>{t("review.statusFilter")}</span>
            <select value={qStatus} onChange={(e) => setQStatus(e.target.value)}>
              <option value="">{t("review.needsAttention")}</option>
              {QUESTION_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {t(`review.status.${s}`)}
                </option>
              ))}
            </select>
          </label>
        </div>
        {rows === null ? (
          <p className="muted">…</p>
        ) : rows.length === 0 ? (
          <p className="muted">{t("review.empty")}</p>
        ) : (
          <div className="table-wrap">
            <table className="table table-stack">
              <thead>
                <tr>
                  <th>{t("review.question")}</th>
                  <th>{t("review.topic")}</th>
                  <th>{t("review.difficulty")}</th>
                  <th>{t("review.statusLabel")}</th>
                  <th>{t("review.issuesLabel")}</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td data-label={t("review.question")}>
                      <RichText className="q-preview" text={r.question_text.length > 160 ? r.question_text.slice(0, 160) + "…" : r.question_text} />
                    </td>
                    <td data-label={t("review.topic")} className="small">
                      {topicName(r.module_key, r.topic_code)} <span className="muted">({r.topic_code}, {r.level.toUpperCase()})</span>
                    </td>
                    <td data-label={t("review.difficulty")}>
                      <DifficultyDots level={r.difficulty} />
                    </td>
                    <td data-label={t("review.statusLabel")}>
                      <span className={`status status-${r.status}`}>{t(`review.status.${r.status}`, { defaultValue: r.status })}</span>
                      {r.spot_check && <span className="chip">{t("review.spotCheck")}</span>}
                    </td>
                    <td data-label={t("review.issuesLabel")}>
                      <IssueChips issues={r.check_results?.issues} />
                      {r.report_count > 0 && <span className="chip chip-warn">{t("review.reports", { count: r.report_count })}</span>}
                    </td>
                    <td className="table-actions">
                      <button type="button" className="btn btn-sm btn-secondary" onClick={() => void open(r.id)}>
                        {t("common.open")}
                      </button>
                    </td>
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

interface Edits {
  question_text: string;
  options: string;
  answer: string;
  worked_solution: string;
  difficulty: number;
  topic_code: string;
  level: "sl" | "hl" | "both";
}

function fromQuestion(q: QuestionFull): Edits {
  return {
    question_text: q.question_text,
    options: (q.options ?? []).map((o) => `${o.key}) ${o.text}`).join("\n"),
    answer: q.answer,
    worked_solution: q.worked_solution,
    difficulty: q.difficulty,
    topic_code: q.topic_code,
    level: q.level,
  };
}

function parseOptions(text: string): { key: string; text: string }[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const m = /^([A-Za-z0-9]{1,2})\s*[).:\-]\s*(.*)$/.exec(line);
      return m ? { key: m[1], text: m[2] } : { key: line.slice(0, 1), text: line };
    });
}

/** Only fields that changed are sent as edits. */
function diff(q: QuestionFull, e: Edits): Record<string, unknown> | null {
  const out: Record<string, unknown> = {};
  if (e.question_text !== q.question_text) out.question_text = e.question_text;
  const opts = parseOptions(e.options);
  if (JSON.stringify(opts) !== JSON.stringify(q.options ?? []) && (opts.length || q.options)) out.options = opts;
  if (e.answer !== q.answer) out.answer = e.answer;
  if (e.worked_solution !== q.worked_solution) out.worked_solution = e.worked_solution;
  if (e.difficulty !== q.difficulty) out.difficulty = e.difficulty;
  if (e.topic_code !== q.topic_code) out.topic_code = e.topic_code;
  if (e.level !== q.level) out.level = e.level;
  return Object.keys(out).length ? out : null;
}

function ReviewPanel({
  q,
  modules,
  onClose,
  onSaved,
}: {
  q: QuestionFull;
  modules: ReviewModule[];
  onClose: () => void;
  onSaved: (q: QuestionFull) => void;
}) {
  const { t } = useTranslation();
  const [edits, setEdits] = useState<Edits>(() => fromQuestion(q));
  const [editing, setEditing] = useState(false);
  const [note, setNote] = useState("");
  const [minutes, setMinutes] = useState(3);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const mod = modules.find((m) => m.module_key === q.module_key);
  const set = <K extends keyof Edits>(k: K, v: Edits[K]) => setEdits((e) => ({ ...e, [k]: v }));

  async function act(action: "approve" | "retire" | "needs_review") {
    setBusy(action);
    setError(null);
    try {
      const updated = await patch<QuestionFull>(`/api/review/questions/${q.id}`, {
        action,
        edits: diff(q, edits),
        note: note.trim() || null,
        minutes,
      });
      onSaved(updated);
    } catch (e) {
      setError(e);
      setBusy(null);
    }
  }

  const checks = q.check_results ?? {};
  const field = (label: string, el: React.ReactNode) => (
    <label className="field">
      <span>{label}</span>
      {el}
    </label>
  );

  return (
    <section className="card review-panel">
      <header className="review-head">
        <div>
          <h2>{t("review.panelTitle")}</h2>
          <p className="small muted">
            {mod?.name ?? q.module_key} · {q.topic_code} · {q.level.toUpperCase()} ·{" "}
            <span className={`status status-${q.status}`}>{t(`review.status.${q.status}`, { defaultValue: q.status })}</span>
          </p>
        </div>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
          {t("common.close")}
        </button>
      </header>

      <div className="grid-2">
        <div>
          <h3>{t("review.question")}</h3>
          <RichText className="preview-box" text={edits.question_text} />
          <ul className="options-list">
            {parseOptions(edits.options).map((o) => (
              <li key={o.key}>
                <b>{o.key}</b> <RichText text={o.text} />
              </li>
            ))}
          </ul>
          <p>
            <b className="small">{t("review.answer")}:</b> <RichText text={edits.answer} />
          </p>
          <h3>{t("review.workedSolution")}</h3>
          <RichText className="preview-box" text={edits.worked_solution || "–"} />
        </div>
        <div>
          <h3>{t("review.checks")}</h3>
          <dl className="facts">
            <dt>{t("review.issuesLabel")}</dt>
            <dd>
              <IssueChips issues={checks.issues} />
            </dd>
            <dt>{t("review.solveAnswer")}</dt>
            <dd>{q.solve_answer ? <RichText text={q.solve_answer} /> : <span className="muted">–</span>}</dd>
            <dt>{t("review.storedAnswer")}</dt>
            <dd>
              <RichText text={q.answer} />
            </dd>
            <dt>{t("review.similarity")}</dt>
            <dd>{typeof checks.max_similarity === "number" ? `${Math.round(checks.max_similarity * 100)}%` : "–"}</dd>
            <dt>{t("review.source")}</dt>
            <dd>
              {q.source} · {q.prompt_version || "–"} · {q.language}
            </dd>
            <dt>{t("review.reportsLabel")}</dt>
            <dd>{q.report_count}</dd>
            {q.review_note && (
              <>
                <dt>{t("review.previousNote")}</dt>
                <dd>{q.review_note}</dd>
              </>
            )}
          </dl>
        </div>
      </div>

      <button type="button" className="link-btn" aria-expanded={editing} onClick={() => setEditing((e) => !e)}>
        {editing ? t("review.hideEdit") : t("review.edit")}
      </button>
      {editing && (
        <div className="form edit-form">
          {field(t("review.question"), <textarea rows={4} value={edits.question_text} onChange={(e) => set("question_text", e.target.value)} />)}
          {field(
            t("review.options"),
            <>
              <textarea rows={4} value={edits.options} onChange={(e) => set("options", e.target.value)} />
              <span className="hint">{t("review.optionsHint")}</span>
            </>,
          )}
          <div className="grid-2">
            {field(t("review.answer"), <input value={edits.answer} onChange={(e) => set("answer", e.target.value)} />)}
            {field(
              t("review.difficulty"),
              <select value={edits.difficulty} onChange={(e) => set("difficulty", Number(e.target.value))}>
                {[1, 2, 3, 4, 5].map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>,
            )}
            {field(
              t("review.topicCode"),
              mod ? (
                <select value={edits.topic_code} onChange={(e) => set("topic_code", e.target.value)}>
                  {mod.topics.map((tp) => (
                    <option key={tp.code} value={tp.code}>
                      {tp.code} · {tp.name}
                    </option>
                  ))}
                </select>
              ) : (
                <input value={edits.topic_code} onChange={(e) => set("topic_code", e.target.value)} />
              ),
            )}
            {field(
              t("review.level"),
              <select value={edits.level} onChange={(e) => set("level", e.target.value as Edits["level"])}>
                {(["sl", "hl", "both"] as const).map((l) => (
                  <option key={l} value={l}>
                    {t(`qbank.levels.${l}`)}
                  </option>
                ))}
              </select>,
            )}
          </div>
          {field(t("review.workedSolution"), <textarea rows={6} value={edits.worked_solution} onChange={(e) => set("worked_solution", e.target.value)} />)}
        </div>
      )}

      <form className="form review-actions" onSubmit={(e: FormEvent) => e.preventDefault()}>
        <div className="grid-2">
          {field(t("review.note"), <input value={note} maxLength={2000} onChange={(e) => setNote(e.target.value)} />)}
          {field(
            t("review.minutes"),
            <input type="number" min={0} max={120} value={minutes} onChange={(e) => setMinutes(Math.max(0, Math.min(120, Number(e.target.value) || 0)))} />,
          )}
        </div>
        {error ? <ErrorText error={error} /> : null}
        <div className="actions">
          <button type="button" className="btn btn-primary" disabled={busy !== null} onClick={() => void act("approve")}>
            {busy === "approve" ? t("common.working") : diff(q, edits) ? t("review.approveEdits") : t("review.approve")}
          </button>
          <button type="button" className="btn btn-secondary" disabled={busy !== null} onClick={() => void act("needs_review")}>
            {t("review.sendBack")}
          </button>
          <button type="button" className="btn btn-danger" disabled={busy !== null} onClick={() => void act("retire")}>
            {t("review.retire")}
          </button>
        </div>
      </form>
    </section>
  );
}
