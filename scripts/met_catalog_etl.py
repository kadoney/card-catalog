"""
Met Museum Catalog Volumes — Chapter-level ETL

Extracts chapter-level text from 5 major Met publications,
generates card metadata via Claude Haiku, produces SQL for D1.

Text sources:
  archive — pre-downloaded djvu.txt from archive.org (Heckscher, Davidson)
  ocr     — Tesseract OCR from scanned PDF (Safford, Tracy, Walk Through)

Usage:
  python met_catalog_etl.py --phase scrape   [--pub heckscher|davidson|safford|tracy|walk|all]
  python met_catalog_etl.py --phase generate [--pub ...]
  python met_catalog_etl.py --phase sql      [--pub ...]
  python met_catalog_etl.py --phase all      [--pub ...]

Requirements:
  pip install anthropic pdfplumber pdf2image pytesseract
  Tesseract-OCR installed (see ocr_config.py)
"""

import argparse, io, json, os, re, sys, time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUT_DIR = Path(__file__).parent
PDF_DIR = OUT_DIR / "met_pdfs"

# ---------------------------------------------------------------------------
# Chapter definitions — the editorial heart of this ETL
# ---------------------------------------------------------------------------

PUBLICATIONS = {

    "heckscher": {
        "title": "American Furniture in The Metropolitan Museum of Art, Vol. II: The Queen Anne and Chippendale Styles",
        "authors": ["Morrison H. Heckscher"],
        "year": 1985,
        "source": "Metropolitan Museum of Art — American Furniture, Vol. II",
        "source_key": "met",
        "view_url": "https://www.metmuseum.org/met-publications/american-furniture-in-the-metropolitan-museum-of-art-late-colonial-period-vol-ii-the-queen-anne-a",
        "download_url": "https://cdn.sanity.io/files/cctd4ker/production/f395c810d8549233af1bce8b1995b9d17acb1a39.pdf",
        "is_free": 1,
        "text_source": "archive",
        "text_file": "archive_heckscher_1985.txt",
        "chapters": [
            {
                "title": "Introduction: Queen Anne and Chippendale Furniture in America",
                "heading": "INTRODUCTION",
                "stop_heading": "THE CATALOGUE",
                "period": ["Queen Anne", "Chippendale"],
                "form": ["Survey / Multiple"],
                "region": ["National / Survey"],
                "topic": ["Connoisseurship", "Design Sources", "Regional Style", "Attribution"],
            },
            {
                "title": "New England Chairs: Queen Anne and Chippendale",
                "heading": "New England Chairs",
                "stop_heading": "New York Chairs",
                "period": ["Queen Anne", "Chippendale"],
                "form": ["Seating"],
                "region": ["New England", "Boston", "Newport"],
                "topic": ["Regional Style", "Attribution", "Construction / Technique"],
            },
            {
                "title": "New York Chairs: Queen Anne and Chippendale",
                "heading": "New York Chairs",
                "stop_heading": "Pennsylvania Chairs",
                "period": ["Queen Anne", "Chippendale"],
                "form": ["Seating"],
                "region": ["New York", "New York City"],
                "topic": ["Regional Style", "Attribution", "Carving / Ornament"],
            },
            {
                "title": "Pennsylvania Chairs: Queen Anne and Chippendale",
                "heading": "Pennsylvania Chairs",
                "stop_heading": "Stools",
                "period": ["Queen Anne", "Chippendale"],
                "form": ["Seating"],
                "region": ["Philadelphia"],
                "topic": ["Regional Style", "Attribution", "Carving / Ornament"],
            },
            {
                "title": "Easy Chairs: Queen Anne and Chippendale",
                "heading": "Easy Chairs",
                "stop_heading": "Settees",
                "period": ["Queen Anne", "Chippendale"],
                "form": ["Easy Chairs / Upholstered Seating"],
                "region": ["National / Survey"],
                "topic": ["Construction / Technique", "Textiles / Covers", "Regional Style"],
            },
            {
                "title": "Tables: Slab, Card, Dining, and Tea",
                "heading": "Slab Tables",
                "stop_heading": "Case Furniture",
                "period": ["Queen Anne", "Chippendale"],
                "form": ["Tables"],
                "region": ["National / Survey"],
                "topic": ["Regional Style", "Attribution", "Construction / Technique"],
            },
            {
                "title": "New England Case Furniture: High Chests, Dressing Tables, and Desks",
                "heading": "New England High Chests",
                "stop_heading": "Pennsylvania High Chests",
                "period": ["Queen Anne", "Chippendale"],
                "form": ["Case pieces"],
                "region": ["New England", "Boston", "Newport"],
                "topic": ["Regional Style", "Attribution", "Carving / Ornament", "Construction / Technique"],
            },
            {
                "title": "Pennsylvania Case Furniture: High Chests, Dressing Tables, and Desks",
                "heading": "Pennsylvania High Chests",
                "stop_heading": "Desks and Bookcases",
                "period": ["Queen Anne", "Chippendale"],
                "form": ["Case pieces"],
                "region": ["Philadelphia"],
                "topic": ["Regional Style", "Attribution", "Carving / Ornament", "Inlay / Veneer"],
            },
            {
                "title": "Clocks and Miscellaneous Case Forms",
                "heading": "Clocks",
                "stop_heading": "Looking Glasses",
                "period": ["Queen Anne", "Chippendale"],
                "form": ["Clocks / Tall Case", "Case pieces"],
                "region": ["National / Survey"],
                "topic": ["Attribution", "Regional Style", "Construction / Technique"],
            },
            {
                "title": "Looking Glasses and Picture Frames",
                "heading": "Looking Glasses",
                "stop_heading": "PHOTOGRAPHIC DETAILS",
                "period": ["Queen Anne", "Chippendale"],
                "form": ["Case pieces"],
                "region": ["National / Survey"],
                "topic": ["Design Sources", "Carving / Ornament", "Attribution"],
            },
        ],
    },

    "davidson": {
        "title": "The American Wing at The Metropolitan Museum of Art",
        "authors": ["Marshall B. Davidson", "Elizabeth Stillinger"],
        "year": 1985,
        "source": "Metropolitan Museum of Art — The American Wing",
        "source_key": "met",
        "view_url": "https://www.metmuseum.org/met-publications/the-american-wing-at-the-metropolitan-museum-of-art-1985",
        "download_url": "https://cdn.sanity.io/files/cctd4ker/production/7886dac8d36fcc46532a898bcbdd432af96ef482.pdf",
        "is_free": 1,
        "text_source": "archive",
        "text_file": "archive_davidson_1985.txt",
        "chapters": [
            {
                "title": "Introduction: The American Wing at The Metropolitan Museum of Art",
                "heading": "INTRODUCTION",
                "stop_heading": "PERIOD ROOMS",
                "period": ["Survey / Multiple"],
                "form": ["Survey / Multiple"],
                "region": ["National / Survey"],
                "topic": ["Historiography", "Connoisseurship"],
            },
            {
                "title": "Early Colonial Period, 1630–1730: Period Rooms and Furniture",
                "heading": "Early Colonial Period, 1630",
                "stop_heading": "Late Colonial Period, 1730",
                "period": ["Early Colonial", "William & Mary"],
                "form": ["Survey / Multiple"],
                "region": ["New England", "Mid-Atlantic"],
                "topic": ["Regional Style", "Construction / Technique", "Social History"],
            },
            {
                "title": "Late Colonial Period, 1730–1790: Period Rooms and Furniture",
                "heading": "Late Colonial Period, 1730",
                "stop_heading": "Federal Period",
                "period": ["Queen Anne", "Chippendale"],
                "form": ["Survey / Multiple"],
                "region": ["National / Survey"],
                "topic": ["Regional Style", "Design Sources", "Carving / Ornament"],
            },
            {
                "title": "The Federal Period, 1790–1820: Period Rooms and Furniture",
                "heading": "Federal Period",
                "stop_heading": "Shaker",
                "period": ["Federal / Neoclassical"],
                "form": ["Survey / Multiple"],
                "region": ["National / Survey", "Baltimore", "New York City"],
                "topic": ["Regional Style", "Inlay / Veneer", "Design Sources"],
            },
            {
                "title": "The Shaker Vernacular and Windsor Chairs",
                "heading": "Shaker Vernacular",
                "stop_heading": "Pre.Civil War",
                "period": ["Federal / Neoclassical", "Empire"],
                "form": ["Seating", "Windsor"],
                "region": ["National / Survey"],
                "topic": ["Shaker / Religious Communities", "Construction / Technique", "Vernacular"],
            },
            {
                "title": "The Greek Revival, 1820–1845",
                "heading": "Greek Revival",
                "stop_heading": "Rococo Revival",
                "period": ["Empire"],
                "form": ["Survey / Multiple"],
                "region": ["National / Survey", "New York City"],
                "topic": ["Design Sources", "Regional Style", "Social History"],
            },
            {
                "title": "The Rococo Revival, 1840–1860",
                "heading": "Rococo Revival",
                "stop_heading": "Gothic Revival",
                "period": ["Victorian"],
                "form": ["Seating", "Case pieces"],
                "region": ["New York City"],
                "topic": ["Carving / Ornament", "Design Sources", "Biography / Shops"],
            },
            {
                "title": "The Gothic Revival, 1830–1875",
                "heading": "Gothic Revival",
                "stop_heading": "Post.Civil War",
                "period": ["Victorian"],
                "form": ["Survey / Multiple"],
                "region": ["National / Survey"],
                "topic": ["Design Sources", "Construction / Technique"],
            },
            {
                "title": "The Renaissance Revival and Later Nineteenth-Century Styles",
                "heading": "Renaissance Revival",
                "stop_heading": None,
                "period": ["Victorian"],
                "form": ["Survey / Multiple"],
                "region": ["New York City", "National / Survey"],
                "topic": ["Design Sources", "Carving / Ornament", "Inlay / Veneer", "Biography / Shops"],
            },
        ],
    },

    "safford": {
        "title": "American Furniture in The Metropolitan Museum of Art, Vol. I: Early Colonial Period",
        "authors": ["Frances Gruber Safford"],
        "year": 2007,
        "source": "Metropolitan Museum of Art — American Furniture, Vol. I",
        "source_key": "met",
        "view_url": "https://www.metmuseum.org/met-publications/american-furniture-in-the-metropolitan-museum-of-art-vol-i-early-colonial-period-the-seventeenth-cen",
        "download_url": "https://cdn.sanity.io/files/cctd4ker/production/df545755bb71a8c317e265bc032781a4429cf610.pdf",
        "is_free": 1,
        "text_source": "ocr",
        "pdf_file": "met_pdfs/2007_safford_2007.pdf",
        "toc_pages": (5, 15),
        "chapters": [
            {
                "title": "Introduction: Early Colonial Furniture in America",
                "page_range": (1, 11),
                "period": ["Early Colonial", "William & Mary"],
                "form": ["Survey / Multiple"],
                "region": ["New England", "Mid-Atlantic"],
                "topic": ["Connoisseurship", "Construction / Technique", "Regional Style", "Materials"],
            },
            {
                "title": "Seating Furniture: Turned, Joined, and Upholstered Chairs",
                "page_range": (12, 55),
                "period": ["Early Colonial", "William & Mary"],
                "form": ["Seating"],
                "region": ["New England"],
                "topic": ["Construction / Technique", "Attribution", "Regional Style"],
            },
            {
                "title": "Tables: Stationary and Hinged-Leaf Forms",
                "page_range": (120, 150),
                "period": ["Early Colonial", "William & Mary"],
                "form": ["Tables"],
                "region": ["New England"],
                "topic": ["Construction / Technique", "Attribution", "Regional Style"],
            },
            {
                "title": "Case Furniture: Chests, Cupboards, and High Chests",
                "page_range": (168, 210),
                "period": ["Early Colonial", "William & Mary"],
                "form": ["Case pieces"],
                "region": ["New England"],
                "topic": ["Construction / Technique", "Painted / Decorated Surfaces", "Attribution", "Regional Style"],
            },
        ],
    },

    "tracy": {
        "title": "Nineteenth-Century America: Furniture and Other Decorative Arts",
        "authors": ["Berry B. Tracy", "Marilynn Johnson", "Marvin D. Schwartz", "Suzanne Boorsch"],
        "year": 1970,
        "source": "Metropolitan Museum of Art — Nineteenth-Century America",
        "source_key": "met",
        "view_url": "https://www.metmuseum.org/met-publications/nineteenth-century-america-furniture-and-other-decorative-arts",
        "download_url": "https://cdn.sanity.io/files/cctd4ker/production/2be2318e7208e7a5a0f989af46199d7323bb370a.pdf",
        "is_free": 1,
        "text_source": "ocr",
        "pdf_file": "met_pdfs/1970_tracy_1970.pdf",
        "toc_pages": (17, 40),
        "chapters": [
            {
                "title": "Introduction: Nineteenth-Century American Decorative Arts, 1800–1910",
                "page_range": (3, 32),
                "period": ["Federal / Neoclassical", "Empire", "Victorian", "Arts & Crafts"],
                "form": ["Survey / Multiple"],
                "region": ["National / Survey", "New York City"],
                "topic": ["Design Sources", "Social History", "Trade / Commerce", "Biography / Shops"],
            },
        ],
    },

    "walk": {
        "title": "A Walk Through The American Wing",
        "authors": ["Curators of the American Wing"],
        "year": 2002,
        "source": "Metropolitan Museum of Art — A Walk Through The American Wing",
        "source_key": "met",
        "view_url": "https://www.metmuseum.org/met-publications/a-walk-through-the-american-wing",
        "download_url": "https://cdn.sanity.io/files/cctd4ker/production/dc8a496f4c58c79df67f4d25caa88dd70921a370.pdf",
        "is_free": 1,
        "text_source": "ocr",
        "pdf_file": "met_pdfs/2002_walk_2002.pdf",
        "toc_pages": (3, 10),
        "chapters": [
            {
                "title": "Introduction: The American Wing — History and Collections",
                "page_range": (9, 20),
                "period": ["Survey / Multiple"],
                "form": ["Survey / Multiple"],
                "region": ["National / Survey"],
                "topic": ["Historiography", "Connoisseurship"],
            },
            {
                "title": "Decorative Arts: American Wing Galleries and Period Rooms",
                "page_range": (21, 100),
                "period": ["Survey / Multiple"],
                "form": ["Survey / Multiple"],
                "region": ["National / Survey"],
                "topic": ["Connoisseurship", "Regional Style", "Social History"],
            },
        ],
    },

    # ── New publications (April 2026) ─────────────────────────────────────

    "phyfe": {
        "title": "Duncan Phyfe: Master Cabinetmaker in New York",
        "authors": ["Peter M. Kenny", "Michael K. Brown", "Frances F. Bretter", "Matthew A. Thurlow"],
        "year": 2011,
        "source": "Metropolitan Museum of Art — Duncan Phyfe",
        "source_key": "met",
        "view_url": "https://www.metmuseum.org/met-publications/duncan-phyfe-master-cabinetmaker-in-new-york",
        "download_url": "https://cdn.sanity.io/files/cctd4ker/production/1a8b3f5408ed665c2fc7ed6b20f3d9340f248e0f.pdf",
        "is_free": 1,
        "text_source": "ocr",
        "pdf_file": "met_pdfs/2011_duncan_phyfe.pdf",
        "toc_pages": (4, 8),
        "chapters": [
            {
                "title": "Introduction: American Icon — Duncan Phyfe",
                "page_range": (14, 33),
                "period": ["Federal / Neoclassical", "Empire"],
                "form": ["Survey / Multiple"],
                "region": ["New York City"],
                "topic": ["Biography / Shops", "Historiography", "Attribution"],
            },
            {
                "title": "Life of a Master Cabinetmaker: Duncan Phyfe in New York",
                "page_range": (34, 75),
                "period": ["Federal / Neoclassical", "Empire"],
                "form": ["Survey / Multiple"],
                "region": ["New York City"],
                "topic": ["Biography / Shops", "Trade / Commerce", "Social History", "Shop Records"],
            },
            {
                "title": "Furniture from the Workshop of Duncan Phyfe",
                "page_range": (76, 125),
                "period": ["Federal / Neoclassical", "Empire"],
                "form": ["Seating", "Tables", "Case pieces"],
                "region": ["New York City"],
                "topic": ["Construction / Technique", "Design Sources", "Carving / Ornament", "Attribution"],
            },
            {
                "title": "Patrons of the Cabinet Warehouse: Duncan Phyfe's Clients",
                "page_range": (126, 168),
                "period": ["Federal / Neoclassical", "Empire"],
                "form": ["Survey / Multiple"],
                "region": ["New York City"],
                "topic": ["Trade / Commerce", "Social History", "Shop Records", "Biography / Shops"],
            },
        ],
    },

    "lannuier": {
        "title": "Honoré Lannuier, Cabinetmaker from Paris: The Life and Work of a French Ébéniste in Federal New York",
        "authors": ["Peter M. Kenny", "Frances F. Bretter", "Ulrich Leben"],
        "year": 1998,
        "source": "Metropolitan Museum of Art — Honoré Lannuier",
        "source_key": "met",
        "view_url": "https://www.metmuseum.org/met-publications/honore-lannuier-cabinetmaker-from-paris-the-life-and-work-of-a-french-ebeniste-in-federal-new-york",
        "download_url": "https://cdn.sanity.io/files/cctd4ker/production/ada3ee4bb2dbc340f85398d23d7b8d8efd1393f1.pdf",
        "is_free": 1,
        "text_source": "ocr",
        "pdf_file": "met_pdfs/1998_lannuier.pdf",
        "toc_pages": (3, 10),
        "chapters": [
            {
                "title": "Charles-Honoré Lannuier's Origins in France: From Chantilly and Paris to New York",
                "page_range": (22, 123),
                "period": ["Federal / Neoclassical"],
                "form": ["Survey / Multiple"],
                "region": ["European Influence"],
                "topic": ["Biography / Shops", "Immigration", "Design Sources"],
            },
            {
                "title": "Lannuier's Life and Work in New York, 1803–1819",
                "page_range": (124, 169),
                "period": ["Federal / Neoclassical"],
                "form": ["Seating", "Tables", "Case pieces"],
                "region": ["New York City"],
                "topic": ["Biography / Shops", "Construction / Technique", "Attribution", "Trade / Commerce"],
            },
            {
                "title": "Lannuier's Clients in America: A Taste for French Style",
                "page_range": (170, 217),
                "period": ["Federal / Neoclassical"],
                "form": ["Survey / Multiple"],
                "region": ["New York City", "National / Survey"],
                "topic": ["Trade / Commerce", "Social History", "Design Sources"],
            },
            {
                "title": "The Essence of Lannuier: Connoisseurship of His Known Work",
                "page_range": (218, 248),
                "period": ["Federal / Neoclassical"],
                "form": ["Tables", "Case pieces", "Seating"],
                "region": ["New York City"],
                "topic": ["Connoisseurship", "Attribution", "Construction / Technique", "Carving / Ornament"],
            },
        ],
    },

    "rococo": {
        "title": "American Rococo, 1750–1775: Elegance in Ornament",
        "authors": ["Morrison H. Heckscher", "Leslie Greene Bowman"],
        "year": 1992,
        "source": "Metropolitan Museum of Art — American Rococo",
        "source_key": "met",
        "view_url": "https://www.metmuseum.org/met-publications/american-rococo-1750-1775-elegance-in-ornament",
        "download_url": "https://cdn.sanity.io/files/cctd4ker/production/c0c5e0e501b5c0f55e30f56f9db02c8a3ab2d3c5.pdf",
        "is_free": 1,
        "text_source": "ocr",
        "pdf_file": "met_pdfs/1992_american_rococo.pdf",
        "toc_pages": (3, 10),
        "chapters": [
            {
                "title": "The American Rococo: An Introduction",
                "page_range": (18, 33),
                "period": ["Chippendale"],
                "form": ["Survey / Multiple"],
                "region": ["National / Survey"],
                "topic": ["Design Sources", "Historiography", "Carving / Ornament"],
            },
            {
                "title": "Architecture in the American Rococo",
                "page_range": (34, 53),
                "period": ["Chippendale"],
                "form": ["Survey / Multiple"],
                "region": ["National / Survey", "Philadelphia", "New England"],
                "topic": ["Design Sources", "Carving / Ornament", "Construction / Technique"],
            },
            {
                "title": "Engravings and the American Rococo",
                "page_range": (54, 87),
                "period": ["Chippendale"],
                "form": ["Survey / Multiple"],
                "region": ["National / Survey", "Philadelphia"],
                "topic": ["Design Sources", "Carving / Ornament", "Trade / Commerce"],
            },
            {
                "title": "Silver in the American Rococo",
                "page_range": (88, 149),
                "period": ["Chippendale"],
                "form": ["Survey / Multiple"],
                "region": ["National / Survey", "New York City", "Philadelphia", "Boston"],
                "topic": ["Carving / Ornament", "Design Sources", "Attribution", "Biography / Shops"],
            },
            {
                "title": "Furniture in the American Rococo",
                "page_range": (150, 235),
                "period": ["Chippendale"],
                "form": ["Seating", "Tables", "Case pieces"],
                "region": ["Philadelphia", "New York City", "Newport", "Boston"],
                "topic": ["Carving / Ornament", "Regional Style", "Design Sources", "Attribution", "Construction / Technique"],
            },
            {
                "title": "Cast Iron, Glass, and Porcelain in the American Rococo",
                "page_range": (236, 256),
                "period": ["Chippendale"],
                "form": ["Survey / Multiple"],
                "region": ["National / Survey"],
                "topic": ["Design Sources", "Carving / Ornament", "Trade / Commerce"],
            },
        ],
    },
}

# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------

CATALOG_ENTRY_RE = re.compile(
    r'^\s*\d{1,3}[\.\s]',  # Lines starting with catalog numbers: "74." or "74 "
)
DIMENSION_RE = re.compile(
    r'^\s*(?:H\.|W\.|D\.|L\.|Diam\.|Overall|Height|Width|Depth)',
)
PROVENANCE_RE = re.compile(
    r'^\s*(?:Provenance|Accession|Gift of|Purchase|Bequest|Rogers Fund)',
    re.IGNORECASE,
)

MAX_CHAPTER_CHARS = 8000  # Feed at most this many chars to Haiku


def strip_catalog_noise(text):
    """Remove object catalog entries, leaving only narrative prose."""
    lines = text.splitlines()
    cleaned = []
    skip_count = 0
    for line in lines:
        if skip_count > 0:
            skip_count -= 1
            continue
        if CATALOG_ENTRY_RE.match(line) or DIMENSION_RE.match(line) or PROVENANCE_RE.match(line):
            skip_count = 4  # skip this line + next few (accession, dimensions, etc.)
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def extract_chapter_from_text(full_text, heading, stop_heading, max_chars=MAX_CHAPTER_CHARS,
                              min_pos=10000):
    """
    Find a chapter heading in archive.org djvu text and extract prose.

    djvu format has: numbered running-header list → blank lines → bare chapter title
    → blank lines → body text. We search for the bare (unnumbered) chapter title,
    which appears as a standalone line surrounded by blank lines.
    """
    # Pattern: heading as a bare line (not preceded by a digit+dot list marker)
    # after min_pos to skip TOC / front matter
    search_text = full_text[min_pos:]

    # Try: blank line + heading (no digit prefix) + blank line
    pattern = r'(?:^|\n)\n(' + re.escape(heading) + r')\s*\n'
    m = re.search(pattern, search_text, re.IGNORECASE)

    if not m:
        # Fallback: just find any occurrence after min_pos
        m = re.search(re.escape(heading), search_text, re.IGNORECASE)

    if not m:
        return ""

    chunk_start = min_pos + m.end()

    if stop_heading:
        stop_pattern = r'(?:^|\n)\n(' + re.escape(stop_heading) + r')\s*\n'
        stop = re.search(stop_pattern, full_text[chunk_start:], re.IGNORECASE)
        if not stop:
            stop = re.search(re.escape(stop_heading), full_text[chunk_start:], re.IGNORECASE)
        chunk_end = chunk_start + (stop.start() if stop else max_chars * 3)
    else:
        chunk_end = chunk_start + max_chars * 3

    chunk = full_text[chunk_start:chunk_end]
    chunk = strip_catalog_noise(chunk)

    if len(chunk) > max_chars:
        chunk = chunk[:max_chars] + "\n[truncated]"

    return chunk.strip()


def ocr_pages(pdf_path, first_page, last_page, dpi=200):
    """OCR a range of PDF pages, return combined text."""
    from ocr_config import POPPLER_PATH, configure_ocr
    from pdf2image import convert_from_path
    import pytesseract
    configure_ocr()

    pages = convert_from_path(
        str(pdf_path), first_page=first_page, last_page=last_page,
        dpi=dpi, poppler_path=POPPLER_PATH
    )
    texts = []
    for page in pages:
        texts.append(pytesseract.image_to_string(page))
    return "\n".join(texts)


# ---------------------------------------------------------------------------
# Controlled vocabulary (same as bulletins)
# ---------------------------------------------------------------------------

CONTROLLED_VOCAB = """
PERIOD (use exact strings, multiple allowed):
Early Colonial, William & Mary, Baroque / Late Baroque, Queen Anne, Chippendale,
Federal / Neoclassical, Empire, Victorian, Colonial Revival, Arts & Crafts, Shaker,
Modern / Studio, Survey / Multiple

FORM (use exact strings, multiple allowed):
Case pieces, Seating, Easy Chairs / Upholstered Seating, Windsor, Vernacular,
Tables, Beds, Clocks / Tall Case, Textiles / Covers, Survey / Multiple

REGION (use exact strings, multiple allowed):
New England, Boston, Newport, Rural New England, New York, New York City,
Philadelphia, Baltimore, Mid-Atlantic, Chesapeake / Virginia, Southern, Charleston,
North Carolina, Rural / Backcountry, National / Survey, European Influence

TOPIC (use exact strings, multiple allowed):
Construction / Technique, Attribution, Regional Style, Design Sources,
Carving / Ornament, Inlay / Veneer, Painted / Decorated Surfaces, Shop Records,
Conservation, Repair / Alteration, Fakes / Authentication, Materials,
Terminology / Nomenclature, Social History, Trade / Commerce, Immigration,
Biography / Shops, Connoisseurship, Historiography, Shaker / Religious Communities,
Studio / Contemporary
"""

CARD_PROMPT = """You are an expert in American decorative arts and period furniture scholarship.
I will give you an excerpt from a Metropolitan Museum of Art publication — either the full text
of a chapter introduction or a section essay. Generate a library card entry in JSON format.

CONTROLLED VOCABULARIES — use ONLY these exact strings:
{vocab}

OUTPUT FORMAT (JSON only, no other text):
{{
  "description": "3-5 sentences. See description rules below.",
  "period": ["exact period string", ...],
  "form": ["exact form string", ...],
  "region": ["exact region string", ...],
  "topic": ["exact topic string", ...],
  "makers": ["Craftsman Name", ...]
}}

RULES:
- description: 3-5 sentences written by one furniture scholar for another — peer to peer.
  The reader is a skilled craftsman who reads deeply: they know Chippendale from Federal,
  they've held a card scraper, they want to know whether this scholarship is worth their time.
  HARD RULE — NEVER open with "This chapter", "This section", "This catalog", "This book",
  "The author", or any variant. NEVER use hedging phrases: "seeks to", "aims to", "explores".
  Lead with the subject itself: the objects, the craftsmen, the region, the argument.
  Be specific — name pieces, makers, towns, joints, woods, techniques.
  Match the register of Met scholarship: serious, precise, authoritative.
- makers: only named craftsmen/cabinetmakers/carvers studied in depth
- Use "Survey / Multiple" only when the section genuinely spans multiple without focusing on one
- Prefer the suggested period/form/region/topic hints below, but override if the text clearly
  indicates otherwise
- If text is noisy OCR, work with what you can discern

SUGGESTED TAGS (override if text disagrees):
Period: {period}
Form: {form}
Region: {region}
Topic: {topic}

PUBLICATION: {pub_title}
AUTHORS: {authors}
YEAR: {year}
CHAPTER/SECTION: {chapter_title}

Chapter text:
{body}
"""


# ---------------------------------------------------------------------------
# Phase 1: Scrape — extract chapter text
# ---------------------------------------------------------------------------

def phase_scrape(pub_keys):
    raw_path = OUT_DIR / "met_catalog_raw.json"

    existing = json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.exists() else []
    done_keys = {(r["pub_key"], r["chapter_title"]) for r in existing}

    for key in pub_keys:
        pub = PUBLICATIONS[key]
        print(f"\n{'='*60}")
        print(f"{pub['year']} — {pub['title'][:60]}")

        if not pub.get("chapters"):
            print(f"  No chapters defined yet — run TOC inspection first")
            continue

        # For archive sources, load full text once
        full_text = None
        if pub["text_source"] == "archive":
            txt_path = OUT_DIR / pub["text_file"]
            if not txt_path.exists():
                print(f"  ERROR: {txt_path} not found")
                continue
            full_text = txt_path.read_text(encoding="utf-8", errors="replace")
            print(f"  Loaded {len(full_text):,} chars from {txt_path.name}")
        elif pub["text_source"] == "ocr":
            # Only build full text cache if any chapter lacks a page_range
            needs_full = any("page_range" not in c for c in pub["chapters"])
            if needs_full:
                cache_path = OUT_DIR / f"ocr_{key}_full.txt"
                if cache_path.exists():
                    full_text = cache_path.read_text(encoding="utf-8", errors="replace")
                    print(f"  OCR cache loaded: {len(full_text):,} chars")
                else:
                    print(f"  OCR-ing full PDF (this will take a while)...")
                    import fitz
                    doc = fitz.open(str(OUT_DIR / pub["pdf_file"]))
                    total_pages = len(doc)
                    doc.close()
                    print(f"  Total pages: {total_pages}")
                    full_text = ocr_pages(OUT_DIR / pub["pdf_file"], 1, total_pages, dpi=200)
                    cache_path.write_text(full_text, encoding="utf-8")
                    print(f"  OCR complete: {len(full_text):,} chars -> {cache_path.name}")

        # Extract each chapter
        for chap in pub["chapters"]:
            ck = (key, chap["title"])
            if ck in done_keys:
                print(f"  SKIP (done): {chap['title'][:60]}")
                continue

            # Targeted page-range OCR takes priority over full-text extraction
            if pub["text_source"] == "ocr" and "page_range" in chap:
                first, last = chap["page_range"]
                print(f"  OCR-ing pages {first}–{last} for '{chap['title'][:50]}'...")
                raw_ocr = ocr_pages(OUT_DIR / pub["pdf_file"], first, last, dpi=200)
                body = strip_catalog_noise(raw_ocr).strip()
                if len(body) > MAX_CHAPTER_CHARS:
                    body = body[:MAX_CHAPTER_CHARS] + "\n[truncated]"
            else:
                body = extract_chapter_from_text(
                    full_text, chap["heading"], chap.get("stop_heading")
                )

            if not body or len(body) < 100:
                print(f"  WARNING: low text ({len(body)} chars) for '{chap['title'][:50]}'")
            else:
                print(f"  OK: '{chap['title'][:55]}' — {len(body)} chars")

            record = {
                "pub_key": key,
                "pub_title": pub["title"],
                "authors": pub["authors"],
                "year": pub["year"],
                "source": pub["source"],
                "source_key": pub["source_key"],
                "view_url": pub["view_url"],
                "download_url": pub["download_url"],
                "is_free": pub["is_free"],
                "chapter_title": chap["title"],
                "period_hint": chap.get("period", []),
                "form_hint": chap.get("form", []),
                "region_hint": chap.get("region", []),
                "topic_hint": chap.get("topic", []),
                "body": body,
            }
            existing.append(record)
            done_keys.add(ck)

        raw_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nScrape complete. {len(existing)} chapter records in {raw_path.name}")


# ---------------------------------------------------------------------------
# Phase 2: Generate card metadata via Claude API
# ---------------------------------------------------------------------------

def phase_generate(pub_keys):
    import anthropic

    raw_path = OUT_DIR / "met_catalog_raw.json"
    cards_path = OUT_DIR / "met_catalog_cards.json"

    if not raw_path.exists():
        print("Run --phase scrape first")
        sys.exit(1)

    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    raw = [r for r in raw if r["pub_key"] in pub_keys]

    cards = json.loads(cards_path.read_text(encoding="utf-8")) if cards_path.exists() else []
    done_keys = {(c["pub_key"], c["chapter_title"]) for c in cards}

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Set ANTHROPIC_API_KEY environment variable")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    for i, rec in enumerate(raw):
        ck = (rec["pub_key"], rec["chapter_title"])
        if ck in done_keys:
            continue

        print(f"[{i+1}/{len(raw)}] {rec['year']} — {rec['chapter_title'][:65]}", flush=True)

        if not rec["body"] or len(rec["body"]) < 50:
            print(f"  SKIP: no usable text")
            continue

        prompt = CARD_PROMPT.format(
            vocab=CONTROLLED_VOCAB,
            pub_title=rec["pub_title"],
            authors=", ".join(rec["authors"]),
            year=rec["year"],
            chapter_title=rec["chapter_title"],
            period=rec.get("period_hint", []),
            form=rec.get("form_hint", []),
            region=rec.get("region_hint", []),
            topic=rec.get("topic_hint", []),
            body=rec["body"][:7000],
        )

        try:
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )
            text = msg.content[0].text.strip()
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if not json_match:
                print(f"  WARNING: no JSON in response")
                continue
            meta = json.loads(json_match.group())

            card = {
                "pub_key": rec["pub_key"],
                "pub_title": rec["pub_title"],
                "chapter_title": rec["chapter_title"],
                "title": rec["chapter_title"],
                "authors": rec["authors"],
                "year": rec["year"],
                "source": rec["source"],
                "source_key": rec["source_key"],
                "card_type": "chapter",
                "description": meta.get("description", ""),
                "period": meta.get("period", rec.get("period_hint", [])),
                "form": meta.get("form", rec.get("form_hint", [])),
                "region": meta.get("region", rec.get("region_hint", [])),
                "topic": meta.get("topic", rec.get("topic_hint", [])),
                "makers": meta.get("makers", []),
                "is_free": rec["is_free"],
                "view_url": rec["view_url"],
                "download_url": rec["download_url"],
            }
            cards.append(card)
            done_keys.add(ck)
            print(f"  OK — period={card['period'][:2]}, topic={card['topic'][:2]}", flush=True)

        except json.JSONDecodeError as e:
            print(f"  JSON error: {e}")
            continue
        except Exception as e:
            print(f"  API error: {e}")
            time.sleep(5)
            continue

        if len(cards) % 5 == 0:
            cards_path.write_text(json.dumps(cards, indent=2, ensure_ascii=False), encoding="utf-8")
        time.sleep(0.8)

    cards_path.write_text(json.dumps(cards, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nGenerate complete. {len(cards)} cards in {cards_path.name}")


# ---------------------------------------------------------------------------
# Phase 3: Generate SQL
# ---------------------------------------------------------------------------

def phase_sql(pub_keys):
    cards_path = OUT_DIR / "met_catalog_cards.json"
    sql_path = OUT_DIR / "met_catalog_inserts.sql"

    if not cards_path.exists():
        print("Run --phase generate first")
        sys.exit(1)

    cards = json.loads(cards_path.read_text(encoding="utf-8"))
    cards = [c for c in cards if c["pub_key"] in pub_keys]

    def esc(s):
        return str(s).replace("'", "''") if s else ""

    lines = [
        "-- Met Museum Catalog Volumes — chapter-level cards",
        f"-- Generated from {len(cards)} chapters across {len(pub_keys)} publications",
        "",
    ]

    for c in cards:
        title    = esc(c["title"])
        authors  = json.dumps(c.get("authors") or [], ensure_ascii=False).replace("'", "''")
        desc     = esc(c.get("description") or "")
        period   = json.dumps(c.get("period") or [], ensure_ascii=False)
        form     = json.dumps(c.get("form") or [], ensure_ascii=False)
        region   = json.dumps(c.get("region") or [])
        topic    = json.dumps(c.get("topic") or [])
        makers   = json.dumps(c.get("makers") or [], ensure_ascii=False).replace("'", "''")
        year     = c.get("year") or "NULL"
        source   = esc(c.get("source") or "")
        src_key  = esc(c.get("source_key") or "")
        c_type   = esc(c.get("card_type") or "chapter")
        view_url = esc(c.get("view_url") or "")
        dl_url   = esc(c.get("download_url") or "")
        is_free  = 1 if c.get("is_free") else 0

        lines.append(
            f"INSERT OR REPLACE INTO library_cards "
            f"(title, authors, year, source, source_key, card_type, "
            f"description, period, form, region, topic, makers, "
            f"is_free, view_url, download_url, status, created_at, updated_at) VALUES "
            f"('{title}', '{authors}', {year}, '{source}', '{src_key}', '{c_type}', "
            f"'{desc}', '{period}', '{form}', '{region}', '{topic}', '{makers}', "
            f"{is_free}, '{view_url}', '{dl_url}', 'approved', datetime('now'), datetime('now'));"
        )

    sql_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"SQL written: {len(cards)} inserts to {sql_path.name}")


# ---------------------------------------------------------------------------
# TOC inspection helper (run before chapters are defined for OCR pubs)
# ---------------------------------------------------------------------------

def inspect_toc(pub_key):
    pub = PUBLICATIONS[pub_key]
    if pub["text_source"] == "archive":
        print("Archive text — use the text file directly")
        return
    first, last = pub.get("toc_pages", (3, 12))
    print(f"OCR-ing pages {first}–{last} of {pub['pdf_file']}...")
    text = ocr_pages(OUT_DIR / pub["pdf_file"], first, last)
    print(text)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def resolve_pub_keys(arg):
    if arg == "all":
        return list(PUBLICATIONS.keys())
    keys = [k.strip() for k in arg.split(",")]
    for k in keys:
        if k not in PUBLICATIONS:
            sys.exit(f"Unknown pub key: {k}. Valid: {list(PUBLICATIONS.keys())}")
    return keys


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Met Catalog Chapter ETL")
    parser.add_argument("--phase", choices=["scrape", "generate", "sql", "all", "toc"], required=True)
    parser.add_argument("--pub", default="heckscher,davidson",
                        help="Comma-separated pub keys or 'all'. Default: heckscher,davidson")
    args = parser.parse_args()

    if args.phase == "toc":
        for k in resolve_pub_keys(args.pub):
            inspect_toc(k)
        sys.exit(0)

    pub_keys = resolve_pub_keys(args.pub)

    if args.phase in ("scrape", "all"):
        phase_scrape(pub_keys)
    if args.phase in ("generate", "all"):
        phase_generate(pub_keys)
    if args.phase in ("sql", "all"):
        phase_sql(pub_keys)
