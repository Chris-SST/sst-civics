import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { get } from "../api";
import { useAuth } from "../auth";

interface Home {
  first_name: string;
  courses: string[];
  curriculum: string | null;
  access: "full" | "read_only" | "none";
  plan_key: string | null;
  tutor_name: string;
  tutor_available: boolean;
}

export default function StudentHome() {
  const { t } = useTranslation();
  const { me } = useAuth();
  const [home, setHome] = useState<Home | null>(null);

  useEffect(() => {
    get<Home>("/api/student/home").then(setHome).catch(() => setHome(null));
  }, []);

  if (!home) return <p className="muted">…</p>;

  return (
    <>
      <h1>{t("student.hello", { name: home.first_name || me?.user.email || "" })}</h1>
      <div className="alert alert-info">{t("student.aiNotice", { name: home.tutor_name })}</div>
      <div className="grid-2">
        <section className="card">
          <h2>{t("student.yourCourses")}</h2>
          {home.courses.length ? (
            <ul>
              {home.courses.map((c) => (
                <li key={c}>{t(`courses.${c}`, { defaultValue: c })}</li>
              ))}
            </ul>
          ) : (
            <p className="muted">{t("student.noCourses")}</p>
          )}
          <p className="small">
            <span className={`status status-${home.access}`}>{t(`access.${home.access}`)}</span>
          </p>
          {home.access === "none" && <p className="small">{t("student.askParent")}</p>}
        </section>
        <section className="card">
          <h2>{t("student.tutorTitle", { name: home.tutor_name })}</h2>
          <p>{t("student.comingSoon")}</p>
          <p className="small">{t("student.integrity")}</p>
        </section>
      </div>
    </>
  );
}
