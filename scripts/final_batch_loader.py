#!/usr/bin/env python3
"""Final loader: parse mesda_batch_03-10.sql and generate clean D1-ready SQL."""
import re
import json
from pathlib import Path

BATCH_DIR = Path('.')

def parse_batch_file(batch_num):
    """Parse a single batch file and return list of card dicts."""
    batch_file = BATCH_DIR / f'mesda_batch_{batch_num:02d}.sql'

    if not batch_file.exists():
        return []

    with open(batch_file, 'r', encoding='utf-8', errors='replace') as f:
        sql = f.read()

    # Extract VALUES section
    match = re.search(r'VALUES\s+(.*?)\s+ON CONFLICT', sql, re.DOTALL)
    if not match:
        print(f"Batch {batch_num:02d}: No VALUES found")
        return []

    values_str = match.group(1).strip()

    # Split by ),( pattern to get individual rows
    rows_raw = re.split(r'\),\s*\(', values_str)

    cards = []
    for row_idx, row_text in enumerate(rows_raw):
        # Clean up row
        row_text = row_text.lstrip('(').rstrip(')')

        # Parse the fields manually
        # The pattern is: 'title', ["authors"], year, 'source', 'description', [period], [form], [region], [topic], '[]', 'card_type'

        # Use a state machine to find field boundaries
        fields = []
        current_field = ""
        in_quotes = False
        in_array = False
        i = 0

        while i < len(row_text):
            char = row_text[i]

            # Check for quote escaping ('' = single quote)
            if char == "'" and in_quotes and i + 1 < len(row_text) and row_text[i + 1] == "'":
                current_field += "''"
                i += 2
                continue

            if char == "'" and (i == 0 or row_text[i - 1] != "'"):
                in_quotes = not in_quotes
                current_field += char
            elif not in_quotes and char == '[':
                in_array = True
                current_field += char
            elif not in_quotes and char == ']':
                in_array = False
                current_field += char
            elif not in_quotes and not in_array and char == ',':
                fields.append(current_field.strip())
                current_field = ""
                i += 1
                # Skip whitespace after comma
                while i < len(row_text) and row_text[i] in (' ', '\n', '\t'):
                    i += 1
                continue
            else:
                current_field += char

            i += 1

        if current_field.strip():
            fields.append(current_field.strip())

        if len(fields) != 11:
            print(f"Batch {batch_num:02d}, Row {row_idx}: Expected 11 fields, got {len(fields)}")
            for j, f in enumerate(fields):
                print(f"  Field {j}: {f[:80] if len(f) > 80 else f}")
            continue

        try:
            # Parse each field
            def parse_quoted(s):
                s = s.strip()
                if s.startswith("'") and s.endswith("'"):
                    return s[1:-1].replace("''", "'")
                return s

            def parse_array(s):
                s = s.strip()
                if s.startswith('[') and s.endswith(']'):
                    try:
                        return json.loads(s)
                    except:
                        return []
                return []

            card = {
                'title': parse_quoted(fields[0]),
                'authors': parse_array(fields[1]),
                'year': int(fields[2]),
                'source': parse_quoted(fields[3]),
                'description': parse_quoted(fields[4]),
                'period': parse_array(fields[5]),
                'form': parse_array(fields[6]),
                'region': parse_array(fields[7]),
                'topic': parse_array(fields[8]),
                'makers': parse_array(fields[9]),
                'card_type': parse_quoted(fields[10])
            }

            cards.append(card)

        except Exception as e:
            print(f"Batch {batch_num:02d}, Row {row_idx}: Parse error - {e}")

    return cards

# Load all batches
all_cards = []
for batch_num in range(3, 11):
    cards = parse_batch_file(batch_num)
    all_cards.extend(cards)
    print(f"Batch {batch_num:02d}: {len(cards)} cards")

print(f"\nTotal: {len(all_cards)} cards extracted")

# Generate clean SQL
if all_cards:
    sql_parts = []
    sql_parts.append("INSERT INTO library_cards (title, authors, year, source, description, period, form, region, topic, makers, card_type)")
    sql_parts.append("VALUES")

    for i, card in enumerate(all_cards):
        # Escape single quotes
        title = card['title'].replace("'", "''")
        source = card['source'].replace("'", "''")
        desc = card['description'].replace("'", "''")

        # JSON arrays
        authors_json = json.dumps(card['authors'], ensure_ascii=False)
        period_json = json.dumps(card['period'], ensure_ascii=False)
        form_json = json.dumps(card['form'], ensure_ascii=False)
        region_json = json.dumps(card['region'], ensure_ascii=False)
        topic_json = json.dumps(card['topic'], ensure_ascii=False)
        makers_json = json.dumps(card['makers'], ensure_ascii=False)

        row = f"('{title}', json('{authors_json}'), {card['year']}, '{source}', '{desc}', json('{period_json}'), json('{form_json}'), json('{region_json}'), json('{topic_json}'), json('{makers_json}'), '{card['card_type']}')"

        if i < len(all_cards) - 1:
            sql_parts.append(row + ",")
        else:
            sql_parts.append(row)

    sql_output = '\n'.join(sql_parts)

    output_file = BATCH_DIR / 'mesda_batches_3_10_final.sql'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(sql_output)

    print(f"\nGenerated: {output_file.name}")
    print(f"SQL size: {len(sql_output):,} bytes")
    print(f"Ready to load {len(all_cards)} cards!")

EOF
