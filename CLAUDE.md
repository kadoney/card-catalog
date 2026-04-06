# SAPFM Card Catalog — C:\dev\card-catalog\

Human-curated reference index for the SAPFM Member Desktop. Part of the broader Members Desktop alongside the Bench.

## Cloudflare Resources

| Resource | Name | ID |
|----------|------|----|
| Account | SAPFM | ebe622eaa5b3a3581cf5664272f26f30 |
| D1 Database | card-catalog | eb944e67-5fcc-4587-8fe1-eae2a9fe3476 |
| Worker | library-api | (deploy via `npm run deploy` in worker/) |

## Project Structure

```
card-catalog/
  worker/           ← Cloudflare Worker (TypeScript)
    src/index.ts    ← All API endpoints
    wrangler.toml
    package.json
    tsconfig.json
  sql/
    01_create_tables.sql   ← library_cards, submissions, vocab_terms
    02_seed_vocab.sql      ← Full controlled vocabulary (all 5 dimensions)
    03_seed_cards.sql      ← 8 Chipstone 1996 pilot cards
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

## Next Corpus Steps

- Remaining Chipstone issues 1997–2023 (~300 cards) — scrape TOC, draft descriptions
- Met Publications American Wing titles — chapter-level cards, free PDF
- Winterthur trade catalogs — Internet Archive, public domain
- MESDA Journal — freely online

## Viewer

`viewer/card-catalog-explorer.html` — standalone, no build, points to production API.
For local testing, change `API` const to `http://localhost:8787`.
Will be deployed to Bench Pages as `public/card-catalog.html`.
