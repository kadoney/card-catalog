// =============================================================================
// SAPFM Catalog API — serves Card Catalog UI in the Members Desktop
//
// Endpoints:
//   GET  /api/catalog/collections         — source groups with card counts + featured card
//   GET  /api/catalog/stacks              — facet counts for a given dimension
//   GET  /api/catalog/cards               — paginated card list filtered by dimension/group
//   GET  /api/catalog/cards/:id           — single card detail with related cards
//   GET  /api/catalog/search              — text search across title, title_en, authors, description
//   POST /api/catalog/teasers/generate    — admin: batch-generate teasers via Anthropic API
//   GET  /api/health                      — health check
//
// D1 database: card-catalog (eb944e67-5fcc-4587-8fe1-eae2a9fe3476)
// =============================================================================

interface Env {
  DB: D1Database;
  JWT_SECRET: string;
  DEV_BYPASS?: string;
  ANTHROPIC_API_KEY?: string;
}

interface JWTPayload {
  user_id?: number;
  id?: number;
  sub?: number;
  membership_type?: string;
  display_name?: string;
  email?: string;
  exp?: number;
  dev?: boolean;
  [key: string]: unknown;
}

// =============================================================================
// Source groups — map raw source strings to display categories
// =============================================================================

const SOURCE_GROUPS = [
  {
    display_name: 'Chipstone — American Furniture',
    description: "Scholarly articles from the Chipstone Foundation's annual journal, covering American furniture history, makers, and regional traditions.",
    patterns: ['Chipstone%'],
  },
  {
    display_name: 'Metropolitan Museum of Art',
    description: "Catalogs, bulletins, and collection studies from the Met's American Wing and decorative arts departments.",
    patterns: ['Metropolitan%', 'The Metropolitan%'],
  },
  {
    display_name: 'Journal of Early Southern Decorative Arts',
    description: "MESDA's scholarly journal covering Southern decorative arts, furniture, and material culture.",
    patterns: ['Journal of Early Southern%'],
  },
  {
    display_name: 'American Period Furniture',
    description: "Articles from the Society of American Period Furniture Makers' own annual journal.",
    patterns: ['American Period Furniture%'],
  },
  {
    display_name: 'Yale University Library',
    description: "Bibliographic catalog records from Yale's arts and decorative arts collections — books, exhibition catalogs, and reference works on American and European furniture.",
    patterns: ['Yale Library%'],
  },
  {
    display_name: 'Public Domain Books',
    description: 'Full-text chapters from public domain furniture reference books, searchable alongside other catalog content.',
    patterns: ['Google Books%', 'Internet Archive%'],
  },
];

function sourceGroupWhere(group: typeof SOURCE_GROUPS[number]): string {
  if (group.patterns.length === 1) return `source LIKE '${group.patterns[0]}'`;
  return '(' + group.patterns.map(p => `source LIKE '${p}'`).join(' OR ') + ')';
}

function otherSourcesWhere(): string {
  const allPatterns = SOURCE_GROUPS.flatMap(g => g.patterns);
  return allPatterns.map(p => `source NOT LIKE '${p}'`).join(' AND ');
}

function sourceMatchesGroup(source: string, group: typeof SOURCE_GROUPS[number]): boolean {
  return group.patterns.some(p => {
    const prefix = p.replace('%', '');
    return source.startsWith(prefix);
  });
}

// =============================================================================
// JWT Authentication — HS256 via Web Crypto (shared with bench-api)
// =============================================================================

function base64UrlDecode(str: string): Uint8Array {
  const base64 = str.replace(/-/g, '+').replace(/_/g, '/');
  const pad = base64.length % 4 === 0 ? '' : '='.repeat(4 - (base64.length % 4));
  const binary = atob(base64 + pad);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

async function verifyJWT(request: Request, env: Env): Promise<JWTPayload | null> {
  const authHeader = request.headers.get('Authorization');
  if (!authHeader?.startsWith('Bearer ')) return null;
  const token = authHeader.slice(7);

  if (env.DEV_BYPASS && token === 'DEV') {
    return { user_id: 1, membership_type: 'admin', dev: true };
  }

  const parts = token.split('.');
  if (parts.length !== 3) return null;
  const [headerB64, payloadB64, signatureB64] = parts;

  try {
    const key = await crypto.subtle.importKey(
      'raw',
      new TextEncoder().encode(env.JWT_SECRET),
      { name: 'HMAC', hash: 'SHA-256' },
      false,
      ['verify'],
    );
    const data = new TextEncoder().encode(`${headerB64}.${payloadB64}`);
    const signature = base64UrlDecode(signatureB64);
    const valid = await crypto.subtle.verify('HMAC', key, signature, data);
    if (!valid) return null;

    const payload = JSON.parse(new TextDecoder().decode(base64UrlDecode(payloadB64)));
    if (payload.exp && payload.exp < Math.floor(Date.now() / 1000)) return null;
    return payload;
  } catch {
    return null;
  }
}

async function requireAdmin(request: Request, env: Env): Promise<JWTPayload | Response> {
  const payload = await verifyJWT(request, env);
  if (!payload) {
    return json({ error: 'Authentication required' }, 401);
  }
  if (!payload.user_id && payload.id) payload.user_id = Number(payload.id);
  else if (!payload.user_id && payload.sub) payload.user_id = Number(payload.sub);
  if (payload.membership_type !== 'admin') {
    return json({ error: 'Admin access required' }, 403);
  }
  return payload;
}

// =============================================================================
// Response helpers
// =============================================================================

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function makeCorsResponse(corsOrigin: string) {
  return (response: Response): Response => {
    const headers = new Headers(response.headers);
    headers.set('Access-Control-Allow-Origin', corsOrigin);
    headers.set('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    headers.set('Access-Control-Allow-Headers', 'Content-Type, Authorization');
    return new Response(response.body, { status: response.status, headers });
  };
}

// =============================================================================
// Data helpers
// =============================================================================

function parseJsonArray(val: string | null | undefined): string[] {
  if (!val) return [];
  try {
    const parsed = JSON.parse(val);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function firstOf(val: string | null | undefined): string | null {
  const arr = parseJsonArray(val);
  return arr.length > 0 ? arr[0] : null;
}

const VALID_DIMENSIONS = ['source', 'period', 'form', 'region', 'topic'];

function isValidDimension(d: string): boolean {
  return VALID_DIMENSIONS.includes(d);
}

// =============================================================================
// GET /api/catalog/collections — source groups + featured card
// =============================================================================

async function handleCollections(env: Env): Promise<Response> {
  const featured = await env.DB.prepare(
    `SELECT id, title, title_en, authors, year, source, card_type, teaser, period, form,
            view_url, download_url, is_free, thumbnail_url
     FROM library_cards WHERE status = 'approved' AND is_featured = 1 LIMIT 1`,
  ).first();

  const allSources = await env.DB.prepare(
    `SELECT source, COUNT(*) as cnt FROM library_cards
     WHERE status = 'approved' GROUP BY source`,
  ).all();

  const collections = SOURCE_GROUPS.map(group => {
    let card_count = 0;
    for (const row of allSources.results) {
      if (sourceMatchesGroup(row.source as string, group)) {
        card_count += (row.cnt as number);
      }
    }
    return {
      display_name: group.display_name,
      description: group.description,
      card_count,
    };
  });

  const total = await env.DB.prepare(
    `SELECT COUNT(*) as cnt FROM library_cards WHERE status = 'approved'`,
  ).first<{ cnt: number }>();

  return json({
    featured: featured
      ? {
          ...featured,
          authors: parseJsonArray(featured.authors as string),
          period: parseJsonArray(featured.period as string),
          form: parseJsonArray(featured.form as string),
        }
      : null,
    collections,
    total_cards: total?.cnt ?? 0,
  });
}

// =============================================================================
// GET /api/catalog/stacks — facet counts for a dimension
// =============================================================================

async function handleStacks(env: Env, url: URL): Promise<Response> {
  const dimension = url.searchParams.get('dimension');
  if (!dimension || !isValidDimension(dimension)) {
    return json({ error: 'Missing or invalid dimension. Use: source, period, form, region, topic' }, 400);
  }

  if (dimension === 'source') {
    const allSources = await env.DB.prepare(
      `SELECT source, COUNT(*) as cnt FROM library_cards
       WHERE status = 'approved' GROUP BY source ORDER BY cnt DESC`,
    ).all();

    const grouped: Array<{ value: string; count: number }> = [];
    const claimed = new Set<string>();

    for (const group of SOURCE_GROUPS) {
      let count = 0;
      for (const row of allSources.results) {
        if (sourceMatchesGroup(row.source as string, group)) {
          count += (row.cnt as number);
          claimed.add(row.source as string);
        }
      }
      if (count > 0) {
        grouped.push({ value: group.display_name, count });
      }
    }

    let otherCount = 0;
    for (const row of allSources.results) {
      if (!claimed.has(row.source as string)) {
        otherCount += (row.cnt as number);
      }
    }
    if (otherCount > 0) {
      grouped.push({ value: 'Other Sources', count: otherCount });
    }

    grouped.sort((a, b) => b.count - a.count);
    return json({ dimension, groups: grouped });
  }

  // Non-source dimensions: explode JSON arrays and count
  const rows = await env.DB.prepare(
    `SELECT ${dimension} FROM library_cards WHERE status = 'approved'`,
  ).all();

  const counts = new Map<string, number>();
  for (const row of rows.results) {
    const values = parseJsonArray(row[dimension] as string);
    for (const v of values) {
      counts.set(v, (counts.get(v) ?? 0) + 1);
    }
  }

  const groups = Array.from(counts.entries())
    .map(([value, count]) => ({ value, count }))
    .sort((a, b) => b.count - a.count);

  return json({ dimension, groups });
}

// =============================================================================
// GET /api/catalog/cards — paginated card list filtered by dimension/group
// =============================================================================

async function handleCardsList(env: Env, url: URL): Promise<Response> {
  const dimension = url.searchParams.get('dimension');
  const group = url.searchParams.get('group');
  const page = Math.max(1, parseInt(url.searchParams.get('page') ?? '1'));
  const limit = Math.min(100, Math.max(1, parseInt(url.searchParams.get('limit') ?? '24')));
  const offset = (page - 1) * limit;

  if (!dimension || !group || !isValidDimension(dimension)) {
    return json({ error: 'Missing dimension or group parameter' }, 400);
  }

  let whereClause: string;
  const binds: string[] = [];

  if (dimension === 'source') {
    if (group === 'Other Sources') {
      whereClause = otherSourcesWhere();
    } else {
      const sourceGroup = SOURCE_GROUPS.find(g => g.display_name === group);
      if (sourceGroup) {
        whereClause = sourceGroupWhere(sourceGroup);
      } else {
        whereClause = 'source = ?';
        binds.push(group);
      }
    }
  } else {
    whereClause = `${dimension} LIKE ?`;
    binds.push(`%"${group}"%`);
  }

  const lang = url.searchParams.get('lang');
  const langClause = lang === 'en' ? " AND (language = 'en' OR language IS NULL)" : '';

  const countSql = `SELECT COUNT(*) as cnt FROM library_cards WHERE status = 'approved' AND ${whereClause}${langClause}`;
  const dataSql = `SELECT id, title, title_en, authors, year, source, card_type, teaser, period, form,
                          view_url, download_url, thumbnail_url, language
                   FROM library_cards WHERE status = 'approved' AND ${whereClause}${langClause}
                   ORDER BY year DESC, title ASC
                   LIMIT ? OFFSET ?`;

  const countStmt = env.DB.prepare(countSql);
  const dataStmt = env.DB.prepare(dataSql);
  const countBound = binds.length > 0 ? countStmt.bind(...binds) : countStmt;
  const dataBound = binds.length > 0 ? dataStmt.bind(...binds, limit, offset) : dataStmt.bind(limit, offset);

  const [countResult, dataResult] = await Promise.all([
    countBound.first<{ cnt: number }>(),
    dataBound.all(),
  ]);

  const total = countResult?.cnt ?? 0;
  const cards = dataResult.results.map(row => ({
    id: row.id,
    title: row.title,
    title_en: row.title_en,
    authors: parseJsonArray(row.authors as string),
    year: row.year,
    source: row.source,
    card_type: row.card_type,
    teaser: row.teaser,
    period: firstOf(row.period as string),
    form: firstOf(row.form as string),
    view_url: row.view_url,
    download_url: row.download_url,
    thumbnail_url: row.thumbnail_url,
    language: row.language,
  }));

  return json({
    cards,
    pagination: { page, limit, total, total_pages: Math.ceil(total / limit) },
  });
}

// =============================================================================
// GET /api/catalog/cards/:id — single card detail + related cards
// =============================================================================

async function handleCardDetail(env: Env, id: number, isAuthenticated = false): Promise<Response> {
  const card = await env.DB.prepare(
    `SELECT * FROM library_cards WHERE id = ? AND status = 'approved'`,
  ).bind(id).first();

  if (!card) return json({ error: 'Card not found' }, 404);

  const periodArr = parseJsonArray(card.period as string);
  const formArr = parseJsonArray(card.form as string);
  const regionArr = parseJsonArray(card.region as string);
  const allTags = [...periodArr, ...formArr, ...regionArr];

  let related: Array<{
    id: unknown; title: unknown; title_en: unknown; language: unknown;
    authors: string[]; year: unknown; source: unknown;
    card_type: unknown; teaser: unknown; overlap: number;
  }> = [];

  if (allTags.length > 0) {
    const tagConditions = allTags.slice(0, 5).map(
      () => `(period LIKE ? OR form LIKE ? OR region LIKE ?)`,
    );
    const tagBinds = allTags.slice(0, 5).flatMap(t => {
      const pattern = `%"${t}"%`;
      return [pattern, pattern, pattern];
    });

    const candidates = await env.DB.prepare(
      `SELECT id, title, title_en, language, authors, year, source, card_type, teaser, period, form, region
       FROM library_cards
       WHERE status = 'approved' AND id != ?
         AND (${tagConditions.join(' OR ')})
       LIMIT 50`,
    ).bind(id, ...tagBinds).all();

    const scored = candidates.results.map(row => {
      const rTags = new Set([
        ...parseJsonArray(row.period as string),
        ...parseJsonArray(row.form as string),
        ...parseJsonArray(row.region as string),
      ]);
      let overlap = 0;
      for (const t of allTags) {
        if (rTags.has(t)) overlap++;
      }
      return { row, overlap };
    });
    scored.sort((a, b) => b.overlap - a.overlap);

    related = scored.slice(0, 3).map(s => ({
      id: s.row.id,
      title: s.row.title,
      title_en: s.row.title_en,
      language: s.row.language,
      authors: parseJsonArray(s.row.authors as string),
      year: s.row.year,
      source: s.row.source,
      card_type: s.row.card_type,
      teaser: s.row.teaser,
      overlap: s.overlap,
    }));
  }

  return json({
    card: {
      id: card.id,
      title: card.title,
      title_en: card.title_en,
      authors: parseJsonArray(card.authors as string),
      year: card.year,
      source: card.source,
      card_type: card.card_type,
      period: periodArr,
      form: formArr,
      region: regionArr,
      topic: parseJsonArray(card.topic as string),
      makers: parseJsonArray(card.makers as string),
      description: card.description,
      teaser: card.teaser,
      is_featured: card.is_featured,
      is_free: card.is_free,
      view_url: isAuthenticated || card.is_free ? card.view_url : null,
      download_url: isAuthenticated || card.is_free ? card.download_url : null,
      thumbnail_url: card.thumbnail_url,
      isbn: card.isbn,
      page_count: card.page_count,
      publisher: card.publisher,
      openlibrary_key: card.openlibrary_key,
      language: card.language,
    },
    related,
  });
}

// =============================================================================
// GET /api/catalog/search — text search
// =============================================================================

async function handleSearch(env: Env, url: URL): Promise<Response> {
  const q = url.searchParams.get('q')?.trim();
  const page = Math.max(1, parseInt(url.searchParams.get('page') ?? '1'));
  const limit = Math.min(100, Math.max(1, parseInt(url.searchParams.get('limit') ?? '24')));
  const offset = (page - 1) * limit;

  if (!q || q.length < 2) {
    return json({ error: 'Search query must be at least 2 characters' }, 400);
  }

  const pattern = `%${q}%`;
  const lang = url.searchParams.get('lang');
  const langFilter = lang === 'en' ? " AND (language = 'en' OR language IS NULL)" : '';
  const where = `status = 'approved' AND (title LIKE ? OR title_en LIKE ? OR authors LIKE ? OR description LIKE ?)${langFilter}`;

  const [countResult, dataResult] = await Promise.all([
    env.DB.prepare(`SELECT COUNT(*) as cnt FROM library_cards WHERE ${where}`)
      .bind(pattern, pattern, pattern, pattern).first<{ cnt: number }>(),
    env.DB.prepare(
      `SELECT id, title, title_en, authors, year, source, card_type, teaser, period, form,
              view_url, download_url, thumbnail_url, language
       FROM library_cards WHERE ${where}
       ORDER BY year DESC, title ASC
       LIMIT ? OFFSET ?`,
    ).bind(pattern, pattern, pattern, pattern, limit, offset).all(),
  ]);

  const total = countResult?.cnt ?? 0;
  const cards = dataResult.results.map(row => ({
    id: row.id,
    title: row.title,
    title_en: row.title_en,
    authors: parseJsonArray(row.authors as string),
    year: row.year,
    source: row.source,
    card_type: row.card_type,
    teaser: row.teaser,
    period: firstOf(row.period as string),
    form: firstOf(row.form as string),
    view_url: row.view_url,
    download_url: row.download_url,
    thumbnail_url: row.thumbnail_url,
    language: row.language,
  }));

  return json({
    query: q,
    cards,
    pagination: { page, limit, total, total_pages: Math.ceil(total / limit) },
  });
}

// =============================================================================
// POST /api/catalog/teasers/generate — admin: batch-generate AI teasers
// =============================================================================

async function handleTeaserGenerate(env: Env): Promise<Response> {
  if (!env.ANTHROPIC_API_KEY) {
    return json({ error: 'ANTHROPIC_API_KEY not configured' }, 500);
  }

  const rows = await env.DB.prepare(
    `SELECT id, title, authors, description, period, form, source
     FROM library_cards
     WHERE status = 'approved' AND teaser IS NULL
     LIMIT 20`,
  ).all();

  if (rows.results.length === 0) {
    return json({ message: 'All cards have teasers', generated: 0, remaining: 0 });
  }

  let generated = 0;
  const errors: string[] = [];

  for (const row of rows.results) {
    const prompt = `You are a scholarly editor for a furniture history journal. Write a 2-3 sentence teaser for this library card entry. The teaser should be specific about what the reader will learn — name the key argument, maker, form, or discovery. Write in a confident academic register, present tense, no hedging.

Title: ${row.title}
Authors: ${row.authors}
Source: ${row.source}
Period: ${row.period}
Form: ${row.form}
Description: ${row.description}`;

    try {
      const response = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': env.ANTHROPIC_API_KEY,
          'anthropic-version': '2023-06-01',
        },
        body: JSON.stringify({
          model: 'claude-sonnet-4-6',
          max_tokens: 200,
          messages: [{ role: 'user', content: prompt }],
        }),
      });

      if (!response.ok) {
        const errBody = await response.text().catch(() => '');
        errors.push(`Card ${row.id}: ${response.status} ${errBody.substring(0, 100)}`);
        continue;
      }

      const result = await response.json() as { content?: Array<{ text?: string }> };
      const teaser = result.content?.[0]?.text?.trim();
      if (!teaser) continue;

      await env.DB.prepare(
        `UPDATE library_cards SET teaser = ?, updated_at = datetime('now') WHERE id = ?`,
      ).bind(teaser, row.id).run();
      generated++;
    } catch (err) {
      errors.push(`Card ${row.id}: ${err instanceof Error ? err.message : 'unknown error'}`);
    }
  }

  const remaining = await env.DB.prepare(
    `SELECT COUNT(*) as cnt FROM library_cards WHERE status = 'approved' AND teaser IS NULL`,
  ).first<{ cnt: number }>();

  return json({
    generated,
    remaining: remaining?.cnt ?? 0,
    errors: errors.length > 0 ? errors : undefined,
    message: remaining?.cnt ? `${remaining.cnt} cards still need teasers — run again` : 'All done',
  });
}

// =============================================================================
// Main fetch handler
// =============================================================================

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const method = request.method;

    const ALLOWED_ORIGINS = [
      'https://bench.sapfm.org',
      'https://sapfm.org',
      'https://www.sapfm.org',
      'https://gallery.sapfm.org',
      'https://sapfm-bench.pages.dev',
    ];
    const requestOrigin = request.headers.get('Origin') ?? '';
    const isAllowedOrigin =
      ALLOWED_ORIGINS.includes(requestOrigin) ||
      requestOrigin.startsWith('http://localhost') ||
      requestOrigin.startsWith('http://127.0.0.1');
    const corsOrigin = isAllowedOrigin ? requestOrigin : ALLOWED_ORIGINS[0];
    const cors = makeCorsResponse(corsOrigin);

    if (method === 'OPTIONS') {
      return cors(new Response(null, { status: 204 }));
    }

    try {
      if (url.pathname === '/api/health' && method === 'GET') {
        return cors(json({ status: 'ok', service: 'sapfm-catalog-api' }));
      }

      if (url.pathname === '/api/catalog/collections' && method === 'GET') {
        return cors(await handleCollections(env));
      }

      if (url.pathname === '/api/catalog/stacks' && method === 'GET') {
        return cors(await handleStacks(env, url));
      }

      const cardDetailMatch = url.pathname.match(/^\/api\/catalog\/cards\/(\d+)$/);
      if (cardDetailMatch && method === 'GET') {
        const auth = await verifyJWT(request, env);
        return cors(await handleCardDetail(env, parseInt(cardDetailMatch[1]), !!auth));
      }

      if (url.pathname === '/api/catalog/cards' && method === 'GET') {
        return cors(await handleCardsList(env, url));
      }

      if (url.pathname === '/api/catalog/search' && method === 'GET') {
        return cors(await handleSearch(env, url));
      }

      if (url.pathname === '/api/catalog/teasers/generate' && method === 'POST') {
        const adminAuth = await requireAdmin(request, env);
        if (adminAuth instanceof Response) return cors(adminAuth);
        return cors(await handleTeaserGenerate(env));
      }

      return cors(json({ error: 'Not found' }, 404));
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Internal server error';
      return cors(json({ error: message }, 500));
    }
  },
};
