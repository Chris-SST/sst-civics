import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink, Route, Routes, useParams } from "react-router-dom";
import { get, post } from "../api";
import ErrorText from "../components/ErrorText";
import QuestionReview, { StatsKpis, type ReviewModule, type ReviewStats } from "../components/QuestionReview";
import { formatDate } from "../i18n";

/** Admin: question bank overview, generation requests, batches, open reports and the review queue. */
export default function AdminQuestions() {
  const { t } = useTranslation();
  return (
    <>
      <nav className="tabs tabs-sub">
        <NavLink to="/admin/questions" end>
          {t("qbank.overview")}
        </NavLink>
        <NavLink to="/admin/questions/review">{t("qbank.reviewQueue")}</NavLink>
      </nav>
      <Routes>
        <Route index element={<Bank />} />
        <Route path="review" element={<QuestionReview />} />
        <Route path="review/:id" element={<ReviewById />} />
      </Routes>
    </>
  );
}

function ReviewById() {
  const { id } = useParams();
  return <QuestionReview initialQuestionId={id} />;
}

interface Batch {
  id: string;
  mode: "batch" | "direct";
  module_key: string;
  level: string;
  topic_codes: string[];
  difficulties: number[];
  per_request: number;
  language: string;
  status: string;
  requests: number;
  questions_created: number;
  error: string | null;
  created_at: string;
  ended_at: string | null;
}

interface Report {
  id: string;
  question_id: string;
  module_key: string;
  topic_code: string;
  comment: string | null;
  created_at: string;
  question_status: string;
}

function Bank() {
  const { t } = useTranslation();
  const [modules, setModules] = useState<ReviewModule[]>([]);
  const [stats, setStats] = useState<ReviewStats | null>(null);
  const [batches, setBatches] = useState<Batch[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [ok, setOk] = useState("");

  // Generation form
  const [moduleKey, setModuleKey] = useState("");
  const [level, setLevel] = useState<"sl" | "hl" | "both">("both");
  const [topics, setTopics] = useState<string[]>([]);
  const [allTopics, setAllTopics] = useState(true);
  const [difficulties, setDifficulties] = useState<number[]>([2, 3, 4]);
  const [perRequest, setPerRequest] = useState(5);
  const [language, setLanguage] = useState<"en" | "de" | "fr">("en");
  const [mode, setMode] = useState<"batch" | "direct">("batch");
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [m, s, b, r] = await Promise.all([
      get<ReviewModule[]>("/api/review/modules"),
      get<ReviewStats>("/api/review/stats"),
      get<Batch[]>("/api/review/batches"),
      get<Report[]>("/api/review/reports"),
    ]);
    setModules(m);
    setStats(s);
    setBatches(b);
    setReports(r);
    setModuleKey((k) => k || m[0]?.module_key || "");
  }, []);

  useEffect(() => {
    load().catch(setError);
  }, [load]);

  const mod = modules.find((m) => m.module_key === moduleKey);
  const moduleName = (key: string) => modules.find((m) => m.module_key === key)?.name ?? key;
  const topicsForLevel = (mod?.topics ?? []).filter((tp) => level === "both" || tp.levels.includes(level));

  async function generate(e: FormEvent) {
    e.preventDefault();
    if (!mod) return;
    setBusy("generate");
    setError(null);
    setOk("");
    try {
      const codes = allTopics ? topicsForLevel.map((tp) => tp.code) : topics;
      const batch = await post<Batch>("/api/review/generate", {
        module_key: moduleKey,
        level,
        topic_codes: codes,
        difficulties,
        per_request: perRequest,
        language,
        mode,
      });
      setOk(t("qbank.submitted", { count: batch.requests }));
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(null);
    }
  }

  async function poll(id: string) {
    setBusy(id);
    setError(null);
    try {
      const b = await post<Batch>(`/api/review/batches/${id}/poll`);
      setBatches((bs) => bs.map((x) => (x.id === b.id ? b : x)));
      setStats(await get<ReviewStats>("/api/review/stats"));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(null);
    }
  }

  const toggle = (list: number[], v: number) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v].sort());
  const requestsEstimate = (allTopics ? topicsForLevel.length : topics.length) * difficulties.length;

  return (
    <>
      {error ? <ErrorText error={error} /> : null}
      {ok && <div className="alert alert-ok">{ok}</div>}
      {stats && <StatsKpis stats={stats} modules={modules} />}

      <section className="card">
        <h2>{t("qbank.generate")}</h2>
        <form className="form" onSubmit={(e) => void generate(e)}>
          <div className="grid-2">
            <label className="field">
              <span>{t("review.module")}</span>
              <select
                value={moduleKey}
                onChange={(e) => {
                  setModuleKey(e.target.value);
                  setTopics([]);
                }}
              >
                {modules.map((m) => (
                  <option key={m.module_key} value={m.module_key}>
                    {m.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>{t("qbank.level")}</span>
              <select value={level} onChange={(e) => setLevel(e.target.value as typeof level)}>
                {(["sl", "hl", "both"] as const).map((l) => (
                  <option key={l} value={l}>
                    {t(`qbank.levels.${l}`)}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="field">
            <span>{t("qbank.topics")}</span>
            <label className="check">
              <input type="checkbox" checked={allTopics} onChange={(e) => setAllTopics(e.target.checked)} />
              <span>{t("qbank.allTopics")}</span>
            </label>
            {!allTopics && (
              <div className="check-grid">
                {topicsForLevel.map((tp) => (
                  <label className="check" key={tp.code}>
                    <input
                      type="checkbox"
                      checked={topics.includes(tp.code)}
                      onChange={(e) => setTopics((ts) => (e.target.checked ? [...ts, tp.code] : ts.filter((c) => c !== tp.code)))}
                    />
                    <span>
                      {tp.code} · {tp.name}
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>
          <div className="field">
            <span>{t("qbank.difficulties")}</span>
            <div className="check-row">
              {[1, 2, 3, 4, 5].map((d) => (
                <label className="check" key={d}>
                  <input type="checkbox" checked={difficulties.includes(d)} onChange={() => setDifficulties((ds) => toggle(ds, d))} />
                  <span>{d}</span>
                </label>
              ))}
            </div>
          </div>
          <div className="grid-2">
            <label className="field">
              <span>{t("qbank.perRequest")}</span>
              <input type="number" min={1} max={10} value={perRequest} onChange={(e) => setPerRequest(Math.max(1, Math.min(10, Number(e.target.value) || 1)))} />
            </label>
            <label className="field">
              <span>{t("qbank.language")}</span>
              <select value={language} onChange={(e) => setLanguage(e.target.value as typeof language)}>
                <option value="en">English</option>
                <option value="de">Deutsch</option>
                <option value="fr">Français</option>
              </select>
            </label>
          </div>
          <div className="field">
            <span>{t("qbank.mode")}</span>
            <label className="check">
              <input type="radio" name="mode" checked={mode === "batch"} onChange={() => setMode("batch")} />
              <span>{t("qbank.modeBatch")}</span>
            </label>
            <label className="check">
              <input type="radio" name="mode" checked={mode === "direct"} onChange={() => setMode("direct")} />
              <span>{t("qbank.modeDirect")}</span>
            </label>
            <span className="hint">{t("qbank.modeHelp")}</span>
          </div>
          <p className="small muted">
            {t("qbank.estimate", { requests: requestsEstimate, questions: requestsEstimate * perRequest })}
          </p>
          <div className="actions">
            <button className="btn btn-primary" disabled={busy !== null || !moduleKey || difficulties.length === 0 || (!allTopics && topics.length === 0)}>
              {busy === "generate" ? t("common.working") : t("qbank.submit")}
            </button>
          </div>
        </form>
      </section>

      <section className="card">
        <h2>{t("qbank.batches")}</h2>
        {batches.length === 0 ? (
          <p className="muted">{t("qbank.noBatches")}</p>
        ) : (
          <div className="table-wrap">
            <table className="table table-stack">
              <thead>
                <tr>
                  <th>{t("admin.received")}</th>
                  <th>{t("review.module")}</th>
                  <th>{t("qbank.mode")}</th>
                  <th>{t("review.statusLabel")}</th>
                  <th>{t("qbank.requests")}</th>
                  <th>{t("qbank.created")}</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {batches.map((b) => (
                  <tr key={b.id}>
                    <td data-label={t("admin.received")} className="small">
                      {formatDate(b.created_at)}
                    </td>
                    <td data-label={t("review.module")} className="small">
                      {moduleName(b.module_key)} · {b.level.toUpperCase()} · {b.language}
                      <br />
                      <span className="muted">
                        {b.topic_codes.length} {t("qbank.topics").toLowerCase()} · {t("qbank.difficulties").toLowerCase()} {b.difficulties.join(", ")} · {b.per_request}/
                        {t("qbank.perRequestShort")}
                      </span>
                    </td>
                    <td data-label={t("qbank.mode")}>{t(`qbank.modes.${b.mode}`)}</td>
                    <td data-label={t("review.statusLabel")}>
                      <span className={`status status-${b.status}`}>{t(`qbank.batchStatus.${b.status}`, { defaultValue: b.status })}</span>
                      {b.error && (
                        <div className="small" style={{ color: "var(--red)" }}>
                          {b.error}
                        </div>
                      )}
                    </td>
                    <td data-label={t("qbank.requests")}>{b.requests}</td>
                    <td data-label={t("qbank.created")}>{b.questions_created}</td>
                    <td className="table-actions">
                      {b.mode === "batch" && b.status === "submitted" && (
                        <button type="button" className="btn btn-sm btn-secondary" disabled={busy !== null} onClick={() => void poll(b.id)}>
                          {busy === b.id ? t("common.working") : t("qbank.checkNow")}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card">
        <h2>{t("qbank.reports")}</h2>
        {reports.length === 0 ? (
          <p className="muted">{t("qbank.noReports")}</p>
        ) : (
          <div className="table-wrap">
            <table className="table table-stack">
              <thead>
                <tr>
                  <th>{t("admin.received")}</th>
                  <th>{t("review.topic")}</th>
                  <th>{t("qbank.comment")}</th>
                  <th>{t("review.statusLabel")}</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {reports.map((r) => (
                  <tr key={r.id}>
                    <td data-label={t("admin.received")} className="small">
                      {formatDate(r.created_at)}
                    </td>
                    <td data-label={t("review.topic")} className="small">
                      {moduleName(r.module_key)} · {r.topic_code}
                    </td>
                    <td data-label={t("qbank.comment")}>{r.comment || <span className="muted">{t("qbank.noComment")}</span>}</td>
                    <td data-label={t("review.statusLabel")}>
                      <span className={`status status-${r.question_status}`}>{t(`review.status.${r.question_status}`, { defaultValue: r.question_status })}</span>
                    </td>
                    <td className="table-actions">
                      <Link to={`/admin/questions/review/${r.question_id}`} className="btn btn-sm btn-secondary">
                        {t("common.open")}
                      </Link>
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
