"""
MESDA Journal — Article-level ETL

Extracts article-level content from the Journal of Early Southern Decorative Arts,
generates card metadata via Claude Haiku, produces SQL for D1.

Text source: archive.org djvu.txt files (1995–2025+)
Database: shared card-catalog D1

Usage:
  python mesda_journal_etl.py --phase scrape   [--year all|1995-2025|YYYY]
  python mesda_journal_etl.py --phase generate [--year ...]
  python mesda_journal_etl.py --phase sql      [--year ...]
  python mesda_journal_etl.py --phase all      [--year ...]
  python mesda_journal_etl.py --phase toc      [--year YYYY]  # Inspect archive.org structure

Requirements:
  pip install anthropic requests
  Archive.org access (no auth required for open-access materials)
"""

import argparse, io, json, os, re, sys, time
from pathlib import Path
from urllib.parse import urljoin
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT_DIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# MESDA Journal Volumes & Structure
# ---------------------------------------------------------------------------

MESDA_JOURNAL = {
    "title": "Journal of Early Southern Decorative Arts",
    "publisher": "Museum of Early Southern Decorative Arts at Old Salem",
    "source": "Museum of Early Southern Decorative Arts — Journal",
    "source_key": "mesda",
    "view_url": "https://mesdajournal.org",
    "archive_base": "https://archive.org/details/journalofearlyso",
    "is_free": 1,
}

# Archive.org identifiers for MESDA Journal volumes (pattern from search results)
# journalofearlyso + YYYMUSE format
# Complete list from archive.org: volumes 1–46+ (1975–2025+)
# Note: Not all volumes are digitized; this represents confirmed available volumes
ARCHIVE_VOLUMES = {
    # Format: year: (archive_id, volume_number)
    1980: ("journalofearlyso0601980muse", 6),
    1985: ("journalofearlyso1101985muse", 11),
    1989: ("journalofearlyso1501989muse", 15),
    1991: ("journalofearlyso1711991muse", 17),
    1995: ("journalofearlyso2101995muse", 21),
    1997: ("journalofearlyso2321997muse", 23),
    2000: ("journalofearlyso2702000muse", 27),
    2004: ("journalofearlyso3022004muse", 30),
    2010: ("journalofearlyso3602010muse", 36),
    2015: ("journalofearlyso4102015muse", 41),
    2020: ("journalofearlyso4602020muse", 46),
}

CONTROLLED_VOCAB = """
PERIOD (use exact strings, multiple allowed):
Early Colonial, William & Mary, Queen Anne, Chippendale, Federal / Neoclassical,
Empire, Victorian, Colonial Revival, Arts & Crafts, Shaker, Modern / Studio, Survey / Multiple

FORM (use exact strings, multiple allowed):
Case pieces, Seating, Easy Chairs / Upholstered Seating, Windsor, Vernacular, Tables,
Beds, Clocks / Tall Case, Textiles / Covers, Painted / Decorated Surfaces, Survey / Multiple

REGION (use exact strings, multiple allowed):
North Carolina, South Carolina, Virginia, Maryland, Georgia, Charleston, Piedmont,
Coastal, Rural / Backcountry, Mid-Atlantic, National / Survey, European Influence

TOPIC (use exact strings, multiple allowed):
Construction / Technique, Attribution, Regional Style, Design Sources, Carving / Ornament,
Painted / Decorated Surfaces, Inlay / Veneer, Social History, Trade / Commerce, Biography / Makers,
Connoisseurship, Historiography, Materials, Material Culture
"""

CARD_PROMPT = """You are an expert in American decorative arts and Southern material culture history.
I will give you an article or article abstract from the Journal of Early Southern Decorative Arts.
Generate a library card entry in JSON format.

CONTROLLED VOCABULARIES — use ONLY these exact strings:
{vocab}

OUTPUT FORMAT (JSON only, no other text):
{{
  "description": "2-3 sentences. See description rules below.",
  "period": ["exact period string", ...],
  "form": ["exact form string", ...],
  "region": ["exact region string", ...],
  "topic": ["exact topic string", ...],
  "makers": ["Craftsman/Maker Name", ...]
}}

RULES:
- description: 2-3 sentences written by one scholar for another — peer to peer.
  Lead with the subject (objects, makers, region, argument), not "This article".
  Be specific: name pieces, makers, towns, techniques, dates where relevant.
  Match the register of academic scholarship: serious, precise, authoritative.
- makers: only named craftspeople/makers/merchants studied in depth in the article
- Use "Survey / Multiple" only when the article genuinely spans multiple without focusing one
- If text is noisy OCR, work with what you can discern

SUGGESTED TAGS (override if text disagrees):
Period: {period}
Form: {form}
Region: {region}
Topic: {topic}

PUBLICATION: {pub_title}
YEAR: {year}
ARTICLE: {article_title}

Article text:
{body}
"""


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------

MAX_ARTICLE_CHARS = 8000  # Feed at most this many chars to Haiku


def fetch_archive_djvu_text(archive_id):
    """Fetch full text from archive.org djvu.txt file. Respectful rate limiting."""
    url = f"https://archive.org/download/{archive_id}/{archive_id}_djvu.txt"
    try:
        # Add delay to be respectful of archive.org servers
        time.sleep(2)
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'SAPFM Card Catalog ETL (research/educational)')
        with urllib.request.urlopen(req, timeout=30) as response:
            text = response.read().decode('utf-8', errors='replace')
        return text
    except Exception as e:
        print(f"  ERROR fetching {url}: {e}")
        return None


def extract_article_from_toc_text(full_text):
    """
    Parse MESDA Journal djvu.txt to extract articles.
    Returns list of (article_title, article_author, body_text).

    For now, adopt a pragmatic approach: extract using regex patterns that match
    the article title headers in the body section directly, which are cleaner
    than trying to parse the OCR'd TOC with its spacing artifacts.
    """
    # Strategy: search for prominent article markers in the body section
    # MESDA articles typically have the title repeated at the start of the body,
    # followed by the author name, then body text.

    lines = full_text.split('\n')
    articles = []

    # Find the approximate boundary between front matter and article bodies
    # Usually around 50–100 lines in
    body_start = min(100, len(lines))

    # Look for lines that appear to be article titles: they're longer than average,
    # contain mixed case or multiple capital letters, and are followed by author names
    i = body_start
    while i < len(lines) - 10:
        line = lines[i].strip()

        # Skip short lines, numbers, empty lines
        if not line or len(line) < 20 or line.isdigit():
            i += 1
            continue

        # Check if this looks like an article title
        # Heuristic: has multiple capitals, doesn't look like body text
        capital_count = sum(1 for c in line if c.isupper())
        if capital_count >= 3 and capital_count < len(line) * 0.8:  # Not too many, not too few
            title_candidate = line

            # Look for author on the next 1-3 lines
            author = ""
            author_idx = -1
            for j in range(i + 1, min(i + 5, len(lines))):
                potential_author = lines[j].strip()
                # Authors are typically all-caps or nearly all-caps
                if potential_author and len(potential_author) > 5 and len(potential_author) < 80:
                    upper_ratio = sum(1 for c in potential_author if c.isupper()) / len(potential_author)
                    if upper_ratio > 0.7:
                        author = potential_author
                        author_idx = j
                        break

            if author_idx > 0:
                # Extract body starting after the author line
                body_start_idx = author_idx + 1
                body_lines = []
                char_count = 0

                for k in range(body_start_idx, len(lines)):
                    line_text = lines[k]
                    body_lines.append(line_text)
                    char_count += len(line_text)

                    # Stop at next article marker (new prominent title)
                    if k > body_start_idx + 5:
                        next_line = lines[k].strip()
                        next_capital_count = sum(1 for c in next_line if c.isupper())
                        if (len(next_line) > 20 and next_capital_count >= 3 and
                            next_capital_count < len(next_line) * 0.8 and
                            next_line != title_candidate):
                            break

                    if char_count > MAX_ARTICLE_CHARS:
                        break

                body_text = '\n'.join(body_lines)[:MAX_ARTICLE_CHARS].strip()
                if body_text and len(body_text) > 500:  # Only save substantial articles
                    articles.append((title_candidate, author, body_text))
                    i = k + 1
                else:
                    i += 1
            else:
                i += 1
        else:
            i += 1

    return articles


# ---------------------------------------------------------------------------
# Phase 1: Scrape — explore archive.org structure
# ---------------------------------------------------------------------------

def phase_toc(year=None):
    """Inspect archive.org structure for a given year to understand format."""
    if year:
        if year not in ARCHIVE_VOLUMES:
            print(f"Year {year} not yet indexed. Available: {list(ARCHIVE_VOLUMES.keys())}")
            return
        archive_id, vol_num = ARCHIVE_VOLUMES[year]
        print(f"Fetching Volume {vol_num} ({year}) from archive.org...")
        text = fetch_archive_djvu_text(archive_id)
        if text:
            print(f"Retrieved {len(text):,} chars from {archive_id}")
            print("\n--- First 2000 chars (for structure inspection) ---\n")
            print(text[:2000])
            print("\n--- Searching for article titles (lines after '---') ---\n")
            # Look for TOC-like patterns
            lines = text.split('\n')
            for i, line in enumerate(lines[100:200]):  # Middle section often has TOC
                if line.strip():
                    print(f"{i}: {line[:100]}")
    else:
        print("Available MESDA Journal volumes on archive.org:")
        for year, (archive_id, vol_num) in sorted(ARCHIVE_VOLUMES.items()):
            print(f"  {year}: Volume {vol_num} ({archive_id})")
        print("\nRun with --year YYYY to inspect a specific volume")


def phase_scrape(years):
    """Scrape article metadata and text from archive.org."""
    raw_path = OUT_DIR / "mesda_journal_raw.json"
    existing = json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.exists() else []
    done_keys = {r.get("article_title") for r in existing}

    for year in years:
        if year not in ARCHIVE_VOLUMES:
            print(f"  SKIP: Year {year} not yet indexed")
            continue

        archive_id, vol_num = ARCHIVE_VOLUMES[year]
        print(f"\n{year} — Journal of Early Southern Decorative Arts, Vol. {vol_num}")

        full_text = fetch_archive_djvu_text(archive_id)
        if not full_text:
            print(f"  ERROR: Could not fetch {archive_id}")
            continue

        print(f"  Fetched {len(full_text):,} chars")

        # Extract articles from djvu.txt
        articles = extract_article_from_toc_text(full_text)
        print(f"  Extracted {len(articles)} articles")

        new_count = 0
        for title, author, body in articles:
            if title not in done_keys:
                record = {
                    "article_title": title,
                    "article_author": author,
                    "year": year,
                    "volume": vol_num,
                    "body": body,
                    "source_key": "mesda",
                    "card_type": "article",
                }
                existing.append(record)
                done_keys.add(title)
                new_count += 1

        print(f"  Added {new_count} new articles")

    raw_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nScrape complete. {len(existing)} total articles in {raw_path.name}")


# ---------------------------------------------------------------------------
# Phase 2: Generate card metadata via Claude API
# ---------------------------------------------------------------------------

def phase_generate(years):
    """Generate card metadata via Claude Haiku for MESDA articles."""
    import anthropic

    raw_path = OUT_DIR / "mesda_journal_raw.json"
    cards_path = OUT_DIR / "mesda_journal_cards.json"

    if not raw_path.exists():
        print("No mesda_journal_raw.json found. Run scrape phase first.")
        return

    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    existing_cards = json.loads(cards_path.read_text(encoding="utf-8")) if cards_path.exists() else []
    done_titles = {c.get("article_title") for c in existing_cards}

    client = anthropic.Anthropic()
    new_cards = []

    for i, record in enumerate(raw):
        title = record.get("article_title")
        if title in done_titles:
            continue

        year = record.get("year")
        volume = record.get("volume")
        author = record.get("article_author", "")
        body = record.get("body", "")

        prompt = CARD_PROMPT.format(
            vocab=CONTROLLED_VOCAB,
            period="Federal / Neoclassical, Victorian, Colonial Revival",
            form="Seating, Tables, Case pieces, Textiles",
            region="North Carolina, South Carolina, Virginia, Charleston",
            topic="Construction / Technique, Regional Style, Attribution, Social History",
            pub_title=MESDA_JOURNAL["title"],
            year=year,
            article_title=title,
            body=body[:MAX_ARTICLE_CHARS],
        )

        try:
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = message.content[0].text

            # Parse JSON response
            card = json.loads(response_text)
            card["article_title"] = title
            card["article_author"] = author
            card["year"] = year
            card["volume"] = volume
            card["source_key"] = "mesda"
            card["card_type"] = "article"

            new_cards.append(card)
            print(f"  [{i+1}] {title[:60]}...")

            # Respectful rate limiting
            time.sleep(1)

        except json.JSONDecodeError as e:
            print(f"  ERROR: Could not parse Haiku response for '{title}': {e}")
        except Exception as e:
            print(f"  ERROR: Haiku failed for '{title}': {e}")

    # Append and save
    existing_cards.extend(new_cards)
    cards_path.write_text(json.dumps(existing_cards, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nGenerate complete. {len(new_cards)} new cards generated. Total: {len(existing_cards)}")


# ---------------------------------------------------------------------------
# Phase 3: Generate SQL
# ---------------------------------------------------------------------------

def phase_sql(years):
    """Generate SQL inserts for MESDA articles."""
    cards_path = OUT_DIR / "mesda_journal_cards.json"
    sql_path = OUT_DIR / "mesda_journal_insert.sql"

    if not cards_path.exists():
        print("No mesda_journal_cards.json found. Run generate phase first.")
        return

    cards = json.loads(cards_path.read_text(encoding="utf-8"))

    sql_lines = [
        "-- MESDA Journal cards (insert/replace)",
        f"-- Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "-- Import with: wrangler d1 execute card-catalog --file=mesda_journal_insert.sql",
        "",
    ]

    for card in cards:
        title = card.get("article_title", "").replace("'", "''")
        description = card.get("description", "").replace("'", "''")
        author = card.get("article_author", "").replace("'", "''")
        year = card.get("year", 0)
        volume = card.get("volume", 0)
        source_key = card.get("source_key", "mesda")
        card_type = card.get("card_type", "article")

        period = json.dumps(card.get("period", []))
        form = json.dumps(card.get("form", []))
        region = json.dumps(card.get("region", []))
        topic = json.dumps(card.get("topic", []))
        makers = json.dumps(card.get("makers", []))

        sql = f"""INSERT INTO library_cards (title, description, author, year, volume, source_key, card_type, period, form, region, topic, makers)
VALUES ('{title}', '{description}', '{author}', {year}, {volume}, '{source_key}', '{card_type}', '{period}', '{form}', '{region}', '{topic}', '{makers}')
ON CONFLICT(source_key, card_type, title) DO UPDATE SET
  description = excluded.description,
  period = excluded.period,
  form = excluded.form,
  region = excluded.region,
  topic = excluded.topic,
  makers = excluded.makers;
"""
        sql_lines.append(sql)

    sql_path.write_text('\n'.join(sql_lines), encoding="utf-8")
    print(f"SQL complete. {len(cards)} inserts written to {sql_path.name}")
    print(f"\nTo load: wrangler d1 execute card-catalog --file={sql_path.name}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def resolve_years(arg):
    """Parse year argument: 'all', '1995-2025', or 'YYYY'."""
    if arg == "all":
        return sorted(ARCHIVE_VOLUMES.keys())
    if "-" in arg:
        start, end = map(int, arg.split("-"))
        return [y for y in ARCHIVE_VOLUMES.keys() if start <= y <= end]
    try:
        return [int(arg)]
    except ValueError:
        print(f"Invalid year format: {arg}")
        return []


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MESDA Journal Article ETL")
    parser.add_argument("--phase", choices=["scrape", "generate", "sql", "all", "toc"], required=True)
    parser.add_argument("--year", default="all",
                        help="Year or range: 'all', '1995-2025', or 'YYYY'. Default: all")
    args = parser.parse_args()

    if args.phase == "toc":
        phase_toc(int(args.year) if args.year.isdigit() else None)
        sys.exit(0)

    years = resolve_years(args.year)
    if not years:
        sys.exit(1)

    if args.phase in ("scrape", "all"):
        phase_scrape(years)
    if args.phase in ("generate", "all"):
        phase_generate(years)
    if args.phase in ("sql", "all"):
        phase_sql(years)
