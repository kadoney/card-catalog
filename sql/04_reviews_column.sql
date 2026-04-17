-- Migration 04: Add reviews JSON column to library_cards
-- Part of phase 2 of SAPFM content migration.
-- Book reviews ported from sapfm.org Book & DVD Reviews category attach to
-- the matching library card via this column. Using a JSON column rather
-- than a separate table because the feature is still evolving; easy to
-- extract later if review browse/search earns its own surface.
-- Each review: {reviewer, review_date, body_html, source_url}

ALTER TABLE library_cards ADD COLUMN reviews TEXT NOT NULL DEFAULT '[]';
