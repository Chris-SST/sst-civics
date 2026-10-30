/** Shapes returned by the practice API (/api/practice). */

export type QType = "mcq" | "numeric" | "short" | "structured";

export interface QuestionPublic {
  id: string;
  module_key?: string;
  topic_code: string;
  difficulty: number;
  qtype: QType;
  calculator_allowed: boolean;
  question_text: string;
  options: { key: string; text: string }[] | null;
  unit: string | null;
  marks: number;
  reviewed: boolean;
}

export interface TopicOverview {
  topic_code: string;
  topic_name: string;
  mastery: number | null;
  attempts: number;
  due: boolean;
  questions_available: number;
}

export interface PracticeOverview {
  course_key: string;
  topics: TopicOverview[];
  overall: number | null;
  questions_available: number;
  diagnostic: { id: string; status: "in_progress" | "done" | "skipped" } | null;
  next: TopicOverview[];
}

export interface DiagnosticOut {
  id: string;
  course_key: string;
  status: "in_progress" | "done" | "skipped";
  position: number;
  total: number;
  question: QuestionPublic | null;
  summary?: TopicOverview[];
  next?: TopicOverview[];
}

export interface MasteryOut {
  topic_code: string;
  mastery: number;
  /** Mastery before this attempt, so the change can be shown. */
  previous?: number;
}

/** A short round of distinct questions on one topic (GET /api/practice/round). */
export interface PracticeRound {
  course_key: string;
  topic_code: string;
  topic_name: string;
  mastery: number;
  attempts: number;
  /** Questions available on the topic, and how many of them the learner has never seen. */
  pool: number;
  unseen: number;
  questions: QuestionPublic[];
}

export interface AttemptOut {
  attempt_id: string;
  correct: boolean;
  score: number;
  feedback: string | null;
  ai_marked: boolean;
  answer: string;
  worked_solution: string;
  mastery: MasteryOut;
  diagnostic?: DiagnosticOut;
}

export type AttemptMode = "diagnostic" | "practice" | "check";

/** The diagnostic picks up to two questions per topic (app settings default). */
export function estimateDiagnosticSize(topics: TopicOverview[]): number {
  return topics.reduce((n, t) => n + Math.min(2, t.questions_available), 0);
}
