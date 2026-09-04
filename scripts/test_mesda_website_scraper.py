"""Tests for the MESDA scraper's article-link predicate.

The predicate is the guard that six page-furniture rows slipped past in the
2026-04-08 scrape (sql/07_remove_mesda_scrape_artifacts.sql). The fixtures
below are the real hrefs from that run.
"""
import json
from pathlib import Path

import pytest

from mesda_website_scraper import is_article_link

RAW = Path(__file__).parent / "mesda_journal_website_raw.json"


@pytest.mark.parametrize("href", [
    "https://www.mesdajournal.org/2012/scratching-surface-thomas-you-charleston-silversmith-engraver-patriot/",
    "https://www.mesdajournal.org/2012/correct-map-province-north-carolina/",
    "https://www.mesdajournal.org/2012/mesda-journal/",   # the Editor's Welcome
    "http://mesdajournal.org/2014/some-article/",         # bare host, http
])
def test_accepts_journal_articles(href):
    assert is_article_link(href) is True


@pytest.mark.parametrize("href", [
    "http://blur.by/1zSp12V",                                       # Blurb print-on-demand
    "http://blur.by/1L3xRwN",
    "http://mesda.org/research/craftsman-database/",                # the museum, not the journal
    "http://www.archive.org/details/journalofearlyso1821992muse",   # unrelated 1992 issue
    "/cdn-cgi/l/email-protection",                                  # became "[email protected]"
    "",
    None,
])
def test_rejects_page_furniture(href):
    assert is_article_link(href) is False


def test_rejects_a_lookalike_host():
    # Substring matching on the domain would let this through.
    assert is_article_link("https://mesdajournal.org.example.com/2012/x/") is False


def test_against_the_real_scrape():
    """Every junk row in the captured scrape is rejected; every article kept."""
    rows = json.loads(RAW.read_text(encoding="utf-8"))
    kept = [r for r in rows if is_article_link(r["url"])]
    dropped = [r for r in rows if not is_article_link(r["url"])]

    assert len(rows) == 79
    assert len(dropped) == 7

    dropped_titles = {r["article_title"] for r in dropped}
    assert "Print-on-Demand Copy" in dropped_titles
    assert "click here." in dropped_titles
    assert "Craftsman Database at www.mesda.org" in dropped_titles
    assert "Vol, 18, No. 2 (November 1992)" in dropped_titles
    assert any(t.startswith("[email") for t in dropped_titles)

    # Nothing real was lost: everything kept is on the journal domain and every
    # dropped row is one of the seven known artifacts.
    assert all("mesdajournal.org" in r["url"] for r in kept)
    assert len(kept) == 72
