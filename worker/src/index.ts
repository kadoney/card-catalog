// SAPFM Library API Worker
// Card Catalog — human-curated reference index for the Member Desktop
//
// Endpoints:
//   GET  /api/library/cards              — list cards (faceted filter + text search)
//   GET  /api/library/cards/:id          — single card detail
//   GET  /api/library/vocab              — all vocab terms grouped by dimension
//   POST /api/library/submissions        — member: submit a new card (JWT required)
//   GET  /api/library/submissions/:id    — member: check own submission status (JWT required)
//
//   GET  /api/library/admin/submissions  — admin: list submissions (filter by status)
//   PATCH /api/library/admin/submissions/:id — admin: approve/reject/request-revision
//   PUT  /api/library/admin/cards/:id    — admin: edit an approved card
//   POST /api/library/admin/vocab        — admin: add a vocab term
//
// D1 database: card-catalog (eb944e67-5fcc-4587-8fe1-eae2a9fe3476)

interface Env {
  DB: D1Database;
  JWT_SECRET: string;
  DEV_BYPASS?: string;
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

interface CardRow {
  id: number;
  title: string;
  authors: string;
  year: number | null;
  source: string | null;
  source_key: string | null;
  card_type: string;
  parent_id: number | null;
  page_start: number | null;
  page_end: number | null;
  edition: string | null;
  description: string;
  period: string;
  form: string;
  region: string;
  topic: string;
  makers: string;
  is_free: number;
  view_url: string | null;
  download_url: string | null;
  contributed_by: string | null;
  contributor_name: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  language: string | null;
  title_en: string | null;
}

// =============================================================================
// JWT Authentication — same pattern as bench-api (HS256 / Web Crypto)
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
      ['verify']
    );
    const data = new TextEncoder().encode(`${headerB64}.${payloadB64}`);
    const signature = base64UrlDecode(signatureB64);
    const valid = await crypto.subtle.verify('HMAC', key, signature, data);
    if (!valid) return null;

    const payload = JSON.parse(atob(payloadB64.replace(/-/g, '+').replace(/_/g, '/')));
    if (payload.exp && Date.now() / 1000 > payload.exp) return null;
    return payload;
  } catch {
    return null;
  }
}

function getUserId(payload: JWTPayload): number {
  return payload.user_id ?? payload.id ?? payload.sub ?? 0;
}

function isAdmin(payload: JWTPayload): boolean {
  return payload.membership_type === 'admin';
}

// =============================================================================
// CORS / Response helpers
// =============================================================================

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, PUT, PATCH, DELETE, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
};

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
  });
}

function err(message: string, status = 400): Response {
  return json({ error: message }, status);
}

// =============================================================================
// Filtering helpers
// =============================================================================

function parseArray(val: string | null): string[] {
  try { return val ? JSON.parse(val) : []; } catch { return []; }
}

// Build a WHERE clause for JSON-array facet filtering.
// Each dimension uses json_each() for OR-within, AND-across.
function buildCardFilter(url: URL): { where: string; params: unknown[] } {
  const clauses: string[] = ['c.status = ?'];
  const params: unknown[] = ['approved'];

  const dimensions: Array<[string, string]> = [
    ['period', 'p'],
    ['form', 'f'],
    ['region', 'r'],
    ['topic', 't'],
  ];

  const joins: string[] = [];
  for (const [dim, alias] of dimensions) {
    const vals = url.searchParams.getAll(dim);
    if (vals.length > 0) {
      joins.push(`, json_each(c.${dim}) ${alias}`);
      clauses.push(`${alias}.value IN (${vals.map(() => '?').join(',')})`);
      params.push(...vals);
    }
  }

  const sourceKey = url.searchParams.get('source_key');
  if (sourceKey) { clauses.push('c.source_key = ?'); params.push(sourceKey); }

  const cardType = url.searchParams.get('card_type');
  if (cardType) { clauses.push('c.card_type = ?'); params.push(cardType); }

  const q = url.searchParams.get('q');
  if (q) {
    clauses.push('(c.title LIKE ? OR c.description LIKE ? OR c.makers LIKE ?)');
    const like = `%${q}%`;
    params.push(like, like, like);
  }

  const fromJoins = joins.join('');
  const distinct = joins.length > 0 ? 'DISTINCT ' : '';
  return {
    where: `FROM library_cards c${fromJoins} WHERE ${clauses.join(' AND ')}`,
    params,
  };
  // caller appends DISTINCT when joins present
  void distinct; // used via caller
}

function formatCard(row: CardRow) {
  return {
    id: row.id,
    title: row.title,
    authors: parseArray(row.authors),
    year: row.year,
    source: row.source,
    source_key: row.source_key,
    card_type: row.card_type,
    parent_id: row.parent_id,
    page_start: row.page_start,
    page_end: row.page_end,
    edition: row.edition,
    description: row.description,
    period: parseArray(row.period),
    form: parseArray(row.form),
    region: parseArray(row.region),
    topic: parseArray(row.topic),
    makers: parseArray(row.makers),
    is_free: row.is_free === 1,
    view_url: row.view_url,
    download_url: row.download_url,
    contributor_name: row.contributor_name,
    created_at: row.created_at,
    language: row.language,
    title_en: row.title_en,
  };
}

// =============================================================================
// Route handlers
// =============================================================================

// Compute facet counts: for each dimension, count how many matching cards
// contain each vocab value. This shows users how many results they'll get
// if they add/change a facet.
async function computeFacetCounts(
  url: URL,
  allVocab: Record<string, Array<{ value: string; label: string; notes: string | null }>>,
  env: Env
): Promise<Record<string, Array<{ value: string; count: number }>>> {
  const facets: Record<string, Array<{ value: string; count: number }>> = {};
  const dimensions = ['period', 'form', 'region', 'topic'];

  for (const dim of dimensions) {
    // Build WHERE clause EXCLUDING this dimension
    const urlNoThisDim = new URL(url);
    urlNoThisDim.searchParams.delete(dim);
    const { where, params } = buildCardFilter(urlNoThisDim);

    // Fetch all cards matching filters (except this dim)
    const hasJoins = urlNoThisDim.searchParams.has('period') || urlNoThisDim.searchParams.has('form') ||
                     urlNoThisDim.searchParams.has('region') || urlNoThisDim.searchParams.has('topic');
    const distinct = hasJoins ? 'DISTINCT ' : '';
    const sql = `SELECT ${distinct}c.${dim} ${where}`;

    const result = await env.DB.prepare(sql).bind(...params).all<{ [key: string]: string }>();

    // Count occurrences of each vocab value
    const counts: Record<string, number> = {};
    for (const vocab of allVocab[dim] ?? []) {
      counts[vocab.value] = 0;
    }

    for (const row of result.results) {
      const arr = parseArray(row[dim] ?? '[]');
      for (const val of arr) {
        if (val in counts) counts[val]++;
      }
    }

    // Return in vocab order, with "Survey / Multiple" always last
    const vocab = allVocab[dim] ?? [];
    facets[dim] = vocab
      .map(v => ({ value: v.value, count: counts[v.value] ?? 0 }))
      .sort((a, b) => {
        if (a.value === 'Survey / Multiple') return 1;
        if (b.value === 'Survey / Multiple') return -1;
        return 0; // maintain vocab order
      });
  }

  return facets;
}

// GET /api/library/cards
async function listCards(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  const limit = Math.min(parseInt(url.searchParams.get('limit') ?? '50'), 200);
  const offset = parseInt(url.searchParams.get('offset') ?? '0');

  const { where, params } = buildCardFilter(url);

  // Need DISTINCT when we have json_each joins
  const hasJoins = url.searchParams.has('period') || url.searchParams.has('form') ||
                   url.searchParams.has('region') || url.searchParams.has('topic');
  const distinct = hasJoins ? 'DISTINCT ' : '';

  const countSql = `SELECT COUNT(${distinct}c.id) as total ${where}`;
  const rowsSql  = `SELECT ${distinct}c.* ${where} ORDER BY c.year DESC, c.title ASC LIMIT ? OFFSET ?`;

  // Fetch vocab first (needed for facet counting)
  const vocabResult = await env.DB.prepare(
    'SELECT dimension, value, label, notes FROM vocab_terms ORDER BY dimension'
  ).all<{ dimension: string; value: string; label: string; notes: string | null }>();

  const allVocab: Record<string, Array<{ value: string; label: string; notes: string | null }>> = {};
  for (const row of vocabResult.results) {
    if (!allVocab[row.dimension]) allVocab[row.dimension] = [];
    allVocab[row.dimension].push({ value: row.value, label: row.label, notes: row.notes });
  }

  const [countResult, rowsResult, facets] = await Promise.all([
    env.DB.prepare(countSql).bind(...params).first<{ total: number }>(),
    env.DB.prepare(rowsSql).bind(...params, limit, offset).all<CardRow>(),
    computeFacetCounts(url, allVocab, env),
  ]);

  return json({
    cards: rowsResult.results.map(formatCard),
    total: countResult?.total ?? 0,
    limit,
    offset,
    facets,
  });
}

// GET /api/library/cards/:id
async function getCard(id: number, env: Env): Promise<Response> {
  const row = await env.DB.prepare(
    'SELECT * FROM library_cards WHERE id = ? AND status = ?'
  ).bind(id, 'approved').first<CardRow>();
  if (!row) return err('Not found', 404);

  const card = formatCard(row);

  // If chapter, fetch parent
  if (row.parent_id) {
    const parent = await env.DB.prepare(
      'SELECT * FROM library_cards WHERE id = ? AND status = ?'
    ).bind(row.parent_id, 'approved').first<CardRow>();
    return json({ card, parent: parent ? formatCard(parent) : null });
  }

  return json({ card });
}

// GET /api/library/vocab
async function getVocab(env: Env): Promise<Response> {
  const { results } = await env.DB.prepare(
    'SELECT dimension, value, label, notes, sort_order FROM vocab_terms ORDER BY dimension, sort_order, value'
  ).all<{ dimension: string; value: string; label: string; notes: string | null; sort_order: number }>();

  const grouped: Record<string, Array<{ value: string; label: string; notes: string | null }>> = {};
  for (const row of results) {
    if (!grouped[row.dimension]) grouped[row.dimension] = [];
    grouped[row.dimension].push({ value: row.value, label: row.label, notes: row.notes });
  }
  return json(grouped);
}

// POST /api/library/submissions
async function submitCard(request: Request, env: Env): Promise<Response> {
  const user = await verifyJWT(request, env);
  if (!user) return err('Unauthorized', 401);

  const body = await request.json() as Record<string, unknown>;
  if (!body.title || !body.description) return err('title and description are required');

  const submittedBy = String(getUserId(user));
  const submitterName = String(body.submitter_name ?? user.display_name ?? 'Member');

  const payload = JSON.stringify({
    title: body.title,
    authors: body.authors ?? [],
    year: body.year ?? null,
    source: body.source ?? null,
    source_key: body.source_key ?? null,
    card_type: body.card_type ?? 'article',
    parent_id: body.parent_id ?? null,
    page_start: body.page_start ?? null,
    page_end: body.page_end ?? null,
    edition: body.edition ?? null,
    description: body.description,
    period: body.period ?? [],
    form: body.form ?? [],
    region: body.region ?? [],
    topic: body.topic ?? [],
    makers: body.makers ?? [],
    is_free: body.is_free ?? 1,
    view_url: body.view_url ?? null,
    download_url: body.download_url ?? null,
  });

  const result = await env.DB.prepare(`
    INSERT INTO submissions (entity_type, entity_id, payload, submitted_by, submitter_name, status)
    VALUES ('library_card', ?, ?, ?, ?, 'pending')
  `).bind(body.entity_id ?? null, payload, submittedBy, submitterName).run();

  return json({ id: result.meta.last_row_id, status: 'pending' }, 201);
}

// GET /api/library/submissions/:id  (member: own submissions only)
async function getSubmission(id: number, request: Request, env: Env): Promise<Response> {
  const user = await verifyJWT(request, env);
  if (!user) return err('Unauthorized', 401);

  const row = await env.DB.prepare(
    'SELECT * FROM submissions WHERE id = ?'
  ).bind(id).first<{
    id: number; submitted_by: string; status: string;
    reviewer_notes: string | null; created_at: string; updated_at: string;
  }>();

  if (!row) return err('Not found', 404);
  if (!isAdmin(user) && row.submitted_by !== String(getUserId(user))) {
    return err('Forbidden', 403);
  }

  return json(row);
}

// GET /api/library/admin/submissions
async function adminListSubmissions(request: Request, env: Env): Promise<Response> {
  const user = await verifyJWT(request, env);
  if (!user || !isAdmin(user)) return err('Forbidden', 403);

  const url = new URL(request.url);
  const status = url.searchParams.get('status') ?? 'pending';
  const entityType = url.searchParams.get('entity_type') ?? 'library_card';
  const limit = Math.min(parseInt(url.searchParams.get('limit') ?? '50'), 200);
  const offset = parseInt(url.searchParams.get('offset') ?? '0');

  const { results } = await env.DB.prepare(`
    SELECT id, entity_type, entity_id, submitted_by, submitter_name,
           status, reviewer_notes, reviewed_by, created_at, updated_at,
           json_extract(payload, '$.title') as title,
           json_extract(payload, '$.source_key') as source_key
    FROM submissions
    WHERE status = ? AND entity_type = ?
    ORDER BY created_at ASC
    LIMIT ? OFFSET ?
  `).bind(status, entityType, limit, offset).all();

  return json({ submissions: results, limit, offset });
}

// PATCH /api/library/admin/submissions/:id
async function adminDecideSubmission(id: number, request: Request, env: Env): Promise<Response> {
  const user = await verifyJWT(request, env);
  if (!user || !isAdmin(user)) return err('Forbidden', 403);

  const body = await request.json() as {
    action: 'approve' | 'reject' | 'revision_requested';
    reviewer_notes?: string;
  };
  if (!['approve', 'reject', 'revision_requested'].includes(body.action)) {
    return err('action must be approve, reject, or revision_requested');
  }

  const sub = await env.DB.prepare(
    'SELECT * FROM submissions WHERE id = ?'
  ).bind(id).first<{ id: number; payload: string; submitted_by: string; submitter_name: string }>();

  if (!sub) return err('Not found', 404);

  const reviewedBy = String(getUserId(user));
  const newStatus = body.action === 'approve' ? 'approved' : body.action;

  if (body.action === 'approve') {
    const p = JSON.parse(sub.payload) as Record<string, unknown>;
    const now = new Date().toISOString();
    await env.DB.prepare(`
      INSERT INTO library_cards
        (title, authors, year, source, source_key, card_type, parent_id,
         page_start, page_end, edition, description, period, form, region, topic, makers,
         is_free, view_url, download_url, contributed_by, contributor_name, status, created_at, updated_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved', ?, ?)
    `).bind(
      p.title, JSON.stringify(p.authors ?? []), p.year ?? null,
      p.source ?? null, p.source_key ?? null, p.card_type ?? 'article',
      p.parent_id ?? null, p.page_start ?? null, p.page_end ?? null,
      p.edition ?? null, p.description,
      JSON.stringify(p.period ?? []), JSON.stringify(p.form ?? []),
      JSON.stringify(p.region ?? []), JSON.stringify(p.topic ?? []),
      JSON.stringify(p.makers ?? []),
      p.is_free ?? 1, p.view_url ?? null, p.download_url ?? null,
      sub.submitted_by, sub.submitter_name, now, now
    ).run();
  }

  await env.DB.prepare(`
    UPDATE submissions SET status = ?, reviewer_notes = ?, reviewed_by = ?, updated_at = ?
    WHERE id = ?
  `).bind(newStatus, body.reviewer_notes ?? null, reviewedBy, new Date().toISOString(), id).run();

  return json({ id, status: newStatus });
}

// PUT /api/library/admin/cards/:id
async function adminEditCard(id: number, request: Request, env: Env): Promise<Response> {
  const user = await verifyJWT(request, env);
  if (!user || !isAdmin(user)) return err('Forbidden', 403);

  const body = await request.json() as Partial<{
    title: string; authors: string[]; year: number; source: string; source_key: string;
    card_type: string; parent_id: number; page_start: number; page_end: number;
    edition: string; description: string; period: string[]; form: string[];
    region: string[]; topic: string[]; makers: string[]; is_free: number;
    view_url: string; download_url: string;
  }>;

  const existing = await env.DB.prepare(
    'SELECT id FROM library_cards WHERE id = ?'
  ).bind(id).first<{ id: number }>();
  if (!existing) return err('Not found', 404);

  const sets: string[] = [];
  const vals: unknown[] = [];
  const fields: Array<[string, unknown]> = [
    ['title', body.title], ['authors', body.authors ? JSON.stringify(body.authors) : undefined],
    ['year', body.year], ['source', body.source], ['source_key', body.source_key],
    ['card_type', body.card_type], ['parent_id', body.parent_id],
    ['page_start', body.page_start], ['page_end', body.page_end], ['edition', body.edition],
    ['description', body.description],
    ['period', body.period ? JSON.stringify(body.period) : undefined],
    ['form', body.form ? JSON.stringify(body.form) : undefined],
    ['region', body.region ? JSON.stringify(body.region) : undefined],
    ['topic', body.topic ? JSON.stringify(body.topic) : undefined],
    ['makers', body.makers ? JSON.stringify(body.makers) : undefined],
    ['is_free', body.is_free], ['view_url', body.view_url], ['download_url', body.download_url],
  ];
  for (const [col, val] of fields) {
    if (val !== undefined) { sets.push(`${col} = ?`); vals.push(val); }
  }
  if (sets.length === 0) return err('No fields to update');

  sets.push('updated_at = ?');
  vals.push(new Date().toISOString(), id);

  await env.DB.prepare(`UPDATE library_cards SET ${sets.join(', ')} WHERE id = ?`).bind(...vals).run();
  return json({ id, updated: true });
}

// POST /api/library/admin/vocab
async function adminAddVocab(request: Request, env: Env): Promise<Response> {
  const user = await verifyJWT(request, env);
  if (!user || !isAdmin(user)) return err('Forbidden', 403);

  const body = await request.json() as {
    dimension: string; value: string; label?: string; notes?: string; sort_order?: number;
  };
  if (!body.dimension || !body.value) return err('dimension and value are required');

  const result = await env.DB.prepare(`
    INSERT INTO vocab_terms (dimension, value, label, notes, sort_order)
    VALUES (?, ?, ?, ?, ?)
  `).bind(
    body.dimension, body.value,
    body.label ?? body.value, body.notes ?? null, body.sort_order ?? 0
  ).run();

  return json({ id: result.meta.last_row_id }, 201);
}

// =============================================================================
// Main fetch handler
// =============================================================================

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: CORS_HEADERS });
    }

    const url = new URL(request.url);
    const path = url.pathname;
    const method = request.method;

    try {
      // Admin routes
      if (path === '/api/library/admin/submissions' && method === 'GET') {
        return adminListSubmissions(request, env);
      }
      const adminSubMatch = path.match(/^\/api\/library\/admin\/submissions\/(\d+)$/);
      if (adminSubMatch && method === 'PATCH') {
        return adminDecideSubmission(parseInt(adminSubMatch[1]), request, env);
      }
      const adminCardMatch = path.match(/^\/api\/library\/admin\/cards\/(\d+)$/);
      if (adminCardMatch && method === 'PUT') {
        return adminEditCard(parseInt(adminCardMatch[1]), request, env);
      }
      if (path === '/api/library/admin/vocab' && method === 'POST') {
        return adminAddVocab(request, env);
      }

      // Member routes (require JWT)
      if (path === '/api/library/cards' && method === 'GET') {
        const user = await verifyJWT(request, env);
        if (!user) return err('Unauthorized', 401);
        return listCards(request, env);
      }
      const cardMatch = path.match(/^\/api\/library\/cards\/(\d+)$/);
      if (cardMatch && method === 'GET') {
        const user = await verifyJWT(request, env);
        if (!user) return err('Unauthorized', 401);
        return getCard(parseInt(cardMatch[1]), env);
      }
      if (path === '/api/library/vocab' && method === 'GET') {
        const user = await verifyJWT(request, env);
        if (!user) return err('Unauthorized', 401);
        return getVocab(env);
      }
      if (path === '/api/library/submissions' && method === 'POST') {
        return submitCard(request, env);
      }
      const subMatch = path.match(/^\/api\/library\/submissions\/(\d+)$/);
      if (subMatch && method === 'GET') {
        return getSubmission(parseInt(subMatch[1]), request, env);
      }

      if (path === '/api/health') {
        return json({ ok: true, service: 'library-api' });
      }

      return err('Not found', 404);
    } catch (e) {
      console.error(e);
      return err('Internal server error', 500);
    }
  },
};
