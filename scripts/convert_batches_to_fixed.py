#!/usr/bin/env python3
"""Convert batch SQL files to properly formatted inserts with json() wrapping."""
import re
from pathlib import Path

BATCH_DIR = Path(r'C:\dev\card-catalog\scripts')

def convert_batch(batch_num):
    """Convert a single batch file."""
    input_file = BATCH_DIR / f'mesda_batch_{batch_num:02d}.sql'

    if not input_file.exists():
        return False

    sql = input_file.read_text(encoding='utf-8', errors='replace')

    # Extract VALUES section
    match = re.search(r'VALUES\s+(.*?)\s+ON CONFLICT', sql, re.DOTALL)
    if not match:
        print(f"Batch {batch_num}: No VALUES found")
        return False

    values_str = match.group(1).strip()

    # Process the values string to add json() calls
    # Strategy: find all [...] patterns that are NOT inside quotes
    fixed = ""
    depth = 0
    in_string = False
    escape = False
    i = 0

    while i < len(values_str):
        char = values_str[i]

        # Handle string literals
        if escape:
            fixed += char
            escape = False
            i += 1
            continue

        if char == '\\' and in_string:
            fixed += char
            escape = True
            i += 1
            continue

        if char == "'" and (i == 0 or values_str[i-1] != "'"):
            in_string = not in_string
            fixed += char
            i += 1
            continue

        # Track parenthesis depth (only when not in string)
        if not in_string:
            if char == '(':
                depth += 1
                fixed += char
            elif char == ')':
                depth -= 1
                fixed += char
            elif char == '[' and depth == 1:
                # Found a top-level array, find its end and wrap with json()
                j = i
                array_depth = 0
                while j < len(values_str):
                    if values_str[j] == '[':
                        array_depth += 1
                    elif values_str[j] == ']':
                        array_depth -= 1
                        if array_depth == 0:
                            # Found the end of the array
                            array_str = values_str[i:j+1]
                            fixed += f"json('{array_str}')"
                            i = j
                            break
                    j += 1
            else:
                fixed += char
        else:
            fixed += char

        i += 1

    output = "INSERT INTO library_cards (title, authors, year, source, description, period, form, region, topic, makers, card_type)\nVALUES "
    output += fixed

    output_file = BATCH_DIR / f'mesda_batch_{batch_num:02d}_fixed.sql'

    # Count rows
    row_count = fixed.count('),(') + 1

    output_file.write_text(output, encoding='utf-8')
    print(f"Batch {batch_num:02d}: {row_count} rows -> {output_file.name}")
    return True

# Process batches 3-10
for batch_num in range(3, 11):
    convert_batch(batch_num)

print("Done!")
