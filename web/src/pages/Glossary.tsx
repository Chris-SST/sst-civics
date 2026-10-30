import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { get } from "../api";
import ErrorText from "../components/ErrorText";

interface GlossaryOut {
  lang: string;
  terms: { term: string; translation: string; note: string | null; reviewed: boolean }[];
}

/** The key terms of the test for the learner's study language: the German term as it appears in
 * the questions, its translation and a short note. Searchable; free for everyone. */
export default function Glossary() {
  const { t } = useTranslation();
  const [data, setData] = useState<GlossaryOut | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    get<GlossaryOut>("/api/study/glossary").then(setData).catch(setError);
  }, []);

  const shown = useMemo(() => {
    const q = query.trim().toLocaleLowerCase();
    if (!data) return [];
    if (!q) return data.terms;
    return data.terms.filter((g) => [g.term, g.translation, g.note ?? ""].some((x) => x.toLocaleLowerCase().includes(q)));
  }, [data, query]);

  return (
    <>
      <header className="page-head">
        <div>
          <Link to="/learner" className="small">
            {"←"} {t("practice.back")}
          </Link>
          <h1>{t("glossary.title")}</h1>
          <p className="small muted">{t("glossary.intro")}</p>
        </div>
      </header>
      {error ? <ErrorText error={error} /> : null}
      {!data && !error && <p className="muted">{"…"}</p>}
      {data && data.terms.length === 0 && <p className="alert alert-info">{t("glossary.none")}</p>}
      {data && data.terms.length > 0 && (
        <section className="card glossary-card">
          <label className="field glossary-search">
            <span>{t("glossary.search")}</span>
            <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t("glossary.searchPlaceholder")} />
          </label>
          <p className="small muted" aria-live="polite">
            {t("glossary.count", { count: shown.length })}
          </p>
          {shown.length === 0 ? (
            <p className="muted">{t("glossary.noMatch")}</p>
          ) : (
            <div className="table-wrap">
              <table className="table table-stack glossary-table">
                <thead>
                  <tr>
                    <th>{t("glossary.german")}</th>
                    <th>{t("glossary.translation")}</th>
                    <th>{t("glossary.note")}</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((g) => (
                    <tr key={g.term}>
                      <td data-label={t("glossary.german")} lang="de">
                        <b>{g.term}</b>
                      </td>
                      <td data-label={t("glossary.translation")} lang={data.lang}>
                        {g.translation}
                        {!g.reviewed && <span className="small muted"> · {t("glossary.unconfirmed")}</span>}
                      </td>
                      <td data-label={t("glossary.note")} lang={data.lang} className="small">
                        {g.note}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </>
  );
}
