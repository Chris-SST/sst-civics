import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { get, patch } from "../api";
import { formatDate } from "../i18n";
import ErrorText from "./ErrorText";
import { DifficultyDots } from "./QuestionCard";
import RichText from "./RichText";

/** Admin review queue for questions imported from content/ (/api/review). Review actions are
 * stored in the app only; the content file is updated by the pipeline (task 1.5). */

const OPTION_KEYS = ["a", "b", "c", "d"] as const;
type OptionKey = (typeof OPTION_KEYS)[number];

export const QUESTION_STATUSES = ["draft", "in_review", "approved", "retired"] as const;

export interface ReviewTopic {
  canton: string;
  code: string;
  scope: "federal" | "canton" | "commune";
  name_de: string;
  name_en: string;
}

export interface ReviewMeta {
  cantons: string[];
  topics: ReviewTopic[];
  statuses: string[];
  languages: string[];
}

interface PendingChange {
  action: string;
  from?: string;
  status: string;
  note?: string | null;
  edits?: Record<string, unknown> | null;
  at: string;
}

interface TranslationState {
  lang: string;
  state: "approved" | "in_review" | "draft" | "stale" | "missing";
  source_version: number | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
}

export interface QuestionFull {
  id: string;
  version: number;
  scope: string;
  canton: string | null;
  topic_code: string;
  difficulty: number;
  question_de: string;
  options_de: Record<OptionKey, string>;
  correct: OptionKey;
  explanation_de: string;
  sources: { url: string; checked: string }[];
  glossary: string[];
  translations_missing: boolean;
  status: string;
  file_status: string;
  file_sync_pending: boolean;
  pending_changes: PendingChange[];
  content_hash: string;
  imported_at: string;
  review_note: string | null;
  reviewed_at: string | null;
  report_count: number;
  translations?: TranslationState[];
  reports?: { id: string; lang: string | null; comment: string | null; created_at: string }[];
}

export interface ReviewStats {
  scopes: { scope: string; by_status: Record<string, number> }[];
  open_reports: number;
  pending_file_updates: number;
  my_review_minutes: number;
}

export interface TranslationStatus {
  approved_questions: number;
  flagged_missing: number;
  languages: { lang: string; approved: number; in_review: number; draft: number; stale: number; missing: number }[];
}

export function useTopicName(meta: ReviewMeta | null) {
  const { i18n } = useTranslation();
  return useCallback(
    (code: string) => {
      const tp = meta?.topics.find((x) => x.code === code);
      if (!tp) return code;
      return i18n.language.startsWith("de") ? tp.name_de : tp.name_en;
    },
    [meta, i18n.language],
  );
}

export function scopeLabel(t: (k: string, o?: Record<string, unknown>) => string, scope: string): string {
  if (scope === "federal") return t("review.federal");
  return t(`cantons.${scope}`, { defaultValue: scope.toUpperCase() });
}

export function StatsKpis({ stats }: { stats: ReviewStats }) {
  const { t } = useTranslation();
  return (
    <div className="kpis review-kpis">
      {stats.scopes.map((s) => (
        <div className="kpi" key={s.scope}>
          <b>{Object.values(s.by_status).reduce((a, b) => a + b, 0)}</b>
          {scopeLabel(t, s.scope)}
          <div className="small muted kpi-breakdown">
            {QUESTION_STATUSES.filter((st) => s.by_status[st]).map((st) => (
              <span key={st}>
                {t(`review.status.${st}`)}: {s.by_status[st]}
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
        <b>{stats.pending_file_updates}</b>
        {t("review.pendingUpdates")}
      </div>
      <div className="kpi">
        <b>{stats.my_review_minutes}</b>
        {t("review.myMinutes")}
      </div>
    </div>
  );
}

/** Per launch language: approved, in review, draft, stale and missing translations of the
 * approved German questions. */
export function TranslationStatusTable({ data }: { data: TranslationStatus }) {
  const { t } = useTranslation();
  const cols = ["approved", "in_review", "draft", "stale", "missing"] as const;
  return (
    <>
      <p className="small muted">{t("qbank.translationsIntro", { count: data.approved_questions })}</p>
      {data.flagged_missing > 0 && <p className="small muted">{t("qbank.flaggedMissing", { count: data.flagged_missing })}</p>}
      <div className="table-wrap">
        <table className="table table-stack">
          <thead>
            <tr>
              <th>{t("qbank.language")}</th>
              {cols.map((c) => (
                <th key={c}>{t(`review.tstate.${c}`)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.languages.map((row) => (
              <tr key={row.lang}>
                <td data-label={t("qbank.language")}>{t(`languages.${row.lang}`, { defaultValue: row.lang })}</td>
                {cols.map((c) => (
                  <td key={c} data-label={t(`review.tstate.${c}`)} className={c === "stale" && row.stale > 0 ? "warn" : undefined}>
                    {row[c]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function QuestionReview({ initialQuestionId }: { initialQuestionId?: string }) {
  const { t } = useTranslation();
  const [meta, setMeta] = useState<ReviewMeta | null>(null);
  const [stats, setStats] = useState<ReviewStats | null>(null);
  const [qStatus, setQStatus] = useState("");
  const [canton, setCanton] = useState("");
  const [topic, setTopic] = useState("");
  const [rows, setRows] = useState<QuestionFull[] | null>(null);
  const [current, setCurrent] = useState<QuestionFull | null>(null);
  const [error, setError] = useState<unknown>(null);
  const topicName = useTopicName(meta);

  const loadStats = useCallback(() => get<ReviewStats>("/api/review/stats").then(setStats).catch(setError), []);

  useEffect(() => {
    get<ReviewMeta>("/api/review/meta").then(setMeta).catch(setError);
    void loadStats();
  }, [loadStats]);

  const loadQueue = useCallback(async () => {
    const qs = new URLSearchParams();
    if (qStatus) qs.set("status", qStatus);
    if (canton) qs.set("canton", canton);
    if (topic) qs.set("topic", topic);
    try {
      setRows(await get<QuestionFull[]>(`/api/review/queue?${qs.toString()}`));
    } catch (e) {
      setError(e);
    }
  }, [qStatus, canton, topic]);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  useEffect(() => {
    if (initialQuestionId) get<QuestionFull>(`/api/review/questions/${encodeURIComponent(initialQuestionId)}`).then(setCurrent).catch(setError);
  }, [initialQuestionId]);

  async function open(id: string) {
    setError(null);
    try {
      setCurrent(await get<QuestionFull>(`/api/review/questions/${encodeURIComponent(id)}`));
      window.scrollTo({ top: 0 });
    } catch (e) {
      setError(e);
    }
  }

  // Topics offered in the filter follow the canton filter: federal topics once, then each canton's own.
  const topicOptions = useMemo(() => {
    const all = meta?.topics ?? [];
    const federal = all.filter((tp, i) => tp.scope === "federal" && all.findIndex((x) => x.code === tp.code) === i);
    const own = all.filter((tp) => tp.scope !== "federal" && (!canton || canton === tp.canton));
    if (canton === "federal") return federal;
    return canton ? own : [...federal, ...own];
  }, [meta, canton]);

  return (
    <>
      {error ? <ErrorText error={error} /> : null}
      {stats && <StatsKpis stats={stats} />}

      {current && (
        <ReviewPanel
          key={`${current.id}-${current.version}-${current.pending_changes.length}`}
          q={current}
          meta={meta}
          onClose={() => setCurrent(null)}
          onSaved={() => {
            setCurrent(null);
            void loadQueue();
            void loadStats();
          }}
        />
      )}

      <section className="card">
        <h2>{t("review.queue")}</h2>
        <div className="filters">
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
          <label className="field">
            <span>{t("review.canton")}</span>
            <select
              value={canton}
              onChange={(e) => {
                setCanton(e.target.value);
                setTopic("");
              }}
            >
              <option value="">{t("review.allCantons")}</option>
              <option value="federal">{t("review.federal")}</option>
              {(meta?.cantons ?? []).map((c) => (
                <option key={c} value={c}>
                  {t(`cantons.${c}`, { defaultValue: c.toUpperCase() })}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>{t("review.topic")}</span>
            <select value={topic} onChange={(e) => setTopic(e.target.value)}>
              <option value="">{t("review.allTopics")}</option>
              {topicOptions.map((tp) => (
                <option key={`${tp.canton}-${tp.code}`} value={tp.code}>
                  {topicName(tp.code)}
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
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td data-label={t("review.question")}>
                      <RichText className="q-preview" text={r.question_de.length > 160 ? r.question_de.slice(0, 160) + "…" : r.question_de} />
                      <span className="small muted">
                        {r.id} · {t("review.version", { version: r.version })}
                      </span>
                    </td>
                    <td data-label={t("review.topic")} className="small">
                      {topicName(r.topic_code)} <span className="muted">({scopeLabel(t, r.scope)})</span>
                    </td>
                    <td data-label={t("review.difficulty")}>
                      <DifficultyDots level={r.difficulty} />
                    </td>
                    <td data-label={t("review.statusLabel")}>
                      <span className={`status status-${r.status}`}>{t(`review.status.${r.status}`, { defaultValue: r.status })}</span>
                      {r.file_sync_pending && <span className="chip chip-warn">{t("review.filePendingShort")}</span>}
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
  question_de: string;
  options_de: Record<OptionKey, string>;
  correct: OptionKey;
  explanation_de: string;
  difficulty: number;
  topic_code: string;
}

function fromQuestion(q: QuestionFull): Edits {
  return {
    question_de: q.question_de,
    options_de: { ...q.options_de },
    correct: q.correct,
    explanation_de: q.explanation_de,
    difficulty: q.difficulty,
    topic_code: q.topic_code,
  };
}

/** Only fields that changed are sent as edits. */
function diff(q: QuestionFull, e: Edits): Record<string, unknown> | null {
  const out: Record<string, unknown> = {};
  if (e.question_de !== q.question_de) out.question_de = e.question_de;
  if (OPTION_KEYS.some((k) => e.options_de[k] !== q.options_de[k])) out.options_de = e.options_de;
  if (e.correct !== q.correct) out.correct = e.correct;
  if (e.explanation_de !== q.explanation_de) out.explanation_de = e.explanation_de;
  if (e.difficulty !== q.difficulty) out.difficulty = e.difficulty;
  if (e.topic_code !== q.topic_code) out.topic_code = e.topic_code;
  return Object.keys(out).length ? out : null;
}

function ReviewPanel({
  q,
  meta,
  onClose,
  onSaved,
}: {
  q: QuestionFull;
  meta: ReviewMeta | null;
  onClose: () => void;
  onSaved: (q: QuestionFull) => void;
}) {
  const { t } = useTranslation();
  const topicName = useTopicName(meta);
  const [edits, setEdits] = useState<Edits>(() => fromQuestion(q));
  const [editing, setEditing] = useState(false);
  const [note, setNote] = useState("");
  const [minutes, setMinutes] = useState(3);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const set = <K extends keyof Edits>(k: K, v: Edits[K]) => setEdits((e) => ({ ...e, [k]: v }));
  const changes = diff(q, edits);
  const retired = q.status === "retired";
  // A federal question takes a federal topic (listed once); a canton question one of its canton's own.
  const topicChoices = (meta?.topics ?? []).filter((tp, i, all) =>
    q.canton === null
      ? tp.scope === "federal" && all.findIndex((x) => x.code === tp.code) === i
      : tp.canton === q.canton && tp.scope !== "federal",
  );

  async function act(action: "approve" | "send_back" | "retire") {
    setBusy(action);
    setError(null);
    try {
      const updated = await patch<QuestionFull>(`/api/review/questions/${encodeURIComponent(q.id)}`, {
        action,
        edits: action === "approve" ? changes : null,
        note: note.trim() || null,
        minutes,
      });
      onSaved(updated);
    } catch (e) {
      setError(e);
      setBusy(null);
    }
  }

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
            {q.id} · {t("review.version", { version: q.version })} · {scopeLabel(t, q.scope)} · {topicName(q.topic_code)} ·{" "}
            <span className={`status status-${q.status}`}>{t(`review.status.${q.status}`, { defaultValue: q.status })}</span>
          </p>
        </div>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
          {t("common.close")}
        </button>
      </header>

      {q.file_sync_pending && <p className="alert alert-warn small">{t("review.filePending")}</p>}

      <div className="grid-2">
        <div>
          <h3>{t("review.question")}</h3>
          <RichText className="preview-box" text={edits.question_de} />
          <ul className="options-list">
            {OPTION_KEYS.map((k) => (
              <li key={k} className={k === edits.correct ? "is-correct" : undefined}>
                <b>{k.toUpperCase()}</b> <RichText text={edits.options_de[k]} />
                {k === edits.correct && <span className="chip">{t("review.answer")}</span>}
              </li>
            ))}
          </ul>
          <h3>{t("review.explanation")}</h3>
          <RichText className="preview-box" text={edits.explanation_de || "–"} />
          <h3>{t("review.sources")}</h3>
          <ul className="small">
            {q.sources.map((s) => (
              <li key={s.url}>
                <a href={s.url} target="_blank" rel="noopener noreferrer">
                  {s.url}
                </a>{" "}
                <span className="muted">{t("review.checked", { date: formatDate(s.checked) })}</span>
              </li>
            ))}
          </ul>
          {q.glossary.length > 0 && (
            <p className="chips">
              <span className="small muted">{t("review.glossary")}:</span>
              {q.glossary.map((g) => (
                <span key={g} className="chip">
                  {g}
                </span>
              ))}
            </p>
          )}
        </div>
        <div>
          <dl className="facts">
            <dt>{t("review.difficulty")}</dt>
            <dd>
              <DifficultyDots level={q.difficulty} />
            </dd>
            <dt>{t("review.fileStatus")}</dt>
            <dd>{t(`review.status.${q.file_status}`, { defaultValue: q.file_status })}</dd>
            <dt>{t("review.imported")}</dt>
            <dd className="small">
              {formatDate(q.imported_at)} · <code>{q.content_hash.slice(0, 10)}</code>
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
          {q.reports && q.reports.length > 0 && (
            <ul className="small">
              {q.reports.map((r) => (
                <li key={r.id}>
                  {formatDate(r.created_at)} {r.lang && <span className="chip">{t(`languages.${r.lang}`, { defaultValue: r.lang })}</span>}{" "}
                  {r.comment || <span className="muted">{t("qbank.noComment")}</span>}
                </li>
              ))}
            </ul>
          )}
          <h3>{t("review.translations")}</h3>
          {q.translations_missing && <p className="small muted">{t("review.translationsMissing")}</p>}
          <table className="table">
            <tbody>
              {(q.translations ?? []).map((tr) => (
                <tr key={tr.lang}>
                  <td>{t(`languages.${tr.lang}`, { defaultValue: tr.lang })}</td>
                  <td>
                    <span className={`status status-${tr.state}`}>{t(`review.tstate.${tr.state}`)}</span>
                  </td>
                  <td className="small muted">
                    {tr.source_version !== null && t("review.sourceVersion", { version: tr.source_version })}
                    {tr.reviewed_by && ` · ${tr.reviewed_by}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {!retired && (
        <button type="button" className="link-btn" aria-expanded={editing} onClick={() => setEditing((e) => !e)}>
          {editing ? t("review.hideEdit") : t("review.edit")}
        </button>
      )}
      {editing && !retired && (
        <div className="form edit-form">
          {field(t("review.question"), <textarea rows={3} value={edits.question_de} onChange={(e) => set("question_de", e.target.value)} />)}
          <div className="grid-2">
            {OPTION_KEYS.map((k) => (
              <div key={k}>
                {field(
                  `${t("review.options")} ${k.toUpperCase()}`,
                  <input value={edits.options_de[k]} onChange={(e) => set("options_de", { ...edits.options_de, [k]: e.target.value })} />,
                )}
              </div>
            ))}
          </div>
          <div className="grid-2">
            {field(
              t("review.answer"),
              <select value={edits.correct} onChange={(e) => set("correct", e.target.value as OptionKey)}>
                {OPTION_KEYS.map((k) => (
                  <option key={k} value={k}>
                    {k.toUpperCase()}
                  </option>
                ))}
              </select>,
            )}
            {field(
              t("review.difficulty"),
              <select value={edits.difficulty} onChange={(e) => set("difficulty", Number(e.target.value))}>
                {[1, 2, 3].map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>,
            )}
            {field(
              t("review.topicCode"),
              <select value={edits.topic_code} onChange={(e) => set("topic_code", e.target.value)}>
                {!topicChoices.some((tp) => tp.code === edits.topic_code) && <option value={edits.topic_code}>{edits.topic_code}</option>}
                {topicChoices.map((tp) => (
                  <option key={tp.code} value={tp.code}>
                    {topicName(tp.code)}
                  </option>
                ))}
              </select>,
            )}
          </div>
          {field(t("review.explanation"), <textarea rows={4} value={edits.explanation_de} onChange={(e) => set("explanation_de", e.target.value)} />)}
        </div>
      )}

      <form className="form review-actions" onSubmit={(e: FormEvent) => e.preventDefault()}>
        <div className="grid-2">
          {field(
            t("review.note"),
            <>
              <input value={note} maxLength={2000} onChange={(e) => setNote(e.target.value)} />
              <span className="hint">{t("review.noteHint")}</span>
            </>,
          )}
          {field(
            t("review.minutes"),
            <input type="number" min={0} max={120} value={minutes} onChange={(e) => setMinutes(Math.max(0, Math.min(120, Number(e.target.value) || 0)))} />,
          )}
        </div>
        <p className="small muted">{t("review.dbOnlyHint")}</p>
        {error ? <ErrorText error={error} /> : null}
        {!retired && (
          <div className="actions">
            <button type="button" className="btn btn-primary" disabled={busy !== null} onClick={() => void act("approve")}>
              {busy === "approve" ? t("common.working") : changes ? t("review.approveEdits") : t("review.approve")}
            </button>
            <button type="button" className="btn btn-secondary" disabled={busy !== null || !note.trim() || !!changes} onClick={() => void act("send_back")}>
              {t("review.sendBack")}
            </button>
            <button type="button" className="btn btn-danger" disabled={busy !== null || !!changes} onClick={() => void act("retire")}>
              {t("review.retire")}
            </button>
          </div>
        )}
      </form>
    </section>
  );
}
