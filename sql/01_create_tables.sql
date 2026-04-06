-- SAPFM Card Catalog — Migration 01: Create tables
-- Run against D1: card-catalog (eb944e67-5fcc-4587-8fe1-eae2a9fe3476)

CREATE TABLE IF NOT EXISTS library_cards (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  title            TEXT    NOT NULL,
  authors          TEXT    NOT NULL DEFAULT '[]',   -- JSON array of strings
  year             INTEGER,
  source           TEXT,                            -- Human label: "Chipstone Foundation — American Furniture"
  source_key       TEXT,                            -- Machine key: chipstone | met | winterthur | mesda | etc.
  card_type        TEXT    NOT NULL DEFAULT 'article', -- article | chapter | book | catalog
  parent_id        INTEGER REFERENCES library_cards(id),
  page_start       INTEGER,
  page_end         INTEGER,
  edition          TEXT,
  description      TEXT    NOT NULL,               -- Original SAPFM prose. NOT reproduced source text.
  period           TEXT    NOT NULL DEFAULT '[]',  -- JSON array — controlled vocab
  form             TEXT    NOT NULL DEFAULT '[]',  -- JSON array — controlled vocab
  region           TEXT    NOT NULL DEFAULT '[]',  -- JSON array — controlled vocab
  topic            TEXT    NOT NULL DEFAULT '[]',  -- JSON array — controlled vocab
  makers           TEXT    NOT NULL DEFAULT '[]',  -- JSON array of craftsman names
  is_free          INTEGER NOT NULL DEFAULT 1,     -- 1 = freely readable online, 0 = citation only
  view_url         TEXT,
  download_url     TEXT,
  contributed_by   TEXT,                           -- PMPro member ID if member-contributed
  contributor_name TEXT,
  status           TEXT    NOT NULL DEFAULT 'approved',
  created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_cards_source_key ON library_cards(source_key);
CREATE INDEX IF NOT EXISTS idx_cards_year       ON library_cards(year);
CREATE INDEX IF NOT EXISTS idx_cards_status     ON library_cards(status);
CREATE INDEX IF NOT EXISTS idx_cards_parent_id  ON library_cards(parent_id);

-- -------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS submissions (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  entity_type    TEXT    NOT NULL DEFAULT 'library_card',
  entity_id      INTEGER,
  payload        TEXT    NOT NULL,   -- JSON blob matching library_cards fields
  submitted_by   TEXT    NOT NULL,
  submitter_name TEXT    NOT NULL,
  status         TEXT    NOT NULL DEFAULT 'pending', -- pending | approved | rejected | revision_requested
  reviewer_notes TEXT,
  reviewed_by    TEXT,
  created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_submissions_status       ON submissions(status);
CREATE INDEX IF NOT EXISTS idx_submissions_entity_type  ON submissions(entity_type);
CREATE INDEX IF NOT EXISTS idx_submissions_submitted_by ON submissions(submitted_by);

-- -------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS vocab_terms (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  dimension  TEXT    NOT NULL, -- period | form | region | topic | source_key | card_type
  value      TEXT    NOT NULL,
  label      TEXT    NOT NULL,
  notes      TEXT,
  sort_order INTEGER NOT NULL DEFAULT 0,
  UNIQUE(dimension, value)
);

CREATE INDEX IF NOT EXISTS idx_vocab_dimension ON vocab_terms(dimension);
