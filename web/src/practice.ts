/** Shapes returned by the practice API (/api/practice) and the content API (/api/content). */

export type TopicScope = "federal" | "canton" | "commune";

export interface OptionOut {
  key: string;
  text: string;
}

export interface QuestionPublic {
  id: string;
  topic_code: string;
  topic_name: string;
  /** 1 to 3 */
  difficulty: number;
  /** The German question, as in the test. */
  question_text: string;
  options: OptionOut[];
  reviewed: boolean;
}

export interface TopicOverview {
  topic_code: string;
  topic_name: string;
  name_de: string;
  name_en: string;
  scope: TopicScope;
  mastery: number | null;
  attempts: number;
  due: boolean;
  questions_available: number;
}

export interface PracticeOverview {
  canton: string;
  topics: TopicOverview[];
  overall: number | null;
  questions_available: number;
  diagnostic_total_estimate: number;
  diagnostic: { id: string; status: "in_progress" | "done" | "skipped" } | null;
  next: TopicOverview[];
}

export interface DiagnosticOut {
  id: string;
  canton: string;
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
  /** The correct option key, a to d. */
  answer: string;
  answer_text: string | null;
  explanation: string;
  mastery: MasteryOut;
  diagnostic?: DiagnosticOut;
}

export type AttemptMode = "diagnostic" | "practice" | "check";

export const TOPIC_SCOPES: TopicScope[] = ["federal", "canton", "commune"];

export function practiceUrl(topicCode: string): string {
  return `/learner/practice?topic_code=${encodeURIComponent(topicCode)}`;
}
