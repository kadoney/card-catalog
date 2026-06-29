#!/usr/bin/env python3
"""
Add a quarterly Pins & Tales issue to the members' library — the STANDARD process.

This is a fixed procedure, not a discovery. Bob Lang emails the issue every quarter
as a .eml with: the final PDF, a WEB cover image, an email banner, and a text doc.
This script takes that .eml plus the explicit season + year (never inferred) and
deterministically produces the same R2 keys and the same library_cards row every
time, mirroring the existing pt-issue template (verified against pt-2026-spring).

Storage (verified):
  - R2 bucket `publications`, keys:
      pins-and-tales/<year>/<season>-<year>.pdf
      pins-and-tales/<year>/<season>-<year>-cover.jpg
  - catalog-api (publications.sapfm.org) serves /publications/<key> from that bucket.
  - One card-catalog `library_cards` row, card_type='pt-issue'.

Run from C:\\dev with the CF env sourced:

    source ~/.sapfm/cf-env.sh
    python card-catalog/scripts/ingest_pt_issue.py <issue.eml> --season Summer --year 2026
    #   ^ dry run: extracts attachments, prints the plan, writes the INSERT SQL — no writes.
    python card-catalog/scripts/ingest_pt_issue.py <issue.eml> --season Summer --year 2026 --execute
    #   ^ does the two R2 puts + the D1 insert, then verifies the public URLs + the row.

Idempotent: aborts if a card with the derived source_key already exists (unless --force).
"""
import argparse, email, json, os, ssl, subprocess, sys, urllib.request
from email import policy

SEASONS = ['spring', 'summer', 'fall', 'winter']
BUCKET = 'publications'
DB = 'card-catalog'
PUB_BASE = 'https://publications.sapfm.org'
HERE = os.path.dirname(os.path.abspath(__file__))


def derive(season: str, year: int) -> dict:
    s = season.strip().lower()
    if s not in SEASONS:
        sys.exit(f'season must be one of {SEASONS}, got {season!r}')
    Season = s.capitalize()
    slug = f'{s}-{year}'
    pdf_key = f'pins-and-tales/{year}/{slug}.pdf'
    cover_key = f'pins-and-tales/{year}/{slug}-cover.jpg'
    return {
        's': s, 'Season': Season, 'year': year, 'slug': slug,
        'source_key': f'pt-{year}-{s}',
        'title': f'Pins & Tales — {Season} {year}',
        'edition': f'{Season} {year}',
        'description': f'Pins & Tales, {Season} {year} issue of the SAPFM quarterly eMagazine.',
        'pdf_key': pdf_key, 'cover_key': cover_key,
        'view_url': f'/publications/{pdf_key}',
        'thumb_url': f'/publications/{cover_key}',
    }


def extract(eml_path: str, outdir: str, season: str, year: int, d: dict):
    """Pull the PDF (the lone application/pdf part) and the WEB cover (image whose
    filename contains 'web') out of the .eml, saved under canonical names."""
    msg = email.message_from_file(open(eml_path, encoding='utf-8', errors='replace'), policy=policy.default)
    pdf = cover = None
    for part in msg.walk():
        fn = part.get_filename()
        if not fn:
            continue
        ct = part.get_content_type()
        if ct == 'application/pdf' and pdf is None:
            pdf = (fn, part.get_payload(decode=True))
        elif ct.startswith('image/') and 'web' in fn.lower() and cover is None:
            cover = (fn, part.get_payload(decode=True))
    if not pdf:
        sys.exit('no application/pdf attachment found in the .eml')
    if not cover:
        sys.exit('no *WEB* cover image found in the .eml (expected a filename containing "web")')
    # Guard against a season/year typo: both filenames should mention the season.
    for label, (fn, _) in (('pdf', pdf), ('cover', cover)):
        if season.strip().lower()[:4] not in fn.lower().replace('_', '').replace(' ', ''):
            print(f'  ! WARNING: {label} "{fn}" does not mention "{season}" — verify --season/--year', file=sys.stderr)
    os.makedirs(outdir, exist_ok=True)
    pdf_path = os.path.join(outdir, f'{d["slug"]}.pdf')
    cover_path = os.path.join(outdir, f'{d["slug"]}-cover.jpg')
    open(pdf_path, 'wb').write(pdf[1])
    open(cover_path, 'wb').write(cover[1])
    return pdf_path, cover_path, pdf[0], cover[0]


def sql_lit(v) -> str:
    return "'" + str(v).replace("'", "''") + "'"


def build_insert_sql(d: dict) -> str:
    # Mirrors the pt-2026-spring row exactly. JSON list columns are literal '[]'.
    return (
        'INSERT INTO library_cards '
        '(title, authors, year, source, source_key, card_type, edition, description, '
        'period, form, region, topic, makers, reviews, is_free, is_featured, status, '
        'publisher, view_url, download_url, thumbnail_url, created_at, updated_at) VALUES ('
        f'{sql_lit(d["title"])}, \'["SAPFM"]\', {d["year"]}, \'SAPFM — Pins & Tales\', '
        f'{sql_lit(d["source_key"])}, \'pt-issue\', {sql_lit(d["edition"])}, {sql_lit(d["description"])}, '
        "'[]', '[]', '[]', '[]', '[]', '[]', 0, 0, 'approved', "
        "'Society of American Period Furniture Makers', "
        f'{sql_lit(d["view_url"])}, {sql_lit(d["view_url"])}, {sql_lit(d["thumb_url"])}, '
        'CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);\n'
    )


def need_cf_env():
    for k in ('CLOUDFLARE_API_TOKEN', 'CLOUDFLARE_ACCOUNT_ID'):
        if not os.environ.get(k):
            sys.exit(f'{k} not set — run `source ~/.sapfm/cf-env.sh` first (RUNBOOK §1).')


def wrangler(args: list) -> subprocess.CompletedProcess:
    # npx is npx.cmd on Windows — must go through the shell. list2cmdline handles
    # arg quoting; the only arg with spaces is a SELECT (no shell metacharacters),
    # and the INSERT (which contains '&') is passed via --file, never --command.
    cmd = subprocess.list2cmdline(['npx', 'wrangler', *args])
    # utf-8/replace so wrangler's emoji + box-drawing output doesn't blow up the
    # reader threads under Windows' default cp1252.
    return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                          encoding='utf-8', errors='replace')


def existing_card_id(source_key: str):
    r = wrangler(['d1', 'execute', DB, '--remote', '--json', '--command',
                  f"SELECT id FROM library_cards WHERE source_key='{source_key}'"])
    if r.returncode != 0:
        return None  # query failed (e.g. env not set in dry run) — caller decides
    try:
        rows = json.loads(r.stdout)[0]['results']
        return rows[0]['id'] if rows else None
    except Exception:
        return None


def http_status(url: str) -> int:
    # GET (not HEAD — some edges reject HEAD) with an unverified context (Windows
    # Python cert-store gaps, same posture as the boto3 verify=False fallback).
    # urlopen returns after headers, so the 10 MB PDF body is never downloaded.
    try:
        # A real UA — Cloudflare 403s the default Python-urllib agent.
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (sapfm-pt-ingest)'})
        with urllib.request.urlopen(req, timeout=25,
                                    context=ssl._create_unverified_context()) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def main():
    ap = argparse.ArgumentParser(description='Ingest a quarterly Pins & Tales issue.')
    ap.add_argument('eml', help='path to the issue .eml from Bob Lang')
    ap.add_argument('--season', required=True, help='Spring | Summer | Fall | Winter')
    ap.add_argument('--year', required=True, type=int)
    ap.add_argument('--execute', action='store_true', help='perform the R2 puts + D1 insert (default: dry run)')
    ap.add_argument('--force', action='store_true', help='proceed even if the source_key already exists')
    a = ap.parse_args()

    d = derive(a.season, a.year)
    outdir = os.path.join(HERE, '..', '..', '_scratch', 'pt-ingest', d['slug'])
    pdf_path, cover_path, pdf_fn, cover_fn = extract(a.eml, outdir, a.season, a.year, d)
    sql = build_insert_sql(d)
    sql_path = os.path.join(outdir, 'insert.sql')
    open(sql_path, 'w', encoding='utf-8', newline='').write(sql)

    print(f'\n=== Pins & Tales — {d["Season"]} {d["year"]} ===')
    print(f'  source_key : {d["source_key"]}')
    print(f'  PDF        : {pdf_fn}  ({os.path.getsize(pdf_path):,} bytes) -> r2 {BUCKET}/{d["pdf_key"]}')
    print(f'  cover      : {cover_fn}  ({os.path.getsize(cover_path):,} bytes) -> r2 {BUCKET}/{d["cover_key"]}')
    print(f'  card row   : library_cards (card_type=pt-issue, status=approved)')
    print(f'  SQL written: {sql_path}')

    dup = existing_card_id(d['source_key'])
    if dup and not a.force:
        sys.exit(f'\nABORT: a card with source_key={d["source_key"]} already exists (id={dup}). Use --force to override.')

    if not a.execute:
        print('\n(dry run — nothing uploaded or inserted. Re-run with --execute to publish.)')
        return

    need_cf_env()
    print('\n--- executing ---')
    for key, path, ctype in ((d['pdf_key'], pdf_path, 'application/pdf'),
                             (d['cover_key'], cover_path, 'image/jpeg')):
        r = wrangler(['r2', 'object', 'put', f'{BUCKET}/{key}', '--file', path,
                      '--content-type', ctype, '--remote'])
        if r.returncode != 0:
            sys.exit(f'R2 put failed for {key}:\n{r.stderr[:400]}')
        print(f'  uploaded {BUCKET}/{key}')
    r = wrangler(['d1', 'execute', DB, '--remote', '--file', sql_path])
    if r.returncode != 0:
        sys.exit(f'D1 insert failed:\n{r.stderr[:400]}')
    print('  inserted library_cards row')

    print('\n--- verify ---')
    cover_status = http_status(PUB_BASE + d['thumb_url'])
    pdf_status = http_status(PUB_BASE + d['view_url'])
    card_id = existing_card_id(d['source_key'])
    print(f'  cover URL  {PUB_BASE + d["thumb_url"]} -> HTTP {cover_status}')
    print(f'  pdf URL    {PUB_BASE + d["view_url"]} -> HTTP {pdf_status}')
    print(f'  card row   id={card_id}')
    ok = cover_status == 200 and pdf_status == 200 and card_id
    print('\n' + ('DONE — issue is live.' if ok else 'WARNING: verification incomplete, check above.'))


if __name__ == '__main__':
    main()
