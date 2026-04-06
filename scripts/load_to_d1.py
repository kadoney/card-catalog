"""Load chipstone_inserts.sql into D1 via Cloudflare REST API."""
import os, sys, json, time
import urllib.request, urllib.error

ACCOUNT_ID = "ebe622eaa5b3a3581cf5664272f26f30"
DATABASE_ID = "eb944e67-5fcc-4587-8fe1-eae2a9fe3476"
TOKEN_FILE = os.path.expanduser(r"~\.wrangler\config\default.toml")

# Read token from wrangler config
token = None
with open(TOKEN_FILE, encoding="utf-8") as f:
    for line in f:
        if line.startswith("oauth_token"):
            token = line.split("=")[1].strip().strip('"')
            break

if not token:
    sys.exit("Could not read oauth_token from wrangler config")

print(f"Token loaded ({token[:20]}...)")

SQL_FILE = os.path.join(os.path.dirname(__file__), "chipstone_inserts.sql")

with open(SQL_FILE, encoding="utf-8") as f:
    inserts = [l.rstrip() for l in f if l.strip().startswith("INSERT")]

print(f"Loaded {len(inserts)} INSERT statements")

url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/d1/database/{DATABASE_ID}/query"

ok = 0
errors = 0

for i, sql in enumerate(inserts):
    payload = json.dumps({"sql": sql}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
            if body.get("success"):
                ok += 1
            else:
                errors += 1
                print(f"  ERROR #{i+1}: {body.get('errors')}")
    except urllib.error.HTTPError as e:
        errors += 1
        print(f"  HTTP {e.code} on insert #{i+1}: {e.read()[:200]}")

    if (i + 1) % 50 == 0:
        print(f"  Progress: {i+1}/{len(inserts)} ({ok} ok, {errors} errors)")

print(f"\nDone. {ok} inserted, {errors} errors.")
