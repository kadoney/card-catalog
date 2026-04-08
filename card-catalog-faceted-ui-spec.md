# SAPFM Card Catalog — Faceted Browser UI Spec
*For use by Claude Code to build the member-facing browse interface*

---

## Overview

The Card Catalog is a human-curated, annotated bibliography of American period furniture scholarship. Members browse by facet (period, form, region, topic), select active filters, and read card details that link directly to the source article.

The UI lives at a Cloudflare Pages URL and calls a Cloudflare Worker API. It is a member-gated app on the SAPFM Member Desktop.

**415 cards** are currently in D1, all `status = 'approved'`. Cards span Chipstone/American Furniture journal articles, APF journal content, and a Southern decorative arts corpus.

---

## Database

- **D1 database name:** `card-catalog`
- **D1 database ID:** `eb944e67-5fcc-4587-8fe1-eae2a9fe3476`
- **Cloudflare account:** SAPFM account (`ebe622...`)

### Tables

**`library_cards`** — canonical card table

```sql
CREATE TABLE library_cards (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  title            TEXT    NOT NULL,
  authors          TEXT    NOT NULL DEFAULT '[]',      -- JSON array of strings
  year             INTEGER,
  source           TEXT,                               -- human label
  source_key       TEXT,                               -- machine key (chipstone, met, etc.)
  card_type        TEXT    NOT NULL DEFAULT 'article', -- article | chapter | book | catalog
  parent_id        INTEGER REFERENCES library_cards(id),
  page_start       INTEGER,
  page_end         INTEGER,
  edition          TEXT,
  description      TEXT    NOT NULL,
  period           TEXT    NOT NULL DEFAULT '[]',      -- JSON array, controlled vocab
  form             TEXT    NOT NULL DEFAULT '[]',      -- JSON array, controlled vocab
  region           TEXT    NOT NULL DEFAULT '[]',      -- JSON array, controlled vocab
  topic            TEXT    NOT NULL DEFAULT '[]',      -- JSON array, controlled vocab
  makers           TEXT    NOT NULL DEFAULT '[]',      -- JSON array of craftsman names
  is_free          INTEGER NOT NULL DEFAULT 1,         -- 1 = freely readable online
  view_url         TEXT,
  download_url     TEXT,
  contributed_by   TEXT,
  contributor_name TEXT,
  status           TEXT    NOT NULL DEFAULT 'approved',
  created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at       TEXT    NOT NULL DEFAULT (datetime('now')),
  teaser           TEXT,
  is_featured      INTEGER DEFAULT 0
);
```

**`vocab_terms`** — canonical controlled vocabulary

```sql
-- columns: id, dimension, value, label, sort_order, notes
-- dimensions: period, form, region, topic, card_type, source_key
```

All facet fields in `library_cards` store JSON arrays. Values must exactly match `vocab_terms.value` strings (case-sensitive). This normalization was completed April 2026.

---

## Controlled Vocabularies (Current canonical state)

### Period (13 values, chronological order)
| Value | Date Range | Notes |
|-------|-----------|-------|
| Early Colonial | Pre-1690 | Joined furniture, Pilgrim Century |
| William & Mary | 1690–1730 | Turned ornament, bun feet, japanning |
| Baroque / Late Baroque | 1700–1740 | Boston Georgian chairs |
| Queen Anne | 1725–1755 | Cabriole leg, splat back, pad foot |
| Chippendale | 1750–1790 | Ball-and-claw, carved ornament, Rococo |
| Federal / Neoclassical | 1785–1820 | Inlay, taper leg, Hepplewhite/Sheraton |
| Empire | 1815–1840 | Archaeological classicism, heavy forms |
| Victorian | 1840–1900 | Revival styles, Reform movement |
| Colonial Revival | 1880–1940 | Revival of early American forms |
| Arts & Crafts | 1880–1920 | Mission, Stickley, Greene & Greene |
| Shaker | 1820–1900 | Distinct community tradition |
| Modern / Studio | Post-1920 | Studio furniture makers |
| Survey / Multiple | — | Articles spanning multiple periods |

### Form (10 values)
| Value | Notes |
|-------|-------|
| Case pieces | Chests, highboys, lowboys, secretaries, bookcases |
| Seating | Chairs, settees, stools, benches |
| Easy Chairs / Upholstered Seating | Easy chairs, wing chairs, sofas |
| Windsor | Windsor chairs and stick-construction seating |
| Vernacular | Non-fashionable, rural, or utilitarian forms |
| Tables | All table forms |
| Beds | Bedsteads, cradles |
| Clocks / Tall Case | Clock cases and timekeeping furniture |
| Textiles / Covers | Protective covers, upholstery fabric |
| Survey / Multiple | Articles spanning multiple forms |

### Region (16 values, geographic order N→S)
| Value | Notes |
|-------|-------|
| New England | CT, MA, RI, VT, NH, ME |
| Boston | City-specific |
| Newport | City-specific; Townsend-Goddard tradition |
| Rural New England | Non-urban New England |
| New York | State broadly |
| New York City | Manhattan; Phyfe, Lannuier |
| Philadelphia | Philadelphia and Delaware Valley |
| Baltimore | Federal period center |
| Mid-Atlantic | PA, DE, MD broadly |
| Chesapeake / Virginia | Tidewater; Colonial Williamsburg sphere |
| Southern | Carolinas, Georgia, other southern states |
| Charleston | City-specific |
| North Carolina | MESDA / Bivins scholarship |
| Rural / Backcountry | Non-urban, cross-regional vernacular |
| National / Survey | No single regional focus |
| European Influence | English or continental design sources |

### Topic (21 values)
| Value | Notes |
|-------|-------|
| Construction / Technique | Joinery, wood technology, hand tool practice |
| Attribution | Establishing maker identity |
| Regional Style | Distinguishing one center's production |
| Design Sources | Pattern books, English precedents |
| Carving / Ornament | Surface decoration, carved elements |
| Inlay / Veneer | Stringing, banding, marquetry |
| Painted / Decorated Surfaces | Japanning, fancy furniture |
| Shop Records | Account books, daybooks, labels |
| Conservation | Technical examination, restoration |
| Repair / Alteration | Period and later repairs |
| Fakes / Authentication | Identifying later work as period |
| Materials | Wood species, hardware, upholstery |
| Terminology / Nomenclature | Period trade terms, part names |
| Social History | Patronage, domestic life |
| Enslaved Craftspeople | Attribution and social history |
| Trade / Commerce | Furniture trade, export, retail |
| Immigration | Immigrant craftsmen and influence |
| Biography / Shops | Craftsman or shop histories |
| Connoisseurship | Methodology of attribution |
| Historiography | History of the field itself |
| Shaker / Religious Communities | Intentional community furniture |
| Studio / Contemporary | Post-1920 studio furniture |

---

## Card Counts by Facet (April 2026 baseline)

### Period
| Value | Count |
|-------|-------|
| Federal / Neoclassical | 218 |
| Queen Anne | 108 |
| Chippendale | 102 |
| Early Colonial | 88 |
| William & Mary | 68 |
| Survey / Multiple | 41 |
| Victorian | 44 |
| Baroque / Late Baroque | 33 |
| Empire | 31 |
| Colonial Revival | 28 |
| Modern / Studio | 27 |
| Arts & Crafts | 14 |
| Shaker | 7 |

### Form
| Value | Count |
|-------|-------|
| Case pieces | 247 |
| Seating | 206 |
| Tables | 152 |
| Survey / Multiple | 125 |
| Clocks / Tall Case | 38 |
| Textiles / Covers | 36 |
| Easy Chairs / Upholstered Seating | 28 |
| Beds | 23 |
| Windsor | 16 |
| Vernacular | 2 |

### Region (top 10)
| Value | Count |
|-------|-------|
| New England | 132 |
| National / Survey | 117 |
| Philadelphia | 82 |
| European Influence | 75 |
| Boston | 74 |
| New York | 65 |
| Chesapeake / Virginia | 55 |
| North Carolina | 48 |
| Mid-Atlantic | 44 |
| Charleston | 44 |

### Topic (top 10)
| Value | Count |
|-------|-------|
| Regional Style | 285 |
| Attribution | 259 |
| Construction / Technique | 241 |
| Connoisseurship | 181 |
| Design Sources | 175 |
| Social History | 168 |
| Biography / Shops | 163 |
| Trade / Commerce | 128 |
| Carving / Ornament | 119 |
| Materials | 105 |

---

## Worker API Endpoints

**Worker name:** `sapfm-card-catalog` (or integrated into existing `sapfm` Worker)
**Base path:** `/api/library/`

### GET /api/library/cards

Returns paginated list of approved cards with optional facet filtering.

**Query parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `period` | string | Filter by period value (exact match in JSON array) |
| `form` | string | Filter by form value |
| `region` | string | Filter by region value |
| `topic` | string | Filter by topic value |
| `source_key` | string | Filter by source (chipstone, met, etc.) |
| `q` | string | Full-text search on title, description, makers |
| `page` | integer | Page number (default: 1) |
| `limit` | integer | Results per page (default: 24, max: 100) |
| `year_min` | integer | Filter by year >= |
| `year_max` | integer | Filter by year <= |
| `is_free` | 0 or 1 | Filter by free access |

**Response:**
```json
{
  "cards": [...],
  "total": 415,
  "page": 1,
  "limit": 24,
  "facets": {
    "period": [{"value": "Federal / Neoclassical", "count": 218}, ...],
    "form": [...],
    "region": [...],
    "topic": [...]
  }
}
```

**CRITICAL:** The `facets` object in every list response must reflect counts **after applying all currently active filters except the dimension being counted**. This enables the "show me how many results each facet will yield" behavior where selecting Period=Chippendale updates the counts shown in Form, Region, and Topic facets.

**D1 filtering approach:** Since facet fields are JSON arrays, use `LIKE '%"Value"%'` for filtering. Example:
```sql
WHERE period LIKE '%"Chippendale"%'
AND form LIKE '%"Case pieces"%'
```

### GET /api/library/cards/:id

Returns a single card with full detail.

### GET /api/library/vocab

Returns the full controlled vocabulary from `vocab_terms`, grouped by dimension. Use this to populate facet panels — do not hardcode vocab in the UI.

**Response:**
```json
{
  "period": [{"value": "Early Colonial", "label": "Early Colonial", "notes": "..."}],
  "form": [...],
  "region": [...],
  "topic": [...]
}
```

### POST /api/library/submissions

Member-authenticated endpoint for submitting new card candidates. Body is the card payload JSON. Writes to `submissions` table with `status = 'pending'`.

### GET /api/library/submissions (admin)
### PATCH /api/library/submissions/:id (admin)

Moderation queue endpoints. PATCH with `{"status": "approved"}` writes the submission payload to `library_cards`.

---

## UI Architecture

### Layout

Three-panel desktop-first layout (matches SAPFM Member Desktop shell):

```
┌─────────────────┬──────────────────────────────────┐
│  FACET PANEL    │  CARD GRID                       │
│  (collapsible)  │                                  │
│  ~280px wide    │  remainder of viewport           │
│                 │                                  │
│  Period ▼       │  [card] [card] [card]            │
│  • Chippendale  │  [card] [card] [card]            │
│    (102)        │  ...                             │
│  • Federal      │                                  │
│    (218)        ├──────────────────────────────────┤
│                 │  CARD DETAIL (right panel or     │
│  Form ▼         │  modal — opens on card click)    │
│  Region ▼       │                                  │
│  Topic ▼        │                                  │
└─────────────────┴──────────────────────────────────┘
```

### Facet Panel Behavior

- Four collapsible sections: Period, Form, Region, Topic
- Each section shows all vocab values with current result count in parentheses
- Values with count 0 are shown dimmed (not hidden) — member can see what exists
- Active selections are highlighted/checked
- **Multiple values within a dimension are OR** (Chippendale OR Queen Anne)
- **Across dimensions are AND** (Chippendale AND Case pieces)
- Active filter count badge on panel header when collapsed
- "Clear all filters" button at panel top
- Facet counts update dynamically as filters are applied (no page reload)

### Card Grid

- Masonry or uniform grid, ~3 columns at 1280px, 2 at 900px
- Card shows: title, author(s), year, source, period tags, 2-line description teaser
- Cards animate position changes when filters change (FLIP animation — see Animation section)
- "No results" state with suggestion to clear filters

### Card Detail

- Opens in right panel (desktop) or as full-width takeover (narrow)
- Shows: full title, authors, year, source, description, all facet tags, makers list
- Primary CTA: "Read Article →" (view_url, opens new tab)
- Secondary: "Download PDF" if download_url present
- Contributor attribution if contributed_by is populated
- "← Back to results" closes detail and restores scroll position in grid

### FLIP Animation (the solitaire-deck effect)

When the active filter set changes, cards should physically travel to their new positions rather than simply appearing/disappearing. Implementation:

1. Before applying new filter: record each card's `getBoundingClientRect()` — store as `{id, x, y, width, height}`
2. Apply the new filter — DOM updates, cards move to new positions
3. Record each card's new `getBoundingClientRect()`
4. For each card: compute delta (oldX - newX, oldY - newY)
5. Instantly apply `transform: translate(deltaX, deltaY)` to move each card back to its old visual position
6. Remove the transform with a CSS transition (e.g. `transition: transform 350ms cubic-bezier(0.4, 0, 0.2, 1)`)
7. Cards fly from their old position to their new position simultaneously

Cards entering the view (not in previous result set) fade in. Cards leaving fade out before the FLIP begins.

```javascript
// Pseudocode
async function applyFilter(newFilters) {
  // 1. Snapshot current positions
  const before = {};
  document.querySelectorAll('.card[data-id]').forEach(el => {
    before[el.dataset.id] = el.getBoundingClientRect();
  });

  // 2. Fade out departing cards
  const nextIds = new Set(await fetchCards(newFilters).map(c => c.id));
  document.querySelectorAll('.card[data-id]').forEach(el => {
    if (!nextIds.has(el.dataset.id)) el.classList.add('leaving');
  });
  await wait(200); // let fade complete

  // 3. Update DOM with new card set
  renderCards(newCards);

  // 4. FLIP remaining cards
  document.querySelectorAll('.card[data-id]').forEach(el => {
    const id = el.dataset.id;
    if (!before[id]) { el.classList.add('entering'); return; }
    const after = el.getBoundingClientRect();
    const dx = before[id].x - after.x;
    const dy = before[id].y - after.y;
    if (dx === 0 && dy === 0) return;
    el.style.transform = `translate(${dx}px, ${dy}px)`;
    el.style.transition = 'none';
    requestAnimationFrame(() => {
      el.style.transition = 'transform 350ms cubic-bezier(0.4, 0, 0.2, 1)';
      el.style.transform = '';
    });
  });
}
```

### Search

- Text search box above facet panel or at grid top
- Searches title, description, makers (full-text via LIKE in Worker)
- Search + facets are combinable
- Debounce 300ms before firing request

### URL State

All active filters and search should be reflected in URL query params so results are bookmarkable and shareable:
```
/catalog?period=Chippendale&form=Case+pieces&q=Philadelphia
```

On load, parse URL params and restore filter state before first fetch.

---

## Styling Notes

- Follows SAPFM Member Desktop visual language: warm earth tones, serif display font for headings, dense-but-readable information layout
- Primary accent: `#d4a574` (warm gold/amber)
- Background: dark (`#0d0d0d` / `#1a1a1a`) to match existing Member Desktop apps
- Card border: `1px solid #333`, hover: `border-color: #d4a574`
- Facet panel: slightly lighter background than card grid (`#1a1a1a` vs `#0d0d0d`)
- Active facet selection: amber highlight
- Tags on cards: small pill badges using amber accent

---

## Implementation Notes for Code

1. **Vocab from API, not hardcoded.** Always fetch `/api/library/vocab` on init and build the facet panel from the response. This allows vocab additions without UI deploys.

2. **Facet counts are dynamic.** The Worker must compute counts for each facet value given current filters. This is the most complex part — see Worker endpoint spec above.

3. **D1 JSON array filtering.** Use `LIKE '%"ExactValue"%'` with double quotes included in the pattern. SQLite LIKE is case-insensitive but the values are canonical — this is fine.

4. **No pagination initially.** 415 cards is manageable client-side. Fetch all matching cards, render with FLIP animation. Add pagination if corpus grows past ~1000.

5. **Card IDs in DOM.** Every rendered card element needs `data-id="{{id}}"` for the FLIP animation to track positions across renders.

6. **Respect `sort_order` from vocab.** Period in particular has a meaningful chronological order — render facet values in `sort_order` sequence, not alphabetically.

7. **`Survey / Multiple` always last.** In Period and Form facets, `Survey / Multiple` should always appear at the bottom of the list regardless of count.

8. **Worker binding.** D1 binding name in Worker wrangler.toml should be `CARD_CATALOG_DB` binding to database ID `eb944e67-5fcc-4587-8fe1-eae2a9fe3476`.

---

## File Structure (suggested)

```
sapfm-card-catalog/
├── wrangler.toml
├── src/
│   └── index.ts          # Worker — all API endpoints
└── public/
    ├── index.html         # SPA shell
    ├── catalog.js         # Main app logic
    └── catalog.css        # Styles
```

Or integrate Worker endpoints into the existing `sapfm` Worker under `/api/library/` prefix.
