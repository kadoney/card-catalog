#!/usr/bin/env python3
"""Load all remaining MESDA batches with proper SQLite escaping."""
import re
import json
from pathlib import Path

BATCH_DIR = Path(r'C:\dev\card-catalog\scripts')

# Load batches 3-10 (batch 1 and 2 already loaded)
for batch_num in range(3, 11):
    batch_file = BATCH_DIR / f'mesda_batch_{batch_num:02d}.sql'
    if not batch_file.exists():
        print(f"Skipping {batch_file.name} (not found)")
        continue

    sql = batch_file.read_text(encoding='utf-8')

    # Extract the VALUES part between VALUES and ON CONFLICT
    match = re.search(r'VALUES\s+(.*?)\s+ON CONFLICT', sql, re.DOTALL)
    if not match:
        print(f"  ERROR: Could not extract VALUES from {batch_file.name}")
        continue

    values_str = match.group(1)

    # Split by row (each row starts with '(')
    rows = []
    depth = 0
    current_row = ""
    for char in values_str:
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1

        current_row += char

        if depth == 0 and char == ')' and current_row.strip():
            rows.append(current_row.strip())
            current_row = ""

    if current_row.strip():
        rows.append(current_row.strip())

    # Convert each row to use json() function
    fixed_rows = []
    for row_str in rows:
        if not row_str or row_str == ',':
            continue

        # Remove leading/trailing parens and comma
        row_str = row_str.lstrip('(').rstrip('),').strip()
        if not row_str:
            continue

        # Split by top-level commas (tricky with nested arrays)
        # Use a simple regex to find quoted strings and arrays
        parts = []
        current_part = ""
        in_string = False
        in_array = False
        escape_next = False

        for i, char in enumerate(row_str):
            if escape_next:
                current_part += char
                escape_next = False
                continue

            if char == '\\':
                escape_next = True
                current_part += char
                continue

            if char == "'" and (i == 0 or row_str[i-1] != "'"):
                in_string = not in_string
            elif char == '[':
                in_array = True
            elif char == ']':
                in_array = False
            elif char == ',' and not in_string and not in_array:
                parts.append(current_part.strip())
                current_part = ""
                continue

            current_part += char

        if current_part.strip():
            parts.append(current_part.strip())

        # Process each part to wrap arrays with json()
        fixed_parts = []
        for part in parts:
            part = part.strip()
            if part.startswith('[') and part.endswith(']'):
                # This is a JSON array, wrap it
                fixed_parts.append(f"json('{part}')")
            else:
                fixed_parts.append(part)

        fixed_row = f"({', '.join(fixed_parts)})"
        fixed_rows.append(fixed_row)

    if fixed_rows:
        new_sql = "INSERT INTO library_cards (title, authors, year, source, description, period, form, region, topic, makers, card_type)\nVALUES "
        new_sql += ",\n".join(fixed_rows)

        output_file = batch_file.parent / f"{batch_file.stem}_fixed.sql"
        output_file.write_text(new_sql, encoding='utf-8')
        print(f"  {batch_file.name}: {len(fixed_rows)} rows → {output_file.name}")
    else:
        print(f"  ERROR: No rows extracted from {batch_file.name}")

print("\nFixed SQL files ready for loading")
