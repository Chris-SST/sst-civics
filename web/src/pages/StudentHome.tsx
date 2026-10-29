import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { get, post } from "../api";
import { useAuth } from "../auth";
import ErrorText from "../components/ErrorText";
import { formatDate } from "../i18n";

interface Topic {
  code: string;
  name: string;
}
interface Course {
  key: string;
  name: string;
  level: string;
  topics: Topic[];
}
interface Recent {
  id: string;
  course_name: string;
  topic_name: string;
  status: "active" | "ended";
  last_activity_at: string;
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
interface Overview {
  tutor_name: string;
  tutor_enabled: boolean;
  access: "full" | "read_only" | "none";
  notice_seen: boolean;
  courses: Course[];
  usage: Usage;
  recent: Recent[];
}

export default function StudentHome() {
  const { t } = useTranslation();
  const { me } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [courseKey, setCourseKey] = useState("");
  const [topicCode, setTopicCode] = useState("");
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    get<Overview>("/api/tutor/overview")
      .then((d) => {
        setData(d);
        if (d.courses.length === 1) setCourseKey(d.courses[0].key);
      })
      .catch(setError);
  }, []);

  if (!data) return error ? <ErrorText error={error} /> : <p className="muted">…</p>;

  const course = data.courses.find((c) => c.key === courseKey);
  const canStart = data.access === "full" && data.tutor_enabled;

  async function acknowledge() {
    try {
      await post("/api/tutor/notice-seen");
      setData((d) => (d ? { ...d, notice_seen: true } : d));
    } catch (e) {
      setError(e);
    }
  }

  async function start() {
    if (!course || !topicCode) return;
    setStarting(true);
    setError(null);
    try {
      const conv = await post<{ id: string }>("/api/tutor/conversations", {
        course_key: course.key,
        topic_code: topicCode,
      });
      navigate(`/student/chat/${conv.id}`);
    } catch (e) {
      setError(e);
      setStarting(false);
    }
  }

  return (
    <>
      <h1>{t("student.hello", { name: me?.user.first_name || me?.user.email || "" })}</h1>

      {!data.notice_seen && canStart && (
        <section className="card notice-card">
          <h2>{t("student.noticeTitle", { name: data.tutor_name })}</h2>
          <p>{t("student.noticeBody")}</p>
          <button type="button" className="btn btn-primary" onClick={acknowledge}>
            {t("student.noticeOk")}
          </button>
        </section>
      )}

      <div className="grid-2">
        <section className="card">
          <h2>{t("student.startSession")}</h2>
          {data.access !== "full" && (
            <p className="alert alert-warn">
              <span className={`status status-${data.access}`}>{t(`access.${data.access}`)}</span>{" "}
              {t("student.askParent")}
            </p>
          )}
          {data.access === "full" && !data.tutor_enabled && (
            <p className="alert alert-info">{t("student.tutorOffline")}</p>
          )}
          {data.courses.length === 0 ? (
            <p className="muted">{t("student.noCourses")}</p>
          ) : (
            <>
              <label className="field">
                <span>{t("student.course")}</span>
                <select
                  value={courseKey}
                  onChange={(e) => {
                    setCourseKey(e.target.value);
                    setTopicCode("");
                  }}
                  disabled={!canStart}
                >
                  <option value="">{t("student.chooseCourse")}</option>
                  {data.courses.map((c) => (
                    <option key={c.key} value={c.key}>
                      {c.name} {c.level && `(${c.level})`}
                    </option>
                  ))}
                </select>
              </label>
              {course && (
                <label className="field">
                  <span>{t("student.topic")}</span>
                  <select
                    value={topicCode}
                    onChange={(e) => setTopicCode(e.target.value)}
                    disabled={!canStart}
                  >
                    <option value="">{t("student.chooseTopic")}</option>
                    {course.topics.map((tp) => (
                      <option key={tp.code} value={tp.code}>
                        {tp.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <div className="actions">
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={!canStart || !courseKey || !topicCode || starting}
                  onClick={start}
                >
                  {starting ? t("common.working") : t("student.start")}
                </button>
              </div>
            </>
          )}
          {error ? <ErrorText error={error} /> : null}
          <p className="small muted">{t("student.integrity")}</p>
        </section>

        <section className="card">
          <h2>{t("student.recent")}</h2>
          {data.recent.length === 0 ? (
            <p className="muted">{t("student.noRecent")}</p>
          ) : (
            <ul className="recent-list">
              {data.recent.map((r) => (
                <li key={r.id}>
                  <Link to={`/student/chat/${r.id}`}>
                    <b>{r.topic_name}</b>
                    <span className="small muted">
                      {r.course_name} · {formatDate(r.last_activity_at)}
                      {r.status === "ended" && ` · ${t("student.endedTag")}`}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
          <h3>{t("student.usage")}</h3>
          <p className="small">
            {t("student.usageToday", {
              used: data.usage.daily_used,
              limit: data.usage.daily_limit ?? "∞",
            })}
            <br />
            {t("student.usageMonth", {
              used: data.usage.monthly_used,
              limit: data.usage.monthly_limit ?? "∞",
            })}
          </p>
          {data.usage.near_monthly_limit && (
            <p className="alert alert-warn small">{t("student.nearLimit")}</p>
          )}
        </section>
      </div>
    </>
  );
}
