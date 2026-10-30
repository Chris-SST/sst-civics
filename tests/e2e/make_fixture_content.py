"""Write 60 clearly marked example Zurich questions for the end-to-end tests.

The questions are generic civics facts in our own words (ids start with `e2e-`). They are
approved, each with an approved English translation, so a learner can practise and a mock
test (50 questions) can start. Nothing here is taken from a cantonal catalogue and nothing
is ever written into content/: the target is a separate directory (default var/e2e/content).

Usage:
  python tests/e2e/make_fixture_content.py [--out var/e2e/content]
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
MARK = "# EXAMPLE FOR END-TO-END TESTS ONLY. Not part of the question bank."
SOURCE = "https://www.ch.ch/de/"

# (scope, code, German name, English name, target)
TOPICS = [
    ("federal", "bund.institutionen", "Bundesbehörden", "Federal authorities", 20),
    ("federal", "bund.volksrechte", "Volksrechte", "Popular rights", 10),
    ("federal", "bund.foederalismus", "Föderalismus", "Federalism", 8),
    ("federal", "bund.land_leute", "Land und Leute", "Land and people", 6),
    ("canton", "kanton.zuerich", "Kanton Zürich", "Canton of Zurich", 11),
    ("commune", "gemeinde.alltag", "Gemeinde im Alltag", "The commune in daily life", 5),
]

B, V, F, L, Z, G = (
    "bund.institutionen",
    "bund.volksrechte",
    "bund.foederalismus",
    "bund.land_leute",
    "kanton.zuerich",
    "gemeinde.alltag",
)

# topic, German question, four German options, index of the correct one, German explanation,
# English question, four English options, English explanation
Q = [
    (
        B,
        "Wie viele Kantone hat die Schweiz?",
        ["20", "23", "26", "30"],
        2,
        "Die Schweiz besteht aus 26 Kantonen.",
        "How many cantons does Switzerland have?",
        ["20", "23", "26", "30"],
        "Switzerland consists of 26 cantons.",
    ),
    (
        F,
        "Aus wie vielen staatlichen Ebenen besteht die Schweiz?",
        ["Aus einer", "Aus zwei", "Aus drei", "Aus fünf"],
        2,
        "Es gibt drei Ebenen: den Bund, die Kantone und die Gemeinden.",
        "How many levels of government does Switzerland have?",
        ["One", "Two", "Three", "Five"],
        "There are three levels: the Confederation, the cantons and the communes.",
    ),
    (
        B,
        "Wie viele Kammern hat das Bundesparlament?",
        ["Eine", "Zwei", "Drei", "Vier"],
        1,
        "Das Parlament besteht aus zwei Kammern, die gleichberechtigt sind.",
        "How many chambers does the federal parliament have?",
        ["One", "Two", "Three", "Four"],
        "Parliament has two chambers with equal standing.",
    ),
    (
        B,
        "Wie heissen die beiden Kammern des Bundesparlaments?",
        [
            "Nationalrat und Ständerat",
            "Grosser Rat und Kleiner Rat",
            "Bundesrat und Nationalrat",
            "Landrat und Kantonsrat",
        ],
        0,
        "Die beiden Kammern heissen Nationalrat und Ständerat.",
        "What are the two chambers of the federal parliament called?",
        [
            "National Council and Council of States",
            "Grand Council and Small Council",
            "Federal Council and National Council",
            "Land Council and Cantonal Council",
        ],
        "The chambers are the National Council and the Council of States.",
    ),
    (
        B,
        "Wie viele Mitglieder hat der Nationalrat?",
        ["46", "100", "200", "246"],
        2,
        "Der Nationalrat hat 200 Mitglieder.",
        "How many members does the National Council have?",
        ["46", "100", "200", "246"],
        "The National Council has 200 members.",
    ),
    (
        B,
        "Wie viele Mitglieder hat der Ständerat?",
        ["26", "46", "100", "200"],
        1,
        "Der Ständerat hat 46 Mitglieder.",
        "How many members does the Council of States have?",
        ["26", "46", "100", "200"],
        "The Council of States has 46 members.",
    ),
    (
        B,
        "Wie viele Mitglieder hat der Bundesrat?",
        ["Fünf", "Sieben", "Neun", "Elf"],
        1,
        "Der Bundesrat, die Landesregierung, hat sieben Mitglieder.",
        "How many members does the Federal Council have?",
        ["Five", "Seven", "Nine", "Eleven"],
        "The Federal Council, the national government, has seven members.",
    ),
    (
        B,
        "Wie heisst die Bundesstadt?",
        ["Zürich", "Genf", "Bern", "Basel"],
        2,
        "Bern ist die Bundesstadt, der Sitz von Regierung und Parlament.",
        "What is the federal city called?",
        ["Zurich", "Geneva", "Bern", "Basel"],
        "Bern is the federal city, where the government and parliament sit.",
    ),
    (
        L,
        "Wie viele Landessprachen hat die Schweiz?",
        ["Zwei", "Drei", "Vier", "Fünf"],
        2,
        "Die Landessprachen sind Deutsch, Französisch, Italienisch und Rätoromanisch.",
        "How many national languages does Switzerland have?",
        ["Two", "Three", "Four", "Five"],
        "The national languages are German, French, Italian and Romansh.",
    ),
    (
        B,
        "Wer wählt die Mitglieder des Bundesrats?",
        [
            "Das Volk",
            "Die Vereinigte Bundesversammlung",
            "Die Kantonsregierungen",
            "Das Bundesgericht",
        ],
        1,
        "Beide Kammern des Parlaments wählen den Bundesrat gemeinsam.",
        "Who elects the members of the Federal Council?",
        [
            "The people",
            "The United Federal Assembly",
            "The cantonal governments",
            "The Federal Supreme Court",
        ],
        "Both chambers of parliament elect the Federal Council together.",
    ),
    (
        B,
        "Für wie viele Jahre wird der Nationalrat gewählt?",
        ["Zwei Jahre", "Drei Jahre", "Vier Jahre", "Sechs Jahre"],
        2,
        "Der Nationalrat wird für vier Jahre gewählt.",
        "For how many years is the National Council elected?",
        ["Two years", "Three years", "Four years", "Six years"],
        "The National Council is elected for four years.",
    ),
    (
        V,
        "Ab welchem Alter dürfen Schweizer Bürgerinnen und Bürger auf Bundesebene wählen?",
        ["16 Jahre", "18 Jahre", "20 Jahre", "25 Jahre"],
        1,
        "Das Stimm- und Wahlrecht auf Bundesebene beginnt mit 18 Jahren.",
        "From what age may Swiss citizens vote at federal level?",
        ["16", "18", "20", "25"],
        "The right to vote at federal level starts at 18.",
    ),
    (
        V,
        "Wie viele Unterschriften braucht eine eidgenössische Volksinitiative?",
        ["10 000", "50 000", "100 000", "500 000"],
        2,
        "Für eine Volksinitiative braucht es 100 000 gültige Unterschriften.",
        "How many signatures does a federal popular initiative need?",
        ["10,000", "50,000", "100,000", "500,000"],
        "A popular initiative needs 100,000 valid signatures.",
    ),
    (
        V,
        "Wie viele Unterschriften braucht ein fakultatives Referendum gegen ein Gesetz?",
        ["5 000", "50 000", "100 000", "200 000"],
        1,
        "Für ein fakultatives Referendum braucht es 50 000 gültige Unterschriften.",
        "How many signatures does an optional referendum against a law need?",
        ["5,000", "50,000", "100,000", "200,000"],
        "An optional referendum needs 50,000 valid signatures.",
    ),
    (
        L,
        "Wie heisst die Währung der Schweiz?",
        ["Euro", "Schweizer Franken", "Schweizer Mark", "Dollar"],
        1,
        "Die Währung ist der Schweizer Franken.",
        "What is the currency of Switzerland?",
        ["Euro", "Swiss franc", "Swiss mark", "Dollar"],
        "The currency is the Swiss franc.",
    ),
    (
        L,
        "An welchem Datum feiert die Schweiz ihren Nationalfeiertag?",
        ["1. Januar", "1. August", "11. November", "25. Dezember"],
        1,
        "Der Nationalfeiertag ist am 1. August.",
        "On what date does Switzerland celebrate its national day?",
        ["1 January", "1 August", "11 November", "25 December"],
        "The national day is on 1 August.",
    ),
    (
        B,
        "Wie heisst das Grundgesetz der Schweiz?",
        ["Zivilgesetzbuch", "Bundesverfassung", "Strafgesetzbuch", "Staatsvertrag"],
        1,
        "Die Bundesverfassung ist die oberste Rechtsgrundlage des Landes.",
        "What is the basic law of Switzerland called?",
        ["Civil Code", "Federal Constitution", "Criminal Code", "State treaty"],
        "The Federal Constitution is the country's highest legal foundation.",
    ),
    (
        F,
        "In welchem Jahr wurde der moderne Bundesstaat gegründet?",
        ["1291", "1648", "1848", "1999"],
        2,
        "Der heutige Bundesstaat besteht seit 1848.",
        "In which year was the modern federal state founded?",
        ["1291", "1648", "1848", "1999"],
        "The present federal state has existed since 1848.",
    ),
    (
        B,
        "Wie heisst das oberste Gericht der Schweiz?",
        ["Obergericht", "Bundesgericht", "Kantonsgericht", "Bezirksgericht"],
        1,
        "Das Bundesgericht in Lausanne ist das oberste Gericht.",
        "What is the highest court of Switzerland called?",
        ["Higher Court", "Federal Supreme Court", "Cantonal Court", "District Court"],
        "The Federal Supreme Court in Lausanne is the highest court.",
    ),
    (
        B,
        "Wie oft wechselt das Amt der Bundespräsidentin oder des Bundespräsidenten?",
        ["Jedes Jahr", "Alle zwei Jahre", "Alle vier Jahre", "Nie"],
        0,
        "Das Amt wechselt jedes Jahr unter den sieben Mitgliedern des Bundesrats.",
        "How often does the office of Federal President change hands?",
        ["Every year", "Every two years", "Every four years", "Never"],
        "The office rotates every year among the seven Federal Council members.",
    ),
    (
        V,
        "Wann ist über eine Änderung der Bundesverfassung immer abzustimmen?",
        ["Nie", "Nur bei Krieg", "Immer", "Nur im Sommer"],
        2,
        "Änderungen der Bundesverfassung müssen Volk und Kantonen vorgelegt werden.",
        "When must a change to the Federal Constitution be put to a vote?",
        ["Never", "Only in wartime", "Always", "Only in summer"],
        "Changes to the Constitution must be put to the people and the cantons.",
    ),
    (
        V,
        "Seit wann dürfen Frauen auf Bundesebene abstimmen und wählen?",
        ["1848", "1918", "1971", "2000"],
        2,
        "Das Frauenstimmrecht auf Bundesebene wurde 1971 eingeführt.",
        "Since when may women vote at federal level?",
        ["1848", "1918", "1971", "2000"],
        "Women's suffrage at federal level was introduced in 1971.",
    ),
    (
        V,
        "Was bedeutet direkte Demokratie?",
        [
            "Das Volk stimmt selbst über Sachfragen ab",
            "Der König entscheidet",
            "Nur das Parlament entscheidet",
            "Die Armee entscheidet",
        ],
        0,
        "In der direkten Demokratie entscheiden die Stimmberechtigten selbst über Vorlagen.",
        "What does direct democracy mean?",
        [
            "The people vote on issues themselves",
            "A king decides",
            "Only parliament decides",
            "The army decides",
        ],
        "In direct democracy the voters decide on proposals themselves.",
    ),
    (
        B,
        "Wie viele Sitze hat ein Vollkanton im Ständerat?",
        ["Einen", "Zwei", "Drei", "Vier"],
        1,
        "Jeder Vollkanton schickt zwei Personen in den Ständerat.",
        "How many seats does a full canton have in the Council of States?",
        ["One", "Two", "Three", "Four"],
        "Each full canton sends two people to the Council of States.",
    ),
    (
        F,
        "Wie viele Halbkantone gibt es?",
        ["Zwei", "Vier", "Sechs", "Acht"],
        2,
        "Es gibt sechs Halbkantone mit je einer Stimme im Ständerat.",
        "How many half-cantons are there?",
        ["Two", "Four", "Six", "Eight"],
        "There are six half-cantons, each with one seat in the Council of States.",
    ),
    (
        B,
        "Wie nennt man die Trennung von Gesetzgebung, Regierung und Rechtsprechung?",
        ["Gewaltenteilung", "Zentralismus", "Monarchie", "Kolonialismus"],
        0,
        "Die Gewaltenteilung verteilt die Macht auf drei Gewalten.",
        "What is the separation of legislation, government and the courts called?",
        ["Separation of powers", "Centralism", "Monarchy", "Colonialism"],
        "The separation of powers divides power between three branches.",
    ),
    (
        B,
        "Welche Behörde ist die Regierung des Bundes?",
        ["Der Nationalrat", "Der Bundesrat", "Das Bundesgericht", "Der Ständerat"],
        1,
        "Der Bundesrat leitet als Kollegium die Regierungsgeschäfte des Bundes.",
        "Which body is the government of the Confederation?",
        [
            "The National Council",
            "The Federal Council",
            "The Federal Supreme Court",
            "The Council of States",
        ],
        "The Federal Council as a body runs the government of the Confederation.",
    ),
    (
        B,
        "Welche Behörde beschliesst die Bundesgesetze?",
        ["Das Bundesgericht", "Das Bundesparlament", "Die Armee", "Die Post"],
        1,
        "Die Bundesversammlung, also das Parlament, beschliesst die Gesetze.",
        "Which body passes federal laws?",
        ["The Federal Supreme Court", "The federal parliament", "The army", "The post office"],
        "The Federal Assembly, that is parliament, passes the laws.",
    ),
    (
        F,
        "Wie heisst der Grundsatz, dass Aufgaben möglichst nahe bei den Betroffenen erledigt werden?",
        ["Subsidiarität", "Neutralität", "Souveränität", "Solidarität"],
        0,
        "Nach der Subsidiarität erledigt eine höhere Ebene nur, was die tiefere nicht kann.",
        "What is the principle called that tasks are handled as close to people as possible?",
        ["Subsidiarity", "Neutrality", "Sovereignty", "Solidarity"],
        "Under subsidiarity a higher level only does what the lower level cannot.",
    ),
    (
        V,
        "Was braucht eine Verfassungsänderung ausser dem Volksmehr?",
        [
            "Das Ständemehr",
            "Die Zustimmung der Armee",
            "Eine Einwilligung des Auslands",
            "Nichts weiter",
        ],
        0,
        "Es braucht die Mehrheit der Stimmenden und die Mehrheit der Kantone.",
        "What does a constitutional change need besides a majority of voters?",
        [
            "A majority of the cantons",
            "Approval by the army",
            "Consent from abroad",
            "Nothing else",
        ],
        "It needs a majority of voters and a majority of the cantons.",
    ),
    (
        L,
        "Wie sieht die Schweizer Flagge aus?",
        [
            "Rotes Kreuz auf weissem Grund",
            "Weisses Kreuz auf rotem Grund",
            "Weisser Stern auf blauem Grund",
            "Drei waagrechte Streifen",
        ],
        1,
        "Die Flagge zeigt ein weisses Kreuz auf rotem Grund.",
        "What does the Swiss flag look like?",
        [
            "Red cross on white",
            "White cross on red",
            "White star on blue",
            "Three horizontal stripes",
        ],
        "The flag shows a white cross on a red background.",
    ),
    (
        L,
        "Welches ist die grösste Stadt der Schweiz?",
        ["Bern", "Genf", "Zürich", "Lugano"],
        2,
        "Zürich hat die meisten Einwohnerinnen und Einwohner.",
        "Which is the largest city in Switzerland?",
        ["Bern", "Geneva", "Zurich", "Lugano"],
        "Zurich has the most inhabitants.",
    ),
    (
        L,
        "Wie heisst der höchste Berg, der ganz in der Schweiz liegt?",
        ["Matterhorn", "Dufourspitze", "Säntis", "Pilatus"],
        1,
        "Die Dufourspitze im Wallis ist der höchste Gipfel der Schweiz.",
        "What is the highest mountain lying entirely in Switzerland called?",
        ["Matterhorn", "Dufourspitze", "Säntis", "Pilatus"],
        "The Dufourspitze in Valais is the highest summit in Switzerland.",
    ),
    (
        L,
        "Welcher Fluss ist der längste, der ganz in der Schweiz fliesst?",
        ["Rhein", "Rhone", "Aare", "Inn"],
        2,
        "Die Aare ist mit gut 290 Kilometern der längste Fluss, der nur in der Schweiz fliesst.",
        "Which is the longest river flowing entirely within Switzerland?",
        ["Rhine", "Rhone", "Aare", "Inn"],
        "At just over 290 kilometres the Aare is the longest river wholly in Switzerland.",
    ),
    (
        L,
        "Welcher See liegt ganz in der Schweiz und ist der grösste?",
        ["Bodensee", "Genfersee", "Neuenburgersee", "Lago Maggiore"],
        2,
        "Der Neuenburgersee ist der grösste See, der ganz in der Schweiz liegt.",
        "Which is the largest lake lying entirely in Switzerland?",
        ["Lake Constance", "Lake Geneva", "Lake Neuchâtel", "Lake Maggiore"],
        "Lake Neuchâtel is the largest lake wholly within Switzerland.",
    ),
    (
        B,
        "Wofür ist der Bund zuständig?",
        [
            "Für die Armee und die Aussenpolitik",
            "Für die Müllabfuhr",
            "Für die Gemeindestrassen",
            "Für den Dorfbrunnen",
        ],
        0,
        "Armee und Aussenpolitik sind Aufgaben des Bundes.",
        "What is the Confederation responsible for?",
        [
            "The army and foreign policy",
            "Rubbish collection",
            "Commune roads",
            "The village fountain",
        ],
        "The army and foreign policy are tasks of the Confederation.",
    ),
    (
        F,
        "Wer ist in der Schweiz hauptsächlich für die Schulen zuständig?",
        ["Der Bund allein", "Die Kantone", "Die Europäische Union", "Die Post"],
        1,
        "Das Schulwesen ist in erster Linie Sache der Kantone.",
        "Who is mainly responsible for schools in Switzerland?",
        ["The Confederation alone", "The cantons", "The European Union", "The post office"],
        "Schooling is first and foremost a matter for the cantons.",
    ),
    (
        V,
        "Wie kann man in der Schweiz abstimmen, ohne zum Wahllokal zu gehen?",
        ["Per Brief", "Per Telefonanruf", "Gar nicht", "Nur per Fax"],
        0,
        "Die briefliche Stimmabgabe ist in der ganzen Schweiz möglich.",
        "How can people vote in Switzerland without going to a polling station?",
        ["By post", "By phone call", "Not at all", "Only by fax"],
        "Voting by post is possible throughout Switzerland.",
    ),
    (
        V,
        "Wer hat auf Bundesebene das Stimmrecht?",
        [
            "Alle Einwohner",
            "Schweizer Bürgerinnen und Bürger ab 18 Jahren",
            "Nur Männer",
            "Nur Beamte",
        ],
        1,
        "Stimmberechtigt sind Schweizer Bürgerinnen und Bürger ab 18 Jahren.",
        "Who has the right to vote at federal level?",
        ["All residents", "Swiss citizens aged 18 or over", "Only men", "Only civil servants"],
        "Swiss citizens aged 18 or over may vote.",
    ),
    (
        V,
        "Was will eine Volksinitiative erreichen?",
        [
            "Die Bundesverfassung ändern",
            "Den Bundesrat abwählen",
            "Ein Urteil aufheben",
            "Die Landesgrenze verschieben",
        ],
        0,
        "Mit einer Volksinitiative verlangen Bürgerinnen und Bürger eine Verfassungsänderung.",
        "What does a popular initiative aim to achieve?",
        [
            "Change the Federal Constitution",
            "Remove the Federal Council",
            "Overturn a court judgment",
            "Move the national border",
        ],
        "With an initiative citizens demand a change to the Constitution.",
    ),
    (
        B,
        "Welches Prinzip bestimmt die Aussenpolitik der Schweiz seit langer Zeit?",
        ["Neutralität", "Kolonialismus", "Monarchie", "Zollunion"],
        0,
        "Die Schweiz ist seit langem neutral und kämpft nicht in fremden Kriegen.",
        "Which principle has long shaped Swiss foreign policy?",
        ["Neutrality", "Colonialism", "Monarchy", "Customs union"],
        "Switzerland has long been neutral and does not fight in foreign wars.",
    ),
    (
        B,
        "Wie wird die Landesregierung auch genannt?",
        ["Bundesrat", "Gemeinderat", "Kantonsrat", "Stadtrat"],
        0,
        "Der Bundesrat ist die Landesregierung.",
        "What is the national government also called?",
        ["Federal Council", "Commune council", "Cantonal Council", "City council"],
        "The Federal Council is the national government.",
    ),
    (
        F,
        "Wer erhebt in der Schweiz Steuern?",
        ["Nur der Bund", "Bund, Kantone und Gemeinden", "Nur die Gemeinden", "Nur die Kantone"],
        1,
        "Alle drei Ebenen erheben Steuern für ihre Aufgaben.",
        "Who levies taxes in Switzerland?",
        [
            "Only the Confederation",
            "Confederation, cantons and communes",
            "Only the communes",
            "Only the cantons",
        ],
        "All three levels levy taxes to pay for their tasks.",
    ),
    (
        B,
        "Wer leitet die Sitzungen des Nationalrats?",
        [
            "Die Nationalratspräsidentin oder der Nationalratspräsident",
            "Der Bundesgerichtspräsident",
            "Der Armeechef",
            "Der Kantonsratspräsident",
        ],
        0,
        "Die Sitzungen leitet eine gewählte Präsidentin oder ein gewählter Präsident des Nationalrats.",
        "Who chairs the sittings of the National Council?",
        [
            "The President of the National Council",
            "The president of the Federal Supreme Court",
            "The head of the army",
            "The president of a cantonal council",
        ],
        "An elected President of the National Council chairs the sittings.",
    ),
    # --- canton of Zurich -----------------------------------------------------------------
    (
        Z,
        "Wie viele Mitglieder hat der Kantonsrat des Kantons Zürich?",
        ["60", "120", "180", "240"],
        2,
        "Der Zürcher Kantonsrat hat 180 Mitglieder.",
        "How many members does the Cantonal Council of Zurich have?",
        ["60", "120", "180", "240"],
        "The Zurich Cantonal Council has 180 members.",
    ),
    (
        Z,
        "Wie viele Mitglieder hat der Regierungsrat des Kantons Zürich?",
        ["Drei", "Fünf", "Sieben", "Neun"],
        2,
        "Der Regierungsrat hat sieben Mitglieder.",
        "How many members does the Executive Council of Zurich have?",
        ["Three", "Five", "Seven", "Nine"],
        "The Executive Council has seven members.",
    ),
    (
        Z,
        "Wie heisst das Parlament des Kantons Zürich?",
        ["Grosser Rat", "Kantonsrat", "Landrat", "Stadtrat"],
        1,
        "Das Parlament des Kantons Zürich heisst Kantonsrat.",
        "What is the parliament of the canton of Zurich called?",
        ["Grand Council", "Cantonal Council", "Land Council", "City Council"],
        "The parliament of the canton of Zurich is the Cantonal Council.",
    ),
    (
        Z,
        "Wie heisst die Regierung des Kantons Zürich?",
        ["Bundesrat", "Regierungsrat", "Gemeinderat", "Obergericht"],
        1,
        "Die Kantonsregierung heisst Regierungsrat.",
        "What is the government of the canton of Zurich called?",
        ["Federal Council", "Executive Council", "Commune council", "Higher Court"],
        "The cantonal government is the Executive Council.",
    ),
    (
        Z,
        "Wer wählt die Mitglieder des Zürcher Regierungsrats?",
        ["Der Bundesrat", "Der Kantonsrat", "Die Stimmberechtigten des Kantons", "Das Obergericht"],
        2,
        "Die Stimmberechtigten wählen die Regierung des Kantons direkt.",
        "Who elects the members of the Zurich Executive Council?",
        [
            "The Federal Council",
            "The Cantonal Council",
            "The voters of the canton",
            "The Higher Court",
        ],
        "The voters of the canton elect its government directly.",
    ),
    (
        Z,
        "Wie heisst das oberste Gericht des Kantons Zürich?",
        ["Bundesgericht", "Obergericht", "Bezirksgericht", "Friedensrichteramt"],
        1,
        "Das Obergericht ist das oberste kantonale Gericht.",
        "What is the highest court of the canton of Zurich called?",
        ["Federal Supreme Court", "Higher Court", "District Court", "Justice of the peace"],
        "The Higher Court is the highest cantonal court.",
    ),
    (
        Z,
        "In welcher Sprache sind die Gesetze des Kantons Zürich geschrieben?",
        ["Französisch", "Deutsch", "Italienisch", "Englisch"],
        1,
        "Im Kanton Zürich ist Deutsch die Amtssprache.",
        "In which language are the laws of the canton of Zurich written?",
        ["French", "German", "Italian", "English"],
        "German is the official language in the canton of Zurich.",
    ),
    (
        Z,
        "Für wie viele Jahre wird der Zürcher Kantonsrat gewählt?",
        ["Zwei Jahre", "Vier Jahre", "Sechs Jahre", "Acht Jahre"],
        1,
        "Der Kantonsrat wird für vier Jahre gewählt.",
        "For how many years is the Zurich Cantonal Council elected?",
        ["Two years", "Four years", "Six years", "Eight years"],
        "The Cantonal Council is elected for four years.",
    ),
    (
        Z,
        "Wie viele Bezirke hat der Kanton Zürich?",
        ["Sechs", "Neun", "Zwölf", "Zwanzig"],
        2,
        "Der Kanton Zürich ist in zwölf Bezirke gegliedert.",
        "How many districts does the canton of Zurich have?",
        ["Six", "Nine", "Twelve", "Twenty"],
        "The canton of Zurich is divided into twelve districts.",
    ),
    (
        Z,
        "Wer erlässt die Gesetze des Kantons Zürich?",
        ["Der Kantonsrat", "Der Bundesrat", "Die Post", "Die Armee"],
        0,
        "Der Kantonsrat beschliesst die kantonalen Gesetze.",
        "Who passes the laws of the canton of Zurich?",
        ["The Cantonal Council", "The Federal Council", "The post office", "The army"],
        "The Cantonal Council passes the cantonal laws.",
    ),
    (
        Z,
        "Welche Aufgabe hat im Kanton Zürich die Kantonspolizei?",
        [
            "Sie sorgt für Sicherheit und Ordnung im Kanton",
            "Sie unterrichtet an Schulen",
            "Sie druckt das Geld",
            "Sie führt die Armee",
        ],
        0,
        "Die Kantonspolizei sorgt für Sicherheit und Ordnung.",
        "What is the task of the cantonal police in Zurich?",
        [
            "It keeps the canton safe and orderly",
            "It teaches in schools",
            "It prints money",
            "It leads the army",
        ],
        "The cantonal police keep the canton safe and orderly.",
    ),
    # --- commune ---------------------------------------------------------------------------
    (
        G,
        "Wo meldet man sich nach einem Umzug an?",
        ["Bei der Wohngemeinde", "Beim Bundesrat", "Beim Bundesgericht", "Bei der Armee"],
        0,
        "Die Anmeldung erfolgt bei der Einwohnerkontrolle der neuen Wohngemeinde.",
        "Where do you register after moving house?",
        [
            "At your commune of residence",
            "With the Federal Council",
            "With the Federal Supreme Court",
            "With the army",
        ],
        "You register with the residents' office of your new commune.",
    ),
    (
        G,
        "Wer ist meistens für die Kehrichtabfuhr zuständig?",
        ["Die Gemeinde", "Der Bund", "Das Parlament in Bern", "Die Armee"],
        0,
        "Die Abfallentsorgung ist in der Regel Aufgabe der Gemeinde.",
        "Who is usually responsible for rubbish collection?",
        ["The commune", "The Confederation", "Parliament in Bern", "The army"],
        "Waste disposal is normally a task of the commune.",
    ),
    (
        G,
        "Wie nennt man die Versammlung aller stimmberechtigten Personen einer Gemeinde?",
        ["Gemeindeversammlung", "Bundesversammlung", "Armeeversammlung", "Generalversammlung"],
        0,
        "In vielen Gemeinden entscheiden die Stimmberechtigten an der Gemeindeversammlung.",
        "What is the assembly of all eligible voters in a commune called?",
        ["Commune assembly", "Federal Assembly", "Army assembly", "General meeting"],
        "In many communes the voters decide at the commune assembly.",
    ),
    (
        G,
        "Welche Ebene baut und unterhält die Strassen im Dorf?",
        ["Meist die Gemeinde", "Immer der Bund", "Die Europäische Union", "Das Bundesgericht"],
        0,
        "Für die örtlichen Strassen ist meist die Gemeinde zuständig.",
        "Which level builds and maintains the roads in a village?",
        [
            "Mostly the commune",
            "Always the Confederation",
            "The European Union",
            "The Federal Supreme Court",
        ],
        "The commune is mostly responsible for local roads.",
    ),
    (
        G,
        "Was ist die kleinste politische Ebene in der Schweiz?",
        ["Die Gemeinde", "Der Kanton", "Der Bund", "Der Bezirk"],
        0,
        "Die Gemeinde ist die unterste der drei staatlichen Ebenen.",
        "What is the smallest political level in Switzerland?",
        ["The commune", "The canton", "The Confederation", "The district"],
        "The commune is the lowest of the three levels of government.",
    ),
]


def dump(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100)
    path.write_text(f"{MARK}\n{body}", encoding="utf-8")


def build(out: Path) -> None:
    content = (REPO / "content").resolve()
    target = out.resolve()
    if target == content or content in target.parents:
        raise SystemExit("Refusing to write into content/.")
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)  # OneDrive may hold a lock
    topics = [
        {
            "code": code,
            "scope": scope,
            "name_de": de,
            "name_en": en,
            "target_questions": n,
            "sources": [],
        }
        for scope, code, de, en, n in TOPICS
    ]
    dump(
        out / "topics" / "zh.yaml",
        {
            "canton": "zh",
            "test": {
                "questions": 50,
                "minutes": 60,
                "pass_mark": 30,
                "proportions": {"federal": 0.78, "canton": 0.16, "commune": 0.06},
            },
            "topics": topics,
        },
    )
    scope_of = {code: scope for scope, code, *_ in TOPICS}
    today = date.today()
    for n, (topic, qde, ode, correct, xde, qen, oen, xen) in enumerate(Q, start=1):
        assert len(ode) == 4 and len(oen) == 4, n
        qid = f"e2e-q{n:02d}"
        federal = scope_of[topic] == "federal"
        keys = "abcd"
        dump(
            out / "questions" / ("federal" if federal else "zh") / f"{qid}.yaml",
            {
                "id": qid,
                "version": 1,
                "scope": "federal" if federal else "zh",
                "canton": None if federal else "zh",
                "topic": topic,
                "question_de": qde,
                "options_de": dict(zip(keys, ode, strict=True)),
                "correct": keys[correct],
                "explanation_de": xde,
                "sources": [{"url": SOURCE, "checked": today}],
                "glossary": [],
                "status": "approved",
                # The first 30 are the free sample set (easiest first, then by id).
                "difficulty": 1 if n <= 30 else 2,
                "translations_missing": True,
            },
        )
        dump(
            out / "translations" / "en" / f"{qid}.yaml",
            {
                "id": qid,
                "lang": "en",
                "source_version": 1,
                "question": qen,
                "options": dict(zip(keys, oen, strict=True)),
                "explanation": xen,
                "status": "approved",
                "reviewed_by": "E2E fixture",
                "reviewed_at": today,
            },
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REPO / "var" / "e2e" / "content")
    args = parser.parse_args(argv)
    if len(Q) != 60:
        raise SystemExit(f"expected 60 questions, found {len(Q)}")
    build(args.out)
    print(f"Wrote {len(Q)} example questions to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
