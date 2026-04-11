/**
 * Vectorize Index Cleanup Worker
 *
 * Deploy temporarily to audit and clean the sapfm-catalog-vectors index.
 *
 * Endpoints:
 *   GET /audit          - Count by source/type, find duplicates
 *   GET /duplicates     - List all bare-numeric card IDs (duplicates of card:N)
 *   GET /junk-marc      - List non-furniture MARC records
 *   POST /delete        - Delete vector IDs (JSON array body)
 *   POST /fix-metadata  - Fix metadata on existing vectors [{id, metadata}]
 *   GET /stats          - Quick index stats
 */

const FURNITURE_KEYWORDS = [
  "furniture", "cabinet", "chair", "table", "desk", "chest", "clock",
  "highboy", "lowboy", "settee", "sofa", "bed", "cupboard", "sideboard",
  "secretary", "bookcase", "wardrobe", "armoire", "commode", "bureau",
  "woodwork", "joinery", "carving", "veneer", "marquetry", "inlay",
  "upholster", "cabinetmak", "chairmaker", "joiners", "turners",
  "chippendale", "hepplewhite", "sheraton", "phyfe", "seymour",
  "townsend", "goddard", "savery", "affleck", "randolph",
  "queen anne", "federal", "colonial", "windsor", "shaker",
  "decorative arts", "american wing", "antique",
  "period furniture", "early american",
];

function isFurnitureRelated(title) {
  if (!title) return false;
  const lower = title.toLowerCase();
  return FURNITURE_KEYWORDS.some(kw => lower.includes(kw));
}

async function exhaustiveScan(env, seedCount = 30, topK = 50) {
  const allEntries = new Map();

  // Run queries in parallel batches of 5 to stay within CPU limits
  for (let batch = 0; batch < seedCount; batch += 5) {
    const promises = [];
    for (let s = batch; s < Math.min(batch + 5, seedCount); s++) {
      const vec = new Array(768).fill(0).map((_, i) =>
        Math.sin(i * (s * 0.37 + 0.1)) * Math.cos(i * 0.02 * s + s * 0.5) * 0.5
      );
      promises.push(env.VECTORIZE.query(vec, {
        topK,
        returnMetadata: "all",
        returnValues: false,
      }));
    }
    const results = await Promise.all(promises);
    for (const r of results) {
      for (const m of r.matches) {
        if (!allEntries.has(m.id)) {
          allEntries.set(m.id, m.metadata || {});
        }
      }
    }
  }

  return allEntries;
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

    if (path === "/stats") {
      try {
        const vec = new Array(768).fill(0.1);
        const r = await env.VECTORIZE.query(vec, { topK: 1, returnMetadata: "none" });
        return json({ count: r.count, matches: r.matches?.length, note: "Use /audit for full breakdown" });
      } catch (e) {
        return json({ error: e.message, stack: e.stack, bindings: Object.keys(env) }, 500);
      }
    }

    if (path === "/test") {
      try {
        const vec = new Array(768).fill(0).map((_, i) => Math.sin(i * 0.1) * 0.5);
        const r = await env.VECTORIZE.query(vec, { topK: 5, returnMetadata: "all", returnValues: false });
        return json({ matches: r.matches });
      } catch (e) {
        return json({ error: e.message, stack: e.stack }, 500);
      }
    }

    if (path === "/audit") {
      try {
      const seeds = parseInt(url.searchParams.get("seeds") || "30");
      const entries = await exhaustiveScan(env, seeds);

      const bySource = {};
      const byType = {};
      const bareNumeric = [];
      const prefixedCards = new Set();
      const junkMarc = [];
      const goodMarc = [];
      const videoChaptersToFix = [];

      for (const [id, meta] of entries) {
        const src = meta.source || "unknown";
        const typ = meta.record_type || "unknown";
        bySource[src] = (bySource[src] || 0) + 1;
        byType[typ] = (byType[typ] || 0) + 1;

        // Track bare numeric IDs
        if (/^\d+$/.test(id)) {
          bareNumeric.push(id);
        }
        if (id.startsWith("card:")) {
          prefixedCards.add(id);
        }

        // Track non-furniture MARC
        if (src.startsWith("yale_marc")) {
          if (isFurnitureRelated(meta.title)) {
            goodMarc.push({ id, title: meta.title });
          } else {
            junkMarc.push({ id, title: meta.title });
          }
        }

        // Track video chapters with wrong collection
        if (typ === "video_chapter" && meta.collection !== "SAPFM") {
          videoChaptersToFix.push({ id, collection: meta.collection });
        }
      }

      // Check which bare IDs are confirmed duplicates
      const confirmedDupes = bareNumeric.filter(id => prefixedCards.has(`card:${id}`));

      return json({
        total_in_index: 11285,
        sampled: entries.size,
        coverage_pct: ((entries.size / 11285) * 100).toFixed(1) + "%",
        by_record_type: Object.entries(byType).sort((a, b) => b[1] - a[1]),
        by_source_top_30: Object.entries(bySource).sort((a, b) => b[1] - a[1]).slice(0, 30),
        duplicates: {
          bare_numeric_ids: bareNumeric.length,
          confirmed_card_dupes: confirmedDupes.length,
          ids: bareNumeric,
        },
        yale_marc: {
          total_sampled: goodMarc.length + junkMarc.length,
          furniture_related: goodMarc.length,
          non_furniture: junkMarc.length,
          junk_ids: junkMarc.map(j => j.id),
          junk_sample: junkMarc.slice(0, 10).map(j => ({ id: j.id, title: j.title })),
        },
        video_metadata_fixes_needed: videoChaptersToFix.length,
      });
      } catch (e) {
        return json({ error: e.message, stack: e.stack }, 500);
      }
    }

    if (path === "/marc-audit") {
      // Targeted scan for yale_marc records only, using varied queries
      try {
        const allMarc = new Map();
        const seeds = parseInt(url.searchParams.get("seeds") || "50");

        for (let batch = 0; batch < seeds; batch += 5) {
          const promises = [];
          for (let s = batch; s < Math.min(batch + 5, seeds); s++) {
            const vec = new Array(768).fill(0).map((_, i) =>
              Math.sin(i * (s * 0.17 + 0.3)) * Math.cos(i * 0.05 * s + s) * 0.4
            );
            promises.push(env.VECTORIZE.query(vec, {
              topK: 50,
              returnMetadata: "all",
              returnValues: false,
              filter: { source: "yale_marc" },
            }));
          }
          const results = await Promise.all(promises);
          for (const r of results) {
            for (const m of r.matches) {
              if (!allMarc.has(m.id)) {
                allMarc.set(m.id, m.metadata || {});
              }
            }
          }
        }

        const junk = [];
        const good = [];
        for (const [id, meta] of allMarc) {
          if (isFurnitureRelated(meta.title)) {
            good.push({ id, title: meta.title });
          } else {
            junk.push({ id, title: meta.title });
          }
        }

        return json({
          total_marc_sampled: allMarc.size,
          furniture_related: good.length,
          non_furniture: junk.length,
          junk_ids: junk.map(j => j.id),
          junk_titles_sample: junk.slice(0, 20).map(j => j.title),
        });
      } catch (e) {
        return json({ error: e.message, stack: e.stack }, 500);
      }
    }

    if (path === "/delete" && request.method === "POST") {
      const ids = await request.json();
      if (!Array.isArray(ids) || ids.length === 0) {
        return json({ error: "POST a JSON array of vector IDs" }, 400);
      }

      let deleted = 0;
      const errors = [];
      for (let i = 0; i < ids.length; i += 100) {
        const batch = ids.slice(i, i + 100);
        try {
          await env.VECTORIZE.deleteByIds(batch);
          deleted += batch.length;
        } catch (e) {
          errors.push(`Batch at ${i}: ${e.message}`);
        }
      }

      return json({ requested: ids.length, deleted, errors: errors.length ? errors : undefined });
    }

    if (path === "/fix-metadata" && request.method === "POST") {
      const fixes = await request.json();
      let updated = 0;
      const errors = [];

      for (let i = 0; i < fixes.length; i += 50) {
        const batch = fixes.slice(i, i + 50);
        const ids = batch.map(f => f.id);
        try {
          const existing = await env.VECTORIZE.getByIds(ids);
          const vectors = [];
          for (const vec of existing) {
            const fix = batch.find(f => f.id === vec.id);
            if (fix && vec.values) {
              vectors.push({
                id: vec.id,
                values: vec.values,
                metadata: { ...vec.metadata, ...fix.metadata },
              });
            }
          }
          if (vectors.length > 0) {
            await env.VECTORIZE.upsert(vectors);
            updated += vectors.length;
          }
        } catch (e) {
          errors.push(`Batch ${i}: ${e.message}`);
        }
      }

      return json({ updated, errors: errors.length ? errors : undefined });
    }

    return json({
      endpoints: [
        "GET  /stats         - Quick check",
        "GET  /audit         - Full scan (slow, ~30s)",
        "POST /delete        - Delete IDs (JSON array)",
        "POST /fix-metadata  - Fix metadata [{id, metadata}]",
      ],
    });
  },
};
