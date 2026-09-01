"""Merge P&T segmentation batches -> review CSV + ASCII-safe D1 migration.

Second half of the P&T article-index pipeline; pt_fetch_extract.py is the first
(pulls the 71 issue PDFs from R2 and writes page-marked text). Between them sits
the segmentation step, which reads those text files and emits one JSON per batch
into <work>/seg/ -- that part is a reading job, not a mechanical one.

Inputs  (in --work, default: cwd):  issues.json, parent_thumbs.json, seg/*.json
Outputs: --csv  review file for a human pass   (default <work>/pt-article-index.csv)
         --sql  the migration                  (default <repo>/sql/06_pt_article_index.sql)

Paths are arguments, not constants: this runs from OFFICE or SHOP, whose home
directories differ.
"""
import argparse, csv, glob, json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument('--work', default=os.getcwd(), help='dir holding issues.json, parent_thumbs.json, seg/')
ap.add_argument('--csv', default=None)
ap.add_argument('--sql', default=os.path.join(REPO, 'sql', '06_pt_article_index.sql'))
args = ap.parse_args()
BASE = args.work
issues = {i['source_key']: i for i in json.load(open(os.path.join(BASE, 'issues.json'), encoding='utf-8'))}
thumbs = {int(k): v for k, v in json.load(open(os.path.join(BASE, 'parent_thumbs.json'))).items()}

seen_issues, all_rows, warnings = {}, [], []
for path in sorted(glob.glob(os.path.join(BASE, 'seg', '*.json'))):
    batch = os.path.basename(path)[:-5]
    data = json.load(open(path, encoding='utf-8'))
    for iss in data['issues']:
        key = iss['source_key']
        if key not in issues:
            warnings.append(f"{batch}: unknown source_key {key}"); continue
        if key in seen_issues:
            warnings.append(f"{batch}: DUPLICATE issue {key} (also in {seen_issues[key]})"); continue
        seen_issues[key] = batch
        meta = issues[key]
        if iss.get('card_id') != meta['id']:
            warnings.append(f"{key}: card_id mismatch {iss.get('card_id')} != {meta['id']}")
        arts = iss.get('articles', [])
        if len(arts) < 2:
            warnings.append(f"{key}: only {len(arts)} articles — likely under-read")
        titles = set()
        for a in arts:
            t = (a.get('title') or '').strip()
            if not t:
                warnings.append(f"{key}: empty title skipped"); continue
            tl = t.lower()
            if tl in titles:
                warnings.append(f"{key}: duplicate title '{t}'"); continue
            titles.add(tl)
            pp = a.get('printed_page')
            dp = a.get('pdf_page')
            if not isinstance(dp, int) or dp < 1:
                warnings.append(f"{key}: '{t}' bad pdf_page {dp!r}"); dp = None
            if pp is not None and (not isinstance(pp, int) or pp < 1 or pp > 200):
                warnings.append(f"{key}: '{t}' odd printed_page {pp!r}"); pp = None
            # Attribution is settled HERE, once, so the review CSV and the SQL can
            # never disagree about who wrote a piece. An unsigned article is credited
            # to "Staff" (Keith, 2026-09-01) rather than left blank; the Board's own
            # column is credited to the Board, which is who actually wrote it.
            authors = [x.strip() for x in a.get('authors') or [] if x and x.strip()]
            if not authors:
                authors = ['SAPFM Board'] if t.strip().lower() == 'board update' else ['Staff']
            all_rows.append({
                'source_key': key, 'card_id': meta['id'], 'edition': meta['edition'],
                'year': meta['year'], 'masthead': (iss.get('masthead') or '').strip(),
                'title': t,
                'authors': authors,
                'printed_page': pp, 'pdf_page': dp,
                'kind': a.get('kind') or 'news', 'flag': a.get('flag') or '',
                'pdf_url': meta['download_url'],
            })

missing = sorted(set(issues) - set(seen_issues))
if missing:
    warnings.append(f"MISSING ISSUES ({len(missing)}): {', '.join(missing)}")

# ---- review CSV ----
csv_path = args.csv or os.path.join(BASE, 'pt-article-index.csv')
with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['edition', 'masthead', 'title', 'authors', 'printed_page', 'pdf_page', 'kind', 'flag'])
    for r in sorted(all_rows, key=lambda r: (r['year'], r['card_id'], r['printed_page'] or 999)):
        w.writerow([r['edition'], r['masthead'], r['title'], '; '.join(r['authors']),
                    r['printed_page'] or '', r['pdf_page'] or '', r['kind'], r['flag']])

# ---- ASCII-safe SQL ----
def sqlq(s):
    """SQL string expression: pure-ASCII literal, non-ASCII spliced via char(N)."""
    parts, buf = [], ''
    for ch in s:
        if 32 <= ord(ch) < 127:
            buf += ch
        else:
            if buf: parts.append("'" + buf.replace("'", "''") + "'"); buf = ''
            parts.append(f"char({ord(ch)})")
    if buf: parts.append("'" + buf.replace("'", "''") + "'")
    return '||'.join(parts) if parts else "''"

SRC = "'SAPFM '||char(8212)||' Pins & Tales'"

def describe(r):
    page = f", page {r['printed_page']}" if r['printed_page'] else ''
    if 'pins' in r['masthead'].lower():
        return f"Article in Pins & Tales, the SAPFM quarterly, {r['edition']} issue{page}."
    return f"Article in Period Furniture (later renamed Pins & Tales), the SAPFM quarterly newsletter, {r['edition']} issue{page}."

lines = [
    "-- 06_pt_article_index.sql",
    f"-- {len(all_rows)} article-level citations for Pins & Tales / Period Furniture,",
    "-- the SAPFM quarterly newsletter, 2008-2026. Derived 2026-08-31 by reading the",
    "-- 71 issue PDFs in R2 publications/pins-and-tales/ (no upstream index survives",
    "-- anywhere; the Joomla dump had sap_apf_master_index for APF but nothing for",
    "-- P&T). Citations only -- no article text stored. card_type 'pt-article' is",
    "-- distinct so a future access decision addresses P&T articles in one clause,",
    "-- mirroring 05_apf_master_index.sql. view_url deep-links the issue PDF via",
    "-- #page=N (PDF page, which differs from the printed page in the 2008-2012",
    "-- print-era files -- several are in imposition order). thumbnail inherited",
    "-- from the parent issue's cover. Re-runnable: the DELETE makes it idempotent.",
    "",
    "DELETE FROM library_cards WHERE card_type = 'pt-article';",
    "",
]
for r in sorted(all_rows, key=lambda r: (r['year'], r['card_id'], r['printed_page'] or 999)):
    # authors is NOT NULL DEFAULT '[]' — never SQL NULL (the APF migration never
    # hit this: every APF row had a byline). Attribution was settled at row-build.
    authors_json = json.dumps(r['authors'], ensure_ascii=True)
    cols = {
        'title': sqlq(r['title']),
        'authors': sqlq(authors_json),
        'source': SRC,
        'card_type': "'pt-article'", 'status': "'approved'", 'is_free': '0',
        'year': str(r['year']),
        'edition': sqlq(r['edition']),
        'page_start': str(r['printed_page']) if r['printed_page'] else 'NULL',
        'parent_id': str(r['card_id']),
        'view_url': sqlq(r['pdf_url'] + (f"#page={r['pdf_page']}" if r['pdf_page'] else '')),
        'thumbnail_url': sqlq(thumbs.get(r['card_id'], '')) if thumbs.get(r['card_id']) else 'NULL',
        'description': sqlq(describe(r)),
    }
    lines.append(f"INSERT INTO library_cards ({', '.join(cols)}) VALUES ({', '.join(cols.values())});")

sql_path = args.sql
out = '\n'.join(lines) + '\n'
assert all(ord(c) < 128 for c in out), 'non-ASCII leaked into SQL'
open(sql_path, 'w', encoding='ascii', newline='\n').write(out)

print(f"rows: {len(all_rows)}  issues: {len(seen_issues)}/{len(issues)}")
print(f"csv:  {csv_path}")
print(f"sql:  {sql_path} ({len(out):,} bytes)")
kinds = {}
for r in all_rows: kinds[r['kind']] = kinds.get(r['kind'], 0) + 1
print('kinds:', kinds)
mast = {}
for r in all_rows: mast[r['masthead']] = mast.get(r['masthead'], 0) + 1
print('mastheads:', mast)
noprint = sum(1 for r in all_rows if not r['printed_page'])
print(f"no printed_page: {noprint}; flagged: {sum(1 for r in all_rows if r['flag'])}")
print(f"\n{len(warnings)} warnings:")
for w in warnings: print(' !', w)
