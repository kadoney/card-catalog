#!/usr/bin/env python3
"""Load MESDA cards to D1 via API using proper SQL escaping."""
import json
import re
from pathlib import Path

BATCH_DIR = Path(r'C:\dev\card-catalog\scripts')

def extract_cards_from_batch(batch_num):
    """Extract card data from a batch SQL file."""
    batch_file = BATCH_DIR / f'mesda_batch_{batch_num:02d}.sql'

    if not batch_file.exists():
        return []

    sql = batch_file.read_text(encoding='utf-8', errors='replace')

    # Extract VALUES section
    match = re.search(r'VALUES\s+(.*?)\s+ON CONFLICT', sql, re.DOTALL)
    if not match:
        print(f"Batch {batch_num}: No VALUES found")
        return []

    values_str = match.group(1).strip()

    # Parse individual rows
    # Each row is: (...), (...), (...)
    # Use a state machine to track parenthesis depth and string literals

    cards = []
    current_row = ""
    depth = 0
    in_string = False
    escape = False

    for char in values_str:
        if escape:
            current_row += char
            escape = False
            continue

        if char == '\\' and in_string:
            current_row += char
            escape = True
            continue

        if char == "'" and (not current_row or current_row[-1] != "'"):
            in_string = not in_string

        if not in_string:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
                if depth == 0:
                    # End of a row
                    current_row += char
                    row_data = parse_row(current_row)
                    if row_data:
                        cards.append(row_data)
                    current_row = ""
                    continue

        current_row += char

    return cards

def parse_row(row_str):
    """Parse a single row tuple into fields."""
    # Remove outer parens
    inner = row_str.strip('(),').strip()

    # Split by comma, being careful about quotes and arrays
    fields = []
    current = ""
    in_string = False
    in_array = False
    escape = False

    for char in inner:
        if escape:
            current += char
            escape = False
        elif char == '\\':
            escape = True
            current += char
        elif char == "'" and (not current or current[-1] != "'"):
            in_string = not in_string
            current += char
        elif char == '[':
            in_array = True
            current += char
        elif char == ']':
            in_array = False
            current += char
        elif char == ',' and not in_string and not in_array:
            fields.append(current.strip())
            current = ""
        else:
            current += char

    if current.strip():
        fields.append(current.strip())

    # Parse fields: title, authors, year, source, description, period, form, region, topic, makers, card_type
    if len(fields) != 11:
        print(f"  WARNING: Expected 11 fields, got {len(fields)}")
        return None

    try:
        title = fields[0].strip("'\"")
        authors = parse_json_array(fields[1])
        year = int(fields[2])
        source = fields[3].strip("'\"")
        description = fields[4].strip("'\"")
        period = parse_json_array(fields[5])
        form = parse_json_array(fields[6])
        region = parse_json_array(fields[7])
        topic = parse_json_array(fields[8])
        makers = parse_json_array(fields[9])
        card_type = fields[10].strip("'\"")

        return {
            'title': title,
            'authors': authors,
            'year': year,
            'source': source,
            'description': description,
            'period': period,
            'form': form,
            'region': region,
            'topic': topic,
            'makers': makers,
            'card_type': card_type
        }
    except Exception as e:
        print(f"  ERROR parsing row: {e}")
        print(f"  Fields: {fields}")
        return None

def parse_json_array(field_str):
    """Parse a JSON array field."""
    field_str = field_str.strip()
    if field_str.startswith('[') and field_str.endswith(']'):
        try:
            return json.loads(field_str)
        except:
            return []
    return []

# Extract cards from batches 3-10
all_cards = []
for batch_num in range(3, 11):
    cards = extract_cards_from_batch(batch_num)
    all_cards.extend(cards)
    print(f"Batch {batch_num:02d}: {len(cards)} cards")

print(f"\nTotal cards extracted: {len(all_cards)}")

# Save to JSON for inspection
output_file = BATCH_DIR / 'mesda_cards_for_loading.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(all_cards, f, indent=2, ensure_ascii=False)

print(f"Saved to {output_file.name}")

# Print SQL insert statement
if all_cards:
    sql_lines = ["INSERT INTO library_cards (title, authors, year, source, description, period, form, region, topic, makers, card_type)"]
    sql_lines.append("VALUES")

    for i, card in enumerate(all_cards):
        # Properly escape single quotes in strings
        title = card['title'].replace("'", "''")
        source = card['source'].replace("'", "''")
        description = card['description'].replace("'", "''")

        authors_json = json.dumps(card['authors'], ensure_ascii=False)
        period_json = json.dumps(card['period'], ensure_ascii=False)
        form_json = json.dumps(card['form'], ensure_ascii=False)
        region_json = json.dumps(card['region'], ensure_ascii=False)
        topic_json = json.dumps(card['topic'], ensure_ascii=False)
        makers_json = json.dumps(card['makers'], ensure_ascii=False)

        values = f"('{title}', json('{authors_json}'), {card['year']}, '{source}', '{description}', json('{period_json}'), json('{form_json}'), json('{region_json}'), json('{topic_json}'), json('{makers_json}'), '{card['card_type']}')"

        if i < len(all_cards) - 1:
            sql_lines.append(values + ",")
        else:
            sql_lines.append(values)

    sql_file = BATCH_DIR / 'mesda_batches_3_10_clean.sql'
    with open(sql_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(sql_lines))

    print(f"Saved SQL to {sql_file.name}")
