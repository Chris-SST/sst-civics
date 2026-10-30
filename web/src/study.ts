/** Shapes returned by the study API (/api/study) and the mock test (/api/mock). The four study
 * modes are a rendering contract: the server says which mode it rendered and sends the blocks
 * that mode shows (app/study/modes.py). */

export type TopicScope = "federal" | "canton" | "commune";
export type StudyMode = "own" | "side" | "help" | "de";

/** In the order a question moves through them as the learner answers it correctly. */
export const STUDY_MODES: StudyMode[] = ["own", "side", "help", "de"];
export const TOPIC_SCOPES: TopicScope[] = ["federal", "canton", "commune"];

export interface OptionOut {
  key: string;
  text: string;
}

export interface TextBlock {
  lang: string;
  question: string;
  options: OptionOut[];
  /** Only when the answer is revealed (Learn cards, the mock-test review). */
  explanation?: string;
}

export interface Term {
  term: string;
  translation: string;
  note: string | null;
  /** False for a term the question links that does not occur word for word in the text. */
  in_text: boolean;
}

export interface QuestionProgress {
  mode: StudyMode;
  mode_reached: StudyMode;
  understood: boolean;
  known: boolean;
  seen: boolean;
  box: number;
}

export interface StudyQuestion {
  id: string;
  version?: number;
  topic_code: string;
  topic_name: string;
  difficulty: number;
  reviewed: boolean;
  requested_mode: StudyMode;
  /** The mode rendered: "de" when the requested mode needs a translation that is not there. */
  mode: StudyMode;
  fallback: boolean;
  lang: string;
  german: TextBlock;
  /** For "own" and "side" only. */
  translation: TextBlock | null;
  /** For "help" only. */
  terms: Term[];
  answer?: string;
  explanation?: { lang: string; text: string };
  progress?: QuestionProgress;
  /** Practise rounds: the mastery of the question's topic before answering. */
  topic_mastery?: number;
  /** Mock-test review: the option the learner gave, null when unanswered. */
  given?: string | null;
}

export interface TopicOverview {
  topic_code: string;
  topic_name: string;
  name_de: string;
  name_en: string;
  scope: TopicScope;
  target_questions: number;
  questions_total: number;
  questions_available: number;
  seen: number;
  understood: number;
  known: number;
  due: number;
  mastery: number;
}

export interface Readiness {
  value: number;
  /** i18n key of the label "practice estimate, not an official result". */
  label_key: string;
}

export interface MockRunSummary {
  id: string;
  status: "in_progress" | "finished" | "expired";
  started_at: string;
  deadline_at: string;
  finished_at: string | null;
  total: number;
  answered: number;
  score: number | null;
  pass_mark: number | null;
  passed: boolean | null;
  free: boolean;
}

export interface MockInfo {
  configured: boolean;
  questions: number | null;
  minutes: number | null;
  pass_mark: number | null;
  pass_mark_confirmed: boolean;
  pass_mark_label_key: string;
  enough_questions: boolean;
  paid: boolean;
  free_mock_used: boolean;
  can_start: boolean;
  active_run_id: string | null;
  recent: MockRunSummary[];
}

export interface StudyOverview {
  canton: string;
  study_language: string;
  free_tier: boolean;
  sample_size: number;
  questions_total: number;
  questions_available: number;
  topics: TopicOverview[];
  readiness: Readiness;
  due: number;
  mock: MockInfo;
}

export interface LearnOut {
  topic_code: string;
  topic_name: string;
  scope: TopicScope;
  mode: StudyMode;
  free_tier: boolean;
  cards: StudyQuestion[];
}

export interface PractiseRound {
  topic_code: string | null;
  topic_name: string | null;
  mastery: number | null;
  readiness: Readiness;
  free_tier: boolean;
  /** Questions the learner may practise, and how many of them were never answered. */
  pool: number;
  unseen: number;
  questions: StudyQuestion[];
}

export interface MasteryOut {
  topic_code: string;
  mastery: number;
  /** Mastery before this answer, so the change can be shown. */
  previous?: number;
}

export interface AnswerProgress {
  mode: StudyMode;
  previous_mode: StudyMode;
  moved_forward: boolean;
  mode_reached: StudyMode;
  understood: boolean;
  known: boolean;
  newly_understood: boolean;
  newly_known: boolean;
  box: number;
  due_at: string | null;
}

export interface AnswerOut {
  attempt_id: string;
  correct: boolean;
  score: number;
  /** The mode the answer was given in. */
  mode: StudyMode;
  /** The correct option key, a to d. */
  answer: string;
  answer_text: string | null;
  answer_text_translated: string | null;
  /** In the learner's study language when a translation is approved, else German. */
  explanation: { lang: string; text: string };
  explanation_de: string;
  progress: AnswerProgress;
  mastery: MasteryOut;
  readiness: Readiness;
}

export interface MockQuestion {
  id: string;
  question: string;
  options: OptionOut[];
}

export interface MockRunOut extends MockRunSummary {
  now: string;
  minutes: number;
  pass_mark_confirmed: boolean;
  pass_mark_label_key: string;
  seconds_left?: number;
  answers?: Record<string, string>;
  questions?: MockQuestion[];
  review?: StudyQuestion[];
}

/** A mock-test question as a German-only study question, for QuestionCard. */
export function mockQuestion(q: MockQuestion, index: number): StudyQuestion {
  return {
    id: q.id,
    topic_code: "",
    topic_name: "",
    difficulty: 0,
    reviewed: true,
    requested_mode: "de",
    mode: "de",
    fallback: false,
    lang: "de",
    german: { lang: "de", question: q.question, options: q.options },
    translation: null,
    terms: [],
    version: index,
  };
}

export function learnUrl(topicCode?: string): string {
  return topicCode ? `/learn?topic=${encodeURIComponent(topicCode)}` : "/learn";
}

export function practiseUrl(topicCode?: string): string {
  return topicCode ? `/practise?topic=${encodeURIComponent(topicCode)}` : "/practise";
}
