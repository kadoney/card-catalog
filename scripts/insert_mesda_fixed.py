#!/usr/bin/env python3
"""
Insert MESDA cards to D1 with correct schema.
"""
import json
from pathlib import Path

OUT_DIR = Path(__file__).parent

def generate_insert():
    """Generate INSERT statement for MESDA cards with correct schema."""
    cards_path = OUT_DIR / "mesda_journal_cards.json"
    cards = json.loads(cards_path.read_text(encoding="utf-8"))

    values = []
    for card in cards:
        title = card.get("article_title", "").replace("'", "''")
        description = card.get("description", "").replace("'", "''")

        # authors as JSON array
        author = card.get("article_author", "")
        authors = json.dumps([author] if author else [])

        # source from journal name and volume/year
        year = card.get("year", "")
        volume = card.get("volume", "")
        source = f"Journal of Early Southern Decorative Arts, Vol. {volume} ({year})"
        source = source.replace("'", "''")

        card_type = card.get("card_type", "article")

        period = json.dumps(card.get("period", []))
        form = json.dumps(card.get("form", []))
        region = json.dumps(card.get("region", []))
        topic = json.dumps(card.get("topic", []))

        value = f"('{title}', {authors}, {year}, '{source}', '{description}', {period}, {form}, {region}, {topic}, '[]', 'article')"
        values.append(value)

    sql = f"""INSERT INTO library_cards (title, authors, year, source, description, period, form, region, topic, makers, card_type)
VALUES {','.join(values)}
ON CONFLICT(title) DO UPDATE SET
  description = excluded.description,
  period = excluded.period,
  form = excluded.form,
  region = excluded.region,
  topic = excluded.topic"""

    return sql, len(cards)

if __name__ == "__main__":
    sql, count = generate_insert()
    print(f"Generated insert for {count} MESDA cards")
    print(f"SQL length: {len(sql):,} chars")

    out_file = OUT_DIR / "mesda_insert_fixed.sql"
    out_file.write_text(sql, encoding="utf-8")
    print(f"Saved to {out_file.name}")
