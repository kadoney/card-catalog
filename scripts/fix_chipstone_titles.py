"""
Fix Chipstone titles: split concatenated "AuthorNameTitle Text" into
separate author and title fields, and update the D1 database.

Usage: python fix_chipstone_titles.py [--dry-run]
"""

import io, json, os, re, sys, time, urllib.request, urllib.error
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ACCOUNT_ID  = "ebe622eaa5b3a3581cf5664272f26f30"
DATABASE_ID = "eb944e67-5fcc-4587-8fe1-eae2a9fe3476"
TOKEN_FILE  = os.path.expanduser(r"~\.wrangler\config\default.toml")

# ---------------------------------------------------------------------------
# Splitting logic
# ---------------------------------------------------------------------------

SKIP_TITLES = {"book reviews", "the chipstone foundation", "annual bibliography"}

def split_author_title(raw_title):
    """
    Split a string like "AuthorNameTitle Text" into (authors_list, clean_title, card_type).

    Patterns handled:
      - "Linda BaumgartenProtective Covers..."
      - "Edward S. Cooke, Jr.Scandinavian Modern..."
      - "Edward S. Cooke, Jr.*Scandinavian Modern..."  (asterisk variant)
      - "Mark Anderson and Robert F. TrentA Catalogue..."
      - "Harry Mack Truax IIHigh Craft..."  (Roman numeral, no period)
      - "Gerald W. R. Ward"America's Contribution..."  (curly-quote title)
      - "Review by Elizabeth Pitzer GuslerTreasures of State..."
    """
    card_type = "article"
    text = raw_title.strip()

    # Section headers — not real cards
    if text.lower().rstrip('.') in SKIP_TITLES:
        return None, raw_title, card_type

    # Handle "Review by " prefix
    if text.lower().startswith("review by "):
        card_type = "review"
        text = text[len("review by "):]

    # Normalize Jr.* → Jr.
    text = re.sub(r'(Jr|Sr)\.\*', r'\1.', text)

    # Candidate split points, in priority order:
    candidates = []

    # 1. Jr./Sr. followed immediately by uppercase (with period)
    for m in re.finditer(r'(?:Jr|Sr)\.[A-Z]', text):
        candidates.append((m.start() + len(m.group()) - 1, "jr_period"))

    # 2. Roman numeral suffix (II/III/IV) followed immediately by uppercase (no period)
    for m in re.finditer(r'(?<!\w)(?:II|III|IV)(?=[A-Z])', text):
        candidates.append((m.end(), "roman"))

    # 3. Curly/straight quote starting a title  [a-z]"Title or [a-z]"Title
    for m in re.finditer(r'[a-z](?=["\u201c\u201d])', text):
        candidates.append((m.start() + 1, "quote"))

    # 4. Lowercase immediately followed by uppercase (general)
    for m in re.finditer(r'[a-z](?=[A-Z])', text):
        candidates.append((m.start() + 1, "lc_uc"))

    if not candidates:
        return [], raw_title, card_type

    # Take the earliest split point
    candidates.sort(key=lambda x: x[0])
    pos, _ = candidates[0]

    author_str = text[:pos].rstrip(',').strip()
    title = text[pos:].strip()

    # Sanity check: author part should be at least 4 chars, title at least 5
    if len(author_str) < 4 or len(title) < 5:
        return [], raw_title, card_type

    # Parse author string into a list
    # Split on " and " or comma, but NOT on ", Jr." / ", Sr." suffixes
    author_str_norm = re.sub(r',\s*(Jr|Sr|II|III|IV)\.?', r' \1.', author_str)
    authors = [a.strip() for a in re.split(r',?\s+and\s+|,\s*', author_str_norm) if a.strip()]

    return authors, title, card_type


# ---------------------------------------------------------------------------
# D1 helpers
# ---------------------------------------------------------------------------

def load_token():
    with open(TOKEN_FILE, encoding="utf-8") as f:
        for line in f:
            if line.startswith("oauth_token"):
                return line.split("=")[1].strip().strip('"')
    sys.exit("Could not read oauth_token from wrangler config")


def d1_query(token, sql, params=None):
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/d1/database/{DATABASE_ID}/query"
    body = {"sql": sql}
    if params:
        body["params"] = params
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("DRY RUN — no DB changes will be made\n")

    token = load_token()
    print(f"Token loaded ({token[:20]}...)\n")

    # Fetch all chipstone cards
    result = d1_query(token, "SELECT id, title, authors, card_type, view_url FROM library_cards WHERE source_key = 'chipstone' ORDER BY id")
    cards = result[0]["results"]
    print(f"Fetched {len(cards)} Chipstone cards\n")

    ok = errors = skipped = 0
    problem_cases = []

    for card in cards:
        raw_title = card["title"]
        current_authors = card["authors"]

        # Skip if authors already populated (manually fixed, e.g. ID 479)
        try:
            existing = json.loads(current_authors) if current_authors else []
        except Exception:
            existing = []

        authors, clean_title, card_type = split_author_title(raw_title)

        if not authors:
            problem_cases.append(card)
            skipped += 1
            continue

        if dry_run:
            print(f"ID {card['id']:4d} | {card_type:7s} | {', '.join(authors)}")
            print(f"         TITLE: {clean_title[:80]}")
            print()
            ok += 1
            continue

        # Build UPDATE
        authors_json = json.dumps(authors, ensure_ascii=False).replace("'", "''")
        clean_title_esc = clean_title.replace("'", "''")

        sql = (
            f"UPDATE library_cards SET "
            f"title = '{clean_title_esc}', "
            f"authors = '{authors_json}', "
            f"card_type = '{card_type}', "
            f"updated_at = datetime('now') "
            f"WHERE id = {card['id']}"
        )

        try:
            res = d1_query(token, sql)
            if res[0].get("success"):
                ok += 1
            else:
                errors += 1
                print(f"  ERROR id={card['id']}: {res[0].get('errors')}")
        except Exception as e:
            errors += 1
            print(f"  EXCEPTION id={card['id']}: {e}")

        time.sleep(0.05)

    print(f"\n{'DRY RUN ' if dry_run else ''}Results: {ok} updated, {errors} errors, {skipped} could not split")

    if problem_cases:
        print("\nCould not split (manual review needed):")
        for c in problem_cases:
            print(f"  ID {c['id']}: {c['title']}")


if __name__ == "__main__":
    main()
