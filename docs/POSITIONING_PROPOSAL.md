# Positioning proposal: lead with tutoring, not with "AI"

For Chris, 29 October 2026. Nothing here is implemented; it is a proposal to pick from.

## The problem

Today the product introduces itself as "an AI tutor", two of the three plans are called
"AI-only", and the add-on and trial text repeat the word. Parents who reach the site are
looking for help with their child's maths and science. Many are wary of AI, and "AI-only"
reads like "no human involved", which is the opposite of what Swiss Science Tutors stands
for. The product is also not AI only: every plan sits next to SST's tutors, the Hybrid plan
includes lessons, Ask a tutor is answered by a person, and the exam sprint is marked by a
person.

The suggestion is to lead every sentence with the benefit (homework and revision help, any
time, in the student's own course) and with SST's tutors, and to mention AI once, plainly,
where honesty requires it: the landing lead, the plan blurb for the subscription, and the
terms, privacy and AI-safety pages. The tutor itself still says it is an AI when asked.

## Inventory of strings that lead with "AI" today, with proposed replacements

Keys are the labels in `web/src/locales/*.json`; German and French follow once the English
is agreed. Plan keys and Stripe lookup keys (`ai_monthly`, `ai_annual`, `hybrid_monthly`,
`ask_tutor_single`, `exam_sprint`) do not change; only the words people see change.

| Where | Today | Proposed |
| --- | --- | --- |
| Landing lead (`landing.lead`) | "An AI tutor for IB, IGCSE, A Level and Swiss school maths and science that guides your child through homework and revision, with Swiss Science Tutors' human tutors one tap away." | "Homework and revision help for IB, IGCSE, A Level and Swiss school maths and science, any time your child needs it. Built by Swiss Science Tutors' tutors, powered by AI, with our tutors one tap away." |
| Landing button (`landing.cta`) | "Start a 7-day free trial" | Keep. |
| Trial note (`landing.trialNote`) | "Prices per student, in CHF. AI-only and hybrid plans start with a 7-day free trial; cancel any time before it ends and you pay nothing." | "Prices per student, in CHF. Every plan starts with a 7-day free trial; cancel before it ends and you pay nothing." |
| Plan name (`plans.ai_monthly.name`) | "AI-only, monthly" | See naming schemes below. |
| Plan blurb (`plans.ai_monthly.blurb`) | "AI tutor and practice for all your enabled courses, plus a weekly parent summary." | "Unlimited homework help and practice in your child's courses, any time, plus a weekly summary for you. The tutor is AI, trained on SST's teaching approach." |
| Plan name (`plans.ai_annual.name`) | "AI-only, annual" | See naming schemes below. |
| Plan blurb (`plans.ai_annual.blurb`) | "The same as monthly, paid once a year at a lower price." | "The same, paid once a year at a lower price." |
| Plan name (`plans.hybrid_monthly.name`) | "Hybrid" | See naming schemes below. "Hybrid" means little to parents. |
| Plan blurb (`plans.hybrid_monthly.blurb`) | "Everything in AI-only, plus one hour a month with an SST tutor and a monthly progress note." | "Everything in [base plan], plus a monthly one-hour lesson with an SST tutor and a written progress note." |
| Add-on (`plans.ask_tutor_single`) | "Ask a tutor": "A written answer from an SST tutor within 24 hours. One credit per question." | Keep the name. Blurb: "Stuck on something? An SST tutor writes back within 24 hours. One credit per question." |
| Add-on (`plans.exam_sprint`) | "IB exam sprint": "February to May revision plan, timed paper-style sets and three hours of tutor marking." | Keep; it already leads with the benefit and a person. |
| Fair-use line (`plans.limits`) | "Fair use: 300 tutor messages a month, 60 a day." | "Fair use: up to 300 questions a month, 60 a day." ("Questions" is what a parent counts.) |
| Student home (`student.comingSoon`, `student.integrity`) | "The chat tutor opens in the next phase..." / "The tutor explains and coaches; it never writes assessed coursework such as IAs, EEs or TOK essays." | Keep. Neither leads with AI. |
| Parent form hint (`parent.firstNameHint`) | "Only this name is shown to tutors. It is never sent to the AI." | Keep: this is a privacy promise and parents value it. |
| Footer link (`footer.aiSafety`) | "AI and safety" | Keep: the link is part of the legal footer. |
| Emails (`app/email/messages.py`) | No email leads with AI now that the invite sentence is gone. | Nothing to change. |
| PWA manifest name (`web/vite.config.ts`) | "SST Virtual Tutor" / short name "SST Tutor" | Keep. |
| PWA manifest description | "AI tutor for IB, IGCSE, A Level and Swiss school science and maths, by Swiss Science Tutors." | "Homework and revision help for IB, IGCSE, A Level and Swiss school maths and science, by Swiss Science Tutors." |
| Page `<meta name="description">` (`web/index.html`) | "SST Virtual Tutor by Swiss Science Tutors" | "Homework and revision help from Swiss Science Tutors, any time." |

Not in this app but worth aligning: the "Virtual Tutor" page on swisssciencetutors.ch that
the landing page links to, and the Stripe product names parents see on receipts and in the
billing portal (those are edited in the Stripe Dashboard; no code change).

## Three naming schemes for the plans

Each column lists the two subscription plans (monthly and annual are the same product with
two billing periods, so the name can be shared and the period shown separately as
"monthly" or "annual") and the plan with lessons.

| | Scheme A: what you get | Scheme B: tiers | Scheme C: SST family |
| --- | --- | --- | --- |
| `ai_monthly` / `ai_annual` | **Tutor** | **Essential** | **SST Tutor** |
| `hybrid_monthly` | **Tutor + lessons** | **Plus** | **SST Tutor + Lessons** |
| How it reads on the card | "Tutor, monthly: CHF ... per student per month" | "Essential, monthly" | "SST Tutor, monthly" |

- **Scheme A** says what is in the box. A parent sees "Tutor + lessons" and knows the
  difference without reading the blurb. Translates cleanly ("Tutor + Unterricht",
  "Tuteur + cours"). The word "Tutor" alone could be read as a person, so the blurb's one
  honest sentence ("The tutor is AI...") matters here.
- **Scheme B** is the common software pattern (Essential, Plus). Neutral and short, but the
  names carry no meaning: a parent has to read the blurb to learn that Plus includes a human
  lesson, which is the selling point.
- **Scheme C** ties every plan to the SST brand, which is the trust signal we want. Slightly
  longer, and "SST" repeats in the header on every page.

**Recommendation: Scheme A**, with the honest sentence in the blurb. It leads with the
benefit, makes the lesson plan the obvious upgrade, and keeps the human tutors in view on
every card. If you prefer a stronger brand link, Scheme C is the fallback.

With Scheme A the plan cards would read:

- **Tutor** (monthly or annual): "Unlimited homework help and practice in your child's
  courses, any time, plus a weekly summary for you. The tutor is AI, trained on SST's
  teaching approach."
- **Tutor + lessons**: "Everything in Tutor, plus a monthly one-hour lesson with an SST
  tutor and a written progress note." (Stays the highlighted card.)

## What stays as it is

- The tutor's name "SST Virtual Tutor". "Virtual" already signals it is not a person without
  saying "AI".
- Plan keys, Stripe lookup keys and all Python code.
- The legal footer links, including "AI and safety".
- The tutor always confirms it is an AI when asked (PLAN.md, "Persona and disclosure").

## Next step

Pick a scheme and approve or edit the English wording in the table. The display names and
blurbs then change in the three language files, the PWA description and the Stripe product
names; that is a small, same-day change.
