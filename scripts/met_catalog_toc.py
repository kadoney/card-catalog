"""
Inspect TOC and structure of Met catalog PDFs.
Downloads each PDF, finds the table of contents, prints it.

Usage: python met_catalog_toc.py
"""
import io, re, sys, time
from pathlib import Path
import requests
import pdfplumber

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT_DIR = Path(__file__).parent
PDF_DIR = OUT_DIR / "met_pdfs"
PDF_DIR.mkdir(exist_ok=True)

CATALOGS = [
    {
        "slug": "heckscher_1985",
        "title": "American Furniture Vol. II: Queen Anne and Chippendale Styles",
        "author": "Morrison H. Heckscher",
        "year": 1985,
        "pdf_url": "https://cdn.sanity.io/files/cctd4ker/production/f395c810d8549233af1bce8b1995b9d17acb1a39.pdf",
        "view_url": "https://www.metmuseum.org/met-publications/american-furniture-in-the-metropolitan-museum-of-art-late-colonial-period-vol-ii-the-queen-anne-a",
    },
    {
        "slug": "safford_2007",
        "title": "American Furniture Vol. I: Early Colonial Period",
        "author": "Frances Gruber Safford",
        "year": 2007,
        "pdf_url": "https://cdn.sanity.io/files/cctd4ker/production/df545755bb71a8c317e265bc032781a4429cf610.pdf",
        "view_url": "https://www.metmuseum.org/met-publications/american-furniture-in-the-metropolitan-museum-of-art-vol-i-early-colonial-period-the-seventeenth-cen",
    },
    {
        "slug": "tracy_1970",
        "title": "Nineteenth-Century America: Furniture and Other Decorative Arts",
        "author": "Berry B. Tracy et al.",
        "year": 1970,
        "pdf_url": "https://cdn.sanity.io/files/cctd4ker/production/2be2318e7208e7a5a0f989af46199d7323bb370a.pdf",
        "view_url": "https://www.metmuseum.org/met-publications/nineteenth-century-america-furniture-and-other-decorative-arts",
    },
    {
        "slug": "davidson_1985",
        "title": "The American Wing at The Metropolitan Museum of Art",
        "author": "Marshall B. Davidson and Elizabeth Stillinger",
        "year": 1985,
        "pdf_url": "https://cdn.sanity.io/files/cctd4ker/production/7886dac8d36fcc46532a898bcbdd432af96ef482.pdf",
        "view_url": "https://www.metmuseum.org/met-publications/the-american-wing-at-the-metropolitan-museum-of-art-1985",
    },
    {
        "slug": "walk_2002",
        "title": "A Walk Through The American Wing",
        "author": "Curators of the American Wing",
        "year": 2002,
        "pdf_url": "https://cdn.sanity.io/files/cctd4ker/production/dc8a496f4c58c79df67f4d25caa88dd70921a370.pdf",
        "view_url": "https://www.metmuseum.org/met-publications/a-walk-through-the-american-wing",
    },
]


def download(pub):
    pdf_path = PDF_DIR / f"{pub['year']}_{pub['slug']}.pdf"
    if pdf_path.exists():
        print(f"  Already downloaded: {pdf_path.name} ({pdf_path.stat().st_size // 1024} KB)")
        return pdf_path
    print(f"  Downloading {pub['pdf_url'][:60]}...")
    resp = requests.get(pub["pdf_url"], timeout=120,
                        headers={"User-Agent": "SAPFM-CardCatalog/1.0 (research; contact@sapfm.org)"})
    resp.raise_for_status()
    pdf_path.write_bytes(resp.content)
    print(f"  Saved {pdf_path.stat().st_size // 1024} KB")
    time.sleep(3)
    return pdf_path


def find_toc_and_chapters(pdf_path, max_toc_pages=20):
    """Extract and print the table of contents + first-page text of each likely chapter."""
    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        print(f"  Total pages: {total}")

        # Scan first max_toc_pages pages for something that looks like a TOC
        toc_text = ""
        toc_page = None
        for i, page in enumerate(pdf.pages[:max_toc_pages]):
            t = page.extract_text() or ""
            if re.search(r'\bcontents\b', t, re.IGNORECASE):
                toc_text = t
                toc_page = i + 1
                # Grab next page too — TOC often spans 2 pages
                if i + 1 < len(pdf.pages):
                    toc_text += "\n" + (pdf.pages[i + 1].extract_text() or "")
                break

        if toc_page:
            print(f"\n  TOC found on page {toc_page}:")
            print("  " + "-" * 60)
            for line in toc_text.splitlines():
                line = line.strip()
                if line:
                    print(f"  {line}")
        else:
            print("  No TOC found in first 20 pages — printing pages 1-5:")
            for i, page in enumerate(pdf.pages[:5]):
                t = page.extract_text() or ""
                print(f"\n  --- Page {i+1} ---")
                print(t[:600])


for pub in CATALOGS:
    print(f"\n{'='*70}")
    print(f"{pub['year']} — {pub['title']}")
    print(f"Author: {pub['author']}")
    print(f"{'='*70}")
    try:
        pdf_path = download(pub)
        find_toc_and_chapters(pdf_path)
    except Exception as e:
        print(f"  ERROR: {e}")
