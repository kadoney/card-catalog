# SAPFM Card Catalog — C:\dev\card-catalog\

Human-curated reference index for the SAPFM Member Desktop. Part of the broader Members Desktop alongside the Bench.

## Cloudflare Resources

| Resource | Name | ID |
|----------|------|----|
| Account | SAPFM | ebe622eaa5b3a3581cf5664272f26f30 |
| D1 Database | card-catalog | eb944e67-5fcc-4587-8fe1-eae2a9fe3476 |
| Worker | sapfm-catalog-api | **Live catalog API** — serves the Bench UI; source at `/c/dev/sapfm-catalog-api/` (separate repo, deployed separately) |
| Worker | sapfm-embedder | Embedding pipeline + semantic search — **source at `sapfm-platform/workers/sapfm-embedder/`** (separate repo, deployed via its CI) |
| Vectorize | sapfm-catalog-vectors | 9,039 deployed vectors (per workspace CLAUDE.md 2026-04-30); 768-dim, cosine — re-embed when corpus grows |

## Project Structure

```
card-catalog/
  scripts/          ← ETL pipelines (Python) + maintenance tools
    chipstone_etl.py
    met_catalog_etl.py
    mesda_website_scraper.py
    vectorize_audit.py      ← Index audit/cleanup tool
    vectorize_cleanup.js    ← Temporary cleanup Worker (used once)
  sql/
    01_create_tables.sql   ← library_cards, submissions, vocab_terms
    02_seed_vocab.sql      ← Full controlled vocabulary (all 5 dimensions)
    03_seed_cards.sql      ← 8 Chipstone 1996 pilot cards
  ui/               ← Card Catalog React UI (integrated into Bench)
  seed-cards.json          ← Source JSON for pilot batch (Chipstone 1996)
  chipstone-vocabulary.md  ← Controlled vocabulary reference
  card-catalog-schema.md   ← Schema + endpoint spec
```

## API

The live card-catalog API is **`sapfm-catalog-api`** (separate repo at `/c/dev/sapfm-catalog-api/`) —
it serves the Members Desktop Card Catalog UI via `publications.sapfm.org` and the `/catalog-api`
proxy, reading this same `card-catalog` D1.

> **`library-api` decommissioned 2026-06-04.** The old `worker/` in this repo (the `library-api`
> Worker, `/api/library/*`) was never deployed and was superseded by `sapfm-catalog-api`. Source
> removed; recoverable from git history. Its member card-submission + admin-moderation endpoints
> were never wired to a UI — if card submission is built later, it belongs in `sapfm-catalog-api`.

## Filter Logic

- AND across dimensions, OR within a dimension
- `period`, `form`, `region`, `topic` — JSON array fields, filtered via `json_each()`
- `source_key`, `card_type` — direct column match
- `q` — LIKE search on title, description, makers

## Corpus D1 setup

```bash
# Apply schema + seed to the card-catalog D1. The corpus lives here; the live
# API (auth, endpoints) is sapfm-catalog-api in its own repo.
wrangler d1 execute card-catalog --file=sql/01_create_tables.sql
wrangler d1 execute card-catalog --file=sql/02_seed_vocab.sql
wrangler d1 execute card-catalog --file=sql/03_seed_cards.sql
```

## Controlled Vocabulary

Dimensions: `period`, `form`, `region`, `topic`, `source_key`, `card_type`

All values defined in `chipstone-vocabulary.md` and seeded in `02_seed_vocab.sql`.
To add a term: INSERT into `vocab_terms` (or via a sapfm-catalog-api admin route if/when one is added).
Extend `chipstone-vocabulary.md` to match — it is the editorial reference.

## Card Entry Flow

1. Staff seed via SQL (current approach for the whole corpus)
2. Member-submission + moderation flow lived only in the decommissioned `library-api` and is **not
   currently wired to any UI**. The `submissions` table still exists in D1; rebuild the flow in
   `sapfm-catalog-api` if member contribution is wanted.

## Corpus Status

> Snapshot taken 2026-04-14; counts below match workspace `CLAUDE.md` as of 2026-05-17. Verify via D1 query before citing.

### Loaded & Complete — 2,269 via the ETL batches below (live D1 total: 2,428 as of 2026-06-12)
- **Chipstone**: 307 cards (1993–2023)
- **Met Museum**: 44 cards — 8 publications + 4 bulletin essays
- **MESDA Journal**: 78 articles (1996–2025)
- **Yale University Library**: 1,817 records — Open Library enriched (455 with covers/ISBNs/publishers)
- **Public Domain Books**: 23 cards (6 books + 17 chapters, PDFs in R2 publications/books/)
- **APF**: empty — authorization pending

### Enrichment (2026-04-14)
- Language detection: 1,343 English, 407 non-English; 362 translated via MyMemory
- English-only toggle (default on) in UI
- Admin hidden toggle on detail cards

### Next Corpus Steps
- APF articles (authorization question pending)
- Winterthur trade catalogs — Internet Archive, public domain
- 45 non-English titles still untranslated (API limit)

## Semantic Search

The `sapfm-embedder` Worker provides semantic search across all SAPFM content:

- **Model:** `@cf/baai/bge-base-en-v1.5` (Workers AI) — 768-dim text embeddings
- **Index:** `sapfm-catalog-vectors` on Cloudflare Vectorize (cosine metric)
- **Source pool:** 8,186 museum objects + 2,269 card catalog + 455 video chapters = 10,910 candidates; **9,039 currently deployed** as of the last `/embed/all` run (per workspace CLAUDE.md). Run `vectorize_audit.py` to reconcile.
- **Search endpoint:** `GET /search?q=...&k=20&type=object|card_catalog|video_chapter`
- **Re-embed:** `POST /embed/all` (or `/embed/museums`, `/embed/cards`, `/embed/videos`) — gated by the `EMBED_TRIGGER_SECRET` header
- Idempotent — safe to re-run when content changes
- **Source:** `sapfm-platform/workers/sapfm-embedder/` (the stale duplicate that used to live in this repo's `embedder/` was removed 2026-06-04). Deployed at `https://sapfm-embedder.sapfm-admin.workers.dev`
- UI: Search page in Members Desktop at `/search`

## Viewer

Card Catalog is integrated as a React page in the Members Desktop (`/card-catalog`), served by
`sapfm-catalog-api`. (The old standalone `viewer/card-catalog-explorer.html` was removed with the
`library-api` decommission on 2026-06-04.)
