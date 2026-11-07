// Interface copy for the articles, the glossary, the eligibility check and the Zurich checklist,
// written out for all eight languages (the older strings in ui.ts only have German and English).
// French, Italian, Portuguese, Spanish, Albanian and Turkish are machine translations reviewed by
// an agent; a native-speaker read is still wanted (see src/content/README.md).

export type RouteId = "ordinary" | "spouse" | "third";

export interface EligibilityStrings {
  title: string;
  description: string;
  h1: string;
  lead: string;
  privacy: string;
  disclaimer: string;
  numberHint: string;
  qCanton: string;
  optZurich: string;
  optOther: string;
  qMarried: string;
  qMarriageYears: string;
  qTogether: string;
  qPermit: string;
  qYears: string;
  qYoung: string;
  qLast5: string;
  qCommune: string;
  qBorn: string;
  qSchool: string;
  qUnder25: string;
  qFamily: string;
  yes: string;
  no: string;
  notSure: string;
  submit: string;
  idle: string;
  errNumber: string;
  heading: string;
  likely: string;
  none: string;
  routes: Record<RouteId, string>;
  status: { fits: string; check: string; notYet: string };
  missingHeading: string;
  nothingMissing: string;
  m: {
    permit: string;
    counted: string;
    actual: string;
    last5: string;
    commune: string;
    spouseMarried: string;
    spouseYears: string;
    spouseLast: string;
    together: string;
    born: string;
    school: string;
    age: string;
    permitThird: string;
    family: string;
  };
  extraOrdinary: string;
  otherCanton: string;
  readNext: string;
  semSpouses: string;
  semThird: string;
}

export interface ChecklistStrings {
  title: string;
  description: string;
  h1: string;
  lead: string;
  print: string;
  printHint: string;
  groups: { id: string; title: string; items: string[] }[];
  notCollect: string;
  moreDetails: string;
  disclaimer: string;
  footerLine: string;
}

export interface More {
  navArticles: string;
  cards: Record<"glossary" | "eligibility" | "checklist", { title: string; text: string }>;
  tags: Record<"glossary" | "eligibility" | "checklist", string>;
  articles: {
    indexTitle: string;
    indexDescription: string;
    indexH1: string;
    indexLead: string;
    soon: string;
    cantonsTitle: string;
    cantonsDescription: string;
    cantonsH1: string;
    cantonsLead: string;
    cantonsSoon: string;
    toCantons: string;
    toArticles: string;
    categories: Record<"eligibility" | "cantons" | "test" | "process" | "after", string>;
    byline: string;
    published: string;
    updated: string;
    checked: string;
    inBrief: string;
    sources: string;
    faq: string;
    relatedGuides: string;
    moreArticles: string;
    guideRelated: string;
    latest: string;
    all: string;
    machine: string;
    readEnglish: string;
    rss: string;
    cantonLabel: string;
    breadcrumbHome: string;
  };
  glossary: {
    title: string;
    description: string;
    h1: string;
    lead: string;
    germanTerm: string;
    inEnglish: string;
    keep: string;
    setName: string;
    noteDe: string;
  };
  eligibility: EligibilityStrings;
  checklist: ChecklistStrings;
}

const en: More = {
  navArticles: "Articles",
  cards: {
    glossary: { title: "Glossary", text: "German words from letters, forms and the test, explained in your language." },
    eligibility: { title: "Eligibility check", text: "Answer a few questions and see which route may fit you. Runs in your browser." },
    checklist: { title: "Zurich document checklist", text: "Tick off the documents you need and print the list on one page." },
  },
  tags: { glossary: "Words", eligibility: "Tool", checklist: "Print" },
  articles: {
    indexTitle: "Articles on Swiss naturalisation",
    indexDescription: "Plain articles on who can become Swiss, the steps, the knowledge test and life after naturalisation, with sources.",
    indexH1: "Articles",
    indexLead: "Plain explanations of the questions people ask most, each with its sources and the date the facts were checked.",
    soon: "The first articles are coming soon. In the meantime, start with the overview.",
    cantonsTitle: "Naturalisation by canton",
    cantonsDescription: "Guides to naturalisation in individual cantons: residence periods, tests, fees and where to apply.",
    cantonsH1: "Guides by canton",
    cantonsLead: "What differs from canton to canton, one guide for each.",
    cantonsSoon: "The first canton guides are coming soon.",
    toCantons: "Guides by canton",
    toArticles: "All articles",
    categories: {
      eligibility: "Who can apply",
      cantons: "Cantons",
      test: "The knowledge test",
      process: "The procedure",
      after: "After naturalisation",
    },
    byline: "By the Viapunt team",
    published: "Published",
    updated: "Updated",
    checked: "Facts checked on {date}",
    inBrief: "In brief",
    sources: "Sources",
    faq: "Questions and answers",
    relatedGuides: "Related guide pages",
    moreArticles: "More articles",
    guideRelated: "Related articles",
    latest: "Latest articles",
    all: "All articles",
    machine: "Translated from English. If anything is unclear, the English version is the reference.",
    readEnglish: "Read the English version",
    rss: "Viapunt articles (RSS)",
    cantonLabel: "Canton",
    breadcrumbHome: "Home",
  },
  glossary: {
    title: "Glossary of German terms for naturalisation",
    description: "German words you meet in letters, forms and the knowledge test about Swiss citizenship, each explained in your language.",
    h1: "Glossary",
    lead: "German words you may meet in letters, forms and the test. Each entry gives the German term first, then what it means.",
    germanTerm: "German term",
    inEnglish: "Explanation in English; there is no text in your language yet.",
    keep: "Learn the German word: it is what the test and the letters use.",
    setName: "Viapunt glossary",
    noteDe: "",
  },
  eligibility: {
    title: "Eligibility check: which route to Swiss citizenship?",
    description: "Answer a few questions to see which route to Swiss citizenship may fit you and what is still missing. Runs in your browser; nothing is sent.",
    h1: "Which route may fit you?",
    lead: "Answer a few questions. You will see which route to Swiss citizenship may fit you, and what is still missing. This is a guide, not a decision.",
    privacy: "This runs in your browser only. Nothing you enter is sent, stored or logged.",
    disclaimer: "This is a guide, not a decision. Only your commune, your canton and the State Secretariat for Migration (SEM) decide. Rules differ between cantons and can change.",
    numberHint: "Whole years; a part of a year counts as the lower number.",
    qCanton: "Where do you live?",
    optZurich: "Canton of Zurich",
    optOther: "Another canton",
    qMarried: "Are you married to a Swiss citizen?",
    qMarriageYears: "For how many years have you been married?",
    qTogether: "Do you live together as a married couple?",
    qPermit: "Do you have a settlement permit (C)?",
    qYears: "How many years have you lived in Switzerland? Count years with a B or C permit. Years with an F permit count by half; N and L do not count.",
    qYoung: "How many of these years fall between your 8th and 18th birthdays?",
    qLast5: "How many of the last 5 years did you live in Switzerland?",
    qCommune: "How many years have you lived in your current commune?",
    qBorn: "Were you born in Switzerland?",
    qSchool: "How many years of compulsory school did you attend in Switzerland?",
    qUnder25: "Are you under 25?",
    qFamily: "Does one of your parents have a C permit, ten years in Switzerland and five years of school here, and was one of your grandparents born in Switzerland or did they have a right of residence?",
    yes: "Yes",
    no: "No",
    notSure: "Not sure",
    submit: "Show my likely route",
    idle: "Answer the questions and press the button.",
    errNumber: "Check this: enter a whole number of years in every number field.",
    heading: "Your likely route",
    likely: "On your answers, this route may fit you: {route}.",
    none: "On your answers, no route is complete yet. Here is what is missing.",
    routes: {
      ordinary: "Ordinary naturalisation",
      spouse: "Facilitated naturalisation for spouses of Swiss citizens",
      third: "Facilitated naturalisation for the third generation",
    },
    status: { fits: "May fit", check: "Check with the authority", notYet: "Not yet" },
    missingHeading: "Still missing or to check",
    nothingMissing: "Nothing is missing on the points asked here.",
    m: {
      permit: "A valid settlement permit (C).",
      counted: "Counted residence is {n} years; the rule asks for 10 (years between 8 and 18 count twice).",
      actual: "Actual residence is {n} years; at least 6 must be real years lived here.",
      last5: "At least 3 of the last 5 years must be lived in Switzerland; you entered {n}.",
      commune: "Zurich asks for at least 2 years in the same commune immediately before you apply; you entered {n}. If you apply before your 25th birthday, 2 years anywhere in the canton are enough instead.",
      spouseMarried: "Living in marital union with your Swiss spouse for 3 years; you entered {n}.",
      spouseYears: "Five years of residence in Switzerland in total; you entered {n}.",
      spouseLast: "The last year before you apply must be lived in Switzerland.",
      together: "Living together as a married couple.",
      born: "Being born in Switzerland.",
      school: "At least 5 years of compulsory school in Switzerland; you entered {n}.",
      age: "Applying before your 25th birthday.",
      permitThird: "A settlement permit (C).",
      family: "The conditions on your parents and grandparents. Check them with the SEM.",
    },
    extraOrdinary: "Also needed for ordinary naturalisation, and not asked here: German at B1 spoken and A2 written, respect for public safety and order, taking part in work or education, and no social assistance in the three years before you apply.",
    otherCanton: "Your canton and commune can add a minimum time of residence there; the SEM mentions two to five years. Ask your commune.",
    readNext: "Read next",
    semSpouses: "SEM: spouses (German)",
    semThird: "SEM: third generation (German)",
  },
  checklist: {
    title: "Zurich document checklist for naturalisation",
    description: "A printable checklist of the documents for ordinary naturalisation in the canton of Zurich, with the maximum age of each. Fits one A4 page.",
    h1: "Zurich document checklist",
    lead: "For ordinary naturalisation in the canton of Zurich. Tick what you have, then print the page. Based on the documents guide, checked on 30 October 2026.",
    print: "Print this page",
    printHint: "On paper, tick the boxes with a pen.",
    groups: [
      {
        id: "everyone",
        title: "For every person in the application",
        items: [
          "Civil status document (for example proof of civil status). At most 6 months old on the day you submit.",
          "Proof of current activity (age 12 or over): employer confirmation, school confirmation, pages 1 to 4 of your tax return if self-employed, benefit statements or proof of assets. At most 3 months old.",
        ],
      },
      {
        id: "ifyouhave",
        title: "If you already have them (age 12 or over)",
        items: [
          "Proof of German (B1 spoken, A2 written): a recognised certificate, a diploma taught in German or school reports. Not needed if German is your mother tongue.",
          "Proof of basic knowledge: school reports, a Swiss upper-secondary qualification or the knowledge test certificate.",
        ],
      },
      {
        id: "sometimes",
        title: "Only in some situations",
        items: [
          "Proof of sole custody, or the consent of both parents, if minor children are included.",
          "Declaration on registered partnership and proof of your partner's citizenship, if you want the shorter residence periods for registered partners.",
          "Proof of personal circumstances (for example a medical certificate), if illness or disability stops you meeting a requirement.",
        ],
      },
      {
        id: "before",
        title: "Before you submit",
        items: [
          "I am in the Swiss civil status register. If you were born or married abroad, register first: it can take weeks to months.",
          "I asked my commune whether the German and knowledge tests come before or after filing.",
          "I ordered the documents last: the civil status document within 6 months, the others within 3 months of submitting.",
          "I am ready to file online at zh.ch/e-einbuergerung.",
        ],
      },
    ],
    notCollect: "You do not collect a debt collection extract, a criminal record extract, a tax certificate or a welfare confirmation. The authorities get them themselves.",
    moreDetails: "Costs, where to get each document and what differs between communes:",
    disclaimer: "This is an independent guide. Check the canton's current checklist before you submit.",
    footerLine: "viapunt.ch",
  },
};

const de: More = {
  navArticles: "Ratgeber",
  cards: {
    glossary: { title: "Glossar", text: "Deutsche Wörter aus Briefen, Formularen und dem Test, in Ihrer Sprache erklärt." },
    eligibility: { title: "Einbürgerungs-Check", text: "Beantworten Sie ein paar Fragen und sehen Sie, welcher Weg passen könnte. Läuft im Browser." },
    checklist: { title: "Checkliste Zürich", text: "Haken Sie die nötigen Unterlagen ab und drucken Sie die Liste auf einer Seite." },
  },
  tags: { glossary: "Wörter", eligibility: "Werkzeug", checklist: "Drucken" },
  articles: {
    indexTitle: "Ratgeber zur Einbürgerung in der Schweiz",
    indexDescription: "Verständliche Ratgeber dazu, wer Schweizerin oder Schweizer werden kann, zu den Schritten, zum Grundkenntnistest und zum Leben nach der Einbürgerung, mit Quellen.",
    indexH1: "Ratgeber",
    indexLead: "Verständliche Antworten auf die häufigsten Fragen, jeweils mit Quellen und dem Datum, an dem die Fakten geprüft wurden.",
    soon: "Die ersten Ratgeber folgen bald. Beginnen Sie bis dahin mit dem Überblick.",
    cantonsTitle: "Einbürgerung nach Kanton",
    cantonsDescription: "Ratgeber zur Einbürgerung in einzelnen Kantonen: Wohnsitzfristen, Tests, Gebühren und wo Sie das Gesuch einreichen.",
    cantonsH1: "Ratgeber nach Kanton",
    cantonsLead: "Was von Kanton zu Kanton anders ist, je ein Ratgeber pro Kanton.",
    cantonsSoon: "Die ersten Kantonsratgeber folgen bald.",
    toCantons: "Ratgeber nach Kanton",
    toArticles: "Alle Ratgeber",
    categories: {
      eligibility: "Wer sich einbürgern lassen kann",
      cantons: "Kantone",
      test: "Der Grundkenntnistest",
      process: "Das Verfahren",
      after: "Nach der Einbürgerung",
    },
    byline: "Vom Viapunt-Team",
    published: "Veröffentlicht",
    updated: "Aktualisiert",
    checked: "Fakten geprüft am {date}",
    inBrief: "Kurz gesagt",
    sources: "Quellen",
    faq: "Fragen und Antworten",
    relatedGuides: "Passende Ratgeberseiten",
    moreArticles: "Weitere Ratgeber",
    guideRelated: "Passende Ratgeber",
    latest: "Neueste Ratgeber",
    all: "Alle Ratgeber",
    machine: "Aus dem Englischen übersetzt. Wenn etwas unklar ist, gilt die englische Fassung.",
    readEnglish: "Englische Fassung lesen",
    rss: "Viapunt-Ratgeber (RSS)",
    cantonLabel: "Kanton",
    breadcrumbHome: "Startseite",
  },
  glossary: {
    title: "Glossar der deutschen Begriffe zur Einbürgerung",
    description: "Deutsche Wörter aus Briefen, Formularen und dem Grundkenntnistest zum Schweizer Bürgerrecht, jeweils erklärt.",
    h1: "Glossar",
    lead: "Deutsche Wörter, die Ihnen in Briefen, Formularen und im Test begegnen können. Zuerst steht der deutsche Begriff, dann was er bedeutet.",
    germanTerm: "Deutscher Begriff",
    inEnglish: "Erklärung auf Englisch; in Ihrer Sprache gibt es noch keinen Text.",
    keep: "Merken Sie sich das deutsche Wort: Test und Briefe verwenden es.",
    setName: "Viapunt-Glossar",
    noteDe: "Die Erklärungen stehen vorerst auf Englisch.",
  },
  eligibility: {
    title: "Einbürgerungs-Check: Welcher Weg zum Schweizer Bürgerrecht?",
    description: "Beantworten Sie ein paar Fragen und sehen Sie, welcher Weg zum Schweizer Bürgerrecht passen könnte und was noch fehlt. Läuft im Browser; nichts wird gesendet.",
    h1: "Welcher Weg könnte passen?",
    lead: "Beantworten Sie ein paar Fragen. Sie sehen, welcher Weg zum Schweizer Bürgerrecht passen könnte und was noch fehlt. Das ist eine Orientierung, kein Entscheid.",
    privacy: "Das läuft nur in Ihrem Browser. Nichts, was Sie eingeben, wird gesendet, gespeichert oder protokolliert.",
    disclaimer: "Das ist eine Orientierung, kein Entscheid. Entscheiden können nur Ihre Gemeinde, Ihr Kanton und das Staatssekretariat für Migration (SEM). Die Regeln unterscheiden sich je nach Kanton und können sich ändern.",
    numberHint: "Ganze Jahre; ein angefangenes Jahr zählt nicht.",
    qCanton: "Wo wohnen Sie?",
    optZurich: "Kanton Zürich",
    optOther: "Anderer Kanton",
    qMarried: "Sind Sie mit einer Schweizer Bürgerin oder einem Schweizer Bürger verheiratet?",
    qMarriageYears: "Seit wie vielen Jahren sind Sie verheiratet?",
    qTogether: "Leben Sie als Ehepaar zusammen?",
    qPermit: "Haben Sie eine Niederlassungsbewilligung (C)?",
    qYears: "Wie viele Jahre haben Sie in der Schweiz gelebt? Zählen Sie Jahre mit Bewilligung B oder C. Jahre mit Bewilligung F zählen zur Hälfte, N und L zählen nicht.",
    qYoung: "Wie viele dieser Jahre liegen zwischen Ihrem 8. und 18. Geburtstag?",
    qLast5: "Wie viele der letzten 5 Jahre haben Sie in der Schweiz gelebt?",
    qCommune: "Wie viele Jahre wohnen Sie in Ihrer jetzigen Gemeinde?",
    qBorn: "Sind Sie in der Schweiz geboren?",
    qSchool: "Wie viele Jahre obligatorische Schule haben Sie in der Schweiz besucht?",
    qUnder25: "Sind Sie unter 25 Jahre alt?",
    qFamily: "Hat ein Elternteil eine Niederlassungsbewilligung, zehn Jahre Aufenthalt in der Schweiz und fünf Jahre Schule hier, und wurde ein Grosselternteil in der Schweiz geboren oder hatte ein Aufenthaltsrecht?",
    yes: "Ja",
    no: "Nein",
    notSure: "Nicht sicher",
    submit: "Meinen wahrscheinlichen Weg anzeigen",
    idle: "Beantworten Sie die Fragen und drücken Sie die Taste.",
    errNumber: "Bitte prüfen: Geben Sie in jedes Zahlenfeld eine ganze Zahl ein.",
    heading: "Ihr wahrscheinlicher Weg",
    likely: "Nach Ihren Angaben könnte dieser Weg passen: {route}.",
    none: "Nach Ihren Angaben ist noch kein Weg vollständig. Das fehlt noch.",
    routes: {
      ordinary: "Ordentliche Einbürgerung",
      spouse: "Erleichterte Einbürgerung für Ehegatten von Schweizer Bürgern",
      third: "Erleichterte Einbürgerung der dritten Generation",
    },
    status: { fits: "Könnte passen", check: "Bei der Behörde klären", notYet: "Noch nicht" },
    missingHeading: "Fehlt noch oder zu klären",
    nothingMissing: "Bei den hier gefragten Punkten fehlt nichts.",
    m: {
      permit: "Eine gültige Niederlassungsbewilligung (C).",
      counted: "Angerechneter Aufenthalt: {n} Jahre; verlangt sind 10 (Jahre zwischen 8 und 18 zählen doppelt).",
      actual: "Tatsächlicher Aufenthalt: {n} Jahre; mindestens 6 müssen wirklich hier gelebte Jahre sein.",
      last5: "Mindestens 3 der letzten 5 Jahre müssen Sie in der Schweiz gelebt haben; Sie haben {n} angegeben.",
      commune: "Zürich verlangt mindestens 2 Jahre in derselben Gemeinde unmittelbar vor dem Gesuch; Sie haben {n} angegeben. Wer das Gesuch vor dem 25. Geburtstag einreicht, braucht stattdessen nur 2 Jahre irgendwo im Kanton.",
      spouseMarried: "Seit 3 Jahren in ehelicher Gemeinschaft mit Ihrer Schweizer Ehepartnerin oder Ihrem Ehepartner; Sie haben {n} angegeben.",
      spouseYears: "Insgesamt fünf Jahre Aufenthalt in der Schweiz; Sie haben {n} angegeben.",
      spouseLast: "Das letzte Jahr vor dem Gesuch müssen Sie in der Schweiz gelebt haben.",
      together: "Als Ehepaar zusammenleben.",
      born: "In der Schweiz geboren sein.",
      school: "Mindestens 5 Jahre obligatorische Schule in der Schweiz; Sie haben {n} angegeben.",
      age: "Das Gesuch vor dem 25. Geburtstag einreichen.",
      permitThird: "Eine Niederlassungsbewilligung (C).",
      family: "Die Voraussetzungen bei Eltern und Grosseltern. Klären Sie diese mit dem SEM.",
    },
    extraOrdinary: "Für die ordentliche Einbürgerung braucht es zusätzlich, hier nicht gefragt: Deutsch auf Niveau B1 mündlich und A2 schriftlich, Beachten der öffentlichen Sicherheit und Ordnung, Teilnahme am Wirtschaftsleben oder an Bildung und kein Sozialhilfebezug in den drei Jahren vor dem Gesuch.",
    otherCanton: "Ihr Kanton und Ihre Gemeinde können eine Mindestdauer des Wohnsitzes dort verlangen; das SEM nennt zwei bis fünf Jahre. Fragen Sie Ihre Gemeinde.",
    readNext: "Weiterlesen",
    semSpouses: "SEM: Ehegatten",
    semThird: "SEM: dritte Generation",
  },
  checklist: {
    title: "Checkliste Unterlagen für die Einbürgerung in Zürich",
    description: "Eine druckbare Checkliste der Unterlagen für die ordentliche Einbürgerung im Kanton Zürich, mit dem maximalen Alter jeder Unterlage. Passt auf eine A4-Seite.",
    h1: "Checkliste Zürich",
    lead: "Für die ordentliche Einbürgerung im Kanton Zürich. Haken Sie ab, was Sie haben, und drucken Sie die Seite. Grundlage ist der Ratgeber zu den Unterlagen, geprüft am 30. Oktober 2026.",
    print: "Seite drucken",
    printHint: "Auf Papier haken Sie die Kästchen mit einem Stift ab.",
    groups: [
      {
        id: "everyone",
        title: "Für jede Person im Gesuch",
        items: [
          "Dokument des Zivilstandsamtes (zum Beispiel Personenstandsausweis). Am Tag der Einreichung höchstens 6 Monate alt.",
          "Nachweis der aktuellen Tätigkeit (ab 12 Jahren): Bestätigung des Arbeitgebers oder der Schule, Seiten 1 bis 4 der Steuererklärung bei Selbständigen, Leistungsbelege oder Vermögensnachweis. Höchstens 3 Monate alt.",
        ],
      },
      {
        id: "ifyouhave",
        title: "Wenn Sie sie schon haben (ab 12 Jahren)",
        items: [
          "Deutschnachweis (B1 mündlich, A2 schriftlich): anerkanntes Zertifikat, Diplom in deutscher Sprache oder Schulzeugnisse. Nicht nötig, wenn Deutsch Ihre Muttersprache ist.",
          "Nachweis der Grundkenntnisse: Schulzeugnisse, ein Schweizer Abschluss der Sekundarstufe II oder die Bestätigung über den Grundkenntnistest.",
        ],
      },
      {
        id: "sometimes",
        title: "Nur in bestimmten Fällen",
        items: [
          "Nachweis der alleinigen Sorge oder Einverständnis beider Eltern, wenn minderjährige Kinder einbezogen sind.",
          "Erklärung zur eingetragenen Partnerschaft und Nachweis des Bürgerrechts der Partnerin oder des Partners, wenn Sie die kürzeren Fristen für eingetragene Partner nutzen wollen.",
          "Nachweis der persönlichen Verhältnisse (zum Beispiel ärztliches Zeugnis), wenn Krankheit oder Behinderung die Erfüllung einer Anforderung verhindert.",
        ],
      },
      {
        id: "before",
        title: "Vor der Einreichung",
        items: [
          "Ich bin im Schweizer Zivilstandsregister eingetragen. Wenn Sie im Ausland geboren oder verheiratet sind, lassen Sie sich zuerst eintragen: Das kann Wochen bis Monate dauern.",
          "Ich habe meine Gemeinde gefragt, ob Deutsch- und Grundkenntnistest vor oder nach dem Gesuch stattfinden.",
          "Ich habe die Unterlagen zuletzt bestellt: Dokument des Zivilstandsamtes höchstens 6 Monate, die übrigen höchstens 3 Monate vor der Einreichung.",
          "Ich bin bereit, das Gesuch online auf zh.ch/e-einbuergerung einzureichen.",
        ],
      },
    ],
    notCollect: "Einen Betreibungsregisterauszug, einen Strafregisterauszug, eine Steuerbestätigung oder eine Sozialhilfebestätigung besorgen Sie nicht. Die Behörden holen sie selbst ein.",
    moreDetails: "Kosten, wo Sie jede Unterlage bekommen und was sich zwischen Gemeinden unterscheidet:",
    disclaimer: "Das ist ein unabhängiger Ratgeber. Prüfen Sie vor der Einreichung die aktuelle Checkliste des Kantons.",
    footerLine: "viapunt.ch",
  },
};

const fr: More = {
  navArticles: "Articles",
  cards: {
    glossary: { title: "Glossaire", text: "Des mots allemands des lettres, des formulaires et du test, expliqués dans votre langue." },
    eligibility: { title: "Vérification des conditions", text: "Répondez à quelques questions et voyez quelle voie peut vous convenir. Fonctionne dans votre navigateur." },
    checklist: { title: "Liste des documents (Zurich)", text: "Cochez les documents nécessaires et imprimez la liste sur une page." },
  },
  tags: { glossary: "Mots", eligibility: "Outil", checklist: "Imprimer" },
  articles: {
    indexTitle: "Articles sur la naturalisation en Suisse",
    indexDescription: "Des articles clairs sur qui peut devenir Suisse, les étapes, le test de connaissances et la vie après la naturalisation, avec les sources.",
    indexH1: "Articles",
    indexLead: "Des explications claires aux questions les plus fréquentes, chacune avec ses sources et la date de vérification des faits.",
    soon: "Les premiers articles arrivent bientôt. En attendant, commencez par l'aperçu.",
    cantonsTitle: "La naturalisation par canton",
    cantonsDescription: "Des guides sur la naturalisation dans chaque canton : durées de résidence, tests, émoluments et où déposer la demande.",
    cantonsH1: "Guides par canton",
    cantonsLead: "Ce qui change d'un canton à l'autre, un guide pour chacun.",
    cantonsSoon: "Les premiers guides cantonaux arrivent bientôt.",
    toCantons: "Guides par canton",
    toArticles: "Tous les articles",
    categories: {
      eligibility: "Qui peut déposer une demande",
      cantons: "Cantons",
      test: "Le test de connaissances",
      process: "La procédure",
      after: "Après la naturalisation",
    },
    byline: "Par l'équipe Viapunt",
    published: "Publié le",
    updated: "Mis à jour le",
    checked: "Faits vérifiés le {date}",
    inBrief: "En bref",
    sources: "Sources",
    faq: "Questions et réponses",
    relatedGuides: "Pages du guide associées",
    moreArticles: "Autres articles",
    guideRelated: "Articles associés",
    latest: "Derniers articles",
    all: "Tous les articles",
    machine: "Traduit de l'anglais. En cas de doute, la version anglaise fait foi.",
    readEnglish: "Lire la version anglaise",
    rss: "Articles Viapunt (RSS)",
    cantonLabel: "Canton",
    breadcrumbHome: "Accueil",
  },
  glossary: {
    title: "Glossaire des termes allemands de la naturalisation",
    description: "Des mots allemands que l'on rencontre dans les lettres, les formulaires et le test de connaissances sur la citoyenneté suisse, expliqués dans votre langue.",
    h1: "Glossaire",
    lead: "Des mots allemands que vous pouvez rencontrer dans les lettres, les formulaires et le test. Chaque entrée donne d'abord le terme allemand, puis son sens.",
    germanTerm: "Terme allemand",
    inEnglish: "Explication en anglais ; il n'y a pas encore de texte dans votre langue.",
    keep: "Retenez le mot allemand : c'est celui du test et des lettres.",
    setName: "Glossaire Viapunt",
    noteDe: "",
  },
  eligibility: {
    title: "Vérification : quelle voie vers la citoyenneté suisse ?",
    description: "Répondez à quelques questions pour voir quelle voie vers la citoyenneté suisse peut vous convenir et ce qui manque encore. Fonctionne dans votre navigateur ; rien n'est envoyé.",
    h1: "Quelle voie peut vous convenir ?",
    lead: "Répondez à quelques questions. Vous verrez quelle voie vers la citoyenneté suisse peut vous convenir et ce qui manque encore. Ceci est un guide, pas une décision.",
    privacy: "Tout se passe dans votre navigateur. Rien de ce que vous saisissez n'est envoyé, enregistré ni journalisé.",
    disclaimer: "Ceci est un guide, pas une décision. Seuls votre commune, votre canton et le Secrétariat d'État aux migrations (SEM) décident. Les règles varient d'un canton à l'autre et peuvent changer.",
    numberHint: "Années entières ; une année commencée ne compte pas.",
    qCanton: "Où habitez-vous ?",
    optZurich: "Canton de Zurich",
    optOther: "Un autre canton",
    qMarried: "Êtes-vous marié(e) à un(e) citoyen(ne) suisse ?",
    qMarriageYears: "Depuis combien d'années êtes-vous marié(e) ?",
    qTogether: "Vivez-vous ensemble en tant que couple marié ?",
    qPermit: "Avez-vous un permis d'établissement (C) ?",
    qYears: "Combien d'années avez-vous vécu en Suisse ? Comptez les années avec un permis B ou C. Les années avec un permis F comptent pour moitié ; N et L ne comptent pas.",
    qYoung: "Parmi ces années, combien se situent entre vos 8 et 18 ans ?",
    qLast5: "Parmi les 5 dernières années, combien avez-vous vécu en Suisse ?",
    qCommune: "Depuis combien d'années habitez-vous dans votre commune actuelle ?",
    qBorn: "Êtes-vous né(e) en Suisse ?",
    qSchool: "Combien d'années de scolarité obligatoire avez-vous suivies en Suisse ?",
    qUnder25: "Avez-vous moins de 25 ans ?",
    qFamily: "L'un de vos parents a-t-il un permis C, dix ans de séjour en Suisse et cinq ans de scolarité ici, et l'un de vos grands-parents est-il né en Suisse ou y avait-il un droit de séjour ?",
    yes: "Oui",
    no: "Non",
    notSure: "Je ne sais pas",
    submit: "Voir ma voie probable",
    idle: "Répondez aux questions et appuyez sur le bouton.",
    errNumber: "À vérifier : saisissez un nombre entier d'années dans chaque champ numérique.",
    heading: "Votre voie probable",
    likely: "D'après vos réponses, cette voie peut vous convenir : {route}.",
    none: "D'après vos réponses, aucune voie n'est encore complète. Voici ce qui manque.",
    routes: {
      ordinary: "Naturalisation ordinaire",
      spouse: "Naturalisation facilitée pour les conjoints de citoyens suisses",
      third: "Naturalisation facilitée de la troisième génération",
    },
    status: { fits: "Peut convenir", check: "À clarifier auprès de l'autorité", notYet: "Pas encore" },
    missingHeading: "Ce qui manque ou reste à vérifier",
    nothingMissing: "Rien ne manque sur les points demandés ici.",
    m: {
      permit: "Un permis d'établissement (C) valable.",
      counted: "Résidence comptée : {n} ans ; la règle demande 10 ans (les années entre 8 et 18 ans comptent double).",
      actual: "Résidence effective : {n} ans ; au moins 6 doivent être de vraies années vécues ici.",
      last5: "Au moins 3 des 5 dernières années doivent avoir été vécues en Suisse ; vous avez indiqué {n}.",
      commune: "Zurich demande au moins 2 ans dans la même commune juste avant la demande ; vous avez indiqué {n}. Si vous déposez la demande avant vos 25 ans, 2 ans n'importe où dans le canton suffisent.",
      spouseMarried: "3 ans de vie commune dans le mariage avec votre conjoint suisse ; vous avez indiqué {n}.",
      spouseYears: "Cinq ans de séjour en Suisse au total ; vous avez indiqué {n}.",
      spouseLast: "La dernière année avant la demande doit avoir été vécue en Suisse.",
      together: "Vivre ensemble en tant que couple marié.",
      born: "Être né(e) en Suisse.",
      school: "Au moins 5 ans de scolarité obligatoire en Suisse ; vous avez indiqué {n}.",
      age: "Déposer la demande avant votre 25e anniversaire.",
      permitThird: "Un permis d'établissement (C).",
      family: "Les conditions concernant vos parents et grands-parents. Vérifiez-les auprès du SEM.",
    },
    extraOrdinary: "Pour la naturalisation ordinaire, il faut aussi, sans que cela soit demandé ici : l'allemand au niveau B1 à l'oral et A2 à l'écrit, le respect de la sécurité et de l'ordre publics, la participation à la vie économique ou à la formation, et l'absence d'aide sociale dans les trois ans précédant la demande.",
    otherCanton: "Votre canton et votre commune peuvent exiger une durée minimale de résidence sur place ; le SEM mentionne de deux à cinq ans. Renseignez-vous auprès de votre commune.",
    readNext: "À lire ensuite",
    semSpouses: "SEM : conjoints (allemand)",
    semThird: "SEM : troisième génération (allemand)",
  },
  checklist: {
    title: "Liste des documents pour la naturalisation à Zurich",
    description: "Une liste imprimable des documents pour la naturalisation ordinaire dans le canton de Zurich, avec l'âge maximal de chacun. Tient sur une page A4.",
    h1: "Liste des documents (Zurich)",
    lead: "Pour la naturalisation ordinaire dans le canton de Zurich. Cochez ce que vous avez, puis imprimez la page. Basée sur le guide des documents, vérifié le 30 octobre 2026.",
    print: "Imprimer cette page",
    printHint: "Sur papier, cochez les cases au stylo.",
    groups: [
      {
        id: "everyone",
        title: "Pour chaque personne de la demande",
        items: [
          "Document de l'état civil (par exemple attestation d'état civil). Au plus 6 mois le jour du dépôt.",
          "Preuve de l'activité actuelle (dès 12 ans) : confirmation de l'employeur ou de l'école, pages 1 à 4 de la déclaration d'impôts si vous êtes indépendant, relevés de prestations ou preuve de fortune. Au plus 3 mois.",
        ],
      },
      {
        id: "ifyouhave",
        title: "Si vous les avez déjà (dès 12 ans)",
        items: [
          "Preuve d'allemand (B1 à l'oral, A2 à l'écrit) : certificat reconnu, diplôme obtenu en allemand ou bulletins scolaires. Inutile si l'allemand est votre langue maternelle.",
          "Preuve des connaissances de base : bulletins scolaires, titre suisse du secondaire II ou attestation du test de connaissances.",
        ],
      },
      {
        id: "sometimes",
        title: "Seulement dans certains cas",
        items: [
          "Preuve de l'autorité parentale exclusive, ou consentement des deux parents, si des enfants mineurs sont inclus.",
          "Déclaration sur le partenariat enregistré et preuve de la nationalité du partenaire, si vous voulez les durées plus courtes pour les partenaires enregistrés.",
          "Preuve de la situation personnelle (par exemple certificat médical), si une maladie ou un handicap vous empêche de remplir une exigence.",
        ],
      },
      {
        id: "before",
        title: "Avant de déposer la demande",
        items: [
          "Je suis inscrit(e) au registre suisse de l'état civil. Si vous êtes né(e) ou marié(e) à l'étranger, inscrivez-vous d'abord : cela peut prendre de quelques semaines à plusieurs mois.",
          "J'ai demandé à ma commune si les tests d'allemand et de connaissances ont lieu avant ou après le dépôt.",
          "J'ai commandé les documents en dernier : le document de l'état civil au plus 6 mois, les autres au plus 3 mois avant le dépôt.",
          "Je suis prêt(e) à déposer la demande en ligne sur zh.ch/e-einbuergerung.",
        ],
      },
    ],
    notCollect: "Vous ne demandez pas d'extrait du registre des poursuites, d'extrait du casier judiciaire, d'attestation fiscale ni de confirmation d'aide sociale. Les autorités les obtiennent elles-mêmes.",
    moreDetails: "Coûts, où obtenir chaque document et ce qui diffère entre communes :",
    disclaimer: "Ceci est un guide indépendant. Vérifiez la liste actuelle du canton avant de déposer la demande.",
    footerLine: "viapunt.ch",
  },
};

const it: More = {
  navArticles: "Articoli",
  cards: {
    glossary: { title: "Glossario", text: "Parole tedesche di lettere, moduli e test, spiegate nella tua lingua." },
    eligibility: { title: "Verifica dei requisiti", text: "Rispondi ad alcune domande e scopri quale via può fare per te. Funziona nel browser." },
    checklist: { title: "Lista dei documenti (Zurigo)", text: "Spunta i documenti necessari e stampa la lista su una pagina." },
  },
  tags: { glossary: "Parole", eligibility: "Strumento", checklist: "Stampa" },
  articles: {
    indexTitle: "Articoli sulla naturalizzazione in Svizzera",
    indexDescription: "Articoli chiari su chi può diventare svizzero, le tappe, il test di conoscenze e la vita dopo la naturalizzazione, con le fonti.",
    indexH1: "Articoli",
    indexLead: "Spiegazioni chiare alle domande più frequenti, ognuna con le sue fonti e la data in cui i fatti sono stati verificati.",
    soon: "I primi articoli arrivano presto. Intanto parti dalla panoramica.",
    cantonsTitle: "La naturalizzazione per cantone",
    cantonsDescription: "Guide sulla naturalizzazione nei singoli cantoni: periodi di residenza, test, tasse e dove presentare la domanda.",
    cantonsH1: "Guide per cantone",
    cantonsLead: "Che cosa cambia da un cantone all'altro, una guida per ciascuno.",
    cantonsSoon: "Le prime guide cantonali arrivano presto.",
    toCantons: "Guide per cantone",
    toArticles: "Tutti gli articoli",
    categories: {
      eligibility: "Chi può presentare domanda",
      cantons: "Cantoni",
      test: "Il test di conoscenze",
      process: "La procedura",
      after: "Dopo la naturalizzazione",
    },
    byline: "A cura del team Viapunt",
    published: "Pubblicato il",
    updated: "Aggiornato il",
    checked: "Fatti verificati il {date}",
    inBrief: "In breve",
    sources: "Fonti",
    faq: "Domande e risposte",
    relatedGuides: "Pagine della guida correlate",
    moreArticles: "Altri articoli",
    guideRelated: "Articoli correlati",
    latest: "Ultimi articoli",
    all: "Tutti gli articoli",
    machine: "Tradotto dall'inglese. In caso di dubbio fa fede la versione inglese.",
    readEnglish: "Leggi la versione inglese",
    rss: "Articoli Viapunt (RSS)",
    cantonLabel: "Cantone",
    breadcrumbHome: "Home",
  },
  glossary: {
    title: "Glossario dei termini tedeschi sulla naturalizzazione",
    description: "Parole tedesche che si incontrano in lettere, moduli e nel test di conoscenze sulla cittadinanza svizzera, spiegate nella tua lingua.",
    h1: "Glossario",
    lead: "Parole tedesche che puoi incontrare in lettere, moduli e nel test. Ogni voce riporta prima il termine tedesco, poi il suo significato.",
    germanTerm: "Termine tedesco",
    inEnglish: "Spiegazione in inglese; nella tua lingua non c'è ancora un testo.",
    keep: "Impara la parola tedesca: è quella usata nel test e nelle lettere.",
    setName: "Glossario Viapunt",
    noteDe: "",
  },
  eligibility: {
    title: "Verifica: quale via verso la cittadinanza svizzera?",
    description: "Rispondi ad alcune domande per vedere quale via verso la cittadinanza svizzera può fare per te e che cosa manca ancora. Funziona nel browser; non viene inviato nulla.",
    h1: "Quale via può fare per te?",
    lead: "Rispondi ad alcune domande. Vedrai quale via verso la cittadinanza svizzera può fare per te e che cosa manca ancora. Questa è una guida, non una decisione.",
    privacy: "Tutto avviene solo nel tuo browser. Nulla di ciò che inserisci viene inviato, salvato o registrato.",
    disclaimer: "Questa è una guida, non una decisione. Decidono solo il tuo comune, il tuo cantone e la Segreteria di Stato della migrazione (SEM). Le regole variano da cantone a cantone e possono cambiare.",
    numberHint: "Anni interi; un anno iniziato non conta.",
    qCanton: "Dove vivi?",
    optZurich: "Cantone di Zurigo",
    optOther: "Un altro cantone",
    qMarried: "Sei sposato/a con un cittadino o una cittadina svizzera?",
    qMarriageYears: "Da quanti anni sei sposato/a?",
    qTogether: "Vivete insieme come coppia sposata?",
    qPermit: "Hai un permesso di domicilio (C)?",
    qYears: "Per quanti anni hai vissuto in Svizzera? Conta gli anni con permesso B o C. Gli anni con permesso F contano per metà; N e L non contano.",
    qYoung: "Quanti di questi anni cadono tra il tuo 8° e il tuo 18° compleanno?",
    qLast5: "Negli ultimi 5 anni, quanti hai vissuto in Svizzera?",
    qCommune: "Da quanti anni vivi nel tuo comune attuale?",
    qBorn: "Sei nato/a in Svizzera?",
    qSchool: "Quanti anni di scuola dell'obbligo hai frequentato in Svizzera?",
    qUnder25: "Hai meno di 25 anni?",
    qFamily: "Uno dei tuoi genitori ha un permesso C, dieci anni di soggiorno in Svizzera e cinque anni di scuola qui, e uno dei tuoi nonni è nato in Svizzera o aveva un diritto di soggiorno?",
    yes: "Sì",
    no: "No",
    notSure: "Non so",
    submit: "Mostra la mia via probabile",
    idle: "Rispondi alle domande e premi il pulsante.",
    errNumber: "Controlla: inserisci un numero intero di anni in ogni campo numerico.",
    heading: "La tua via probabile",
    likely: "In base alle tue risposte, questa via può fare per te: {route}.",
    none: "In base alle tue risposte, nessuna via è ancora completa. Ecco che cosa manca.",
    routes: {
      ordinary: "Naturalizzazione ordinaria",
      spouse: "Naturalizzazione agevolata per i coniugi di cittadini svizzeri",
      third: "Naturalizzazione agevolata della terza generazione",
    },
    status: { fits: "Può andare bene", check: "Da chiarire con l'autorità", notYet: "Non ancora" },
    missingHeading: "Che cosa manca o va verificato",
    nothingMissing: "Sui punti chiesti qui non manca nulla.",
    m: {
      permit: "Un permesso di domicilio (C) valido.",
      counted: "Residenza conteggiata: {n} anni; la regola richiede 10 anni (gli anni tra gli 8 e i 18 anni contano doppio).",
      actual: "Residenza effettiva: {n} anni; almeno 6 devono essere anni realmente vissuti qui.",
      last5: "Almeno 3 degli ultimi 5 anni devono essere stati vissuti in Svizzera; hai indicato {n}.",
      commune: "Zurigo chiede almeno 2 anni nello stesso comune subito prima della domanda; hai indicato {n}. Se presenti la domanda prima dei 25 anni, bastano 2 anni in qualsiasi luogo del Cantone.",
      spouseMarried: "3 anni di vita in comunione coniugale con il tuo coniuge svizzero; hai indicato {n}.",
      spouseYears: "Cinque anni di soggiorno in Svizzera in totale; hai indicato {n}.",
      spouseLast: "L'ultimo anno prima della domanda deve essere stato vissuto in Svizzera.",
      together: "Vivere insieme come coppia sposata.",
      born: "Essere nato/a in Svizzera.",
      school: "Almeno 5 anni di scuola dell'obbligo in Svizzera; hai indicato {n}.",
      age: "Presentare la domanda prima del 25° compleanno.",
      permitThird: "Un permesso di domicilio (C).",
      family: "Le condizioni riguardanti genitori e nonni. Verificale con la SEM.",
    },
    extraOrdinary: "Per la naturalizzazione ordinaria servono anche, ma non sono chiesti qui: tedesco al livello B1 orale e A2 scritto, rispetto della sicurezza e dell'ordine pubblici, partecipazione alla vita economica o alla formazione, e nessun aiuto sociale nei tre anni prima della domanda.",
    otherCanton: "Il tuo cantone e il tuo comune possono richiedere un periodo minimo di residenza sul posto; la SEM indica da due a cinque anni. Chiedi al tuo comune.",
    readNext: "Da leggere dopo",
    semSpouses: "SEM: coniugi (tedesco)",
    semThird: "SEM: terza generazione (tedesco)",
  },
  checklist: {
    title: "Lista dei documenti per la naturalizzazione a Zurigo",
    description: "Una lista stampabile dei documenti per la naturalizzazione ordinaria nel cantone di Zurigo, con l'età massima di ciascuno. Sta su una pagina A4.",
    h1: "Lista dei documenti (Zurigo)",
    lead: "Per la naturalizzazione ordinaria nel cantone di Zurigo. Spunta ciò che hai, poi stampa la pagina. Si basa sulla guida ai documenti, verificata il 30 ottobre 2026.",
    print: "Stampa questa pagina",
    printHint: "Su carta, spunta le caselle con una penna.",
    groups: [
      {
        id: "everyone",
        title: "Per ogni persona della domanda",
        items: [
          "Documento dello stato civile (per esempio attestato dello stato civile). Al massimo 6 mesi il giorno della presentazione.",
          "Prova dell'attività attuale (dai 12 anni): conferma del datore di lavoro o della scuola, pagine da 1 a 4 della dichiarazione d'imposta per gli indipendenti, estratti delle prestazioni o prova del patrimonio. Al massimo 3 mesi.",
        ],
      },
      {
        id: "ifyouhave",
        title: "Se li hai già (dai 12 anni)",
        items: [
          "Prova di tedesco (B1 orale, A2 scritto): certificato riconosciuto, diploma in lingua tedesca o pagelle. Non serve se il tedesco è la tua lingua madre.",
          "Prova delle conoscenze di base: pagelle, titolo svizzero del livello secondario II o attestato del test di conoscenze.",
        ],
      },
      {
        id: "sometimes",
        title: "Solo in alcuni casi",
        items: [
          "Prova dell'affidamento esclusivo, o consenso di entrambi i genitori, se sono inclusi figli minorenni.",
          "Dichiarazione sull'unione domestica registrata e prova della cittadinanza del partner, se vuoi i periodi più brevi per i partner registrati.",
          "Prova della situazione personale (per esempio certificato medico), se una malattia o una disabilità ti impedisce di soddisfare un requisito.",
        ],
      },
      {
        id: "before",
        title: "Prima di presentare la domanda",
        items: [
          "Sono iscritto/a nel registro svizzero dello stato civile. Se sei nato/a o sposato/a all'estero, iscriviti prima: può richiedere da alcune settimane a diversi mesi.",
          "Ho chiesto al mio comune se i test di tedesco e di conoscenze si svolgono prima o dopo la domanda.",
          "Ho ordinato i documenti per ultimi: il documento dello stato civile al massimo 6 mesi, gli altri al massimo 3 mesi prima della presentazione.",
          "Sono pronto/a a presentare la domanda online su zh.ch/e-einbuergerung.",
        ],
      },
    ],
    notCollect: "Non devi richiedere un estratto del registro delle esecuzioni, un estratto del casellario giudiziale, un attestato fiscale né una conferma di aiuto sociale. Le autorità li ottengono da sole.",
    moreDetails: "Costi, dove ottenere ogni documento e che cosa cambia tra i comuni:",
    disclaimer: "Questa è una guida indipendente. Controlla la lista attuale del cantone prima di presentare la domanda.",
    footerLine: "viapunt.ch",
  },
};

const pt: More = {
  navArticles: "Artigos",
  cards: {
    glossary: { title: "Glossário", text: "Palavras alemãs de cartas, formulários e do teste, explicadas na sua língua." },
    eligibility: { title: "Verificação de requisitos", text: "Responda a algumas perguntas e veja que via pode servir. Funciona no seu navegador." },
    checklist: { title: "Lista de documentos (Zurique)", text: "Assinale os documentos necessários e imprima a lista numa página." },
  },
  tags: { glossary: "Palavras", eligibility: "Ferramenta", checklist: "Imprimir" },
  articles: {
    indexTitle: "Artigos sobre a naturalização na Suíça",
    indexDescription: "Artigos claros sobre quem pode tornar-se suíço, as etapas, o teste de conhecimentos e a vida depois da naturalização, com as fontes.",
    indexH1: "Artigos",
    indexLead: "Explicações claras para as perguntas mais frequentes, cada uma com as suas fontes e a data em que os factos foram verificados.",
    soon: "Os primeiros artigos chegam em breve. Entretanto, comece pela visão geral.",
    cantonsTitle: "A naturalização por cantão",
    cantonsDescription: "Guias sobre a naturalização em cada cantão: períodos de residência, testes, taxas e onde apresentar o pedido.",
    cantonsH1: "Guias por cantão",
    cantonsLead: "O que muda de cantão para cantão, um guia para cada um.",
    cantonsSoon: "Os primeiros guias cantonais chegam em breve.",
    toCantons: "Guias por cantão",
    toArticles: "Todos os artigos",
    categories: {
      eligibility: "Quem pode pedir",
      cantons: "Cantões",
      test: "O teste de conhecimentos",
      process: "O procedimento",
      after: "Depois da naturalização",
    },
    byline: "Pela equipa Viapunt",
    published: "Publicado em",
    updated: "Atualizado em",
    checked: "Factos verificados em {date}",
    inBrief: "Em resumo",
    sources: "Fontes",
    faq: "Perguntas e respostas",
    relatedGuides: "Páginas do guia relacionadas",
    moreArticles: "Mais artigos",
    guideRelated: "Artigos relacionados",
    latest: "Artigos mais recentes",
    all: "Todos os artigos",
    machine: "Traduzido do inglês. Em caso de dúvida, a versão em inglês é a de referência.",
    readEnglish: "Ler a versão em inglês",
    rss: "Artigos Viapunt (RSS)",
    cantonLabel: "Cantão",
    breadcrumbHome: "Início",
  },
  glossary: {
    title: "Glossário de termos alemães sobre a naturalização",
    description: "Palavras alemãs que encontra em cartas, formulários e no teste de conhecimentos sobre a cidadania suíça, explicadas na sua língua.",
    h1: "Glossário",
    lead: "Palavras alemãs que pode encontrar em cartas, formulários e no teste. Cada entrada mostra primeiro o termo alemão e depois o seu significado.",
    germanTerm: "Termo alemão",
    inEnglish: "Explicação em inglês; ainda não há texto na sua língua.",
    keep: "Fixe a palavra alemã: é a que o teste e as cartas usam.",
    setName: "Glossário Viapunt",
    noteDe: "",
  },
  eligibility: {
    title: "Verificação: que via para a cidadania suíça?",
    description: "Responda a algumas perguntas para ver que via para a cidadania suíça pode servir e o que ainda falta. Funciona no navegador; nada é enviado.",
    h1: "Que via pode servir?",
    lead: "Responda a algumas perguntas. Verá que via para a cidadania suíça pode servir e o que ainda falta. Isto é um guia, não uma decisão.",
    privacy: "Isto funciona apenas no seu navegador. Nada do que introduzir é enviado, guardado ou registado.",
    disclaimer: "Isto é um guia, não uma decisão. Só o seu município, o seu cantão e a Secretaria de Estado da Migração (SEM) decidem. As regras variam entre cantões e podem mudar.",
    numberHint: "Anos inteiros; um ano incompleto não conta.",
    qCanton: "Onde vive?",
    optZurich: "Cantão de Zurique",
    optOther: "Outro cantão",
    qMarried: "É casado/a com um cidadão ou uma cidadã suíça?",
    qMarriageYears: "Há quantos anos é casado/a?",
    qTogether: "Vivem juntos como casal casado?",
    qPermit: "Tem uma autorização de estabelecimento (C)?",
    qYears: "Quantos anos viveu na Suíça? Conte os anos com autorização B ou C. Os anos com autorização F contam metade; N e L não contam.",
    qYoung: "Quantos desses anos estão entre os seus 8 e os 18 anos?",
    qLast5: "Dos últimos 5 anos, quantos viveu na Suíça?",
    qCommune: "Há quantos anos vive no seu município atual?",
    qBorn: "Nasceu na Suíça?",
    qSchool: "Quantos anos de escolaridade obrigatória frequentou na Suíça?",
    qUnder25: "Tem menos de 25 anos?",
    qFamily: "Um dos seus pais tem autorização C, dez anos de residência na Suíça e cinco anos de escola aqui, e um dos seus avós nasceu na Suíça ou tinha direito de residência?",
    yes: "Sim",
    no: "Não",
    notSure: "Não tenho a certeza",
    submit: "Mostrar a minha via provável",
    idle: "Responda às perguntas e prima o botão.",
    errNumber: "Verifique: introduza um número inteiro de anos em cada campo numérico.",
    heading: "A sua via provável",
    likely: "Pelas suas respostas, esta via pode servir: {route}.",
    none: "Pelas suas respostas, ainda nenhuma via está completa. Eis o que falta.",
    routes: {
      ordinary: "Naturalização ordinária",
      spouse: "Naturalização facilitada para cônjuges de cidadãos suíços",
      third: "Naturalização facilitada da terceira geração",
    },
    status: { fits: "Pode servir", check: "A esclarecer com a autoridade", notYet: "Ainda não" },
    missingHeading: "O que falta ou deve ser verificado",
    nothingMissing: "Nos pontos aqui perguntados não falta nada.",
    m: {
      permit: "Uma autorização de estabelecimento (C) válida.",
      counted: "Residência contada: {n} anos; a regra exige 10 (os anos entre os 8 e os 18 anos contam a dobrar).",
      actual: "Residência efetiva: {n} anos; pelo menos 6 têm de ser anos realmente vividos aqui.",
      last5: "Pelo menos 3 dos últimos 5 anos têm de ter sido vividos na Suíça; indicou {n}.",
      commune: "Zurique exige pelo menos 2 anos no mesmo município imediatamente antes do pedido; indicou {n}. Se apresentar o pedido antes dos 25 anos, bastam 2 anos em qualquer lugar do cantão.",
      spouseMarried: "3 anos de vida em comunhão conjugal com o seu cônjuge suíço; indicou {n}.",
      spouseYears: "Cinco anos de residência na Suíça no total; indicou {n}.",
      spouseLast: "O último ano antes do pedido tem de ter sido vivido na Suíça.",
      together: "Viver juntos como casal casado.",
      born: "Ter nascido na Suíça.",
      school: "Pelo menos 5 anos de escolaridade obrigatória na Suíça; indicou {n}.",
      age: "Apresentar o pedido antes do 25.º aniversário.",
      permitThird: "Uma autorização de estabelecimento (C).",
      family: "As condições relativas aos pais e avós. Verifique-as junto da SEM.",
    },
    extraOrdinary: "Para a naturalização ordinária são ainda necessários, e não são perguntados aqui: alemão ao nível B1 oral e A2 escrito, respeito pela segurança e ordem públicas, participação na vida económica ou na formação, e nenhum apoio social nos três anos anteriores ao pedido.",
    otherCanton: "O seu cantão e o seu município podem exigir um período mínimo de residência no local; a SEM refere de dois a cinco anos. Pergunte ao seu município.",
    readNext: "Ler a seguir",
    semSpouses: "SEM: cônjuges (alemão)",
    semThird: "SEM: terceira geração (alemão)",
  },
  checklist: {
    title: "Lista de documentos para a naturalização em Zurique",
    description: "Uma lista imprimível dos documentos para a naturalização ordinária no cantão de Zurique, com a idade máxima de cada um. Cabe numa página A4.",
    h1: "Lista de documentos (Zurique)",
    lead: "Para a naturalização ordinária no cantão de Zurique. Assinale o que tem e depois imprima a página. Baseada no guia dos documentos, verificado a 30 de outubro de 2026.",
    print: "Imprimir esta página",
    printHint: "No papel, assinale as caixas com uma caneta.",
    groups: [
      {
        id: "everyone",
        title: "Para cada pessoa no pedido",
        items: [
          "Documento do registo civil (por exemplo, atestado de estado civil). No máximo 6 meses no dia da entrega.",
          "Prova da atividade atual (a partir dos 12 anos): confirmação da entidade patronal ou da escola, páginas 1 a 4 da declaração de impostos se for independente, extratos de prestações ou prova de património. No máximo 3 meses.",
        ],
      },
      {
        id: "ifyouhave",
        title: "Se já os tiver (a partir dos 12 anos)",
        items: [
          "Prova de alemão (B1 oral, A2 escrito): certificado reconhecido, diploma em língua alemã ou boletins escolares. Não é necessária se o alemão for a sua língua materna.",
          "Prova de conhecimentos básicos: boletins escolares, qualificação suíça do ensino secundário superior ou certificado do teste de conhecimentos.",
        ],
      },
      {
        id: "sometimes",
        title: "Apenas em certas situações",
        items: [
          "Prova da guarda exclusiva, ou consentimento de ambos os pais, se estiverem incluídos filhos menores.",
          "Declaração sobre a parceria registada e prova da cidadania do parceiro, se quiser os prazos mais curtos para parceiros registados.",
          "Prova da situação pessoal (por exemplo, atestado médico), se uma doença ou deficiência o impedir de cumprir um requisito.",
        ],
      },
      {
        id: "before",
        title: "Antes de entregar o pedido",
        items: [
          "Estou inscrito/a no registo civil suíço. Se nasceu ou casou no estrangeiro, inscreva-se primeiro: pode demorar de semanas a meses.",
          "Perguntei ao meu município se os testes de alemão e de conhecimentos são antes ou depois do pedido.",
          "Pedi os documentos por último: o do registo civil no máximo 6 meses, os restantes no máximo 3 meses antes da entrega.",
          "Estou pronto/a para entregar o pedido em linha em zh.ch/e-einbuergerung.",
        ],
      },
    ],
    notCollect: "Não precisa de pedir um extrato do registo de execuções, um extrato do registo criminal, um certificado fiscal nem uma confirmação de apoio social. As autoridades obtêm-nos elas próprias.",
    moreDetails: "Custos, onde obter cada documento e o que difere entre municípios:",
    disclaimer: "Este é um guia independente. Verifique a lista atual do cantão antes de entregar o pedido.",
    footerLine: "viapunt.ch",
  },
};

const es: More = {
  navArticles: "Artículos",
  cards: {
    glossary: { title: "Glosario", text: "Palabras alemanas de cartas, formularios y del examen, explicadas en tu idioma." },
    eligibility: { title: "Comprobación de requisitos", text: "Responde a unas preguntas y mira qué vía puede encajar. Funciona en tu navegador." },
    checklist: { title: "Lista de documentos (Zúrich)", text: "Marca los documentos necesarios e imprime la lista en una página." },
  },
  tags: { glossary: "Palabras", eligibility: "Herramienta", checklist: "Imprimir" },
  articles: {
    indexTitle: "Artículos sobre la naturalización en Suiza",
    indexDescription: "Artículos claros sobre quién puede hacerse suizo, los pasos, la prueba de conocimientos y la vida tras la naturalización, con fuentes.",
    indexH1: "Artículos",
    indexLead: "Explicaciones claras a las preguntas más frecuentes, cada una con sus fuentes y la fecha en que se comprobaron los hechos.",
    soon: "Los primeros artículos llegarán pronto. Mientras tanto, empieza por el resumen.",
    cantonsTitle: "La naturalización por cantón",
    cantonsDescription: "Guías sobre la naturalización en cada cantón: periodos de residencia, pruebas, tasas y dónde presentar la solicitud.",
    cantonsH1: "Guías por cantón",
    cantonsLead: "Qué cambia de un cantón a otro, una guía para cada uno.",
    cantonsSoon: "Las primeras guías cantonales llegarán pronto.",
    toCantons: "Guías por cantón",
    toArticles: "Todos los artículos",
    categories: {
      eligibility: "Quién puede solicitarla",
      cantons: "Cantones",
      test: "La prueba de conocimientos",
      process: "El procedimiento",
      after: "Después de la naturalización",
    },
    byline: "Por el equipo de Viapunt",
    published: "Publicado el",
    updated: "Actualizado el",
    checked: "Datos comprobados el {date}",
    inBrief: "En breve",
    sources: "Fuentes",
    faq: "Preguntas y respuestas",
    relatedGuides: "Páginas de la guía relacionadas",
    moreArticles: "Más artículos",
    guideRelated: "Artículos relacionados",
    latest: "Últimos artículos",
    all: "Todos los artículos",
    machine: "Traducido del inglés. Si algo no está claro, la versión en inglés es la de referencia.",
    readEnglish: "Leer la versión en inglés",
    rss: "Artículos de Viapunt (RSS)",
    cantonLabel: "Cantón",
    breadcrumbHome: "Inicio",
  },
  glossary: {
    title: "Glosario de términos alemanes de la naturalización",
    description: "Palabras alemanas que aparecen en cartas, formularios y en la prueba de conocimientos sobre la ciudadanía suiza, explicadas en tu idioma.",
    h1: "Glosario",
    lead: "Palabras alemanas que puedes encontrar en cartas, formularios y en el examen. Cada entrada muestra primero el término alemán y después su significado.",
    germanTerm: "Término alemán",
    inEnglish: "Explicación en inglés; todavía no hay texto en tu idioma.",
    keep: "Aprende la palabra alemana: es la que usan el examen y las cartas.",
    setName: "Glosario de Viapunt",
    noteDe: "",
  },
  eligibility: {
    title: "Comprobación: ¿qué vía hacia la ciudadanía suiza?",
    description: "Responde a unas preguntas para ver qué vía hacia la ciudadanía suiza puede encajar contigo y qué falta todavía. Funciona en el navegador; no se envía nada.",
    h1: "¿Qué vía puede encajar contigo?",
    lead: "Responde a unas preguntas. Verás qué vía hacia la ciudadanía suiza puede encajar contigo y qué falta todavía. Esto es una guía, no una decisión.",
    privacy: "Esto funciona solo en tu navegador. Nada de lo que escribas se envía, se guarda ni se registra.",
    disclaimer: "Esto es una guía, no una decisión. Solo deciden tu municipio, tu cantón y la Secretaría de Estado de Migración (SEM). Las normas varían entre cantones y pueden cambiar.",
    numberHint: "Años completos; un año empezado no cuenta.",
    qCanton: "¿Dónde vives?",
    optZurich: "Cantón de Zúrich",
    optOther: "Otro cantón",
    qMarried: "¿Estás casado/a con un ciudadano o una ciudadana suiza?",
    qMarriageYears: "¿Cuántos años llevas casado/a?",
    qTogether: "¿Vivís juntos como matrimonio?",
    qPermit: "¿Tienes un permiso de establecimiento (C)?",
    qYears: "¿Cuántos años has vivido en Suiza? Cuenta los años con permiso B o C. Los años con permiso F cuentan la mitad; N y L no cuentan.",
    qYoung: "¿Cuántos de esos años caen entre tus 8 y tus 18 años?",
    qLast5: "De los últimos 5 años, ¿cuántos has vivido en Suiza?",
    qCommune: "¿Cuántos años llevas viviendo en tu municipio actual?",
    qBorn: "¿Naciste en Suiza?",
    qSchool: "¿Cuántos años de escolaridad obligatoria cursaste en Suiza?",
    qUnder25: "¿Tienes menos de 25 años?",
    qFamily: "¿Alguno de tus padres tiene un permiso C, diez años de residencia en Suiza y cinco años de escuela aquí, y alguno de tus abuelos nació en Suiza o tenía derecho de residencia?",
    yes: "Sí",
    no: "No",
    notSure: "No estoy seguro/a",
    submit: "Ver mi vía probable",
    idle: "Responde a las preguntas y pulsa el botón.",
    errNumber: "Revisa: escribe un número entero de años en cada campo numérico.",
    heading: "Tu vía probable",
    likely: "Según tus respuestas, esta vía puede encajar contigo: {route}.",
    none: "Según tus respuestas, todavía no hay ninguna vía completa. Esto es lo que falta.",
    routes: {
      ordinary: "Naturalización ordinaria",
      spouse: "Naturalización facilitada para cónyuges de ciudadanos suizos",
      third: "Naturalización facilitada de la tercera generación",
    },
    status: { fits: "Puede encajar", check: "Consultar con la autoridad", notYet: "Todavía no" },
    missingHeading: "Lo que falta o hay que comprobar",
    nothingMissing: "En los puntos preguntados aquí no falta nada.",
    m: {
      permit: "Un permiso de establecimiento (C) válido.",
      counted: "Residencia computada: {n} años; la norma exige 10 (los años entre los 8 y los 18 cuentan doble).",
      actual: "Residencia efectiva: {n} años; al menos 6 deben ser años realmente vividos aquí.",
      last5: "Al menos 3 de los últimos 5 años deben haberse vivido en Suiza; indicaste {n}.",
      commune: "Zúrich exige al menos 2 años en el mismo municipio inmediatamente antes de la solicitud; indicaste {n}. Si presentas la solicitud antes de cumplir 25 años, bastan 2 años en cualquier lugar del cantón.",
      spouseMarried: "3 años de vida en comunidad matrimonial con tu cónyuge suizo; indicaste {n}.",
      spouseYears: "Cinco años de residencia en Suiza en total; indicaste {n}.",
      spouseLast: "El último año antes de la solicitud debe haberse vivido en Suiza.",
      together: "Vivir juntos como matrimonio.",
      born: "Haber nacido en Suiza.",
      school: "Al menos 5 años de escolaridad obligatoria en Suiza; indicaste {n}.",
      age: "Presentar la solicitud antes de cumplir 25 años.",
      permitThird: "Un permiso de establecimiento (C).",
      family: "Las condiciones sobre tus padres y abuelos. Compruébalas con la SEM.",
    },
    extraOrdinary: "Para la naturalización ordinaria hace falta además, y aquí no se pregunta: alemán de nivel B1 oral y A2 escrito, respeto de la seguridad y el orden públicos, participación en la vida económica o en la formación, y no haber recibido ayuda social en los tres años anteriores a la solicitud.",
    otherCanton: "Tu cantón y tu municipio pueden exigir un tiempo mínimo de residencia allí; la SEM menciona de dos a cinco años. Pregunta en tu municipio.",
    readNext: "Para leer a continuación",
    semSpouses: "SEM: cónyuges (alemán)",
    semThird: "SEM: tercera generación (alemán)",
  },
  checklist: {
    title: "Lista de documentos para la naturalización en Zúrich",
    description: "Una lista imprimible de los documentos para la naturalización ordinaria en el cantón de Zúrich, con la antigüedad máxima de cada uno. Cabe en una página A4.",
    h1: "Lista de documentos (Zúrich)",
    lead: "Para la naturalización ordinaria en el cantón de Zúrich. Marca lo que tienes y después imprime la página. Basada en la guía de documentos, comprobada el 30 de octubre de 2026.",
    print: "Imprimir esta página",
    printHint: "En papel, marca las casillas con un bolígrafo.",
    groups: [
      {
        id: "everyone",
        title: "Para cada persona de la solicitud",
        items: [
          "Documento del registro civil (por ejemplo, certificado de estado civil). Como máximo 6 meses el día de la presentación.",
          "Prueba de la actividad actual (desde los 12 años): confirmación del empleador o de la escuela, páginas 1 a 4 de la declaración de impuestos si eres autónomo, justificantes de prestaciones o prueba de patrimonio. Como máximo 3 meses.",
        ],
      },
      {
        id: "ifyouhave",
        title: "Si ya los tienes (desde los 12 años)",
        items: [
          "Prueba de alemán (B1 oral, A2 escrito): certificado reconocido, título cursado en alemán o boletines escolares. No hace falta si el alemán es tu lengua materna.",
          "Prueba de conocimientos básicos: boletines escolares, titulación suiza de secundaria superior o certificado de la prueba de conocimientos.",
        ],
      },
      {
        id: "sometimes",
        title: "Solo en algunos casos",
        items: [
          "Prueba de la custodia exclusiva, o consentimiento de ambos progenitores, si se incluyen hijos menores.",
          "Declaración sobre la pareja registrada y prueba de la ciudadanía de tu pareja, si quieres los plazos más cortos para parejas registradas.",
          "Prueba de circunstancias personales (por ejemplo, certificado médico), si una enfermedad o discapacidad te impide cumplir un requisito.",
        ],
      },
      {
        id: "before",
        title: "Antes de presentar la solicitud",
        items: [
          "Estoy inscrito/a en el registro civil suizo. Si naciste o te casaste en el extranjero, inscríbete primero: puede tardar de semanas a meses.",
          "He preguntado a mi municipio si las pruebas de alemán y de conocimientos son antes o después de la solicitud.",
          "He pedido los documentos al final: el del registro civil como máximo 6 meses, los demás como máximo 3 meses antes de presentarla.",
          "Estoy listo/a para presentar la solicitud en línea en zh.ch/e-einbuergerung.",
        ],
      },
    ],
    notCollect: "No tienes que pedir un extracto del registro de embargos, un extracto de antecedentes penales, un certificado fiscal ni una confirmación de ayuda social. Las autoridades los obtienen por sí mismas.",
    moreDetails: "Costes, dónde conseguir cada documento y qué cambia entre municipios:",
    disclaimer: "Esta es una guía independiente. Consulta la lista actual del cantón antes de presentar la solicitud.",
    footerLine: "viapunt.ch",
  },
};

const sq: More = {
  navArticles: "Artikuj",
  cards: {
    glossary: { title: "Fjalori", text: "Fjalë gjermane nga letrat, formularët dhe testi, të shpjeguara në gjuhën tuaj." },
    eligibility: { title: "Kontrolli i kushteve", text: "Përgjigjuni disa pyetjeve dhe shihni cila rrugë mund t'ju përshtatet. Funksionon në shfletuesin tuaj." },
    checklist: { title: "Lista e dokumenteve (Cyrih)", text: "Shënoni dokumentet e nevojshme dhe printoni listën në një faqe." },
  },
  tags: { glossary: "Fjalë", eligibility: "Mjet", checklist: "Printo" },
  articles: {
    indexTitle: "Artikuj mbi natyralizimin në Zvicër",
    indexDescription: "Artikuj të qartë mbi kush mund të bëhet zviceran, hapat, testin e njohurive dhe jetën pas natyralizimit, me burimet.",
    indexH1: "Artikuj",
    indexLead: "Shpjegime të qarta për pyetjet më të shpeshta, secili me burimet e veta dhe datën kur janë kontrolluar faktet.",
    soon: "Artikujt e parë vijnë së shpejti. Ndërkohë filloni me pasqyrën e përgjithshme.",
    cantonsTitle: "Natyralizimi sipas kantonit",
    cantonsDescription: "Udhëzues për natyralizimin në kantone të veçanta: afatet e qëndrimit, testet, tarifat dhe ku dorëzohet kërkesa.",
    cantonsH1: "Udhëzues sipas kantonit",
    cantonsLead: "Çfarë ndryshon nga një kanton te tjetri, një udhëzues për secilin.",
    cantonsSoon: "Udhëzuesit e parë kantonalë vijnë së shpejti.",
    toCantons: "Udhëzues sipas kantonit",
    toArticles: "Të gjithë artikujt",
    categories: {
      eligibility: "Kush mund të aplikojë",
      cantons: "Kantonet",
      test: "Testi i njohurive",
      process: "Procedura",
      after: "Pas natyralizimit",
    },
    byline: "Nga ekipi i Viapunt",
    published: "Publikuar më",
    updated: "Përditësuar më",
    checked: "Faktet u kontrolluan më {date}",
    inBrief: "Shkurt",
    sources: "Burimet",
    faq: "Pyetje dhe përgjigje",
    relatedGuides: "Faqe të lidhura të udhëzuesit",
    moreArticles: "Më shumë artikuj",
    guideRelated: "Artikuj të lidhur",
    latest: "Artikujt e fundit",
    all: "Të gjithë artikujt",
    machine: "Përkthyer nga anglishtja. Nëse diçka nuk është e qartë, versioni anglisht është ai i referencës.",
    readEnglish: "Lexo versionin anglisht",
    rss: "Artikujt e Viapunt (RSS)",
    cantonLabel: "Kantoni",
    breadcrumbHome: "Ballina",
  },
  glossary: {
    title: "Fjalori i termave gjermanë të natyralizimit",
    description: "Fjalë gjermane që has në letra, formularë dhe në testin e njohurive për shtetësinë zvicerane, të shpjeguara në gjuhën tuaj.",
    h1: "Fjalori",
    lead: "Fjalë gjermane që mund të has në letra, formularë dhe në test. Çdo shënim jep së pari termin gjerman, pastaj kuptimin e tij.",
    germanTerm: "Termi gjerman",
    inEnglish: "Shpjegim në anglisht; ende nuk ka tekst në gjuhën tuaj.",
    keep: "Mësoni fjalën gjermane: është ajo që përdorin testi dhe letrat.",
    setName: "Fjalori i Viapunt",
    noteDe: "",
  },
  eligibility: {
    title: "Kontrolli: cila rrugë drejt shtetësisë zvicerane?",
    description: "Përgjigjuni disa pyetjeve për të parë cila rrugë drejt shtetësisë zvicerane mund t'ju përshtatet dhe çfarë mungon ende. Funksionon në shfletues; nuk dërgohet asgjë.",
    h1: "Cila rrugë mund t'ju përshtatet?",
    lead: "Përgjigjuni disa pyetjeve. Do të shihni cila rrugë drejt shtetësisë zvicerane mund t'ju përshtatet dhe çfarë mungon ende. Ky është një udhëzues, jo një vendim.",
    privacy: "Kjo funksionon vetëm në shfletuesin tuaj. Asgjë nga ato që shkruani nuk dërgohet, ruhet apo regjistrohet.",
    disclaimer: "Ky është një udhëzues, jo një vendim. Vendosin vetëm komuna juaj, kantoni juaj dhe Sekretariati Shtetëror për Migracionin (SEM). Rregullat ndryshojnë nga kantoni në kanton dhe mund të ndryshojnë me kohën.",
    numberHint: "Vite të plota; një vit i filluar nuk numërohet.",
    qCanton: "Ku jetoni?",
    optZurich: "Kantoni i Cyrihut",
    optOther: "Një kanton tjetër",
    qMarried: "A jeni i/e martuar me një shtetas zviceran?",
    qMarriageYears: "Prej sa vitesh jeni i/e martuar?",
    qTogether: "A jetoni së bashku si çift i martuar?",
    qPermit: "A keni leje vendimi (C)?",
    qYears: "Sa vjet keni jetuar në Zvicër? Numëroni vitet me leje B ose C. Vitet me leje F numërohen përgjysmë; N dhe L nuk numërohen.",
    qYoung: "Sa nga këto vite bien midis ditëlindjes së 8-të dhe të 18-të?",
    qLast5: "Nga 5 vitet e fundit, sa keni jetuar në Zvicër?",
    qCommune: "Sa vjet jetoni në komunën tuaj aktuale?",
    qBorn: "A keni lindur në Zvicër?",
    qSchool: "Sa vjet shkollë të detyrueshme keni ndjekur në Zvicër?",
    qUnder25: "A jeni nën 25 vjeç?",
    qFamily: "A ka një prej prindërve tuaj leje C, dhjetë vjet qëndrim në Zvicër dhe pesë vjet shkollë këtu, dhe a ka lindur një gjysh a gjyshe në Zvicër ose ka pasur të drejtë qëndrimi?",
    yes: "Po",
    no: "Jo",
    notSure: "Nuk jam i sigurt",
    submit: "Shfaq rrugën time të mundshme",
    idle: "Përgjigjuni pyetjeve dhe shtypni butonin.",
    errNumber: "Kontrolloni: shkruani një numër të plotë vitesh në çdo fushë numerike.",
    heading: "Rruga juaj e mundshme",
    likely: "Sipas përgjigjeve tuaja, kjo rrugë mund t'ju përshtatet: {route}.",
    none: "Sipas përgjigjeve tuaja, asnjë rrugë nuk është ende e plotë. Ja çfarë mungon.",
    routes: {
      ordinary: "Natyralizimi i zakonshëm",
      spouse: "Natyralizimi i lehtësuar për bashkëshortët e shtetasve zviceranë",
      third: "Natyralizimi i lehtësuar i brezit të tretë",
    },
    status: { fits: "Mund të përshtatet", check: "Për t'u sqaruar me autoritetin", notYet: "Ende jo" },
    missingHeading: "Çfarë mungon ose duhet kontrolluar",
    nothingMissing: "Në pikat e pyetura këtu nuk mungon asgjë.",
    m: {
      permit: "Një leje vendimi (C) e vlefshme.",
      counted: "Qëndrimi i numëruar: {n} vjet; rregulli kërkon 10 (vitet midis 8 dhe 18 vjeç numërohen dyfish).",
      actual: "Qëndrimi real: {n} vjet; të paktën 6 duhet të jenë vite të jetuara vërtet këtu.",
      last5: "Të paktën 3 nga 5 vitet e fundit duhet të jenë jetuar në Zvicër; ju shënuat {n}.",
      commune: "Cyrihu kërkon të paktën 2 vjet në të njëjtën komunë menjëherë para kërkesës; ju shënuat {n}. Nëse e paraqitni kërkesën para moshës 25 vjeç, mjaftojnë 2 vjet kudo në kanton.",
      spouseMarried: "3 vjet jetë bashkëshortore me bashkëshortin tuaj zviceran; ju shënuat {n}.",
      spouseYears: "Pesë vjet qëndrim në Zvicër në total; ju shënuat {n}.",
      spouseLast: "Viti i fundit para kërkesës duhet të jetë jetuar në Zvicër.",
      together: "Të jetoni së bashku si çift i martuar.",
      born: "Të keni lindur në Zvicër.",
      school: "Të paktën 5 vjet shkollë të detyrueshme në Zvicër; ju shënuat {n}.",
      age: "Të dorëzoni kërkesën përpara ditëlindjes së 25-të.",
      permitThird: "Një leje vendimi (C).",
      family: "Kushtet për prindërit dhe gjyshërit. Sqaroni ato me SEM-in.",
    },
    extraOrdinary: "Për natyralizimin e zakonshëm duhen gjithashtu, dhe nuk pyeten këtu: gjermanishtja në nivelin B1 me gojë dhe A2 me shkrim, respektimi i sigurisë dhe rendit publik, pjesëmarrja në jetën ekonomike ose në arsim, dhe asnjë ndihmë sociale në tre vitet para kërkesës.",
    otherCanton: "Kantoni dhe komuna juaj mund të kërkojnë një kohëzgjatje minimale qëndrimi aty; SEM përmend dy deri në pesë vjet. Pyesni komunën tuaj.",
    readNext: "Lexo më pas",
    semSpouses: "SEM: bashkëshortët (gjermanisht)",
    semThird: "SEM: brezi i tretë (gjermanisht)",
  },
  checklist: {
    title: "Lista e dokumenteve për natyralizimin në Cyrih",
    description: "Një listë e printueshme e dokumenteve për natyralizimin e zakonshëm në kantonin e Cyrihut, me moshën maksimale të secilit. Hyn në një faqe A4.",
    h1: "Lista e dokumenteve (Cyrih)",
    lead: "Për natyralizimin e zakonshëm në kantonin e Cyrihut. Shënoni çfarë keni, pastaj printoni faqen. Bazuar në udhëzuesin e dokumenteve, kontrolluar më 30 tetor 2026.",
    print: "Printo këtë faqe",
    printHint: "Në letër, shënoni kutitë me stilolaps.",
    groups: [
      {
        id: "everyone",
        title: "Për çdo person në kërkesë",
        items: [
          "Dokument i gjendjes civile (për shembull vërtetim i gjendjes civile). Më së shumti 6 muaj të vjetër ditën e dorëzimit.",
          "Dëshmi e veprimtarisë aktuale (nga 12 vjeç): konfirmim nga punëdhënësi ose shkolla, faqet 1 deri 4 të deklaratës së tatimit për të vetëpunësuarit, dëshmi përfitimesh ose dëshmi pasurie. Më së shumti 3 muaj e vjetër.",
        ],
      },
      {
        id: "ifyouhave",
        title: "Nëse i keni tashmë (nga 12 vjeç)",
        items: [
          "Dëshmi e gjermanishtes (B1 me gojë, A2 me shkrim): certifikatë e njohur, diplomë në gjuhën gjermane ose dëftesa shkollore. Nuk nevojitet nëse gjermanishtja është gjuha juaj amtare.",
          "Dëshmi e njohurive bazë: dëftesa shkollore, kualifikim zviceran i arsimit të mesëm të lartë ose certifikata e testit të njohurive.",
        ],
      },
      {
        id: "sometimes",
        title: "Vetëm në disa raste",
        items: [
          "Dëshmi e kujdestarisë së vetme, ose pëlqimi i të dy prindërve, nëse përfshihen fëmijë të mitur.",
          "Deklaratë për partneritetin e regjistruar dhe dëshmi e shtetësisë së partnerit, nëse dëshironi afatet më të shkurtra për partnerët e regjistruar.",
          "Dëshmi e rrethanave personale (për shembull vërtetim mjekësor), nëse sëmundja ose paaftësia ju pengon të plotësoni një kërkesë.",
        ],
      },
      {
        id: "before",
        title: "Para se ta dorëzoni kërkesën",
        items: [
          "Jam i regjistruar në regjistrin zviceran të gjendjes civile. Nëse keni lindur ose jeni martuar jashtë vendit, regjistrohuni më parë: mund të zgjasë nga disa javë deri në disa muaj.",
          "I kam pyetur komunës sime nëse testet e gjermanishtes dhe të njohurive bëhen para apo pas kërkesës.",
          "I kam porositur dokumentet në fund: dokumentin e gjendjes civile më së shumti 6 muaj, të tjerat më së shumti 3 muaj para dorëzimit.",
          "Jam gati ta dorëzoj kërkesën në internet te zh.ch/e-einbuergerung.",
        ],
      },
    ],
    notCollect: "Nuk duhet të merrni ekstrakt nga regjistri i përmbarimit, ekstrakt të regjistrit penal, vërtetim tatimor apo konfirmim ndihme sociale. Autoritetet i marrin vetë.",
    moreDetails: "Kostot, ku merret çdo dokument dhe çfarë ndryshon midis komunave:",
    disclaimer: "Ky është një udhëzues i pavarur. Kontrolloni listën aktuale të kantonit para se ta dorëzoni kërkesën.",
    footerLine: "viapunt.ch",
  },
};

const tr: More = {
  navArticles: "Makaleler",
  cards: {
    glossary: { title: "Sözlük", text: "Mektuplarda, formlarda ve testte karşılaşılan Almanca sözcükler, kendi dilinizde açıklanır." },
    eligibility: { title: "Koşul kontrolü", text: "Birkaç soruyu yanıtlayın, hangi yolun size uygun olabileceğini görün. Tarayıcınızda çalışır." },
    checklist: { title: "Zürih belge listesi", text: "Gerekli belgeleri işaretleyin ve listeyi tek sayfada yazdırın." },
  },
  tags: { glossary: "Sözcükler", eligibility: "Araç", checklist: "Yazdır" },
  articles: {
    indexTitle: "İsviçre'de vatandaşlığa alınma üzerine makaleler",
    indexDescription: "Kimin İsviçre vatandaşı olabileceği, adımlar, bilgi testi ve vatandaşlık sonrası yaşam üzerine sade makaleler, kaynaklarıyla.",
    indexH1: "Makaleler",
    indexLead: "En sık sorulan sorulara sade yanıtlar; her birinde kaynaklar ve bilgilerin kontrol edildiği tarih yer alır.",
    soon: "İlk makaleler yakında geliyor. O zamana kadar genel bakışla başlayın.",
    cantonsTitle: "Kantonlara göre vatandaşlığa alınma",
    cantonsDescription: "Tek tek kantonlarda vatandaşlığa alınma rehberleri: ikamet süreleri, testler, ücretler ve başvurunun nereye yapılacağı.",
    cantonsH1: "Kantonlara göre rehberler",
    cantonsLead: "Kantondan kantona neyin değiştiği; her kanton için bir rehber.",
    cantonsSoon: "İlk kanton rehberleri yakında geliyor.",
    toCantons: "Kantonlara göre rehberler",
    toArticles: "Tüm makaleler",
    categories: {
      eligibility: "Kimler başvurabilir",
      cantons: "Kantonlar",
      test: "Bilgi testi",
      process: "Süreç",
      after: "Vatandaşlıktan sonra",
    },
    byline: "Viapunt ekibinden",
    published: "Yayımlanma",
    updated: "Güncelleme",
    checked: "Bilgiler {date} tarihinde kontrol edildi",
    inBrief: "Kısaca",
    sources: "Kaynaklar",
    faq: "Sorular ve yanıtlar",
    relatedGuides: "İlgili rehber sayfaları",
    moreArticles: "Diğer makaleler",
    guideRelated: "İlgili makaleler",
    latest: "Son makaleler",
    all: "Tüm makaleler",
    machine: "İngilizceden çevrilmiştir. Anlaşılmayan bir şey olursa İngilizce sürüm esas alınır.",
    readEnglish: "İngilizce sürümü okuyun",
    rss: "Viapunt makaleleri (RSS)",
    cantonLabel: "Kanton",
    breadcrumbHome: "Ana sayfa",
  },
  glossary: {
    title: "Vatandaşlığa alınma için Almanca terimler sözlüğü",
    description: "İsviçre vatandaşlığıyla ilgili mektuplarda, formlarda ve bilgi testinde karşılaşılan Almanca sözcükler, kendi dilinizde açıklanır.",
    h1: "Sözlük",
    lead: "Mektuplarda, formlarda ve testte karşılaşabileceğiniz Almanca sözcükler. Her maddede önce Almanca terim, sonra anlamı yer alır.",
    germanTerm: "Almanca terim",
    inEnglish: "Açıklama İngilizce; kendi dilinizde henüz metin yok.",
    keep: "Almanca sözcüğü öğrenin: test ve mektuplar onu kullanır.",
    setName: "Viapunt sözlüğü",
    noteDe: "",
  },
  eligibility: {
    title: "Koşul kontrolü: İsviçre vatandaşlığına hangi yol?",
    description: "Birkaç soruyu yanıtlayarak İsviçre vatandaşlığına giden hangi yolun size uygun olabileceğini ve nelerin eksik olduğunu görün. Tarayıcıda çalışır; hiçbir şey gönderilmez.",
    h1: "Hangi yol size uygun olabilir?",
    lead: "Birkaç soruyu yanıtlayın. İsviçre vatandaşlığına giden hangi yolun size uygun olabileceğini ve nelerin eksik olduğunu göreceksiniz. Bu bir rehberdir, karar değildir.",
    privacy: "Bu yalnızca tarayıcınızda çalışır. Yazdığınız hiçbir şey gönderilmez, saklanmaz veya kaydedilmez.",
    disclaimer: "Bu bir rehberdir, karar değildir. Yalnızca komününüz, kantonunuz ve Devlet Göç Sekreterliği (SEM) karar verir. Kurallar kantondan kantona değişir ve değişebilir.",
    numberHint: "Tam yıl olarak girin; başlamış ama dolmamış yıl sayılmaz.",
    qCanton: "Nerede yaşıyorsunuz?",
    optZurich: "Zürih kantonu",
    optOther: "Başka bir kanton",
    qMarried: "Bir İsviçre vatandaşıyla evli misiniz?",
    qMarriageYears: "Kaç yıldır evlisiniz?",
    qTogether: "Evli çift olarak birlikte yaşıyor musunuz?",
    qPermit: "C yerleşim izniniz var mı?",
    qYears: "İsviçre'de kaç yıl yaşadınız? B veya C izniyle geçen yılları sayın. F izniyle geçen yıllar yarım sayılır; N ve L sayılmaz.",
    qYoung: "Bu yıllardan kaçı 8. ve 18. doğum günleriniz arasında?",
    qLast5: "Son 5 yılın kaçını İsviçre'de yaşadınız?",
    qCommune: "Şu anki komününüzde kaç yıldır yaşıyorsunuz?",
    qBorn: "İsviçre'de mi doğdunuz?",
    qSchool: "İsviçre'de kaç yıl zorunlu eğitim gördünüz?",
    qUnder25: "25 yaşından küçük müsünüz?",
    qFamily: "Anne veya babanızdan birinin C izni, İsviçre'de on yıl ikameti ve burada beş yıl okulu var mı; ve büyükanne veya büyükbabanızdan biri İsviçre'de mi doğdu ya da ikamet hakkına mı sahipti?",
    yes: "Evet",
    no: "Hayır",
    notSure: "Emin değilim",
    submit: "Olası yolumu göster",
    idle: "Soruları yanıtlayın ve düğmeye basın.",
    errNumber: "Kontrol edin: her sayı alanına tam bir yıl sayısı yazın.",
    heading: "Olası yolunuz",
    likely: "Yanıtlarınıza göre bu yol size uygun olabilir: {route}.",
    none: "Yanıtlarınıza göre henüz tamamlanmış bir yol yok. Eksikler şunlar.",
    routes: {
      ordinary: "Olağan vatandaşlığa alınma",
      spouse: "İsviçre vatandaşlarının eşleri için kolaylaştırılmış vatandaşlığa alınma",
      third: "Üçüncü kuşak için kolaylaştırılmış vatandaşlığa alınma",
    },
    status: { fits: "Uygun olabilir", check: "Makamla netleştirin", notYet: "Henüz değil" },
    missingHeading: "Eksik olanlar veya kontrol edilecekler",
    nothingMissing: "Burada sorulan konularda eksik bir şey yok.",
    m: {
      permit: "Geçerli bir C yerleşim izni.",
      counted: "Sayılan ikamet: {n} yıl; kural 10 yıl ister (8 ile 18 yaş arasındaki yıllar iki kat sayılır).",
      actual: "Fiili ikamet: {n} yıl; en az 6 yıl burada gerçekten yaşanmış olmalı.",
      last5: "Son 5 yılın en az 3'ü İsviçre'de geçmiş olmalı; siz {n} yazdınız.",
      commune: "Zürih, başvurudan hemen önce aynı komünde en az 2 yıl ister; siz {n} yazdınız. Başvurunuzu 25 yaşından önce yaparsanız, kantonun herhangi bir yerinde 2 yıl yeterlidir.",
      spouseMarried: "İsviçreli eşinizle 3 yıldır evlilik birliği içinde yaşamak; siz {n} yazdınız.",
      spouseYears: "İsviçre'de toplam beş yıl ikamet; siz {n} yazdınız.",
      spouseLast: "Başvurudan önceki son yıl İsviçre'de geçmiş olmalı.",
      together: "Evli çift olarak birlikte yaşamak.",
      born: "İsviçre'de doğmuş olmak.",
      school: "İsviçre'de en az 5 yıl zorunlu eğitim; siz {n} yazdınız.",
      age: "Başvuruyu 25. doğum gününüzden önce yapmak.",
      permitThird: "Bir C yerleşim izni.",
      family: "Anne baba ve büyükanne büyükbabaya ilişkin koşullar. Bunları SEM ile netleştirin.",
    },
    extraOrdinary: "Olağan vatandaşlığa alınma için ayrıca şunlar gerekir ve burada sorulmaz: konuşmada B1, yazıda A2 düzeyinde Almanca, kamu güvenliğine ve düzenine saygı, çalışma ya da eğitimle ekonomik hayata katılım ve başvurudan önceki üç yılda sosyal yardım almamış olmak.",
    otherCanton: "Kantonunuz ve komününüz orada asgari bir ikamet süresi isteyebilir; SEM iki ila beş yıldan söz eder. Komününüze sorun.",
    readNext: "Sonra okuyun",
    semSpouses: "SEM: eşler (Almanca)",
    semThird: "SEM: üçüncü kuşak (Almanca)",
  },
  checklist: {
    title: "Zürih'te vatandaşlığa alınma belge listesi",
    description: "Zürih kantonunda olağan vatandaşlığa alınma için belgelerin yazdırılabilir listesi; her belgenin en fazla ne kadar eski olabileceğiyle. Tek A4 sayfasına sığar.",
    h1: "Zürih belge listesi",
    lead: "Zürih kantonunda olağan vatandaşlığa alınma için. Elinizde olanları işaretleyin, sonra sayfayı yazdırın. Belgeler rehberine dayanır, 30 Ekim 2026'da kontrol edilmiştir.",
    print: "Bu sayfayı yazdır",
    printHint: "Kağıt üzerinde kutuları kalemle işaretleyin.",
    groups: [
      {
        id: "everyone",
        title: "Başvurudaki her kişi için",
        items: [
          "Nüfus (medeni durum) dairesinden belge (örneğin medeni durum belgesi). Başvuru günü en fazla 6 aylık.",
          "Güncel faaliyet belgesi (12 yaş ve üzeri): işveren veya okul onayı, serbest çalışanlar için vergi beyannamesinin 1 ila 4. sayfaları, ödeme belgeleri veya varlık belgesi. En fazla 3 aylık.",
        ],
      },
      {
        id: "ifyouhave",
        title: "Zaten elinizde varsa (12 yaş ve üzeri)",
        items: [
          "Almanca belgesi (konuşmada B1, yazıda A2): tanınan bir sertifika, Almanca eğitim veren bir okuldan diploma veya karne. Anadiliniz Almancaysa gerekmez.",
          "Temel bilgi belgesi: karneler, İsviçre'de ikinci kademe ortaöğretim belgesi veya bilgi testi sertifikası.",
        ],
      },
      {
        id: "sometimes",
        title: "Yalnızca bazı durumlarda",
        items: [
          "Küçük çocuklar dahilse tek velayet belgesi veya her iki ebeveynin onayı.",
          "Kayıtlı birliktelik beyanı ve partnerin vatandaşlık belgesi; kayıtlı partnerler için daha kısa süreleri kullanmak istiyorsanız.",
          "Kişisel durum belgesi (örneğin doktor raporu); hastalık veya engel bir koşulu yerine getirmenizi engelliyorsa.",
        ],
      },
      {
        id: "before",
        title: "Başvurmadan önce",
        items: [
          "İsviçre nüfus kütüğüne kayıtlıyım. Yurt dışında doğduysanız veya evlendiyseniz önce kayıt yaptırın: haftalar ya da aylar sürebilir.",
          "Komünüme Almanca ve bilgi testinin başvurudan önce mi sonra mı yapıldığını sordum.",
          "Belgeleri en son sipariş ettim: medeni durum belgesi en fazla 6 ay, diğerleri en fazla 3 ay önce.",
          "Başvuruyu zh.ch/e-einbuergerung adresinden çevrimiçi yapmaya hazırım.",
        ],
      },
    ],
    notCollect: "İcra kaydı çıktısı, sabıka kaydı, vergi belgesi veya sosyal yardım onayı almanız gerekmez. Makamlar bunları kendileri edinir.",
    moreDetails: "Maliyetler, her belgenin nereden alınacağı ve komünler arasındaki farklar:",
    disclaimer: "Bu bağımsız bir rehberdir. Başvurmadan önce kantonun güncel listesine bakın.",
    footerLine: "viapunt.ch",
  },
};

const ALL: Record<string, More> = { en, de, fr, it, pt, es, sq, tr };

export function more(lang: string): More {
  return ALL[lang] ?? en;
}

/** "{n}" and friends: fills the placeholders of a template string. */
export function fill(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_m, k) => String(vars[k] ?? ""));
}
