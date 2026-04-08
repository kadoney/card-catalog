#!/usr/bin/env python3
"""
Create batched insert files for MESDA cards.
"""
import json
from pathlib import Path

OUT_DIR = Path(__file__).parent

def generate_batches(batch_size=8):
    """Generate INSERT statements for MESDA cards in batches."""
    cards_path = OUT_DIR / "mesda_journal_cards.json"
    cards = json.loads(cards_path.read_text(encoding="utf-8"))

    batches = []
    for batch_num in range(0, len(cards), batch_size):
        batch = cards[batch_num:batch_num+batch_size]
        values = []

        for card in batch:
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
  topic = excluded.topic;"""

        batches.append(sql)

    return batches

if __name__ == "__main__":
    batches = generate_batches(batch_size=8)
    print(f"Generated {len(batches)} batches ({len(batches[0])} chars each)")

    for i, batch in enumerate(batches):
        batch_file = OUT_DIR / f"mesda_batch_{i+1:02d}.sql"
        batch_file.write_text(batch, encoding="utf-8")
        print(f"  Batch {i+1}: {batch_file.name} ({len(batch)} chars, {batch.count('VALUES')} rows)")
