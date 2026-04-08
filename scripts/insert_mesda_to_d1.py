#!/usr/bin/env python3
"""
Insert MESDA cards to D1 via batch SQL inserts.
"""
import json
from pathlib import Path

OUT_DIR = Path(__file__).parent

def generate_insert_batches(batch_size=10):
    """Generate INSERT statements for MESDA cards in batches."""
    cards_path = OUT_DIR / "mesda_journal_cards.json"
    cards = json.loads(cards_path.read_text(encoding="utf-8"))

    batches = []
    for i in range(0, len(cards), batch_size):
        batch = cards[i:i+batch_size]
        values = []

        for card in batch:
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

            value = f"('{title}', '{description}', '{author}', {year}, {volume}, '{source_key}', '{card_type}', '{period}', '{form}', '{region}', '{topic}', '{makers}')"
            values.append(value)

        sql = f"""INSERT INTO library_cards (title, description, author, year, volume, source_key, card_type, period, form, region, topic, makers)
VALUES {','.join(values)}
ON CONFLICT(source_key, card_type, title) DO UPDATE SET
  description = excluded.description"""

        batches.append(sql)

    return batches

if __name__ == "__main__":
    batches = generate_insert_batches(batch_size=10)
    print(f"Generated {len(batches)} batches")
    for i, batch in enumerate(batches):
        print(f"\nBatch {i+1}:")
        print(f"  SQL length: {len(batch):,} chars")
        # Save each batch to a separate file
        batch_file = OUT_DIR / f"mesda_insert_batch_{i+1:02d}.sql"
        batch_file.write_text(batch, encoding="utf-8")
        print(f"  Saved to {batch_file.name}")
