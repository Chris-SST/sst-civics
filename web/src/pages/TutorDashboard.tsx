import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes, useParams } from "react-router-dom";
import { get } from "../api";
import QuestionReview from "../components/QuestionReview";

interface Dash {
  first_name: string;
  tagged_courses: string[];
  available: boolean;
  queue: unknown[];
  time_log_minutes_this_month: number;
}

export default function TutorDashboard() {
  const { t } = useTranslation();
  const [dash, setDash] = useState<Dash | null>(null);

  useEffect(() => {
    get<Dash>("/api/tutor/dashboard").then(setDash).catch(() => setDash(null));
  }, []);

  if (!dash) return <p className="muted">…</p>;

  return (
    <>
      <h1>{t("tutor.title", { name: dash.first_name })}</h1>
      <nav className="tabs">
        <NavLink to="/tutor" end>
          {t("tutor.dashboardTab")}
        </NavLink>
        <NavLink to="/tutor/review">{t("review.tab")}</NavLink>
      </nav>
      <Routes>
        <Route index element={<Home dash={dash} />} />
        <Route path="review" element={<QuestionReview />} />
        <Route path="review/:id" element={<ReviewById />} />
      </Routes>
    </>
  );
}

function ReviewById() {
  // Deep link from the reports list: /tutor/review/<question id>
  const { id } = useParams();
  return <QuestionReview initialQuestionId={id} />;
}

function Home({ dash }: { dash: Dash }) {
  const { t } = useTranslation();
  return (
    <div className="grid-2">
      <section className="card">
        <h2>{t("tutor.queue")}</h2>
        <p className="muted">{t("tutor.queueEmpty")}</p>
      </section>
      <section className="card">
        <h2>{t("tutor.profile")}</h2>
        <p>
          <b>{t("tutor.courses")}:</b>{" "}
          {dash.tagged_courses.length
            ? dash.tagged_courses.map((c) => t(`courses.${c}`, { defaultValue: c })).join(", ")
            : t("tutor.noCourses")}
        </p>
        <p>
          <b>{t("tutor.availability")}:</b> {dash.available ? t("tutor.available") : t("tutor.away")}
        </p>
        <p>
          <b>{t("tutor.timeLog")}:</b> {dash.time_log_minutes_this_month} min
        </p>
      </section>
    </div>
  );
}
