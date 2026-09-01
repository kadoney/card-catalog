#!/usr/bin/env python3
"""
Add an American Period Furniture annual volume to the library — the STANDARD process.

APF is the Society's annual journal. Like Pins & Tales it indexes at two levels: one
`apf-issue` card for the volume, and one `apf-article` citation per article, parented
to it. This script does both halves plus the R2 uploads, mirroring ingest_pt_issue.py.

⚠ THE TWO HALVES HAVE OPPOSITE ACCESS RULES, AND THAT IS DELIBERATE:
  - the ISSUE is a separate paid product. `card_type='apf-issue'` is named in the
    embedder's RESTRICTED_CARD_SQL, so the volume is purged from the search index on
    every embed run. Membership does NOT include APF.
  - the ARTICLE CITATIONS are freely published promotion (the table of contents is
    a teaser — Keith, 2026-08-31), so they ARE embedded and searchable. They carry
    title, byline and page only; no article text is ever stored.
  Do not "fix" the apparent inconsistency by aligning them.

This replaces a manual process Keith maintained for years — the `sap_apf_master_index`
table in the retired Joomla site, which is where the 2001–2023 citations were
recovered from (card-catalog/sql/05_apf_master_index.sql, the only surviving copy).

Storage (matches the 24 existing volumes exactly):
  R2 bucket `publications`:  apf/<year>/apf-<year>.pdf
                             apf/<year>/apf-<year>-cover.jpg

Run from C:\\dev with the CF env sourced (RUNBOOK §1):

  source ~/.sapfm/cf-env.sh

  # 1. dump the front matter so the contents can be read out of it
  python card-catalog/scripts/ingest_apf_issue.py --year 2027 --pdf vol.pdf --toc-pages 1-6

  # 2. write the articles JSON (see --toc-pages output for the template), then dry-run
  python card-catalog/scripts/ingest_apf_issue.py --year 2027 --pdf vol.pdf \\
      --cover cover.jpg --articles apf-2027-articles.json

  # 3. publish
  python card-catalog/scripts/ingest_apf_issue.py --year 2027 --pdf vol.pdf \\
      --cover cover.jpg --articles apf-2027-articles.json --execute

`--articles` may be supplied on its own (no --pdf/--cover) to add or correct the
citations for a volume whose PDF is already uploaded — which is how the missing 2024
index gets filled without touching the volume itself.
"""
import argparse, json, os, ssl, sys, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import article_index as ai

BUCKET = 'publications'
PUB_BASE = 'https://publications.sapfm.org'
HERE = os.path.dirname(os.path.abspath(__file__))


def derive(year: int) -> dict:
    slug = 'apf-%d' % year
    pdf_key = 'apf/%d/%s.pdf' % (year, slug)
    cover_key = 'apf/%d/%s-cover.jpg' % (year, slug)
    return {
        'year': year, 'slug': slug, 'source_key': slug,
        'title': 'American Period Furniture \u2014 %d' % year,
        'edition': str(year),
        'description': 'American Period Furniture, the %d annual journal of the '
                       'Society of American Period Furniture Makers.' % year,
        'pdf_key': pdf_key, 'cover_key': cover_key,
        'view_url': '/publications/%s' % pdf_key,
        'thumb_url': '/publications/%s' % cover_key,
    }


def build_issue_sql(d: dict) -> str:
    """The volume card. Mirrors the existing apf-issue rows (verified against 2024)."""
    q = ai.sqlq
    cols = {
        'title': q(d['title']), 'authors': "'[\"SAPFM\"]'", 'year': str(d['year']),
        'source': ai.SOURCE_APF, 'source_key': q(d['source_key']),
        'card_type': "'apf-issue'", 'edition': q(d['edition']),
        'description': q(d['description']),
        'period': "'[]'", 'form': "'[]'", 'region': "'[]'", 'topic': "'[]'",
        'makers': "'[]'", 'reviews': "'[]'",
        'is_free': '0', 'is_featured': '0', 'status': "'approved'",
        'publisher': "'Society of American Period Furniture Makers'",
        'view_url': q(d['view_url']), 'download_url': q(d['view_url']),
        'thumbnail_url': q(d['thumb_url']),
        'created_at': 'CURRENT_TIMESTAMP', 'updated_at': 'CURRENT_TIMESTAMP',
    }
    return 'INSERT INTO library_cards (%s) VALUES (%s);\n' % (
        ', '.join(cols), ', '.join(cols.values()))


def describe(edition: str):
    def f(r):
        page = ', page %d' % r['printed_page'] if r['printed_page'] else ''
        return ('Article in American Period Furniture, the SAPFM annual journal, '
                '%s volume%s.' % (edition, page))
    return f


def card_id_for(source_key: str):
    r = ai.wrangler(['d1', 'execute', ai.DB, '--remote', '--json', '--command',
                     "SELECT id FROM library_cards WHERE source_key='%s'" % source_key])
    if r.returncode != 0:
        return None
    try:
        rows = json.loads(r.stdout)[0]['results']
        return rows[0]['id'] if rows else None
    except Exception:
        return None


def dump_toc(pdf_path: str, spec: str, out_path: str):
    """Write page-marked text for the given pages so the contents can be read out.

    Deliberately not a parser. An APF table of contents is a reading job: bylines in
    the TOC disagree with the printed page often enough that the page wins, and the
    TOC omits pieces that carry their own titles inside.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        sys.exit('pypdf not installed: python -m pip install pypdf\n'
                 '(on OFFICE use `python -m pip`, not pip.exe — RUNBOOK §10a item 6)')
    lo, _, hi = spec.partition('-')
    lo, hi = int(lo), int(hi or lo)
    r = PdfReader(pdf_path)
    out = ['# %s pages %d-%d — read the contents out of this into the JSON below.'
           % (os.path.basename(pdf_path), lo, min(hi, len(r.pages)))]
    for n in range(lo, min(hi, len(r.pages)) + 1):
        out.append('\n=== PDF PAGE %d ===' % n)
        out.append((r.pages[n - 1].extract_text() or '').strip())
    open(out_path, 'w', encoding='utf-8').write('\n'.join(out))
    print('wrote %s (%d pages of text)' % (out_path, min(hi, len(r.pages)) - lo + 1))
    print('\nArticles JSON template — one object per article:')
    print(json.dumps([{'title': 'Exact title as printed', 'authors': ['First Last'],
                       'printed_page': 6, 'pdf_page': 8}], indent=1))
    print('\n  printed_page = the number printed on the page (what a citation cites)')
    print('  pdf_page     = position in the PDF (what #page= links to); often differs')
    print('  authors      = [] for an unsigned piece; it becomes "Staff"')


def http_status(url: str) -> int:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (sapfm-apf-ingest)'})
        with urllib.request.urlopen(req, timeout=25,
                                    context=ssl._create_unverified_context()) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def main():
    ap = argparse.ArgumentParser(description='Ingest an American Period Furniture volume.')
    ap.add_argument('--year', required=True, type=int)
    ap.add_argument('--pdf', help='the volume PDF')
    ap.add_argument('--cover', help='the cover JPEG')
    ap.add_argument('--articles', help='JSON list of articles (see --toc-pages)')
    ap.add_argument('--toc-pages', help='e.g. 1-6: dump those pages as text and exit')
    ap.add_argument('--execute', action='store_true', help='perform the writes (default: dry run)')
    ap.add_argument('--force', action='store_true', help='proceed even if the volume already exists')
    a = ap.parse_args()

    d = derive(a.year)
    outdir = os.path.join(HERE, '..', '..', '_scratch', 'apf-ingest', d['slug'])
    os.makedirs(outdir, exist_ok=True)

    if a.toc_pages:
        if not a.pdf:
            sys.exit('--toc-pages needs --pdf')
        dump_toc(a.pdf, a.toc_pages, os.path.join(outdir, 'toc.txt'))
        return

    if not a.pdf and not a.articles:
        sys.exit('nothing to do: pass --pdf (with --cover) to publish a volume, '
                 'and/or --articles to write its citations')
    if a.pdf and not a.cover:
        sys.exit('--pdf needs --cover (every existing volume has one)')

    existing = card_id_for(d['source_key'])
    print('\n=== American Period Furniture %d ===' % a.year)
    print('  source_key : %s' % d['source_key'])
    print('  volume card: %s' % ('EXISTS id=%s' % existing if existing else 'will be created'))

    if a.pdf:
        if existing and not a.force:
            sys.exit('\nABORT: %s already exists (id=%s). Use --force to re-add the '
                     'volume card, or drop --pdf/--cover to only update citations.'
                     % (d['source_key'], existing))
        print('  PDF        : %s (%s bytes) -> r2 %s/%s'
              % (os.path.basename(a.pdf), format(os.path.getsize(a.pdf), ','), BUCKET, d['pdf_key']))
        print('  cover      : %s -> r2 %s/%s' % (os.path.basename(a.cover), BUCKET, d['cover_key']))
        open(os.path.join(outdir, 'insert-issue.sql'), 'w', encoding='ascii').write(build_issue_sql(d))

    arts = None
    if a.articles:
        arts = ai.normalize(json.load(open(a.articles, encoding='utf-8')))
        print('  citations  : %d articles' % len(arts))
        unsigned = sum(1 for r in arts if r['authors'] == ['Staff'])
        if unsigned:
            print('               (%d unsigned -> credited "Staff")' % unsigned)
        nopage = sum(1 for r in arts if not r['printed_page'])
        if nopage:
            print('               ! %d have no printed_page — citations without a page' % nopage)

    if not a.execute:
        print('\n(dry run — nothing uploaded or inserted. Re-run with --execute.)')
        return

    for k in ('CLOUDFLARE_API_TOKEN', 'CLOUDFLARE_ACCOUNT_ID'):
        if not os.environ.get(k):
            sys.exit('%s not set — run `source ~/.sapfm/cf-env.sh` first (RUNBOOK §1).' % k)

    print('\n--- executing ---')
    if a.pdf:
        for key, path, ctype in ((d['pdf_key'], a.pdf, 'application/pdf'),
                                 (d['cover_key'], a.cover, 'image/jpeg')):
            # --remote is mandatory: without it wrangler writes to a local .wrangler
            # dir, prints "Upload complete", and the object never reaches R2 (§4).
            r = ai.wrangler(['r2', 'object', 'put', '%s/%s' % (BUCKET, key),
                             '--file', path, '--content-type', ctype, '--remote'])
            if r.returncode != 0:
                sys.exit('R2 put failed for %s:\n%s' % (key, r.stderr[:400]))
            print('  uploaded %s/%s' % (BUCKET, key))
        ai.load(os.path.join(outdir, 'insert-issue.sql'))
        print('  inserted volume card')

    parent_id = card_id_for(d['source_key'])
    if arts:
        if not parent_id:
            sys.exit('no volume card for %s — upload the volume first' % d['source_key'])
        sql_path = os.path.join(outdir, 'insert-articles.sql')
        open(sql_path, 'w', encoding='ascii').write(ai.build_sql(
            arts, parent_id=parent_id, card_type='apf-article', source_sql=ai.SOURCE_APF,
            year=a.year, edition=d['edition'], pdf_url=d['view_url'],
            thumb_url=d['thumb_url'], describe=describe(d['edition'])))
        ai.load(sql_path)
        print('  inserted %d article citations' % len(arts))

    print('\n--- verify ---')
    if a.pdf:
        print('  cover URL  -> HTTP %d' % http_status(PUB_BASE + d['thumb_url']))
        print('  pdf URL    -> HTTP %d' % http_status(PUB_BASE + d['view_url']))
    print('  volume card id=%s' % parent_id)
    if arts:
        n = ai.count_for(parent_id, 'apf-article')
        print('  citations in D1: %s (expected %d)' % (n, len(arts)))
        print('  re-embed: %s' % ai.reembed())
        print('  (the volume itself is purged from the index by design — it is the paid product)')


if __name__ == '__main__':
    main()
