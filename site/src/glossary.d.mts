export type GlossaryEntry = {
  id: string;
  term: string;
  translation: string;
  note: string;
  keepGerman: boolean;
  fallback: boolean;
  noteFallback: boolean;
};
export function glossaryDir(): string;
export function anchorFor(term: string): string;
export function glossaryFor(lang: string): GlossaryEntry[];
