// The sample question on the home page. Copied from the question bank
// (content/questions/federal/referendum-gesetz-verhindern.yaml and its English translation);
// update both together if that question changes. The site has no access to the bank at build time.
export const SAMPLE_QUESTION = {
  id: "referendum-gesetz-verhindern",
  correct: "b",
  de: {
    question: "Was können Stimmberechtigte mit einem Referendum erreichen?",
    options: {
      a: "Sie können ein neues Gesetz selbst schreiben und in Kraft setzen.",
      b: "Sie können ein vom Parlament beschlossenes Gesetz verhindern.",
      c: "Sie können die Mitglieder des Bundesrates abwählen.",
      d: "Sie können das Parlament auflösen und Neuwahlen verlangen.",
    },
    explanation:
      "Mit einem Referendum können Stimmberechtigte verlangen, dass über ein vom Parlament beschlossenes Gesetz abgestimmt wird. Lehnt das Volk das Gesetz ab, tritt es nicht in Kraft.",
  },
  en: {
    question: "What can citizens entitled to vote achieve with a referendum?",
    options: {
      a: "They can write a new law themselves and bring it into force.",
      b: "They can prevent a law passed by Parliament.",
      c: "They can remove the members of the Federal Council (Bundesrat) from office.",
      d: "They can dissolve Parliament and demand new elections.",
    },
    explanation:
      "With a referendum, citizens entitled to vote can demand that a vote be held on a law passed by Parliament. If the people reject the law, it does not come into force.",
  },
} as const;
