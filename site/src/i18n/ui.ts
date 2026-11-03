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
  ruleTitle: string;
  ruleText: string;
}

export interface Ui {
  skip: string;
  homeLabel: string;
  langLabel: string;
  mainNav: string;
  footerNav: string;
  navGuides: string;
  navFree: string;
  navFaq: string;
  navStart: string;
  navApp: string;
  legal: { nav: string; imprint: string; privacy: string; terms: string; contact: string; about: string };
  chat: {
    launcher: string;
    title: string;
    intro: string;
    note: string;
    placeholder: string;
    send: string;
    close: string;
    clear: string;
    remaining: string;
    limit: string;
    limitCta: string;
    busy: string;
    error: string;
    unavailable: string;
  };
  fallbackNote: string;
  fallbackGerman: string;
  fallbackEnglish: string;
  placeholderNote: string;
  toc: string;
  lastChecked: string;
  reviewed: string;
  sourcesHeading: string;
  cta: Record<"free-questions" | "mock" | "pass", { heading: string; text: string; button: string }>;
  home: {
    title: string;
    description: string;
    eyebrow: string;
    h1: string;
    lead: string;
    ctaFree: string;
    ctaGuide: string;
    trust: string[];
    q: { heading: string; daily: string; topic: string; german: string; right: string; wrong: string; more: string; reveal: string };
    how: { heading: string; steps: { title: string; text: string }[] };
    guidesHeading: string;
    groups: { swiss: string; zh: string };
    read: string;
    soon: string;
    tags: Record<string, string>;
    langs: { heading: string; text: string };
    pass: { badge: string; period: string; pay: string; points: string[]; button: string };
  };
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
  mainNav: "Main",
  footerNav: "Guides",
  navGuides: "Guides",
  navFree: "Free practice",
  navFaq: "FAQ",
  navStart: "Start free",
  navApp: "Open the app",
  legal: { nav: "Legal", imprint: "Imprint", privacy: "Privacy", terms: "Terms of use", contact: "Contact", about: "About Viapunt" },
  chat: {
    launcher: "Ask a question",
    title: "Ask Viapunt",
    intro: "Ask about the knowledge test, its topics or the naturalisation procedure, in your language.",
    note: "Answered by AI, based on the Viapunt guide.",
    placeholder: "Your question",
    send: "Send",
    close: "Close",
    clear: "Start again",
    remaining: "{n} questions left today",
    limit: "You have used today's questions here. A free account gives you more each day, plus practice questions.",
    limitCta: "Create a free account",
    busy: "Many people are asking right now. Please try again later.",
    error: "Something went wrong. Please try again in a moment.",
    unavailable: "The help chat is not available right now.",
  },
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
      heading: "Practise the test questions",
      text: "Try 30 sample questions in your own language, with the German beside them. No account needed.",
      button: "Try 30 free questions",
    },
    mock: {
      heading: "Take a free mock test",
      text: "Sign up with your email for one free mock test, then see how you do under test conditions.",
      button: "Take the free mock test",
    },
    pass: {
      heading: "Prepare with the Viapunt Pass",
      text: "The Viapunt Pass opens every question and study mode for your canton. Start with the free questions.",
      button: "Try 30 free questions",
    },
  },
  home: {
    title: "Swiss naturalisation guide and citizenship test practice",
    description:
      "Step-by-step guides to Swiss naturalisation, and citizenship test practice in German with your language side by side. Try 30 questions free.",
    eyebrow: "Naturalisation in Switzerland",
    h1: "Understand it in your language. Pass it in German.",
    lead: "Plain guides to every step of becoming Swiss, from documents to the knowledge test, with the details for the canton of Zurich. Then practise the test questions with the German and your language side by side.",
    ctaFree: "Try 30 free questions",
    ctaGuide: "Read the Zurich guide",
    trust: ["No account needed to start", "8 languages", "Sources linked on every page"],
    q: {
      heading: "Try a test question",
      daily: "Question of the day",
      topic: "Popular rights",
      german: "Deutsch",
      right: "Correct.",
      wrong: "Not quite. The right answer is marked.",
      more: "29 more free questions",
      reveal: "Show the answer",
    },
    how: {
      heading: "How it works",
      steps: [
        { title: "Read the guide", text: "Residence rules, documents, fees and the tests, explained step by step, with the sources linked." },
        { title: "Try 30 free questions", text: "See the kind of questions the test asks, in German with your language beside it. No account needed." },
        { title: "Practise until you are ready", text: "Learn, practise your weak topics and take mock tests." },
      ],
    },
    guidesHeading: "Guides to becoming Swiss",
    groups: { swiss: "For everyone in Switzerland", zh: "Canton of Zurich" },
    read: "Read",
    soon: "Coming soon",
    tags: {
      overview: "Start here", zurich: "Zurich", documents: "Checklist", test: "Test", language: "German",
      fees: "Costs", calculator: "Tool", free: "Free", faq: "Answers", interview: "Interview",
    },
    langs: {
      heading: "Your language beside the German",
      text: "The test is in German. Every question shows a translation as a study aid, so you understand first and then get used to the German.",
    },
    pass: {
      badge: "Viapunt Pass",
      period: "12 months, paid once. No subscription.",
      pay: "Pay by card or TWINT. Extension: 3 more months for CHF 9.",
      points: [
        "Questions on every topic of the test, for Zurich or the rest of Switzerland",
        "Mock tests to see where you stand",
        "Explain this: ask about any question in your language",
        "Practice that focuses on your weak topics",
      ],
      button: "Start with 30 free questions",
    },
  },
  cards: {
    overview: { title: "Overview", text: "Federal requirements, the order of steps and how long it takes." },
    zurich: { title: "Zurich, step by step", text: "Residence rules, documents, fees, timeline and where to apply." },
    documents: { title: "Documents", text: "What to provide, where to get it and how old it may be." },
    test: { title: "The Zurich knowledge test", text: "50 questions, 30 to pass: format, topics and how to prepare." },
    interview: { title: "The naturalisation interview", text: "What the commune asks, in which language, and how to prepare." },
    language: { title: "Language certificates", text: "Which ones count, which levels, prices and where to take them." },
    fees: { title: "Fees", text: "Federal, cantonal and communal fees in the canton of Zurich." },
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
    mockNote: "The real test is set by your canton and is in German.",
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
  mainNav: "Hauptnavigation",
  footerNav: "Ratgeber",
  navGuides: "Ratgeber",
  navFree: "Gratis üben",
  navFaq: "FAQ",
  navStart: "Gratis starten",
  navApp: "App öffnen",
  legal: { nav: "Rechtliches", imprint: "Impressum", privacy: "Datenschutz", terms: "Nutzungsbedingungen", contact: "Kontakt", about: "Über Viapunt" },
  chat: {
    launcher: "Frage stellen",
    title: "Viapunt fragen",
    intro: "Fragen Sie zum Grundkenntnistest, zu seinen Themen oder zum Einbürgerungsverfahren, in Ihrer Sprache.",
    note: "Antwort von KI, gestützt auf den Viapunt-Ratgeber.",
    placeholder: "Ihre Frage",
    send: "Senden",
    close: "Schliessen",
    clear: "Neu beginnen",
    remaining: "Heute noch {n} Fragen",
    limit: "Sie haben die heutigen Fragen hier aufgebraucht. Mit einem kostenlosen Konto erhalten Sie mehr pro Tag und dazu Übungsfragen.",
    limitCta: "Kostenloses Konto erstellen",
    busy: "Gerade fragen sehr viele. Bitte versuchen Sie es später noch einmal.",
    error: "Etwas ist schiefgelaufen. Bitte versuchen Sie es gleich noch einmal.",
    unavailable: "Der Hilfe-Chat ist gerade nicht verfügbar.",
  },
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
      heading: "Testfragen üben",
      text: "Probieren Sie 30 Beispielfragen in Ihrer Sprache aus, mit dem deutschen Text daneben. Ohne Konto.",
      button: "30 Fragen gratis testen",
    },
    mock: {
      heading: "Gratis-Probeprüfung",
      text: "Melden Sie sich mit Ihrer E-Mail-Adresse an und machen Sie eine Probeprüfung gratis, unter Prüfungsbedingungen.",
      button: "Gratis-Probeprüfung starten",
    },
    pass: {
      heading: "Mit dem Viapunt Pass vorbereiten",
      text: "Der Viapunt Pass schaltet alle Fragen und Lernmodi für Ihren Kanton frei. Beginnen Sie mit den Gratisfragen.",
      button: "30 Fragen gratis testen",
    },
  },
  home: {
    title: "Einbürgerung Schweiz: Ratgeber und Einbürgerungstest üben",
    description:
      "Die Einbürgerung in der Schweiz Schritt für Schritt erklärt, dazu Übungsfragen für den Einbürgerungstest mit Übersetzung in Ihre Sprache. 30 Fragen gratis.",
    eyebrow: "Einbürgerung in der Schweiz",
    h1: "In Ihrer Sprache verstehen. Auf Deutsch bestehen.",
    lead: "Verständliche Ratgeber zu jedem Schritt der Einbürgerung, von den Unterlagen bis zum Wissenstest, mit den Details für den Kanton Zürich. Danach üben Sie die Testfragen, auf Deutsch und auf Wunsch mit Übersetzung daneben.",
    ctaFree: "30 Fragen gratis testen",
    ctaGuide: "Zum Zürich-Ratgeber",
    trust: ["Ohne Konto starten", "8 Sprachen", "Quellen auf jeder Seite verlinkt"],
    q: {
      heading: "Probieren Sie eine Testfrage",
      daily: "Frage des Tages",
      topic: "Volksrechte",
      german: "Deutsch",
      right: "Richtig.",
      wrong: "Nicht ganz. Die richtige Antwort ist markiert.",
      more: "29 weitere Gratisfragen",
      reveal: "Antwort zeigen",
    },
    how: {
      heading: "So funktioniert es",
      steps: [
        { title: "Ratgeber lesen", text: "Aufenthalt, Unterlagen, Gebühren und Tests, Schritt für Schritt erklärt, mit verlinkten Quellen." },
        { title: "30 Fragen gratis testen", text: "Sehen Sie, wie die Testfragen aussehen, auf Deutsch und mit Ihrer Sprache daneben. Ohne Konto." },
        { title: "Üben, bis Sie bereit sind", text: "Lernen, schwache Themen gezielt üben und Probeprüfungen machen." },
      ],
    },
    guidesHeading: "Ratgeber zur Einbürgerung",
    groups: { swiss: "Für alle in der Schweiz", zh: "Kanton Zürich" },
    read: "Lesen",
    soon: "Folgt in Kürze",
    tags: {
      overview: "Hier starten", zurich: "Zürich", documents: "Checkliste", test: "Test", language: "Deutsch",
      fees: "Kosten", calculator: "Werkzeug", free: "Gratis", faq: "Antworten", interview: "Gespräch",
    },
    langs: {
      heading: "Ihre Sprache neben dem Deutschen",
      text: "Der Test ist auf Deutsch. Jede Frage zeigt eine Übersetzung als Lernhilfe: Sie verstehen zuerst und gewöhnen sich dann an das Deutsch.",
    },
    pass: {
      badge: "Viapunt Pass",
      period: "12 Monate, einmal bezahlt. Kein Abo.",
      pay: "Bezahlen mit Karte oder TWINT. Verlängerung: 3 Monate für CHF 9.",
      points: [
        "Fragen zu allen Themen des Tests, für Zürich oder die übrige Schweiz",
        "Probeprüfungen, damit Sie Ihren Stand kennen",
        "Erklärungen zu jeder Frage in Ihrer Sprache",
        "Üben, das sich auf Ihre schwachen Themen konzentriert",
      ],
      button: "Mit 30 Gratisfragen starten",
    },
  },
  cards: {
    overview: { title: "Überblick", text: "Bundesvoraussetzungen, Reihenfolge der Schritte und Dauer." },
    zurich: { title: "Zürich, Schritt für Schritt", text: "Aufenthalt, Unterlagen, Gebühren, Zeitplan und Anmeldung." },
    documents: { title: "Unterlagen", text: "Was Sie einreichen, wo Sie es bekommen und wie alt es sein darf." },
    test: { title: "Der Zürcher Grundkenntnistest", text: "50 Fragen, 30 zum Bestehen: Aufbau, Themen und Vorbereitung." },
    interview: { title: "Das Einbürgerungsgespräch", text: "Was die Gemeinde fragt, in welcher Sprache und wie Sie sich vorbereiten." },
    language: { title: "Sprachnachweise", text: "Welche zählen, welche Niveaus, Preise und Prüfungsorte." },
    fees: { title: "Gebühren", text: "Gebühren von Bund, Kanton Zürich und Gemeinde im Überblick." },
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
    mockNote: "Den echten Test legt Ihr Kanton fest; er ist auf Deutsch.",
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
  de: "Viapunt ist ein unabhängiger Dienst ohne Verbindung zu Behörden von Bund, Kantonen oder Gemeinden.",
  en: "Viapunt is an independent service, not connected to any federal, cantonal or communal authority.",
  fr: "Viapunt est un service indépendant, sans lien avec une autorité fédérale, cantonale ou communale.",
  it: "Viapunt è un servizio indipendente, non collegato ad alcuna autorità federale, cantonale o comunale.",
  pt: "O Viapunt é um serviço independente, sem ligação a qualquer autoridade federal, cantonal ou municipal.",
  es: "Viapunt es un servicio independiente, sin vinculación con ninguna autoridad federal, cantonal ni municipal.",
  sq: "Viapunt është një shërbim i pavarur, pa lidhje me asnjë autoritet federal, kantonal apo komunal.",
  tr: "Viapunt, federal, kantonal veya yerel hiçbir makamla bağlantısı olmayan bağımsız bir hizmettir.",
};
