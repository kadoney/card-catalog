"""
Met Museum Bulletin — American Furniture ETL Pipeline
Downloads PDFs, extracts text, generates card metadata via Claude API.

Usage:
  python met_bulletin_etl.py --phase scrape    # download PDFs + extract text -> met_bulletin_raw.json
  python met_bulletin_etl.py --phase generate  # call Claude API -> met_bulletin_cards.json
  python met_bulletin_etl.py --phase sql       # convert -> met_bulletin_inserts.sql
  python met_bulletin_etl.py --phase all       # run all three phases

Requirements:
  pip install pdfplumber anthropic requests

Set ANTHROPIC_API_KEY in environment before running generate phase.
"""

import argparse
import io
import json
import os
import re
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import requests
import pdfplumber
import anthropic

OUT_DIR = Path(__file__).parent

# Pilot corpus: Met Museum Bulletins on American furniture
BULLETINS = [
    {
        "title": "American Japanned Furniture",
        "authors": ["Alyce Perry Englund"],
        "year": 2025,
        "source": "The Metropolitan Museum of Art Bulletin, Vol. 82, No. 3",
        "source_key": "met",
        "card_type": "essay",
        "view_url": "https://www.metmuseum.org/met-publications/american-japanned-furniture",
        "pdf_url": "https://cdn.sanity.io/files/cctd4ker/production/a957d8ba246cab8bbe9788d37af46034e379e0ba.pdf",
        "is_free": 1,
    },
    {
        "title": "Artistic Furniture of the Gilded Age",
        "authors": ["Alice Cooney Frelinghuysen", "Nicholas C. Vincent"],
        "year": 2016,
        "source": "The Metropolitan Museum of Art Bulletin, Vol. 73, No. 3",
        "source_key": "met",
        "card_type": "essay",
        "view_url": "https://www.metmuseum.org/met-publications/artistic-furniture-of-the-gilded-age",
        "pdf_url": "https://cdn.sanity.io/files/cctd4ker/production/e4727973160a1e327e474f2aca361cb67bfba951.pdf",
        "is_free": 1,
    },
    {
        "title": "Chippendale's Director: A Manifesto of Furniture Design",
        "authors": ["Morrison H. Heckscher"],
        "year": 2018,
        "source": "The Metropolitan Museum of Art Bulletin, Vol. 75, No. 4",
        "source_key": "met",
        "card_type": "essay",
        "view_url": "https://www.metmuseum.org/met-publications/chippendales-director-a-manifesto-of-furniture-design",
        "pdf_url": "https://cdn.sanity.io/files/cctd4ker/production/d0237fe67426be9d1c469fd65459cbc3f3f92b60.pdf",
        "is_free": 1,
    },
    {
        "title": "Baltimore Federal Furniture in The American Wing",
        "authors": ["Marilynn Johnson Bordes"],
        "year": 1972,
        "source": "The Metropolitan Museum of Art Bulletin, Vol. 31, No. 2",
        "source_key": "met",
        "card_type": "essay",
        "view_url": "https://www.metmuseum.org/met-publications/baltimore-federal-furniture-in-the-american-wing",
        "pdf_url": "https://cdn.sanity.io/files/cctd4ker/production/493634202544463c53097e61eeda362c3ebdf02c.pdf",
        "is_free": 1,
    },
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
I will give you the full text of a Metropolitan Museum of Art Bulletin essay on American furniture.
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
- Use "Survey / Multiple" for period/form/region only when the essay genuinely spans multiple without focusing on one
- If you cannot determine a field, use [] for arrays or a brief honest description

ESSAY:
Title: {title}
Authors: {authors}
Year: {year}
Source: {source}
URL: {url}

Full text:
{body}
"""


# ===========================================================================
# Phase 1: Download PDFs + extract text
# ===========================================================================

def extract_pdf_text(pdf_path, max_chars=8000):
    """Extract text from a PDF file using pdfplumber."""
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    full_text = "\n".join(text_parts)
    if len(full_text) > max_chars:
        full_text = full_text[:max_chars] + "\n[truncated]"
    return full_text


def phase_scrape():
    raw_path = OUT_DIR / "met_bulletin_raw.json"
    pdf_dir = OUT_DIR / "met_pdfs"
    pdf_dir.mkdir(exist_ok=True)

    if raw_path.exists():
        with open(raw_path, encoding="utf-8") as f:
            existing = json.load(f)
        done_urls = {r["view_url"] for r in existing}
        print(f"Resuming: {len(existing)} bulletins already processed")
    else:
        existing = []
        done_urls = set()

    for bul in BULLETINS:
        if bul["view_url"] in done_urls:
            print(f"SKIP (already done): {bul['title']}")
            continue

        print(f"\nProcessing: {bul['title']}")

        # Download PDF
        slug = re.sub(r"[^\w-]", "_", bul["title"].lower())[:40]
        pdf_path = pdf_dir / f"{bul['year']}_{slug}.pdf"

        if not pdf_path.exists():
            print(f"  Downloading PDF...")
            try:
                resp = requests.get(
                    bul["pdf_url"],
                    timeout=60,
                    headers={"User-Agent": "SAPFM-CardCatalog/1.0 (research; contact@sapfm.org)"},
                )
                resp.raise_for_status()
                pdf_path.write_bytes(resp.content)
                print(f"  Saved {len(resp.content)//1024} KB to {pdf_path.name}")
                time.sleep(2)
            except Exception as e:
                print(f"  ERROR downloading: {e}")
                continue
        else:
            print(f"  PDF already downloaded: {pdf_path.name}")

        # Extract text
        print(f"  Extracting text...")
        try:
            body = extract_pdf_text(pdf_path)
            print(f"  Extracted {len(body)} chars")
        except Exception as e:
            print(f"  ERROR extracting: {e}")
            continue

        record = {
            "title": bul["title"],
            "authors": bul["authors"],
            "year": bul["year"],
            "source": bul["source"],
            "source_key": bul["source_key"],
            "card_type": bul["card_type"],
            "view_url": bul["view_url"],
            "pdf_url": bul["pdf_url"],
            "is_free": bul["is_free"],
            "body": body,
        }
        existing.append(record)
        done_urls.add(bul["view_url"])

    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    print(f"\nScrape complete. {len(existing)} bulletins in {raw_path}")


# ===========================================================================
# Phase 2: Generate card metadata via Claude API
# ===========================================================================

def phase_generate():
    raw_path = OUT_DIR / "met_bulletin_raw.json"
    cards_path = OUT_DIR / "met_bulletin_cards.json"

    if not raw_path.exists():
        print("Run --phase scrape first")
        sys.exit(1)

    with open(raw_path, encoding="utf-8") as f:
        raw = json.load(f)

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
        if rec["view_url"] in done_urls:
            continue

        print(f"[{i+1}/{len(raw)}] {rec['year']} — {rec['title']}", flush=True)

        prompt = CARD_PROMPT.format(
            vocab=CONTROLLED_VOCAB,
            title=rec["title"],
            authors=", ".join(rec["authors"]),
            year=rec["year"],
            source=rec["source"],
            url=rec["view_url"],
            body=rec["body"][:7000],
        )

        try:
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )
            text = msg.content[0].text.strip()

            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if not json_match:
                print(f"  WARNING: no JSON in response — {text[:200]}")
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
                "is_free": rec["is_free"],
                "view_url": rec["view_url"],
                "download_url": rec["pdf_url"],
                "contributed_by": None,
                "contributor_name": None,
            }
            cards.append(card)
            done_urls.add(rec["view_url"])
            print(f"  OK — period={card['period']}, topic={card['topic'][:2]}", flush=True)

        except json.JSONDecodeError as e:
            print(f"  JSON parse error: {e} — {text[:200]}", flush=True)
            continue
        except Exception as e:
            print(f"  API error: {e}")
            time.sleep(5)
            continue

        time.sleep(1.0)

    with open(cards_path, "w", encoding="utf-8") as f:
        json.dump(cards, f, indent=2, ensure_ascii=False)

    print(f"\nGenerate complete. {len(cards)} cards in {cards_path}")


# ===========================================================================
# Phase 3: Generate SQL inserts
# ===========================================================================

def phase_sql():
    cards_path = OUT_DIR / "met_bulletin_cards.json"
    sql_path = OUT_DIR / "met_bulletin_inserts.sql"

    if not cards_path.exists():
        print("Run --phase generate first")
        sys.exit(1)

    with open(cards_path, encoding="utf-8") as f:
        cards = json.load(f)

    lines = [
        "-- Met Museum Bulletins — American Furniture pilot corpus",
        f"-- Generated from {len(cards)} essays",
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
        card_type = esc(c.get("card_type") or "essay")
        view_url = esc(c.get("view_url") or "")
        download_url = esc(c.get("download_url") or "")
        is_free = 1 if c.get("is_free") else 0

        lines.append(
            f"INSERT OR REPLACE INTO library_cards "
            f"(title, authors, year, source, source_key, card_type, "
            f"description, period, form, region, topic, makers, "
            f"is_free, view_url, download_url, status, created_at, updated_at) VALUES "
            f"('{title}', '{authors}', {year}, '{source}', '{source_key}', '{card_type}', "
            f"'{desc}', '{period}', '{form}', '{region}', '{topic}', '{makers}', "
            f"{is_free}, '{view_url}', '{download_url}', 'approved', datetime('now'), datetime('now'));"
        )

    with open(sql_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"SQL written: {len(cards)} inserts to {sql_path}")


# ===========================================================================
# Main
# ===========================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Met Bulletin ETL pipeline")
    parser.add_argument("--phase", choices=["scrape", "generate", "sql", "all"], required=True)
    args = parser.parse_args()

    if args.phase in ("scrape", "all"):
        phase_scrape()
    if args.phase in ("generate", "all"):
        phase_generate()
    if args.phase in ("sql", "all"):
        phase_sql()
