/** CHF with the Swiss apostrophe as thousands separator: 1250 -> "CHF 1’250", 800.5 -> "CHF 800.50". */
export function chf(amount: number): string {
  const hasCents = Math.round(amount * 100) % 100 !== 0;
  const [int, dec] = Math.abs(amount).toFixed(hasCents ? 2 : 0).split(".");
  const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, "’");
  return `${amount < 0 ? "-" : ""}CHF ${grouped}${dec ? "." + dec : ""}`;
}

const LOCALE_TAG: Record<string, string> = {
  de: "de-CH",
  en: "en-GB",
  fr: "fr-CH",
  it: "it-CH",
  pt: "pt-PT",
  es: "es-ES",
  sq: "sq-AL",
  tr: "tr-TR",
};

export function longDate(d: Date, lang: string): string {
  return new Intl.DateTimeFormat(LOCALE_TAG[lang] ?? "en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(d);
}

export function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** Plain-text version of a Markdown answer, for FAQ structured data. */
export function plainText(md: string): string {
  return md
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/[*_`>#]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}
