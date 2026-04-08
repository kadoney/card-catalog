#!/usr/bin/env python3
"""
Generate MESDA Journal cards from website metadata.
Uses article titles, authors, and journal context to create descriptions via Claude Haiku.
"""

import json
import os
import sys
import time
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic package not installed. Run: pip install anthropic")
    sys.exit(1)

OUT_DIR = Path(__file__).parent
CARD_PROMPT = """You are a librarian creating catalog cards for the Journal of Early Southern Decorative Arts (MESDA Journal).

Create a brief, informative card description for this article:
- Title: {title}
- Author: {author}
- Journal: Journal of Early Southern Decorative Arts, Vol. {volume} ({year})

The card should:
1. Summarize the article's likely content based on the title and author context
2. Be 2-3 sentences (roughly 50-80 words)
3. Include relevant period, form, region, and topic keywords from this list:

**Periods**: Colonial, Federal, Neoclassical, Victorian, Arts & Crafts, Art Nouveau, Early 20th Century
**Forms**: Seating, Tables, Case Pieces, Textiles, Ceramics, Silver, Maps, Paintings
**Regions**: North Carolina, South Carolina, Virginia, Tennessee, Kentucky, Charleston, Virginia Piedmont
**Topics**: Attribution, Construction/Technique, Regional Style, Social History, Makers, Enslaved Craftspeople

Return ONLY valid JSON (no markdown, no code blocks):
{{
  "description": "Brief 2-3 sentence summary of the article",
  "period": ["Colonial", "Federal"],
  "form": ["Seating", "Tables"],
  "region": ["Virginia", "North Carolina"],
  "topic": ["Attribution", "Regional Style"]
}}
"""

def generate_cards(limit: int = None):
    """Generate cards for MESDA articles from website metadata."""
    raw_path = OUT_DIR / "mesda_journal_website_raw.json"

    if not raw_path.exists():
        print("ERROR: mesda_journal_website_raw.json not found. Run scraper first.")
        return

    articles = json.loads(raw_path.read_text(encoding="utf-8"))
    if limit:
        articles = articles[:limit]

    cards_path = OUT_DIR / "mesda_journal_cards.json"
    existing_cards = json.loads(cards_path.read_text(encoding="utf-8")) if cards_path.exists() else []
    done_titles = {c.get("article_title") for c in existing_cards}

    client = anthropic.Anthropic()
    new_cards = []

    print(f"\nGenerating cards for {len(articles)} MESDA articles...")
    for i, article in enumerate(articles):
        title = article.get("article_title", "")

        if title in done_titles:
            print(f"  [{i+1}] SKIP (already exists): {title[:60]}...")
            continue

        author = article.get("article_author", "")
        year = article.get("year", 0)
        volume = article.get("volume", 0)
        url = article.get("url", "")

        prompt = CARD_PROMPT.format(
            title=title,
            author=author,
            year=year,
            volume=volume
        )

        try:
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = message.content[0].text

            # Strip markdown code blocks if present
            if response_text.startswith("```"):
                response_text = response_text.replace("```json", "").replace("```", "").strip()

            # Parse JSON response
            card = json.loads(response_text)
            card["article_title"] = title
            card["article_author"] = author
            card["year"] = year
            card["volume"] = volume
            card["url"] = url
            card["source_key"] = "mesda"
            card["card_type"] = "article"

            new_cards.append(card)
            print(f"  [{i+1}] {title[:60]}...")

            # Respectful rate limiting
            time.sleep(0.5)

        except json.JSONDecodeError as e:
            print(f"  [{i+1}] ERROR: Invalid JSON from Haiku: {e}")
            print(f"      Response: {response_text[:100]}")
        except Exception as e:
            print(f"  [{i+1}] ERROR: Haiku failed: {e}")

    # Append and save
    existing_cards.extend(new_cards)
    cards_path.write_text(json.dumps(existing_cards, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nGenerate complete. {len(new_cards)} new cards generated.")
    print(f"Total: {len(existing_cards)} cards in {cards_path.name}")

def generate_sql():
    """Generate SQL insert statements for MESDA cards."""
    cards_path = OUT_DIR / "mesda_journal_cards.json"
    sql_path = OUT_DIR / "mesda_journal_insert.sql"

    if not cards_path.exists():
        print("ERROR: mesda_journal_cards.json not found. Run generate phase first.")
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
  topic = excluded.topic;
"""
        sql_lines.append(sql)

    sql_path.write_text('\n'.join(sql_lines), encoding="utf-8")
    print(f"SQL complete. {len(cards)} inserts written to {sql_path.name}")
    print(f"\nTo load: wrangler d1 execute card-catalog --file={sql_path.name}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python mesda_journal_cards_generate.py [generate|sql] [limit]")
        print("  generate [N] — Generate cards (optionally limit to first N articles)")
        print("  sql          — Generate SQL insert statements")
        return

    phase = sys.argv[1]
    limit = None
    if len(sys.argv) > 2:
        limit = int(sys.argv[2])

    if phase == "generate":
        generate_cards(limit=limit)
    elif phase == "sql":
        generate_sql()
    else:
        print(f"Unknown phase: {phase}")

if __name__ == "__main__":
    main()
