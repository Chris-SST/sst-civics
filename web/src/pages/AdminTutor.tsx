import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { get } from "../api";
import ErrorText from "../components/ErrorText";
import { formatChf, formatDate } from "../i18n";

interface UsageOut {
  period_start: string;
  calls: number;
  cost_chf: number;
  input_tokens: number;
  cache_read_tokens: number;
  output_tokens: number;
  learner_messages: number;
  by_purpose: { purpose: string; calls: number; cost_chf: number; avg_latency_ms: number; errors: number }[];
  top_learners: { user_id: string; email: string | null; calls: number; cost_chf: number }[];
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
          <b>{data.learner_messages}</b>
          {t("usage.messages")}
        </div>
        <div className="kpi">
          <b>{data.calls}</b>
          {t("usage.calls")}
        </div>
        <div className="kpi">
          <b>{data.learner_messages ? formatChf(Math.round((data.cost_chf / data.learner_messages) * 100)) : "–"}</b>
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
        <h2>{t("usage.topLearners")}</h2>
        {data.top_learners.length === 0 ? (
          <p className="muted">{t("usage.noLearners")}</p>
        ) : (
          <div className="table-wrap">
            <table className="table table-stack">
              <thead>
                <tr>
                  <th>{t("usage.learner")}</th>
                  <th>{t("usage.calls")}</th>
                  <th>{t("usage.cost")}</th>
                </tr>
              </thead>
              <tbody>
                {data.top_learners.map((s) => (
                  <tr key={s.user_id}>
                    <td data-label={t("usage.learner")}>{s.email ?? s.user_id}</td>
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
