/**
 * SAPFM Embedding Pipeline Worker
 *
 * Reads content from all D1 databases, generates text embeddings via Workers AI
 * (BGE-base-en-v1.5, 768 dims), and upserts to the sapfm-catalog-vectors
 * Vectorize index.
 *
 * Endpoints:
 *   POST /embed/museum       — all 8 museum collections
 *   POST /embed/cards        — card catalog (429 cards)
 *   POST /embed/videos       — video chapters (455 chapters)
 *   POST /embed/all          — everything
 *   GET  /status             — index vector count
 *   GET  /health             — health check
 *
 * Each endpoint is idempotent (upsert). Safe to re-run.
 * Processes in batches to stay within Worker CPU limits.
 * Returns progress as it goes via streaming JSON.
 */

const AI_MODEL = "@cf/baai/bge-base-en-v1.5";
const EMBED_BATCH = 50;   // texts per AI call (model limit ~100, stay safe)
const UPSERT_BATCH = 100; // vectors per Vectorize upsert (API limit)

// ─── Text construction per source type ──────────────────────────────

function museumText(row, source) {
  const parts = [row.title];

  if (row.form_type || row.form_bucket) parts.push(row.form_type || row.form_bucket);
  if (row.maker_name) parts.push(`by ${row.maker_name}`);
  if (row.medium || row.technique || row.material || row.materials)
    parts.push(row.medium || row.technique || row.material || row.materials);
  if (row.culture) parts.push(row.culture);
  if (row.origin) parts.push(row.origin);
  if (row.date_display) parts.push(row.date_display);
  if (row.department) parts.push(row.department);
  if (row.description) parts.push(row.description.slice(0, 500));
  if (row.did_you_know) parts.push(row.did_you_know.slice(0, 300));

  return parts.filter(Boolean).join(". ");
}

function museumMeta(row, source, collection, idField) {
  const sourceId = String(row[idField] ?? row.id);
  const refId = `${source}:${sourceId}`;
  return {
    id: `ref:${refId}`,
    metadata: {
      ref_id: refId,
      source,
      record_type: "object",
      collection,
      title: (row.title || "").slice(0, 200),
      year: row.date_begin || 0,
      source_id: sourceId,
      url: row.collection_url || "",
    },
  };
}

function cardText(row) {
  const parts = [row.title];
  if (row.authors) {
    try { parts.push(`by ${JSON.parse(row.authors).join(", ")}`); } catch {}
  }
  if (row.source) parts.push(row.source);
  if (row.teaser) parts.push(row.teaser);
  if (row.description) parts.push(row.description.slice(0, 600));
  // Add facet terms as text for semantic matching
  for (const field of ["period", "form", "region", "topic"]) {
    if (row[field]) {
      try { parts.push(JSON.parse(row[field]).join(", ")); } catch {}
    }
  }
  return parts.filter(Boolean).join(". ");
}

function chapterText(row) {
  const parts = [];
  if (row.video_title) parts.push(row.video_title);
  if (row.title) parts.push(row.title);
  if (row.summary) parts.push(row.summary);
  // Include start of transcript for richer embedding (but not too much)
  if (row.chapter_transcript) parts.push(row.chapter_transcript.slice(0, 400));
  return parts.filter(Boolean).join(". ");
}

// ─── Embed + upsert pipeline ────────────────────────────────────────

async function embedAndUpsert(env, items) {
  // items: [{ id, metadata, text }]
  let embedded = 0;

  for (let i = 0; i < items.length; i += EMBED_BATCH) {
    const batch = items.slice(i, i + EMBED_BATCH);
    const texts = batch.map((it) => it.text);

    // Call Workers AI
    const aiResult = await env.AI.run(AI_MODEL, { text: texts });
    const vectors = aiResult.data;

    if (!vectors || vectors.length !== batch.length) {
      throw new Error(
        `AI returned ${vectors?.length ?? 0} vectors for ${batch.length} texts at offset ${i}`
      );
    }

    // Build Vectorize upsert payload
    const toUpsert = batch.map((it, j) => ({
      id: it.id,
      values: vectors[j],
      metadata: it.metadata,
    }));

    // Upsert in sub-batches of UPSERT_BATCH
    for (let u = 0; u < toUpsert.length; u += UPSERT_BATCH) {
      const uBatch = toUpsert.slice(u, u + UPSERT_BATCH);
      await env.VECTORIZE.upsert(uBatch);
    }

    embedded += batch.length;
  }

  return embedded;
}

// ─── Museum collection configs ──────────────────────────────────────

const MUSEUM_CONFIGS = [
  {
    name: "Met",
    binding: "DB_MET",
    source: "met_object",
    collection: "Metropolitan Museum of Art",
    idField: "id",
    query: `SELECT id, title, objectName, objectNameNorm AS form_type,
                   formBucket AS form_bucket, artistName AS maker_name,
                   medium, date AS date_display, dateBegin AS date_begin,
                   culture, department, country AS origin,
                   objectURL AS collection_url
            FROM furniture`,
  },
  {
    name: "Yale",
    binding: "DB_YALE",
    source: "yale_object",
    collection: "Yale University Art Gallery",
    idField: "source_id",
    query: `SELECT id, source_id, title, specific_form AS form_type,
                   form_bucket, maker_name, medium,
                   date_display, date_begin, place_primary AS origin,
                   canonical_url AS collection_url
            FROM furniture`,
  },
  {
    name: "Rijks",
    binding: "DB_RIJKS",
    source: "rijks_object",
    collection: "Rijksmuseum",
    idField: "rijks_id",
    query: `SELECT id, rijks_id, title, specific_form AS form_type,
                   form_bucket, maker_name, medium, date_display,
                   date_begin, description, collection_url
            FROM furniture`,
  },
  {
    name: "Cleveland",
    binding: "DB_CLEVELAND",
    source: "cleveland_object",
    collection: "Cleveland Museum of Art",
    idField: "cma_id",
    query: `SELECT id, cma_id, title, form_type, form_bucket,
                   maker_name, technique AS medium, culture, origin,
                   date_display, date_begin, description, did_you_know,
                   collection_url
            FROM furniture`,
  },
  {
    name: "Chicago",
    binding: "DB_CHICAGO",
    source: "chicago_object",
    collection: "Art Institute of Chicago",
    idField: "aic_id",
    query: `SELECT id, aic_id, title, form_type, form_bucket,
                   maker_name, medium, origin, date_display, date_begin,
                   collection_url
            FROM furniture`,
  },
  {
    name: "PMA",
    binding: "DB_PMA",
    source: "pma_object",
    collection: "Philadelphia Museum of Art",
    idField: "pma_id",
    query: `SELECT id, pma_id, title, form_type, form_bucket,
                   maker_name, medium, style, origin, date_display, date_begin,
                   collection_url
            FROM furniture`,
  },
  {
    name: "SLAM",
    binding: "DB_SLAM",
    source: "slam_object",
    collection: "St. Louis Art Museum",
    idField: "slam_id",
    query: `SELECT id, slam_id, title, form_type, form_bucket,
                   maker_name, material, culture, origin,
                   date_display, date_begin, collection_url
            FROM furniture`,
  },
  {
    name: "Winterthur",
    binding: "DB_WINTERTHUR",
    source: "winterthur_object",
    collection: "Winterthur Museum",
    idField: "recid",
    query: `SELECT id, recid, title, form_type, form_bucket,
                   maker_name, materials, techniques AS technique,
                   origin, date_display, date_begin, collection_url
            FROM furniture`,
  },
];

// ─── Route handlers ─────────────────────────────────────────────────

async function embedMuseum(env, configFilter) {
  const results = [];
  const configs = configFilter
    ? MUSEUM_CONFIGS.filter((c) => c.name.toLowerCase() === configFilter.toLowerCase())
    : MUSEUM_CONFIGS;

  for (const cfg of configs) {
    const db = env[cfg.binding];
    const rows = await db.prepare(cfg.query).all();
    const items = rows.results.map((row) => {
      const meta = museumMeta(row, cfg.source, cfg.collection, cfg.idField);
      return {
        id: meta.id,
        metadata: meta.metadata,
        text: museumText(row, cfg.source),
      };
    });

    const count = await embedAndUpsert(env, items);
    results.push({ source: cfg.name, rows: rows.results.length, embedded: count });
  }

  return results;
}

async function embedCards(env) {
  const rows = await env.DB_CATALOG.prepare(
    `SELECT * FROM library_cards WHERE status = 'approved'`
  ).all();

  const items = rows.results.map((row) => ({
    id: `card:${row.id}`,
    metadata: {
      ref_id: `card:${row.id}`,
      source: row.source || "card_catalog",
      record_type: "card_catalog",
      collection: "SAPFM Card Catalog",
      title: (row.title || "").slice(0, 200),
      year: row.year || 0,
      url: row.view_url || "",
    },
    text: cardText(row),
  }));

  const count = await embedAndUpsert(env, items);
  return [{ source: "Card Catalog", rows: rows.results.length, embedded: count }];
}

async function embedVideos(env) {
  // Join chapters with video title
  const rows = await env.DB_SAPFM.prepare(
    `SELECT vc.chapter_id, vc.title, vc.summary, vc.chapter_transcript,
            vc.start_seconds, v.title AS video_title, v.slug AS video_slug
     FROM video_chapter vc
     JOIN video v ON vc.video_id = v.video_id`
  ).all();

  const items = rows.results.map((row) => ({
    id: `video_chapter:${row.chapter_id}`,
    metadata: {
      ref_id: `video_chapter:${row.chapter_id}`,
      source: `SAPFM Video: ${(row.video_title || "").slice(0, 100)}`,
      record_type: "video_chapter",
      collection: "SAPFM",
      title: (row.title || "").slice(0, 200),
      year: 0,
      video_slug: row.video_slug || "",
      start_seconds: row.start_seconds || 0,
    },
    text: chapterText(row),
  }));

  const count = await embedAndUpsert(env, items);
  return [{ source: "Video Chapters", rows: rows.results.length, embedded: count }];
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (path === "/health") {
      return json({ status: "ok", service: "sapfm-embedder" });
    }

    if (path === "/search" && request.method === "GET") {
      const q = url.searchParams.get("q");
      const topK = parseInt(url.searchParams.get("k") || "10");
      const typeFilter = url.searchParams.get("type"); // object, card_catalog, video_chapter
      if (!q) return json({ error: "?q= required" }, 400);

      try {
        const aiResult = await env.AI.run(AI_MODEL, { text: [q] });
        const queryVec = aiResult.data[0];

        const opts = {
          topK: Math.min(topK, 50),
          returnMetadata: "all",
          returnValues: false,
        };
        if (typeFilter) opts.filter = { record_type: typeFilter };

        const results = await env.VECTORIZE.query(queryVec, opts);
        return json({
          query: q,
          count: results.matches.length,
          matches: results.matches.map((m) => ({
            id: m.id,
            score: m.score,
            ...m.metadata,
          })),
        });
      } catch (e) {
        return json({ error: e.message }, 500);
      }
    }

    if (path === "/status") {
      try {
        const vec = new Array(768).fill(0.01);
        const r = await env.VECTORIZE.query(vec, { topK: 1, returnMetadata: "none" });
        return json({ index: "sapfm-catalog-vectors", vectors: "query works", note: "Use wrangler vectorize info for exact count" });
      } catch (e) {
        return json({ error: e.message }, 500);
      }
    }

    // All embed endpoints require POST
    if (request.method !== "POST") {
      return json({
        endpoints: [
          "POST /embed/museum          — all 8 museum collections",
          "POST /embed/museum?only=Met  — single museum",
          "POST /embed/cards            — card catalog",
          "POST /embed/videos           — video chapters",
          "POST /embed/all              — everything",
          "GET  /status                 — index status",
          "GET  /health                 — health check",
        ],
      });
    }

    try {
      let results = [];

      if (path === "/embed/museum") {
        const only = url.searchParams.get("only");
        results = await embedMuseum(env, only);
      } else if (path === "/embed/cards") {
        results = await embedCards(env);
      } else if (path === "/embed/videos") {
        results = await embedVideos(env);
      } else if (path === "/embed/all") {
        const museum = await embedMuseum(env);
        const cards = await embedCards(env);
        const videos = await embedVideos(env);
        results = [...museum, ...cards, ...videos];
      } else {
        return json({ error: "Unknown endpoint" }, 404);
      }

      const total = results.reduce((s, r) => s + r.embedded, 0);
      return json({ success: true, total_embedded: total, sources: results });
    } catch (e) {
      return json({ error: e.message, stack: e.stack }, 500);
    }
  },
};
