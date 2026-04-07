"""
Chipstone American Furniture — Full ETL Pipeline
Fetches all issues 1993-2023, reads each article, generates card metadata via Claude API.

Usage:
  python chipstone_etl.py --phase scrape    # fetch TOCs + article text -> chipstone_raw.json
  python chipstone_etl.py --phase generate  # call Claude API -> chipstone_cards.json
  python chipstone_etl.py --phase sql       # convert -> chipstone_inserts.sql
  python chipstone_etl.py --phase all       # run all three phases

Requirements:
  pip install requests beautifulsoup4 anthropic

Set ANTHROPIC_API_KEY in environment before running generate phase.
"""

import argparse
import io
import json
import os
import re
import time
import sys
from pathlib import Path

# Force UTF-8 output so Unicode titles don't crash on Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import requests
from bs4 import BeautifulSoup
import anthropic

BASE = "https://chipstone.org"
OUT_DIR = Path(__file__).parent

# All Chipstone American Furniture issues (year -> issue path)
# Excludes 1996 (already seeded) and 2024 (out of scope for initial run)
ISSUES = {
    1993: "/issue.php/15/American-Furniture-1993",
    1994: "/issue.php/16/American-Furniture-1994",
    1995: "/issue.php/17/American-Furniture-1995",
    # 1996: already seeded as pilot batch
    1997: "/issue.php/19/American-Furniture-1997",
    1998: "/issue.php/20/American-Furniture-1998",
    1999: "/issue.php/21/American-Furniture-1999",
    2000: "/issue.php/22/American-Furniture-2000",
    2001: "/issue.php/23/American-Furniture-2001",
    2002: "/issue.php/24/American-Furniture-2002",
    2003: "/issue.php/35/American-Furniture-2003",
    2004: "/issue.php/25/American-Furniture-2004",
    2005: "/issue.php/26/American-Furniture-2005",
    2006: "/issue.php/27/American-Furniture-2006",
    2007: "/issue.php/28/American-Furniture-2007",
    2008: "/issue.php/29/American-Furniture-2008",
    2009: "/issue.php/30/American-Furniture-2009",
    2010: "/issue.php/31/American-Furniture-2010",
    2011: "/issue.php/32/American-Furniture-2011",
    2012: "/issue.php/33/American-Furniture-2012",
    2013: "/issue.php/34/American-Furniture-2013",
    2014: "/issue.php/37/American-Furniture-2014",
    2015: "/issue.php/39/American-Furniture-2015",
    2016: "/issue.php/41/American-Furniture-2016",
    2017: "/issue.php/43/American-Furniture-2017",
    2018: "/issue.php/44/American-Furniture-2018",
    2019: "/issue.php/46/American-Furniture-2019",
    2020: "/issue.php/49/American-Furniture-2020",
    2022: "/issue.php/50/American-Furniture-2022",  # combined 2021-22 issue
    2023: "/issue.php/54/American-Furniture-2023",
}

# Titles that are NOT substantive scholarship cards
SKIP_TITLE_PATTERNS = [
    r"^editorial statement",
    r"^preface",
    r"^introduction$",
    r"^foreword",
    r"^in memoriam",
    r"^acknowledgment",
    r"^errata",
    r"^annual bibliography",  # Keep: actually useful for citation-only cards
]

CONTROLLED_VOCAB = """
PERIOD (use exact strings, multiple allowed):
Early Colonial, William & Mary, Baroque / Late Baroque, Queen Anne, Chippendale,
Federal / Neoclassical, Empire, Victorian, Colonial Revival, Arts & Crafts, Shaker,
Modern / Studio, Survey / Multiple

FORM (use exact strings, multiple allowed):
Case pieces, Seating, Easy Chairs / Upholstered Seating, Windsor, Vernacular,
Tables, Beds, Clocks / Tall Case, Textiles / Covers, Survey / Multiple

REGION (use exact strings, multiple allowed):
New England, Boston, Newport, Rural New England, New York, New York City,
Philadelphia, Baltimore, Mid-Atlantic, Chesapeake / Virginia, Southern, Charleston,
North Carolina, Rural / Backcountry, National / Survey, European Influence

TOPIC (use exact strings, multiple allowed):
Construction / Technique, Attribution, Regional Style, Design Sources,
Carving / Ornament, Inlay / Veneer, Painted / Decorated Surfaces, Shop Records,
Conservation, Repair / Alteration, Fakes / Authentication, Materials,
Terminology / Nomenclature, Social History, Trade / Commerce, Immigration,
Biography / Shops, Connoisseurship, Historiography, Shaker / Religious Communities,
Studio / Contemporary
"""

CARD_PROMPT = """You are an expert in American decorative arts and period furniture scholarship.
I will give you the full text of an article from Chipstone Foundation's "American Furniture" journal.
Generate a library card entry in JSON format.

CONTROLLED VOCABULARIES — use ONLY these exact strings:
{vocab}

OUTPUT FORMAT (JSON only, no other text):
{{
  "description": "3-5 sentences. See description rules below.",
  "period": ["exact period string", ...],
  "form": ["exact form string", ...],
  "region": ["exact region string", ...],
  "topic": ["exact topic string", ...],
  "makers": ["Craftsman Name", ...]
}}

RULES:
- description: 3-5 sentences written by one furniture scholar for another — peer to peer, not
  popularized. The reader is a skilled craftsman who also reads deeply: they know their Chippendale
  from their Federal, they've held a card scraper, and they want to know whether this piece of
  scholarship is worth their time.
  HARD RULE — NEVER open with "This article", "The article", "In this article", "This study",
  "The study", "The author", or any variant. NEVER use hedging phrases: "seeks to", "aims to",
  "attempts to", "looks at", "explores". NEVER use the passive construction "is examined" or
  "is analyzed" in the opening clause.
  Lead with the subject itself: the object, the craftsman, the shop, the technique, the argument.
  Be specific — name the pieces, the makers, the towns, the joints, the woods.
  Match the register of the journal: serious, precise, collegial. Not breathless, not textbook.
- makers: only named craftsmen/cabinetmakers/carvers studied in depth (not every person mentioned)
- Use "Survey / Multiple" for period/form/region only when the article genuinely spans multiple without focusing on one
- Book reviews: treat as the article being reviewed's subject matter
- Annual bibliographies: description = "Annual bibliography of American furniture scholarship for [year]." period=["Survey / Multiple"] form=["Survey / Multiple"] region=["National / Survey"] topic=["Historiography"] makers=[]
- If you cannot determine a field, use [] for arrays or a brief honest description

ARTICLE:
Title: {title}
Authors: {authors}
Year: {year}
URL: {url}

Full text:
{body}
"""


# ===========================================================================
# Phase 1: Scrape
# ===========================================================================

def fetch(url, delay=1.0):
    """Fetch a URL with polite delay."""
    time.sleep(delay)
    r = requests.get(url, timeout=30, headers={"User-Agent": "SAPFM-CardCatalog/1.0 (research; contact@sapfm.org)"})
    r.raise_for_status()
    return r.text


def parse_issue_toc(html, year):
    """Extract article links from an issue TOC page."""
    soup = BeautifulSoup(html, "html.parser")
    articles = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/article.php/" in href:
            title = a.get_text(strip=True)
            if title:
                full_url = href if href.startswith("http") else BASE + href
                articles.append({"title": title, "url": full_url, "year": year})
    # Deduplicate by URL
    seen = set()
    unique = []
    for art in articles:
        if art["url"] not in seen:
            seen.add(art["url"])
            unique.append(art)
    return unique


def should_skip(title):
    """Return True if this article type should not become a card."""
    t = title.strip().lower()
    for pat in SKIP_TITLE_PATTERNS:
        if re.match(pat, t):
            return True
    return False


def parse_article(html, url):
    """Extract title, authors, and body text from an article page."""
    soup = BeautifulSoup(html, "html.parser")

    # Title: look for h1 or the article title element
    title = ""
    for sel in ["h1.article-title", "h1", ".title", "title"]:
        el = soup.select_one(sel)
        if el:
            title = el.get_text(strip=True)
            if title and "chipstone" not in title.lower():
                break

    # Authors: look for author byline
    authors = []
    for sel in [".author", ".byline", ".article-author", "[class*='author']"]:
        els = soup.select(sel)
        if els:
            for el in els:
                txt = el.get_text(strip=True)
                if txt and len(txt) < 150:
                    # Split on "and", "&", ";"
                    parts = re.split(r"\s+and\s+|\s*[;&]\s*", txt)
                    authors.extend([p.strip() for p in parts if p.strip()])
            if authors:
                break

    # Body: main article content
    body = ""
    for sel in [".article-body", ".content", "article", ".main-content", "#content", "main"]:
        el = soup.select_one(sel)
        if el:
            # Remove footnotes, nav, headers
            for tag in el.select("nav, header, footer, .footnote, .notes, script, style"):
                tag.decompose()
            body = el.get_text(separator="\n", strip=True)
            if len(body) > 200:
                break

    # Fallback: all paragraphs
    if len(body) < 200:
        paras = soup.find_all("p")
        body = "\n".join(p.get_text(strip=True) for p in paras if len(p.get_text(strip=True)) > 50)

    # Truncate body to ~6000 chars to keep API calls reasonable
    if len(body) > 6000:
        body = body[:6000] + "\n[truncated]"

    return title, authors, body


def phase_scrape():
    raw_path = OUT_DIR / "chipstone_raw.json"

    # Load existing if resuming
    if raw_path.exists():
        with open(raw_path, encoding="utf-8") as f:
            existing = json.load(f)
        done_urls = {a["url"] for a in existing}
        print(f"Resuming: {len(existing)} articles already scraped")
    else:
        existing = []
        done_urls = set()

    for year, issue_path in sorted(ISSUES.items()):
        print(f"\n--- {year} ---")
        issue_url = BASE + issue_path
        try:
            toc_html = fetch(issue_url, delay=3.0)
        except Exception as e:
            print(f"  ERROR fetching TOC: {e}")
            continue

        toc_articles = parse_issue_toc(toc_html, year)
        print(f"  Found {len(toc_articles)} articles in TOC")

        for art in toc_articles:
            if art["url"] in done_urls:
                print(f"  SKIP (already done): {art['title'][:60]}")
                continue

            if should_skip(art["title"]):
                print(f"  SKIP (non-card): {art['title'][:60]}")
                continue

            print(f"  Fetching: {art['title'][:70]}")
            try:
                html = fetch(art["url"], delay=5.0)
                title, authors, body = parse_article(html, art["url"])

                # Use TOC title if article title parse fails
                if not title or len(title) < 5:
                    title = art["title"]

                record = {
                    "title": title or art["title"],
                    "authors": authors,
                    "year": year,
                    "url": art["url"],
                    "body": body,
                    "source": "Chipstone Foundation — American Furniture",
                    "source_key": "chipstone",
                    "card_type": "article",
                }
                existing.append(record)
                done_urls.add(art["url"])

            except Exception as e:
                print(f"  ERROR: {e}")
                continue

        # Save after each issue
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
        print(f"  Saved {len(existing)} total records")

    print(f"\nScrape complete. {len(existing)} articles in {raw_path}")


# ===========================================================================
# Phase 2: Generate card metadata via Claude API
# ===========================================================================

def phase_generate():
    raw_path = OUT_DIR / "chipstone_raw.json"
    cards_path = OUT_DIR / "chipstone_cards.json"

    if not raw_path.exists():
        print("Run --phase scrape first")
        sys.exit(1)

    with open(raw_path, encoding="utf-8") as f:
        raw = json.load(f)

    # Load existing generated cards for resumption
    if cards_path.exists():
        with open(cards_path, encoding="utf-8") as f:
            cards = json.load(f)
        done_urls = {c["view_url"] for c in cards}
        print(f"Resuming: {len(cards)} cards already generated")
    else:
        cards = []
        done_urls = set()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Set ANTHROPIC_API_KEY environment variable")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    for i, rec in enumerate(raw):
        if rec["url"] in done_urls:
            continue

        print(f"[{i+1}/{len(raw)}] {rec['year']} — {rec['title'][:70]}", flush=True)

        prompt = CARD_PROMPT.format(
            vocab=CONTROLLED_VOCAB,
            title=rec["title"],
            authors=", ".join(rec["authors"]) if rec["authors"] else "Unknown",
            year=rec["year"],
            url=rec["url"],
            body=rec["body"][:5000],
        )

        try:
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )
            text = msg.content[0].text.strip()

            # Extract JSON — sometimes Claude wraps in ```json
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if not json_match:
                print(f"  WARNING: no JSON in response, skipping")
                continue

            meta = json.loads(json_match.group())

            card = {
                "title": rec["title"],
                "authors": rec["authors"],
                "year": rec["year"],
                "source": rec["source"],
                "source_key": rec["source_key"],
                "card_type": rec["card_type"],
                "description": meta.get("description", ""),
                "period": meta.get("period", []),
                "form": meta.get("form", []),
                "region": meta.get("region", []),
                "topic": meta.get("topic", []),
                "makers": meta.get("makers", []),
                "is_free": 1,
                "view_url": rec["url"],
                "download_url": None,
                "contributed_by": None,
                "contributor_name": None,
            }
            cards.append(card)
            done_urls.add(rec["url"])
            print(f"  OK — period={card['period'][:2]}, topic={card['topic'][:2]}", flush=True)

        except json.JSONDecodeError as e:
            print(f"  JSON parse error: {e} — response: {text[:200]}", flush=True)
            continue
        except Exception as e:
            print(f"  API error: {e}")
            time.sleep(5)
            continue

        # Save every 10 cards
        if len(cards) % 10 == 0:
            with open(cards_path, "w", encoding="utf-8") as f:
                json.dump(cards, f, indent=2, ensure_ascii=False)

        time.sleep(0.5)  # polite API pacing

    with open(cards_path, "w", encoding="utf-8") as f:
        json.dump(cards, f, indent=2, ensure_ascii=False)

    print(f"\nGenerate complete. {len(cards)} cards in {cards_path}")


# ===========================================================================
# Phase 3: Generate SQL inserts
# ===========================================================================

def phase_sql():
    cards_path = OUT_DIR / "chipstone_cards.json"
    sql_path = OUT_DIR / "chipstone_inserts.sql"

    if not cards_path.exists():
        print("Run --phase generate first")
        sys.exit(1)

    with open(cards_path, encoding="utf-8") as f:
        cards = json.load(f)

    lines = [
        "-- Chipstone American Furniture — Full corpus (all issues except 1996)",
        f"-- Generated from {len(cards)} articles",
        "",
    ]

    for c in cards:
        def esc(s):
            return str(s).replace("'", "''") if s else ""

        title = esc(c["title"])
        authors = json.dumps(c.get("authors") or [], ensure_ascii=False).replace("'", "''")
        desc = esc(c.get("description") or "")
        period = json.dumps(c.get("period") or [], ensure_ascii=False)
        form = json.dumps(c.get("form") or [], ensure_ascii=False)
        region = json.dumps(c.get("region") or [])
        topic = json.dumps(c.get("topic") or [])
        makers = json.dumps(c.get("makers") or [], ensure_ascii=False).replace("'", "''")
        year = c.get("year") or "NULL"
        source = esc(c.get("source") or "")
        source_key = esc(c.get("source_key") or "")
        card_type = esc(c.get("card_type") or "article")
        view_url = esc(c.get("view_url") or "")
        is_free = 1 if c.get("is_free") else 0

        lines.append(
            f"INSERT OR REPLACE INTO library_cards"
            f"(title, authors, year, source, source_key, card_type, "
            f"description, period, form, region, topic, makers, "
            f"is_free, view_url, status, created_at, updated_at) VALUES "
            f"('{title}', '{authors}', {year}, '{source}', '{source_key}', '{card_type}', "
            f"'{desc}', '{period}', '{form}', '{region}', '{topic}', '{makers}', "
            f"{is_free}, '{view_url}', 'approved', datetime('now'), datetime('now'));"
        )

    with open(sql_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"SQL written: {len(cards)} inserts to {sql_path}")


# ===========================================================================
# Main
# ===========================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chipstone ETL pipeline")
    parser.add_argument("--phase", choices=["scrape", "generate", "sql", "all"], required=True)
    args = parser.parse_args()

    if args.phase in ("scrape", "all"):
        phase_scrape()
    if args.phase in ("generate", "all"):
        phase_generate()
    if args.phase in ("sql", "all"):
        phase_sql()
