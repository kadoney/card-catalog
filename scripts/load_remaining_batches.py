#!/usr/bin/env python3
"""Load remaining MESDA batches (3-10) by executing the SQL directly."""
import re
from pathlib import Path
import subprocess
import json

BATCH_DIR = Path(r'C:\dev\card-catalog\scripts')

# Load batches 3-10 using the fixed SQL files we created
for batch_num in range(3, 11):
    fixed_file = BATCH_DIR / f'mesda_batch_{batch_num:02d}_fixed.sql'

    if not fixed_file.exists():
        print(f"Batch {batch_num:02d}: {fixed_file.name} not found")
        continue

    # Read the SQL file
    sql = fixed_file.read_text(encoding='utf-8')

    # For debugging, print the first 500 chars
    print(f"\nBatch {batch_num:02d}: Executing...")
    print(f"SQL preview: {sql[:200]}...")

    # To execute via Python subprocess calling wrangler would be:
    # But we'll instead use the MCP D1 API via a separate Python call

print("\nNow loading via D1 API...")

# Load each batch via the D1 API
from mcp__77b74114-ce74-46ad-8b94-452bf0870165__d1_database_query import query

for batch_num in range(3, 11):
    fixed_file = BATCH_DIR / f'mesda_batch_{batch_num:02d}_fixed.sql'

    if not fixed_file.exists():
        continue

    sql = fixed_file.read_text(encoding='utf-8')

    try:
        result = query(
            database_id='eb944e67-5fcc-4587-8fe1-eae2a9fe3476',
            sql=sql
        )
        if result.get('success'):
            rows = result.get('result', {}).get('meta', {}).get('changes', 0)
            print(f"Batch {batch_num:02d}: SUCCESS ({rows} rows inserted)")
        else:
            print(f"Batch {batch_num:02d}: FAILED")
            print(f"  Error: {result}")
    except Exception as e:
        print(f"Batch {batch_num:02d}: ERROR - {e}")
