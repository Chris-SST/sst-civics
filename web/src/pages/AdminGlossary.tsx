import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { get, patch } from "../api";
import ErrorText from "../components/ErrorText";
import { formatDate } from "../i18n";

interface Term {
  id: string;
  term: string;
  lang: string;
  translation: string;
  note: string | null;
  source: string | null;
  keep_german: boolean;
  status: "draft" | "reviewed";
  reviewed_by: string | null;
  reviewed_at: string | null;
  file_sync_pending: boolean;
}

interface GlossaryList {
  lang: string;
  languages: string[];
  reviewed: number;
  terms: Term[];
}

/** Admin: review the glossary of one language. Edits are saved to the database and marked as
 * waiting for the file (`scripts.content.sync_reviews` writes them to content/glossary/). */
export default function AdminGlossary() {
  const { t } = useTranslation();
  const [lang, setLang] = useState("en");
  const [data, setData] = useState<GlossaryList | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [translation, setTranslation] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (code: string) => {
    setData(null);
    setError(null);
    try {
      setData(await get<GlossaryList>(`/api/review/glossary?lang=${encodeURIComponent(code)}`));
    } catch (e) {
      setError(e);
    }
  }, []);

  useEffect(() => {
    void load(lang);
  }, [lang, load]);

  function startEdit(g: Term) {
    setEditing(g.id);
    setTranslation(g.translation);
    setNote(g.note ?? "");
  }

  async function save(g: Term, values: { translation: string; note: string | null; reviewed: boolean }) {
    setBusy(true);
    setError(null);
    try {
      const updated = await patch<Term>(`/api/review/glossary/${g.id}`, values);
      setData((d) =>
        d
          ? {
              ...d,
              terms: d.terms.map((x) => (x.id === g.id ? updated : x)),
              reviewed: d.terms.filter((x) => (x.id === g.id ? updated : x).status === "reviewed").length,
            }
          : d,
      );
      setEditing(null);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h2>{t("glossary.adminTitle")}</h2>
      <p className="small muted">{t("glossary.adminIntro")}</p>
      <div className="filters">
        <label className="field">
          <span>{t("qbank.language")}</span>
          <select value={lang} onChange={(e) => setLang(e.target.value)}>
            {(data?.languages ?? ["en", "fr", "it", "pt", "es", "sq", "tr"]).map((l) => (
              <option key={l} value={l}>
                {t(`languages.${l}`, { defaultValue: l })}
              </option>
            ))}
          </select>
        </label>
        {data && <p className="small muted">{t("glossary.reviewedCount", { reviewed: data.reviewed, total: data.terms.length })}</p>}
      </div>
      {error ? <ErrorText error={error} /> : null}
      {!data && !error && <p className="muted">{"…"}</p>}
      {data && data.terms.length === 0 && <p className="muted">{t("glossary.adminNone")}</p>}
      {data && data.terms.length > 0 && (
        <div className="table-wrap card">
          <table className="table table-stack">
            <thead>
              <tr>
                <th>{t("glossary.german")}</th>
                <th>{t("glossary.translation")}</th>
                <th>{t("glossary.note")}</th>
                <th>{t("glossary.source")}</th>
                <th>{t("review.statusLabel")}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.terms.map((g) => {
                const isEditing = editing === g.id;
                return (
                  <tr key={g.id}>
                    <td data-label={t("glossary.german")} lang="de">
                      <b>{g.term}</b>
                    </td>
                    <td data-label={t("glossary.translation")} lang={g.lang}>
                      {isEditing ? (
                        <label className="field">
                          <span className="visually-hidden">{t("glossary.translation")}</span>
                          <input value={translation} maxLength={200} onChange={(e) => setTranslation(e.target.value)} />
                        </label>
                      ) : (
                        g.translation
                      )}
                    </td>
                    <td data-label={t("glossary.note")} lang={g.lang} className="small">
                      {isEditing ? (
                        <label className="field">
                          <span className="visually-hidden">{t("glossary.note")}</span>
                          <textarea rows={3} value={note} maxLength={2000} onChange={(e) => setNote(e.target.value)} />
                        </label>
                      ) : (
                        g.note
                      )}
                    </td>
                    <td data-label={t("glossary.source")} className="small muted">
                      {g.source}
                    </td>
                    <td data-label={t("review.statusLabel")} className="small">
                      <span className={`status status-${g.status === "reviewed" ? "full" : "none"}`}>{t(`glossary.status.${g.status}`)}</span>
                      {g.status === "reviewed" && g.reviewed_by && (
                        <div className="muted">{t("glossary.reviewedBy", { name: g.reviewed_by, date: formatDate(g.reviewed_at) })}</div>
                      )}
                      {g.file_sync_pending && <div className="muted">{t("glossary.pendingSync")}</div>}
                    </td>
                    <td className="table-actions">
                      {isEditing ? (
                        <div className="actions">
                          <button
                            type="button"
                            className="btn btn-sm btn-primary"
                            disabled={busy || !translation.trim()}
                            onClick={() => void save(g, { translation: translation.trim(), note: note.trim() || null, reviewed: true })}
                          >
                            {t("glossary.saveReviewed")}
                          </button>
                          <button type="button" className="btn btn-sm btn-ghost" disabled={busy} onClick={() => setEditing(null)}>
                            {t("common.cancel")}
                          </button>
                        </div>
                      ) : (
                        <div className="actions">
                          <button type="button" className="btn btn-sm btn-secondary" disabled={busy || editing !== null} onClick={() => startEdit(g)}>
                            {t("glossary.edit")}
                          </button>
                          {g.status !== "reviewed" && (
                            <button
                              type="button"
                              className="btn btn-sm btn-ghost"
                              disabled={busy || editing !== null}
                              onClick={() => void save(g, { translation: g.translation, note: g.note, reviewed: true })}
                            >
                              {t("glossary.markReviewed")}
                            </button>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
