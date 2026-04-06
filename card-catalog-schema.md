# SAPFM Card Catalog — Schema & Endpoints

Part of the SAPFM Member Desktop / Cloudflare Worker stack.  
Follow existing Worker patterns for auth, D1 binding, error handling.

---

## D1 Tables

### `library_cards`

Canonical card table. One row per indexable unit of scholarship.  
Cards enter via `submissions` table — never written directly except by seed script and moderation approval.

```sql
CREATE TABLE IF NOT EXISTS library_cards (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  title            TEXT    NOT NULL,
  authors          TEXT    NOT NULL DEFAULT '[]',  -- JSON array of strings
  year             INTEGER,
  source           TEXT,                           -- Human label: "Chipstone Foundation — American Furniture"
  source_key       TEXT,                           -- Machine key: "chipstone" | "met" | "winterthur" | "mesda" | "pma" | "cleveland" | "internet_archive" | "member"
  card_type        TEXT    NOT NULL DEFAULT 'article', -- "article" | "chapter" | "book" | "catalog"
  parent_id        INTEGER REFERENCES library_cards(id), -- chapter -> book parent
  page_start       INTEGER,
  page_end         INTEGER,
  edition          TEXT,
  description      TEXT    NOT NULL,              -- Original SAPFM prose. NOT reproduced source text.
  period           TEXT    NOT NULL DEFAULT '[]', -- JSON array — controlled vocab
  form             TEXT    NOT NULL DEFAULT '[]', -- JSON array — controlled vocab
  region           TEXT    NOT NULL DEFAULT '[]', -- JSON array — controlled vocab
  topic            TEXT    NOT NULL DEFAULT '[]', -- JSON array — controlled vocab
  makers           TEXT    NOT NULL DEFAULT '[]', -- JSON array of craftsman names
  is_free          INTEGER NOT NULL DEFAULT 1,    -- 1 = freely readable online, 0 = citation only
  view_url         TEXT,                          -- Direct link to article/chapter (HTML or PDF viewer)
  download_url     TEXT,                          -- Direct PDF download if available
  contributed_by   TEXT,                          -- PMPro member ID if member-contributed, NULL if staff
  contributor_name TEXT,                          -- Display name for attribution on card detail
  status           TEXT    NOT NULL DEFAULT 'approved',
  created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_cards_source_key ON library_cards(source_key);
CREATE INDEX IF NOT EXISTS idx_cards_year       ON library_cards(year);
CREATE INDEX IF NOT EXISTS idx_cards_status     ON library_cards(status);
CREATE INDEX IF NOT EXISTS idx_cards_parent_id  ON library_cards(parent_id);
```

---

### `submissions`

Member-submitted card candidates. On approval, writes to `library_cards` and updates status here.  
Same table handles all entity types — extensible beyond library cards.

```sql
CREATE TABLE IF NOT EXISTS submissions (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  entity_type    TEXT    NOT NULL DEFAULT 'library_card', -- extensible: "museum_show", "publication", etc.
  entity_id      INTEGER,                -- NULL = new card. Populated = correction to existing card.
  payload        TEXT    NOT NULL,       -- JSON blob matching library_cards fields (minus system fields)
  submitted_by   TEXT    NOT NULL,       -- PMPro member ID
  submitter_name TEXT    NOT NULL,       -- Display name captured at submit time
  status         TEXT    NOT NULL DEFAULT 'pending', -- "pending" | "approved" | "rejected" | "revision_requested"
  reviewer_notes TEXT,                   -- Editor feedback, visible to submitter
  reviewed_by    TEXT,                   -- Admin user ID
  created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_submissions_status      ON submissions(status);
CREATE INDEX IF NOT EXISTS idx_submissions_entity_type ON submissions(entity_type);
CREATE INDEX IF NOT EXISTS idx_submissions_submitted_by ON submissions(submitted_by);
```

---

### `vocab_terms`

Managed vocabulary table. Source of truth for browse UI filter options.  
Avoids hardcoding vocabulary in Worker or UI — adding a term is a data change, not a code change.

```sql
CREATE TABLE IF NOT EXISTS vocab_terms (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  dimension  TEXT    NOT NULL, -- "period" | "form" | "region" | "topic" | "source_key" | "card_type"
  value      TEXT    NOT NULL, -- Exact string used in library_cards JSON arrays
  label      TEXT    NOT NULL, -- Display label (usually same as value)
  notes      TEXT,             -- Editorial notes on usage
  sort_order INTEGER NOT NULL DEFAULT 0,
  UNIQUE(dimension, value)
);

CREATE INDEX IF NOT EXISTS idx_vocab_dimension ON vocab_terms(dimension);
```

Seed from `chipstone-vocabulary.md`. All values in that file should have a corresponding row here.

---

## Worker Endpoints

Base path: `/api/library/`  
Auth: PMPro JWT for member routes. Admin token for moderation routes.  
Follow existing SAPFM Worker auth pattern — do not invent new auth.

### Public / Member

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/library/cards` | None | List cards. Query params: `period`, `form`, `region`, `topic`, `source_key`, `card_type`, `q` (text search on title + description + makers), `limit`, `offset` |
| `GET` | `/api/library/cards/:id` | None | Single card detail including parent if chapter |
| `GET` | `/api/library/vocab` | None | All vocab terms grouped by dimension — used to populate filter UI |
| `POST` | `/api/library/submissions` | Member | Submit a new card. Body: payload JSON. Returns submission ID. |
| `GET` | `/api/library/submissions/:id` | Member (own) | Check status of own submission |

### Admin / Moderation

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/library/admin/submissions` | Admin | List submissions. Filter by `status`, `entity_type`. |
| `PATCH` | `/api/library/admin/submissions/:id` | Admin | Approve → writes to `library_cards`. Reject or request revision → updates status + reviewer_notes. |
| `PUT` | `/api/library/admin/cards/:id` | Admin | Edit an existing approved card. |
| `POST` | `/api/library/admin/vocab` | Admin | Add vocab term. |

---

## Card List Response Shape

```json
{
  "cards": [
    {
      "id": 1,
      "title": "Seventeenth-Century Joinery from Braintree, Massachusetts...",
      "authors": ["Peter Follansbee", "John D. Alexander"],
      "year": 1996,
      "source": "Chipstone Foundation — American Furniture",
      "source_key": "chipstone",
      "card_type": "article",
      "description": "A detailed technical study...",
      "period": ["Early Colonial", "William & Mary"],
      "form": ["Case pieces"],
      "region": ["New England"],
      "topic": ["Construction / Technique", "Regional Style", "Biography / Shops"],
      "makers": ["William Savell Sr.", "William Savell Jr.", "John Savell"],
      "is_free": 1,
      "view_url": "https://chipstone.org/article.php/222/...",
      "download_url": null,
      "contributor_name": null
    }
  ],
  "total": 8,
  "limit": 20,
  "offset": 0
}
```

---

## Filtering Logic

All facet filters are **AND** between dimensions, **OR** within a dimension.  
Example: `period=Chippendale&region=Philadelphia&region=New+York` returns cards tagged Chippendale AND (Philadelphia OR New York).

Since period/form/region/topic are stored as JSON arrays in SQLite, use `json_each()` for filtering:

```sql
SELECT DISTINCT c.*
FROM library_cards c,
     json_each(c.period) p,
     json_each(c.region) r
WHERE p.value IN ('Chippendale')
  AND r.value IN ('Philadelphia', 'New York City')
  AND c.status = 'approved'
ORDER BY c.year DESC;
```

Text search (`q`) queries: `title LIKE '%' || ? || '%' OR description LIKE '%' || ? || '%'`  
For better text search later: consider D1 FTS5 virtual table on title + description + makers.

---

## Submission Approval Flow

```
Member submits → submissions row (status: pending)
      ↓
Admin reviews in moderation queue
      ↓
  ┌─────────────────────────────────────────────────┐
  │ Approve                                          │
  │   1. INSERT into library_cards from payload      │
  │   2. Set contributed_by, contributor_name        │
  │   3. UPDATE submissions SET status = 'approved'  │
  └─────────────────────────────────────────────────┘
  ┌─────────────────────────────────────────────────┐
  │ Reject / Revision requested                      │
  │   1. UPDATE submissions SET status, reviewer_notes│
  │   2. No write to library_cards                   │
  └─────────────────────────────────────────────────┘
```

---

## Notes for Coding Session

- D1 binding name: match existing SAPFM Worker convention (check `wrangler.toml`)
- JSON array fields: store as TEXT, parse/serialize in Worker. Do not use D1 JSON functions for writes.
- `vocab_terms` table drives all filter UI — seed it before testing browse.
- Seed cards in `seed-cards.json` — run seed script against D1 before testing.
- Attribution display: if `contributor_name` is non-null, show "Contributed by [name]" on card detail.
- Member Desktop UI pattern: three-panel layout (filter sidebar / card list / card detail). Follow existing Desktop component conventions.
