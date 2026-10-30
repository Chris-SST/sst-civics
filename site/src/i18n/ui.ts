// Interface copy for the template pages (home, calculator, FAQ, free practice, 404) and the
// shared chrome. German and English are written out; every other language falls back to the
// English strings and the page shows a note saying the full pages exist in German and English.
// The content writer fills the key pages in the other languages later.
import { COPY_LOCALES } from "./pages.mjs";

export interface CalcStrings {
  title: string;
  intro: string;
  dobLabel: string;
  dobHint: string;
  periodsLegend: string;
  from: string;
  to: string;
  toHint: string;
  addPeriod: string;
  removePeriod: string;
  submit: string;
  idle: string;
  errDob: string;
  errPeriod: string;
  errNone: string;
  resActual: string;
  resDouble: string;
  resCounted: string;
  resRule: string;
  resShort: string;
  resOk: string;
  resNote: string;
  years: string;
  privacy: string;
  disclaimer: string;
  ruleTitle: string;
  ruleText: string;
}

export interface Ui {
  skip: string;
  homeLabel: string;
  langLabel: string;
  navFree: string;
  navFaq: string;
  navApp: string;
  fallbackNote: string;
  fallbackGerman: string;
  fallbackEnglish: string;
  placeholderNote: string;
  toc: string;
  lastChecked: string;
  reviewed: string;
  sourcesHeading: string;
  cta: Record<"free-questions" | "mock" | "pass", { heading: string; text: string; button: string }>;
  home: { title: string; description: string; h1: string; lead: string; cardsHeading: string; soon: string };
  cards: Record<string, { title: string; text: string }>;
  calcPage: { title: string; description: string; h1: string };
  calc: CalcStrings;
  faqPage: { title: string; description: string; h1: string; empty: string; more: string };
  free: { title: string; description: string; h1: string; lead: string; points: string[]; how: string; howText: string; button: string; mockNote: string };
  notFound: { title: string; text: string; back: string };
}

const en: Ui = {
  skip: "Skip to content",
  homeLabel: "Home",
  langLabel: "Language",
  navFree: "Free practice",
  navFaq: "FAQ",
  navApp: "Open the app",
  fallbackNote: "The full pages of this guide are available in German and English.",
  fallbackGerman: "Read in German",
  fallbackEnglish: "Read in English",
  placeholderNote: "Placeholder page: the real content follows.",
  toc: "On this page",
  lastChecked: "Last checked",
  reviewed: "We review this page every year.",
  sourcesHeading: "Sources and last checked",
  cta: {
    "free-questions": {
      heading: "Ready to practise?",
      text: "Try 30 sample questions in your own language, with the German beside them. No account needed.",
      button: "Try 30 free questions",
    },
    mock: {
      heading: "Ready for a mock test?",
      text: "Sign up with your email for one free mock test, then see how you do under test conditions.",
      button: "Take the free mock test",
    },
    pass: {
      heading: "Want to prepare fully?",
      text: "The Civics Pass opens every question and study mode for your canton. Start with the free questions.",
      button: "Try 30 free questions",
    },
  },
  home: {
    title: "Becoming Swiss: the knowledge test explained",
    description:
      "Plain guidance on naturalisation in Switzerland: the order of the steps, residence, fees, language certificates and the knowledge test, with free practice questions.",
    h1: "Becoming Swiss: the steps, in plain language",
    lead: "Naturalisation has a clear order: residence, documents, language, the knowledge test, then the application. Start with the overview, or jump to the part you need.",
    cardsHeading: "Guides and tools",
    soon: "Coming soon",
  },
  cards: {
    overview: { title: "Overview", text: "Federal requirements, the order of steps and how long it takes." },
    zurich: { title: "Zurich, step by step", text: "Residence rules, documents, fees, timeline and where to apply." },
    test: { title: "The knowledge test", text: "Format, topics and how to prepare." },
    language: { title: "Language certificates", text: "Which ones count, which levels, prices and where to take them." },
    fees: { title: "Fees", text: "Federal, cantonal and typical communal fees." },
    calculator: { title: "Residence-years calculator", text: "Count your years. It runs in your browser and sends nothing." },
    free: { title: "Free practice", text: "30 sample questions with translations. No account needed." },
    faq: { title: "Questions and answers", text: "Short answers that link to the guides." },
  },
  calcPage: {
    title: "Residence-years calculator",
    description:
      "Count your years of residence in Switzerland, with the years between ages 8 and 18 counted twice. Runs in your browser; nothing is sent.",
    h1: "Residence-years calculator",
  },
  calc: {
    title: "Count your years",
    intro:
      "Enter when you were born and the periods you have lived in Switzerland. The tool counts the years between your 8th and 18th birthdays twice.",
    dobLabel: "Date of birth",
    dobHint: "Used only for the 8 to 18 rule, in this browser.",
    periodsLegend: "Periods of residence in Switzerland",
    from: "From",
    to: "To",
    toHint: "Leave empty if you still live here.",
    addPeriod: "Add a period",
    removePeriod: "Remove",
    submit: "Count my years",
    idle: "Enter your dates and press the button.",
    errDob: "Check this: enter your date of birth.",
    errPeriod: "Check this: each period needs a start date, and the end must not be before the start.",
    errNone: "Check this: add at least one period of residence.",
    resActual: "Years actually lived in Switzerland",
    resDouble: "Extra years for ages 8 to 18",
    resCounted: "Counted years",
    resRule: "The federal rule asks for 10 counted years, with at least 6 years of actual residence.",
    resShort: "Actual residence is under 6 years, so the double counting cannot make up the difference.",
    resOk: "On these dates the counted years reach 10 and the actual years reach 6.",
    resNote: "Also check the requirement of 3 years in the last 5 before you apply, and your canton's and commune's own conditions.",
    years: "years",
    privacy: "This runs in your browser only. Nothing you enter is sent, stored or logged.",
    disclaimer: "General information, not legal advice. It is an estimate for planning, not a decision on your application.",
    ruleTitle: "How the count works",
    ruleText:
      "Time lived in Switzerland between your 8th and 18th birthdays counts twice. Overlapping periods are counted once. The doubled time cannot replace actual residence: at least six years must be real years lived here. Your commune and canton may add their own minimum periods; check their pages.",
  },
  faqPage: {
    title: "Frequently asked questions",
    description: "Short answers about naturalisation, the knowledge test and the practice questions, with links to the guides.",
    h1: "Frequently asked questions",
    empty: "Questions and answers follow.",
    more: "Not answered here? Start with the overview.",
  },
  free: {
    title: "Free practice: 30 sample questions",
    description:
      "Try 30 sample questions for the knowledge test, in your language with the German beside them. No account needed.",
    h1: "Free practice: 30 sample questions",
    lead: "See how the questions work before you decide anything. The 30 sample questions are free and need no account.",
    points: [
      "Each question appears in German, the language of the test, with a translation beside it.",
      "You get an explanation after every answer.",
      "After you sign up with your email you can also take one free mock test.",
    ],
    how: "How it works",
    howText:
      "The practice runs in the app, not on this website. Choose your language and start; you can switch the translation off whenever you like.",
    button: "Try 30 free questions",
    mockNote: "This service is independent. The real knowledge test is set by your canton, in German.",
  },
  notFound: {
    title: "Page not found",
    text: "This page does not exist, or it has moved. Try the home page or the overview.",
    back: "Back to the home page",
  },
};

const de: Ui = {
  skip: "Zum Inhalt springen",
  homeLabel: "Startseite",
  langLabel: "Sprache",
  navFree: "Gratis üben",
  navFaq: "FAQ",
  navApp: "App öffnen",
  fallbackNote: "Die vollständigen Seiten dieses Ratgebers gibt es auf Deutsch und auf Englisch.",
  fallbackGerman: "Auf Deutsch lesen",
  fallbackEnglish: "Auf Englisch lesen",
  placeholderNote: "Platzhalterseite: der eigentliche Inhalt folgt.",
  toc: "Auf dieser Seite",
  lastChecked: "Zuletzt geprüft",
  reviewed: "Wir überprüfen diese Seite jedes Jahr.",
  sourcesHeading: "Quellen und letzte Prüfung",
  cta: {
    "free-questions": {
      heading: "Bereit zum Üben?",
      text: "Probieren Sie 30 Beispielfragen in Ihrer Sprache aus, mit dem deutschen Text daneben. Ohne Konto.",
      button: "30 Fragen gratis testen",
    },
    mock: {
      heading: "Bereit für eine Probeprüfung?",
      text: "Melden Sie sich mit Ihrer E-Mail-Adresse an und machen Sie eine Probeprüfung gratis, unter Prüfungsbedingungen.",
      button: "Gratis-Probeprüfung starten",
    },
    pass: {
      heading: "Gründlich vorbereiten?",
      text: "Der Civics Pass schaltet alle Fragen und Lernmodi für Ihren Kanton frei. Beginnen Sie mit den Gratisfragen.",
      button: "30 Fragen gratis testen",
    },
  },
  home: {
    title: "Schweizer werden: der Wissenstest erklärt",
    description:
      "Verständliche Hinweise zur Einbürgerung in der Schweiz: Ablauf, Aufenthaltsdauer, Gebühren, Sprachnachweise und Wissenstest, mit Gratis-Übungsfragen.",
    h1: "Schweizer werden: die Schritte, einfach erklärt",
    lead: "Die Einbürgerung folgt einer klaren Reihenfolge: Aufenthalt, Unterlagen, Sprache, Wissenstest, dann das Gesuch. Beginnen Sie mit der Übersicht oder springen Sie zum Teil, den Sie brauchen.",
    cardsHeading: "Ratgeber und Werkzeuge",
    soon: "Folgt in Kürze",
  },
  cards: {
    overview: { title: "Überblick", text: "Bundesvoraussetzungen, Reihenfolge der Schritte und Dauer." },
    zurich: { title: "Zürich, Schritt für Schritt", text: "Aufenthalt, Unterlagen, Gebühren, Zeitplan und Anmeldung." },
    test: { title: "Der Wissenstest", text: "Aufbau, Themen und Vorbereitung." },
    language: { title: "Sprachnachweise", text: "Welche zählen, welche Niveaus, Preise und Prüfungsorte." },
    fees: { title: "Gebühren", text: "Gebühren von Bund, Kanton und Gemeinde im Überblick." },
    calculator: { title: "Rechner für Aufenthaltsjahre", text: "Zählen Sie Ihre Jahre. Läuft im Browser und sendet nichts." },
    free: { title: "Gratis üben", text: "30 Beispielfragen mit Übersetzung. Ohne Konto." },
    faq: { title: "Häufige Fragen", text: "Kurze Antworten mit Links zu den Ratgebern." },
  },
  calcPage: {
    title: "Rechner für Aufenthaltsjahre",
    description:
      "Zählen Sie Ihre Aufenthaltsjahre in der Schweiz, wobei die Jahre zwischen 8 und 18 doppelt zählen. Läuft im Browser; nichts wird gesendet.",
    h1: "Rechner für Aufenthaltsjahre",
  },
  calc: {
    title: "Jahre zählen",
    intro:
      "Geben Sie Ihr Geburtsdatum und Ihre Aufenthaltsperioden in der Schweiz ein. Die Jahre zwischen dem 8. und dem 18. Geburtstag werden doppelt gezählt.",
    dobLabel: "Geburtsdatum",
    dobHint: "Wird nur für die Regel 8 bis 18 verwendet, in diesem Browser.",
    periodsLegend: "Aufenthaltsperioden in der Schweiz",
    from: "Von",
    to: "Bis",
    toHint: "Leer lassen, wenn Sie noch hier wohnen.",
    addPeriod: "Periode hinzufügen",
    removePeriod: "Entfernen",
    submit: "Jahre zählen",
    idle: "Geben Sie Ihre Daten ein und drücken Sie die Taste.",
    errDob: "Bitte prüfen: Geben Sie Ihr Geburtsdatum ein.",
    errPeriod: "Bitte prüfen: Jede Periode braucht ein Startdatum, und das Ende darf nicht vor dem Start liegen.",
    errNone: "Bitte prüfen: Fügen Sie mindestens eine Aufenthaltsperiode hinzu.",
    resActual: "Tatsächlich in der Schweiz verbrachte Jahre",
    resDouble: "Zusätzliche Jahre für das Alter 8 bis 18",
    resCounted: "Angerechnete Jahre",
    resRule: "Die Bundesregel verlangt 10 angerechnete Jahre, davon mindestens 6 Jahre tatsächlicher Aufenthalt.",
    resShort: "Der tatsächliche Aufenthalt beträgt weniger als 6 Jahre; die Doppelzählung kann das nicht ausgleichen.",
    resOk: "Mit diesen Daten erreichen die angerechneten Jahre 10 und die tatsächlichen Jahre 6.",
    resNote: "Prüfen Sie zusätzlich die Bedingung von 3 Jahren in den letzten 5 vor dem Gesuch sowie die Bedingungen Ihres Kantons und Ihrer Gemeinde.",
    years: "Jahre",
    privacy: "Die Berechnung läuft nur in Ihrem Browser. Nichts, was Sie eingeben, wird gesendet, gespeichert oder protokolliert.",
    disclaimer: "Allgemeine Informationen, keine Rechtsberatung. Es ist eine Schätzung zur Planung, kein Entscheid über Ihr Gesuch.",
    ruleTitle: "So wird gezählt",
    ruleText:
      "Die Zeit in der Schweiz zwischen dem 8. und dem 18. Geburtstag zählt doppelt. Sich überschneidende Perioden werden nur einmal gezählt. Die doppelt gezählte Zeit kann den tatsächlichen Aufenthalt nicht ersetzen: Mindestens sechs Jahre müssen wirklich hier verbracht worden sein. Kanton und Gemeinde können eigene Mindestfristen verlangen; lesen Sie deren Seiten.",
  },
  faqPage: {
    title: "Häufige Fragen",
    description: "Kurze Antworten zur Einbürgerung, zum Wissenstest und zu den Übungsfragen, mit Links zu den Ratgebern.",
    h1: "Häufige Fragen",
    empty: "Fragen und Antworten folgen.",
    more: "Nicht beantwortet? Beginnen Sie mit der Übersicht.",
  },
  free: {
    title: "Gratis üben: 30 Beispielfragen",
    description:
      "Probieren Sie 30 Beispielfragen für den Wissenstest aus, in Ihrer Sprache mit dem deutschen Text daneben. Ohne Konto.",
    h1: "Gratis üben: 30 Beispielfragen",
    lead: "Sehen Sie, wie die Fragen funktionieren, bevor Sie sich entscheiden. Die 30 Beispielfragen sind gratis und brauchen kein Konto.",
    points: [
      "Jede Frage erscheint auf Deutsch, der Sprache des Tests, mit einer Übersetzung daneben.",
      "Nach jeder Antwort erhalten Sie eine Erklärung.",
      "Nach der Anmeldung mit Ihrer E-Mail-Adresse können Sie zusätzlich eine Probeprüfung gratis machen.",
    ],
    how: "So funktioniert es",
    howText:
      "Das Üben läuft in der App, nicht auf dieser Website. Wählen Sie Ihre Sprache und legen Sie los; die Übersetzung können Sie jederzeit ausblenden.",
    button: "30 Fragen gratis testen",
    mockNote: "Dieser Dienst ist unabhängig. Den echten Wissenstest legt Ihr Kanton fest, auf Deutsch.",
  },
  notFound: {
    title: "Seite nicht gefunden",
    text: "Diese Seite gibt es nicht oder sie ist umgezogen. Versuchen Sie die Startseite oder den Überblick.",
    back: "Zur Startseite",
  },
};

export function ui(lang: string): Ui {
  return lang === "de" ? de : en;
}

/** True when this language shows English chrome with the "full pages in German and English" note. */
export function usesFallback(lang: string): boolean {
  return !COPY_LOCALES.includes(lang);
}

// Independence notice, copied from web/src/locales/*.json key footer.independence (do not import
// the app's files). Update here when the app's strings change.
export const INDEPENDENCE: Record<string, string> = {
  de: "Unabhängiger Dienst ohne Verbindung zu Bundes-, Kantons- oder Gemeindebehörden. Allgemeine Informationen, keine Rechtsberatung.",
  en: "Independent service, not connected to any federal, cantonal or communal authority. General information, not legal advice.",
  fr: "Service indépendant, sans lien avec une autorité fédérale, cantonale ou communale. Informations générales, pas de conseil juridique.",
  it: "Servizio indipendente, non collegato ad alcuna autorità federale, cantonale o comunale. Informazioni generali, non consulenza legale.",
  pt: "Serviço independente, sem ligação a qualquer autoridade federal, cantonal ou municipal. Informação geral, não aconselhamento jurídico.",
  es: "Servicio independiente, sin vinculación con ninguna autoridad federal, cantonal ni municipal. Información general, no asesoramiento jurídico.",
  sq: "Shërbim i pavarur, pa lidhje me asnjë autoritet federal, kantonal apo komunal. Informacion i përgjithshëm, jo këshillim juridik.",
  tr: "Federal, kantonal veya yerel hiçbir makamla bağlantısı olmayan bağımsız bir hizmettir. Genel bilgidir, hukuki danışmanlık değildir.",
};
