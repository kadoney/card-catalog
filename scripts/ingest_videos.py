"""
ingest_videos — catalog museum/publisher videos as `library_cards` rows.

WHY A CARD AND NOT A FEED ITEM
    The Met's Allan Breed / Duncan Phyfe bedpost film was uploaded in 2012. A
    feed carries recent uploads, so it will never surface -- and a member asking
    "what do we have on Phyfe?" is not asking what is new. Cataloging makes 2012
    findable in 2026, next to the objects and the P&T and APF articles.

WHY NOT THE `video` TABLE
    ⚠ `sapfm.video` is OUR archive: 36 films in Cloudflare Stream, member-gated,
    with 522 chapters of transcript. A Met film is neither ours nor gated. Filing
    it there would imply we host it and would inherit the visibility rules. The
    card catalog is already the place for material we do not own -- it holds
    museum objects, books and journal citations on exactly that basis.

WHAT WE STORE, AND THE LINE WE DO NOT CROSS
    Title, description, upload date, duration, thumbnail URL, watch URL -- public
    metadata -- plus OUR tagging and teaser. ⚠ We embed and we link. We never
    download, re-host or re-upload, and we never take captions or transcripts.
    Embedding a public video is the sanctioned use of it and sends the view to
    the owner, which is what makes this categorically different from the scraped
    catalog text that has 379 museum cards hidden pending outreach.

TWO THINGS THAT WILL BITE
    ⚠ EMBEDDABILITY IS THE OWNER'S TO REVOKE. `playableInEmbed` is checked at
    ingest and stored, but the Met can turn it off tomorrow and nothing will
    tell us. That is why `view_url` always holds the watch URL: if the player
    breaks, the card still works as a link. Never build a card whose only route
    to the video is the embed.

    ⚠ DESCRIPTIONS ARRIVE JSON-ESCAPED, NOT UNICODE-ESCAPED. `shortDescription`
    is a JSON string literal; decoding it with `unicode_escape` turns
    "Charles-Honoré" into "Charles-HonorÃ©" -- the same CP1252 double-decode the
    runbook warns about for D1 writes. Decode it with json.loads.

Usage:
    source ~/.sapfm/cf-env.sh
    python scripts/ingest_videos.py data/met-video-selection.json --dry
    python scripts/ingest_videos.py data/met-video-selection.json --apply
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request

# ⚠ Windows consoles default to cp1252 and raise UnicodeEncodeError on any
# non-Latin-1 character. This script prints '·' and '⚠' in its progress lines
# and once crashed on a '✅' AFTER every row had been written -- a run that
# looked failed and had entirely succeeded, which is the worst way to end.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DB = 'card-catalog'
CARD_TYPE = 'external-video'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')


# ---------------------------------------------------------------- metadata ---

def fetch_metadata(video_id: str) -> dict:
    """Public watch-page metadata. No media, no captions."""
    req = urllib.request.Request(
        f'https://www.youtube.com/watch?v={video_id}',
        headers={'User-Agent': UA, 'Accept-Language': 'en-US,en'})
    html = urllib.request.urlopen(req, timeout=60).read().decode('utf-8', 'replace')

    def grab(pattern, cast=str):
        m = re.search(pattern, html)
        return cast(m.group(1)) if m else None

    # ⚠ json.loads, NOT unicode_escape -- see the module docstring.
    description = None
    m = re.search(r'"shortDescription":(".*?"),"isCrawlable"', html, re.S)
    if m:
        try:
            description = json.loads(m.group(1))
        except json.JSONDecodeError:
            description = None
    title = None
    m = re.search(r'"title":(".*?"),"lengthSeconds"', html, re.S)
    if m:
        try:
            title = json.loads(m.group(1))
        except json.JSONDecodeError:
            title = None

    return {
        'id': video_id,
        'title': title,
        'description': description,
        'upload_date': grab(r'"uploadDate":"([^"]+)"'),
        'duration_s': grab(r'"lengthSeconds":"(\d+)"', int),
        'embeddable': grab(r'"playableInEmbed":(true|false)') == 'true',
        'watch_url': f'https://www.youtube.com/watch?v={video_id}',
        'thumb_url': f'https://i.ytimg.com/vi/{video_id}/hqdefault.jpg',
    }


# --------------------------------------------------------------------- SQL ---

def build_row(meta: dict, sel: dict, source: str) -> tuple:
    """One row as (sql, params) for the D1 REST API.

    ⚠ PARAMETER-BOUND, AND NOT VIA `wrangler d1 execute --file`, WHICH THIS
    TABLE'S OTHER INGESTS USE. Those write pure-ASCII SQL because wrangler reads
    a --file as CP1252 on Windows and double-encodes any UTF-8 (RUNBOOK §3) --
    "Charles-Honoré" would land as "Charles-HonorÃ©". The documented workarounds
    are numeric HTML entities (wrong here: `title` is plain text, so &#233;
    would render literally) or SQLite char() concatenation (correct but
    unreadable). The REST API sidesteps the whole class: JSON over HTTPS is
    UTF-8 end to end, and bound parameters remove the quoting question with it.
    """
    year = int(meta['upload_date'][:4]) if meta.get('upload_date') else None
    # Duration rides `edition` -- free-text provenance on this table -- so a
    # member sees "7 min" before committing to a click.
    mins = round((meta['duration_s'] or 0) / 60)
    sql = (
        'INSERT INTO library_cards '
        '(title, authors, year, source, source_key, card_type, edition, description, '
        'teaser, period, form, region, topic, makers, reviews, is_free, is_featured, '
        'status, publisher, view_url, download_url, thumbnail_url, created_at, updated_at) '
        'VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,?15,?16,?17,?18,?19,?20,?21,?22,'
        'CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)'
    )
    params = [
        meta['title'], '[]', year, source, 'youtube:' + meta['id'], CARD_TYPE,
        f'{mins} min' if mins else None,
        meta['description'], sel.get('teaser'),
        json.dumps(sel.get('period') or []), json.dumps(sel.get('form') or []),
        json.dumps(sel.get('region') or []), json.dumps(sel.get('topic') or []),
        json.dumps(sel.get('makers') or []), '[]',
        1,   # is_free: a public video anyone can watch, NOT a paid product
        0,
        'approved', source,
        meta['watch_url'],
        # ⚠ download_url stays NULL. There is nothing to download, and a value
        # here would invite somebody building one.
        None,
        meta['thumb_url'],
    ]
    return sql, params


# ------------------------------------------------------------------ D1 API ---

ACCOUNT = 'ebe622eaa5b3a3581cf5664272f26f30'
DB_UUID = 'eb944e67-5fcc-4587-8fe1-eae2a9fe3476'   # card-catalog (RUNBOOK §3)


def need_cf_env():
    if not os.environ.get('CLOUDFLARE_API_TOKEN'):
        sys.exit('CLOUDFLARE_API_TOKEN not set — run `source ~/.sapfm/cf-env.sh` (RUNBOOK §1).')


def d1(sql: str, params: list | None = None) -> dict:
    body = json.dumps({'sql': sql, 'params': params or []}).encode('utf-8')
    req = urllib.request.Request(
        f'https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/d1/database/{DB_UUID}/query',
        data=body,
        headers={'Authorization': f'Bearer {os.environ["CLOUDFLARE_API_TOKEN"]}',
                 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode('utf-8'))


def existing_keys() -> set:
    res = d1("SELECT source_key FROM library_cards WHERE card_type = ?1", [CARD_TYPE])
    if not res.get('success'):
        sys.exit(f'D1 read failed: {res.get("errors")}')
    return {row['source_key'] for row in res['result'][0]['results']}


# -------------------------------------------------------------------- main ---

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('selection', help='curation JSON (data/*-video-selection.json)')
    ap.add_argument('--apply', action='store_true', help='write to D1 (default: dry run)')
    args = ap.parse_args()

    sel = json.load(open(args.selection, encoding='utf-8'))
    source = sel['source']
    videos = sel['videos']
    need_cf_env()

    have = existing_keys()
    print(f'{len(videos)} selected · {len(have)} {CARD_TYPE} cards already on file\n')

    pending, skipped, unembeddable = [], [], []
    for v in videos:
        if 'youtube:' + v['id'] in have:
            skipped.append(v['id'])
            continue
        meta = fetch_metadata(v['id'])
        if not meta['title']:
            # Loud, not silent: a watch page that stops yielding a title means
            # the extraction broke, and a quietly-skipped video looks identical
            # to one we chose not to catalog.
            print(f'  ⚠ {v["id"]}: no title returned — SKIPPED (watch page changed?)')
            continue
        if not meta['embeddable']:
            # Recorded rather than dropped: the card is still worth having as a
            # link, but somebody should know the player will not work.
            unembeddable.append(f'{v["id"]} {meta["title"][:60]}')
        pending.append((meta, v))
        print(f'  + {meta["upload_date"][:10]}  '
              f'{round((meta["duration_s"] or 0)/60):>3} min  {meta["title"][:66]}')
        time.sleep(0.4)

    print(f'\n{len(pending)} to insert · {len(skipped)} already present')
    if unembeddable:
        print(f'⚠ {len(unembeddable)} NOT embeddable — they will render as links only:')
        for u in unembeddable:
            print(f'    {u}')
    if not pending:
        print('nothing to do')
        return

    if not args.apply:
        print('\nDRY RUN — re-run with --apply to write')
        return

    written = 0
    for meta, v in pending:
        sql, params = build_row(meta, v, source)
        res = d1(sql, params)
        if not res.get('success'):
            sys.exit(f'insert FAILED on {meta["id"]}: {res.get("errors")}')
        written += 1
    print(f'✅ inserted {written}')


if __name__ == '__main__':
    main()
