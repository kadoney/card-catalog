#!/usr/bin/env python3
"""Generate clean SQL for loading MESDA batches 3-10."""
import re
import json
from pathlib import Path

BATCH_DIR = Path(r'C:\dev\card-catalog\scripts')

def extract_values_from_sql(sql_content):
    """Extract the VALUES section from batch SQL."""
    match = re.search(r'VALUES\s+(.*?)\s+ON CONFLICT', sql_content, re.DOTALL)
    if not match:
        return None
    return match.group(1).strip()

def parse_sql_row(row_text):
    """Parse a single SQL row using regex to extract field values."""
    # This is tricky because we need to handle nested quotes, arrays, etc.
    # We'll use a state machine approach

    row_text = row_text.strip('(),').strip()
    fields = []
    current_field = ""
    in_quotes = False
    in_array = False
    brace_depth = 0
    escape_next = False

    for i, char in enumerate(row_text):
        if escape_next:
            current_field += char
            escape_next = False
            continue

        if char == '\\':
            current_field += char
            escape_next = True
            continue

        if char == "'" and (i == 0 or row_text[i-1] != "'"):
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
        else:
            current_field += char

    if current_field.strip():
        fields.append(current_field.strip())

    return fields

def extract_from_quotes(text):
    """Extract a string from single quotes, handling doubled quotes."""
    text = text.strip()
    if text.startswith("'") and text.endswith("'"):
        # Remove outer quotes and unescape doubled quotes
        inner = text[1:-1]
        return inner.replace("''", "'")
    return text

def parse_json_array(text):
    """Parse a JSON array from text."""
    text = text.strip()
    if text.startswith('[') and text.endswith(']'):
        try:
            return json.loads(text)
        except:
            return []
    return []

# Load batches and generate SQL
all_cards = []

for batch_num in range(3, 11):
    batch_file = BATCH_DIR / f'mesda_batch_{batch_num:02d}.sql'

    if not batch_file.exists():
        continue

    print(f"Processing Batch {batch_num:02d}...")
    sql = batch_file.read_text(encoding='utf-8', errors='replace')
    values_str = extract_values_from_sql(sql)

    if not values_str:
        print(f"  ERROR: No VALUES found")
        continue

    # Split by row using a simple regex (split on ),( pattern)
    rows = re.findall(r'\([^)]*(?:\[[^\]]*\][^)]*)*\)', values_str)

    print(f"  Found {len(rows)} rows")

    for row_idx, row_text in enumerate(rows):
        try:
            fields = parse_sql_row(row_text)

            if len(fields) != 11:
                print(f"    Row {row_idx}: Expected 11 fields, got {len(fields)}")
                continue

            card = {
                'title': extract_from_quotes(fields[0]),
                'authors': parse_json_array(fields[1]),
                'year': int(fields[2]),
                'source': extract_from_quotes(fields[3]),
                'description': extract_from_quotes(fields[4]),
                'period': parse_json_array(fields[5]),
                'form': parse_json_array(fields[6]),
                'region': parse_json_array(fields[7]),
                'topic': parse_json_array(fields[8]),
                'makers': parse_json_array(fields[9]),
                'card_type': extract_from_quotes(fields[10])
            }

            all_cards.append(card)
        except Exception as e:
            print(f"    Row {row_idx}: ERROR - {e}")

print(f"\nTotal cards extracted: {len(all_cards)}")

# Generate SQL for all extracted cards
if all_cards:
    sql_lines = ["INSERT INTO library_cards (title, authors, year, source, description, period, form, region, topic, makers, card_type)"]
    sql_lines.append("VALUES")

    for i, card in enumerate(all_cards):
        title = card['title'].replace("'", "''")
        source = card['source'].replace("'", "''")
        desc = card['description'].replace("'", "''")

        authors_json = json.dumps(card['authors'], ensure_ascii=False)
        period_json = json.dumps(card['period'], ensure_ascii=False)
        form_json = json.dumps(card['form'], ensure_ascii=False)
        region_json = json.dumps(card['region'], ensure_ascii=False)
        topic_json = json.dumps(card['topic'], ensure_ascii=False)
        makers_json = json.dumps(card['makers'], ensure_ascii=False)

        row = f"('{title}', json('{authors_json}'), {card['year']}, '{source}', '{desc}', json('{period_json}'), json('{form_json}'), json('{region_json}'), json('{topic_json}'), json('{makers_json}'), '{card['card_type']}')"

        if i < len(all_cards) - 1:
            sql_lines.append(row + ",")
        else:
            sql_lines.append(row)

    sql_output = '\n'.join(sql_lines)

    output_file = BATCH_DIR / 'mesda_batches_3_10_clean.sql'
    output_file.write_text(sql_output, encoding='utf-8')

    print(f"Saved clean SQL to {output_file.name}")
    print(f"SQL size: {len(sql_output):,} bytes")
