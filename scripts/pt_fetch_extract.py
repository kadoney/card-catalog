"""Download all 71 P&T issue PDFs and extract page-marked text.

Output: pdfs/<source_key>.pdf, text/<source_key>.txt
Each text file starts with an issue header, then '=== PDF PAGE n ===' markers.
"""
import json, os, sys, urllib.request
from pypdf import PdfReader

BASE = os.environ.get('PT_WORK_DIR') or os.getcwd()  # not __file__: this is a tracked
# script run from a scratch dir on either machine (OFFICE/SHOP homes differ).
ISSUES = json.load(open(os.path.join(BASE, 'issues.json'), encoding='utf-8'))
PDF_DIR = os.path.join(BASE, 'pdfs')
TXT_DIR = os.path.join(BASE, 'text')
os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(TXT_DIR, exist_ok=True)

failures = []
for it in ISSUES:
    key = it['source_key']
    pdf_path = os.path.join(PDF_DIR, key + '.pdf')
    url = 'https://publications.sapfm.org' + it['download_url']
    if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) == 0:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'curl/8.9.1'})
            with urllib.request.urlopen(req) as resp, open(pdf_path, 'wb') as f:
                f.write(resp.read())
        except Exception as e:
            failures.append((key, 'download', str(e)))
            continue
    txt_path = os.path.join(TXT_DIR, key + '.txt')
    if os.path.exists(txt_path) and os.path.getsize(txt_path) > 0:
        continue
    try:
        r = PdfReader(pdf_path)
        out = [f"ISSUE: {it['edition']}  source_key={key}  card_id={it['id']}  pdf_pages={len(r.pages)}"]
        for n, p in enumerate(r.pages, 1):
            out.append(f"\n=== PDF PAGE {n} ===")
            out.append((p.extract_text() or '').strip())
        open(txt_path, 'w', encoding='utf-8').write('\n'.join(out))
    except Exception as e:
        failures.append((key, 'extract', str(e)))

print(f"{len(ISSUES)} issues; {len(os.listdir(PDF_DIR))} pdfs; {len(os.listdir(TXT_DIR))} txts")
for f in failures:
    print('FAIL', *f)
# summary line per issue: pages + chars
for it in ISSUES:
    key = it['source_key']
    tp = os.path.join(TXT_DIR, key + '.txt')
    if os.path.exists(tp):
        t = open(tp, encoding='utf-8').read()
        pages = t.count('=== PDF PAGE')
        print(f"{key}: {pages}p {len(t):,}ch")
sys.exit(1 if failures else 0)
