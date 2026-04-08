const API_BASE = import.meta.env.DEV
  ? 'http://localhost:8787/api/library'
  : 'https://library-api.sapfm-admin.workers.dev/api/library';

function getAuthHeaders(): HeadersInit {
  // Get JWT from localStorage (set by SAPFM Member Desktop auth)
  const token = localStorage.getItem('jwt_token');
  const headers = token
    ? { 'Authorization': `Bearer ${token}` }
    : { 'Authorization': 'Bearer DEV' };
  console.log('getAuthHeaders() returning:', headers);
  return headers;
}

export async function fetchVocab() {
  const headers = getAuthHeaders();
  console.log('fetchVocab() calling fetch with headers:', headers);
  const res = await fetch(`${API_BASE}/vocab`, {
    headers,
  });
  console.log('fetchVocab() response status:', res.status);
  if (!res.ok) throw new Error('Failed to fetch vocab');
  return res.json();
}

export interface FetchCardsOptions {
  period?: string[];
  form?: string[];
  region?: string[];
  topic?: string[];
  source_key?: string[];
  q?: string;
  limit?: number;
  offset?: number;
}

export async function fetchCards(options: FetchCardsOptions) {
  const params = new URLSearchParams();
  params.set('limit', String(options.limit ?? 50));
  params.set('offset', String(options.offset ?? 0));

  if (options.period) {
    options.period.forEach((v) => params.append('period', v));
  }
  if (options.form) {
    options.form.forEach((v) => params.append('form', v));
  }
  if (options.region) {
    options.region.forEach((v) => params.append('region', v));
  }
  if (options.topic) {
    options.topic.forEach((v) => params.append('topic', v));
  }
  if (options.source_key) {
    options.source_key.forEach((v) => params.append('source_key', v));
  }
  if (options.q?.trim()) {
    params.set('q', options.q.trim());
  }

  const res = await fetch(`${API_BASE}/cards?${params}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Failed to fetch cards');
  return res.json();
}

export async function fetchCard(id: number) {
  const res = await fetch(`${API_BASE}/cards/${id}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Card not found');
  return res.json();
}
