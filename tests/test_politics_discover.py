"""Politics discovery (D-074): the parsers on saved copies of the real sources (fetched on
7 November 2026), the sources file, dates, slugs and the seat count. No network."""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.politics import discover
from app.politics.sources import load, sources_path
from tests.politics_helpers import fixture


def test_sources_file_is_valid_and_complete():
    cantons = load(sources_path())
    zh = cantons["zh"]
    types = {s.type for s in zh.sources}
    assert types == {"listing", "rss", "vote_list", "people"}
    assert all(s.url.startswith("https://") for s in zh.sources)
    ids = {s.id for s in zh.sources}
    for needed in ("zh-regierungsrat", "zh-kantonsrat", "zh-stadt-zuerich", "zh-winterthur",
                   "ch-federal-votes", "zh-cantonal-votes", "zh-regierungsrat-members",
                   "zh-kantonsrat-members", "zh-stadtrat-zuerich", "zh-stadtrat-winterthur"):  # fmt: skip
        assert needed in ids
    assert zh.host_allowed("https://www.kantonsrat.zh.ch/x")
    assert zh.host_allowed("https://parlzhcdws.cmicloud.ch/parlzh3/cdws/Files/a/1/pdf")
    assert not zh.host_allowed("https://www.nzz.ch/zuerich")
    assert not zh.host_allowed("http://www.zh.ch/")


def test_dates_in_german_text():
    assert discover.find_date("05.11.2026 Bulletin") == date(2026, 11, 5)
    assert discover.find_date("Titel 6. November 2026 Stadtrat") == date(2026, 11, 6)
    assert discover.find_date("am 28. Februar 2027") == date(2027, 2, 28)
    assert discover.find_date("keine Angabe") is None


def test_slugs_from_german_titles():
    title = "Volksinitiative vom 03.11.2023 «Für eine Einschränkung von Feuerwerk»"
    assert discover.slugify(title) == "einschraenkung-feuerwerk"
    key = discover.vote_key("ch", "2026-11-29", title)
    assert key == "vote-ch-2026-11-29-einschraenkung-feuerwerk"
    assert len(discover.vote_key("zh", "2027-02-28", "x " * 200)) <= 80


def test_zh_news_json():
    entries = discover.parse_zhweb_news(fixture("zhweb_news.json"))
    assert len(entries) == 15
    first = entries[0]
    assert first.url.startswith("https://www.zh.ch/de/news-uebersicht/medienmitteilungen/2026/11/")
    assert first.item_date == date(2026, 11, 5)
    titles = [e.title for e in entries]
    assert "Eine kantonale Abstimmungsvorlage am 28. Februar 2027" in titles
    assert all(e.item_date for e in entries)


def test_city_rss_feeds():
    zurich = discover.parse_rss(fixture("stadt_zuerich.rss"))
    assert len(zurich) == 10
    assert zurich[0].title.startswith("Budget 2027")
    assert zurich[0].item_date == date(2026, 11, 6)
    assert zurich[0].url.startswith("https://www.stadt-zuerich.ch/de/aktuell/medienmitteilungen/")
    winti = discover.parse_rss(fixture("winterthur.rss"))
    assert len(winti) == 4
    assert winti[0].url == (
        "https://stadt.winterthur.ch/medien/verguetung-2027-von-stadtwerk-winterthur-stadtkasse"
    )
    assert winti[0].item_date == date(2026, 11, 6)


def test_rss_parser_does_not_expand_entities():
    evil = (
        '<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaaaaaaaa">]><rss><channel><item>'
        "<title>&a;&a;</title><link>https://www.zh.ch/x</link>"
        "<pubDate>Fri, 06 Nov 2026 07:47:33 +0100</pubDate></item></channel></rss>"
    )
    [e] = discover.parse_rss(evil)
    assert "aaaa" not in e.title


def test_kantonsrat_home_page_links_with_dates():
    entries = discover.parse_html_dated(
        fixture("kantonsrat.html"), "https://www.kantonsrat.zh.ch/", r"(?i)bulletin|beschl"
    )
    bulletins = [e for e in entries if "Bulletin" in e.title]
    assert bulletins, entries
    b = next(e for e in bulletins if e.item_date == date(2026, 11, 1))
    assert b.url.startswith("https://parlzhcdws.cmicloud.ch/")
    assert "Beschlüsse des Kantonsrates" in b.title
    assert all("Mitglieder" not in e.title for e in entries)  # undated links are left out


def test_federal_votes_and_results():
    votes = discover.parse_lindas(fixture("lindas_votes.json"))
    upcoming = [v for v in votes if v["date"] == "2026-11-29"]
    assert len(upcoming) == 4
    assert all(v["result"] is None for v in votes)  # no figures before the count
    done = discover.parse_lindas(fixture("lindas_results.json"))
    r = done[0]["result"]
    assert r == {"yes_percent": 57.73, "turnout_percent": 49.53, "accepted": True}
    assert done[2]["result"]["accepted"] is False


def test_parlament_next_vote():
    parsed = discover.parse_parlament_votes(fixture("parlament_votes.html"))
    assert parsed["vote_date"] == "2026-11-29"
    ids = [a["affair_id"] for a in parsed["affairs"]]
    assert ids == ["20240073", "20240080", "20250018", "20250024"]
    assert "Feuerwerk" in parsed["affairs"][1]["title"]
    assert discover.affair_url("20240080").startswith("https://www.parlament.ch/")
    assert discover.affair_data_url("20240080").startswith("https://ws.parlament.ch/")


def test_party_seats_are_counted_not_guessed():
    text = "Agosti Reto\nFDP\nKSSG\nAlder Ronald\nGLP\nBienek Sandra\nGLP–\nX\nSVP–\nY\nSVP\n"
    assert discover.party_seats(text) == {"GLP": 2, "SVP": 2, "FDP": 1}


def test_linked_member_pages():
    page = (
        '<a href="/de/politik/stadtrat/raphael-golta.html">Golta</a>'
        '<a href="/de/politik/stadtrat/ehemalige-stadtratsmitglieder.html">Ehemalige</a>'
        '<a href="https://www.nzz.ch/">x</a>'
    )
    urls = discover.linked_pages(
        page, "https://www.stadt-zuerich.ch/de/politik/stadtrat.html",
        r"^/de/politik/stadtrat/(?!ehemalige)[a-z-]+\.html$",
    )  # fmt: skip
    assert urls == ["https://www.stadt-zuerich.ch/de/politik/stadtrat/raphael-golta.html"]


def test_vote_publication_is_four_weeks_ahead():
    now = datetime(2026, 11, 7, 10, 0, tzinfo=UTC)
    at = discover.vote_publish_at(date(2027, 2, 28), now)
    assert at == datetime(2027, 1, 31, 6, 0, tzinfo=UTC)  # 07:00 Zurich, 28 days before
    # Found too late for that: as soon as possible.
    assert discover.vote_publish_at(date(2026, 11, 29), now) == now


def test_links_in_web_components_are_followed():
    page = (
        '<stzh-card-superteaser heading="Stadtpräsident Raphael Golta" '
        'href="/de/politik/stadtrat/raphael-golta.html"></stzh-card-superteaser>'
        '<link rel="stylesheet" href="/de/politik/stadtrat/style.html">'
    )
    assert discover.anchors(page) == [
        ("/de/politik/stadtrat/raphael-golta.html", "Stadtpräsident Raphael Golta")
    ]
