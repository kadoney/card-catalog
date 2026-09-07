"""
youtube_channel — read a public YouTube channel's listing, to decide what is
worth cataloging by hand.

WHY THIS EXISTS
    Museum and publisher channels hold research material our members would want
    and cannot find: the Met's Allan Breed / Duncan Phyfe bedpost film is from
    2012, so no feed will ever surface it. Cataloging it as a `library_cards`
    row makes it findable in 2026. This module answers the prior question --
    WHICH videos are worth the cataloging pass.

WHAT IT READS, AND WHAT IT DOES NOT
    Public listing and watch-page metadata only: id, title, description, upload
    date, duration, and the embeddable flag. ⚠ It never fetches video, audio or
    captions. We embed and link; we do not host, and we do not harvest
    transcripts. That line is what keeps this categorically different from the
    scraped-catalog problem that has 379 museum cards hidden pending outreach.

⚠ NO API KEY, BY CIRCUMSTANCE NOT PREFERENCE
    We hold no YouTube Data API key. This reads the site's own InnerTube
    endpoints instead, which is what the page does. That makes it BRITTLE: the
    channel grid moved from `videoRenderer` to `lockupViewModel` at some point
    before 2026-09, and `walk()` handles both for exactly that reason. If a scan
    suddenly returns 0, suspect a renderer change first. Now that SAPFM is in
    Google for Nonprofits, a Data API key is the durable replacement.

⚠ SEARCH HIT COUNTS ARE MEANINGLESS. `search()` returns a page, and YouTube's
    channel search is fuzzy -- nearly every term comes back with a full ~30. The
    counts measure page size, not relevance. Only reading the titles tells you
    anything. Same lesson as the P&T keyword pass, which "recovered" 243
    articles that were mostly news items placed by passing vocabulary.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')


def get(url: str, data: bytes | None = None) -> str:
    req = urllib.request.Request(url, data=data, headers={
        'User-Agent': UA,
        'Accept-Language': 'en-US,en',
        'Content-Type': 'application/json',
    })
    return urllib.request.urlopen(req, timeout=60).read().decode('utf-8', 'replace')


def _initial_data(html: str) -> dict | None:
    m = re.search(r'var ytInitialData = (\{.*?\});</script>', html, re.S)
    return json.loads(m.group(1)) if m else None


def walk(node, seen: set, out: list) -> None:
    """Collect {id, title, published} from renderer shapes new and old."""
    if isinstance(node, dict):
        # Current shape (2026): lockupViewModel
        if 'contentId' in node and 'metadata' in node:
            vid = node.get('contentId')
            lm = (node.get('metadata') or {}).get('lockupMetadataViewModel') or {}
            title = (lm.get('title') or {}).get('content')
            published = None
            rows = (((lm.get('metadata') or {}).get('contentMetadataViewModel') or {})
                    .get('metadataRows') or [])
            for r in rows:
                for part in r.get('metadataParts', []):
                    txt = (part.get('text') or {}).get('content') or ''
                    if 'ago' in txt:
                        published = txt
            if vid and title and vid not in seen:
                seen.add(vid)
                out.append({'id': vid, 'title': title, 'published': published})
        # Legacy shape: videoRenderer
        vid = node.get('videoId')
        if vid and isinstance(node.get('title'), dict):
            t = node['title']
            title = t.get('simpleText') or ''.join(
                r.get('text', '') for r in t.get('runs', []))
            if title and vid not in seen:
                seen.add(vid)
                out.append({
                    'id': vid, 'title': title,
                    'published': (node.get('publishedTimeText') or {}).get('simpleText'),
                })
        for v in node.values():
            walk(v, seen, out)
    elif isinstance(node, list):
        for v in node:
            walk(v, seen, out)


def search(handle: str, query: str) -> list:
    """Search one channel's back catalog. Returns a PAGE -- see the ⚠ above."""
    html = get(f'https://www.youtube.com/{handle}/search'
               f'?query={urllib.parse.quote(query)}')
    data = _initial_data(html)
    if not data:
        return []
    seen, out = set(), []
    walk(data, seen, out)
    return out


def sweep(handle: str, terms: list) -> list:
    """Run several searches and union them, recording which terms found what."""
    found: dict = {}
    for t in terms:
        hits = search(handle, t)
        for h in hits:
            found.setdefault(h['id'], {**h, 'terms': set()})['terms'].add(t)
        print(f'  {t:<26} {len(hits):>3} on the page', file=sys.stderr)
        time.sleep(0.4)
    for v in found.values():
        v['terms'] = sorted(v['terms'])
    return list(found.values())


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit('usage: youtube_channel.py @handle "term,term,term" > candidates.json')
    videos = sweep(sys.argv[1], [t.strip() for t in sys.argv[2].split(',')])
    print(f'{len(videos)} distinct videos', file=sys.stderr)
    json.dump(sorted(videos, key=lambda v: v['title']), sys.stdout,
              ensure_ascii=False, indent=1)
