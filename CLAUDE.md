# SAPFM Card Catalog — C:\dev\card-catalog\

Human-curated reference index for the SAPFM Member Desktop. Part of the broader Members Desktop alongside the Bench.

## Cloudflare Resources

| Resource | Name | ID |
|----------|------|----|
| Account | SAPFM | ebe622eaa5b3a3581cf5664272f26f30 |
| D1 Database | card-catalog | eb944e67-5fcc-4587-8fe1-eae2a9fe3476 |
| Worker | library-api | (deploy via `npm run deploy` in worker/) |
| Worker | sapfm-catalog-api | Serves Bench UI (deployed separately) |
| Worker | sapfm-embedder | Embedding pipeline + semantic search |
| Vectorize | sapfm-catalog-vectors | 9,039 vectors, 768-dim, cosine |

## Project Structure

```
card-catalog/
  worker/           ← library-api Worker (TypeScript) — card catalog CRUD
    src/index.ts    ← All API endpoints
    wrangler.toml
  embedder/         ← sapfm-embedder Worker (JS) — embedding pipeline + search
    src/index.js    ← Embed + search endpoints, binds all 10 D1 databases
    wrangler.toml   ← AI + Vectorize + all D1 bindings
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
  viewer/
    card-catalog-explorer.html  ← Standalone HTML browse UI
  seed-cards.json          ← Source JSON for pilot batch (Chipstone 1996)
  chipstone-vocabulary.md  ← Controlled vocabulary reference
  card-catalog-schema.md   ← Schema + endpoint spec
```

## API Base URL

Production: `https://library-api.sapfm-admin.workers.dev`
Local dev:  `http://localhost:8787` (wrangler dev)

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/library/cards | None | List cards — faceted filter + text search |
| GET | /api/library/cards/:id | None | Single card detail |
| GET | /api/library/vocab | None | All vocab terms grouped by dimension |
| POST | /api/library/submissions | Member JWT | Submit a new card |
| GET | /api/library/submissions/:id | Member JWT | Own submission status |
| GET | /api/library/admin/submissions | Admin JWT | List submission queue |
| PATCH | /api/library/admin/submissions/:id | Admin JWT | Approve / reject / revise |
| PUT | /api/library/admin/cards/:id | Admin JWT | Edit approved card |
| POST | /api/library/admin/vocab | Admin JWT | Add vocab term |
| GET | /api/health | None | Health check |

## Filter Logic

- AND across dimensions, OR within a dimension
- `period`, `form`, `region`, `topic` — JSON array fields, filtered via `json_each()`
- `source_key`, `card_type` — direct column match
- `q` — LIKE search on title, description, makers

## Auth

Same JWT pattern as bench-api (HS256, Web Crypto):
- `Bearer DEV` works in dev if `DEV_BYPASS` secret is set
- `membership_type: "admin"` required for admin routes
- Set secrets: `wrangler secret put JWT_SECRET` (from WordPress Simple-JWT-Login)

## First-Time Setup

```bash
cd worker && npm install

# Apply migrations
wrangler d1 execute card-catalog --file=../sql/01_create_tables.sql
wrangler d1 execute card-catalog --file=../sql/02_seed_vocab.sql
wrangler d1 execute card-catalog --file=../sql/03_seed_cards.sql

# Set auth secret
wrangler secret put JWT_SECRET

# Deploy
npm run deploy
```

## Controlled Vocabulary

Dimensions: `period`, `form`, `region`, `topic`, `source_key`, `card_type`

All values defined in `chipstone-vocabulary.md` and seeded in `02_seed_vocab.sql`.
To add a term: `POST /api/library/admin/vocab` (admin) or INSERT into `vocab_terms`.
Extend `chipstone-vocabulary.md` to match — it is the editorial reference.

## Card Entry Flow

1. Staff seed via SQL (current approach for Chipstone corpus)
2. Member submits → `submissions` table (status: pending)
3. Admin reviews in moderation queue → approves → writes to `library_cards`

## Corpus Status (2026-04-11)

### Loaded & Complete — 429 cards total
- **Chipstone**: 187 articles + 120 reviews = 307 cards (1993–2023), all metadata fixed
- **Met Museum**: 44 cards — 8 publications + 4 bulletin essays (Heckscher, Davidson, Tracy, Safford, Walk, Phyfe, Lannuier, Rococo)
- **MESDA Journal**: 78 articles (all 10 batches, 1996–2025) — web-scraped from mesdajournal.org

### Next Corpus Steps
- Winterthur trade catalogs — Internet Archive, public domain
- American Period Furniture (SAPFM's own journal)
- Additional Met Bulletin essays

## Semantic Search (2026-04-11)

The `sapfm-embedder` Worker provides semantic search across all SAPFM content:

- **Model:** `@cf/baai/bge-base-en-v1.5` (Workers AI) — 768-dim text embeddings
- **Index:** `sapfm-catalog-vectors` on Cloudflare Vectorize (cosine metric)
- **9,039 vectors:** 8,155 museum objects + 429 card catalog + 455 video chapters
- **Search endpoint:** `GET /search?q=...&k=20&type=object|card_catalog|video_chapter`
- **Re-embed:** `POST /embed/all` (or `/embed/museum`, `/embed/cards`, `/embed/videos`)
- Idempotent — safe to re-run when content changes
- Deployed at `https://sapfm-embedder.sapfm-admin.workers.dev`
- UI: Search page in Members Desktop at `/search`

## Viewer

`viewer/card-catalog-explorer.html` — standalone HTML browse UI, points to production API.
Card Catalog is also integrated as a React page in the Members Desktop (`/card-catalog`).
