#!/usr/bin/env python3
"""Shared article-citation machinery for the two SAPFM publications.

Pins & Tales (quarterly) and American Period Furniture (annual) both index at two
levels: one card for the ISSUE, and one card per ARTICLE parented to it. The issue
half differs (different R2 prefixes, different access rules); the article half is
identical, so it lives here and both ingest scripts call it.

Used by ingest_pt_issue.py and ingest_apf_issue.py. Also used by
build_pt_article_index.py for the 2008-2026 P&T backfill.

WHAT THIS DOES NOT DO: decide which articles an issue contains. That is a reading
job -- open the PDF, find the pieces, note title/author/page. The scripts here take
that list as JSON and handle everything mechanical around it. Nothing about a table
of contents is reliable enough to parse blind: bylines disagree with the TOC (seen
repeatedly in both publications, where the printed page is correct and the TOC is
not), continuations look like new articles, and house ads look like content.

WHY THE SQL IS PURE ASCII: `wrangler d1 execute --file` reads the file as CP1252 on
Windows and silently double-encodes any UTF-8 (RUNBOOK section 3). Titles carry
curly quotes and em-dashes constantly, so every non-ASCII character is emitted as a
SQLite char(N) splice instead. Verified by round-trip before the P&T batch load.
"""
import json, os, subprocess, sys

DB = 'card-catalog'
# 'SAPFM <em-dash> <name>' — matches the issue cards exactly; em-dash spliced.
SOURCE_PT = "'SAPFM '||char(8212)||' Pins & Tales'"
SOURCE_APF = "'SAPFM '||char(8212)||' American Period Furniture'"


def sqlq(s: str) -> str:
    """A pure-ASCII SQL string expression; non-ASCII spliced via char(N)."""
    parts, buf = [], ''
    for ch in str(s):
        if 32 <= ord(ch) < 127:
            buf += ch
        else:
            if buf:
                parts.append("'" + buf.replace("'", "''") + "'")
                buf = ''
            parts.append('char(%d)' % ord(ch))
    if buf:
        parts.append("'" + buf.replace("'", "''") + "'")
    return '||'.join(parts) if parts else "''"


def normalize(articles: list, *, default_byline: str = 'Staff') -> list:
    """Validate and clean a read-out article list. Returns rows; raises on junk.

    An unsigned piece is credited to `default_byline` rather than left blank:
    `authors` is NOT NULL DEFAULT '[]' in the schema, and a blank byline in a search
    result reads as a bug rather than as an editorial fact (Keith, 2026-09-01).
    """
    out, seen = [], set()
    for i, a in enumerate(articles, 1):
        title = (a.get('title') or '').strip()
        if not title:
            raise ValueError('article %d has no title' % i)
        key = title.lower()
        if key in seen:
            print('  ! skipping duplicate title: %s' % title, file=sys.stderr)
            continue
        seen.add(key)
        authors = [x.strip() for x in (a.get('authors') or []) if x and x.strip()]
        if not authors:
            authors = [default_byline]
        pdf_page = a.get('pdf_page')
        printed = a.get('printed_page')
        if pdf_page is not None and (not isinstance(pdf_page, int) or pdf_page < 1):
            raise ValueError('article %r has a bad pdf_page: %r' % (title, pdf_page))
        if printed is not None and (not isinstance(printed, int) or printed < 1):
            raise ValueError('article %r has a bad printed_page: %r' % (title, printed))
        out.append({'title': title, 'authors': authors,
                    'pdf_page': pdf_page, 'printed_page': printed})
    if not out:
        raise ValueError('no usable articles')
    return out


def build_sql(articles: list, *, parent_id: int, card_type: str, source_sql: str,
              year: int, edition: str, pdf_url: str, thumb_url: str,
              describe) -> str:
    """Emit the idempotent article-citation migration for ONE issue.

    The DELETE is scoped to this issue's parent_id, so re-running an issue replaces
    only its own articles and never touches another issue's.
    """
    rows = normalize(articles)
    lines = [
        '-- %d article citations for %s (parent card %d).' % (len(rows), edition, parent_id),
        '-- Citations only: title, byline, page. No article text is stored.',
        '-- Idempotent for THIS issue: the DELETE is scoped to its parent_id.',
        '',
        "DELETE FROM library_cards WHERE card_type = %s AND parent_id = %d;"
        % (sqlq(card_type), parent_id),
        '',
    ]
    for r in sorted(rows, key=lambda r: (r['printed_page'] or 10**6, r['title'])):
        anchor = pdf_url + ('#page=%d' % r['pdf_page'] if r['pdf_page'] else '')
        cols = {
            'title': sqlq(r['title']),
            'authors': sqlq(json.dumps(r['authors'], ensure_ascii=True)),
            'source': source_sql,
            'card_type': sqlq(card_type),
            'status': "'approved'",
            'is_free': '0',
            'year': str(year),
            'edition': sqlq(edition),
            'page_start': str(r['printed_page']) if r['printed_page'] else 'NULL',
            'parent_id': str(parent_id),
            'view_url': sqlq(anchor),
            'thumbnail_url': sqlq(thumb_url) if thumb_url else 'NULL',
            'description': sqlq(describe(r)),
        }
        lines.append('INSERT INTO library_cards (%s) VALUES (%s);'
                     % (', '.join(cols), ', '.join(cols.values())))
    sql = '\n'.join(lines) + '\n'
    non_ascii = [c for c in sql if ord(c) > 127]
    if non_ascii:
        raise AssertionError('non-ASCII leaked into SQL: %r' % non_ascii[:5])
    return sql


def wrangler(args: list) -> subprocess.CompletedProcess:
    """npx is npx.cmd on Windows, so this must go through the shell."""
    cmd = subprocess.list2cmdline(['npx', 'wrangler', *args])
    return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                          encoding='utf-8', errors='replace')


def load(sql_path: str) -> None:
    r = wrangler(['d1', 'execute', DB, '--remote', '--file', sql_path])
    if r.returncode != 0:
        sys.exit('article-citation load failed:\n%s' % r.stderr[:600])


def count_for(parent_id: int, card_type: str):
    r = wrangler(['d1', 'execute', DB, '--remote', '--json', '--command',
                  "SELECT COUNT(*) n FROM library_cards WHERE card_type='%s' AND parent_id=%d"
                  % (card_type, parent_id)])
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)[0]['results'][0]['n']
    except Exception:
        return None


def reembed() -> str:
    """Trigger the card re-embed so new citations enter semantic search.

    The secret goes in an Authorization: Bearer header -- NOT a ?key= query param,
    which returns 401 and reads like a bad secret.
    """
    import urllib.request
    path = os.path.expanduser('~/.sapfm/platform-trigger-secrets')
    if not os.path.exists(path):
        return 'SKIPPED — no ~/.sapfm/platform-trigger-secrets on this machine'
    secret = None
    for line in open(path, encoding='utf-8'):
        if line.startswith('EMBED_TRIGGER_SECRET'):
            secret = line.split('=', 1)[1].strip().strip('"\'')
    if not secret:
        return 'SKIPPED — EMBED_TRIGGER_SECRET not found in the secrets file'
    # ⚠ A User-Agent is REQUIRED: Cloudflare 403s urllib's default agent, and the
    # 403 reads exactly like a bad secret. Cost a wrong diagnosis on the APF 2024
    # load, and it is the same trap ingest_pt_issue.http_status() already carries.
    req = urllib.request.Request(
        'https://sapfm-embedder.sapfm-admin.workers.dev/embed/cards',
        method='POST', headers={'Authorization': 'Bearer ' + secret,
                                'User-Agent': 'sapfm-article-index'})
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            d = json.load(resp)
        s = (d.get('sources') or [{}])[0]
        return 'embedded %s cards (purged %s restricted)' % (s.get('embedded'), s.get('purged'))
    except Exception as e:
        return 'FAILED — %s (re-run by hand: POST /embed/cards)' % e
