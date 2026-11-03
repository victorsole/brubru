// frontend/src/services/api_console.ts
// The API Console reads everything from the live API: the catalogue from the OpenAPI spec and the prices from
// /api/v2/pricing, never from a list kept by hand. Nothing here calls a metered route until the visitor presses Send.

const API_ORIGIN: string = import.meta.env.VITE_API_URL || '';
const SANDBOX_KEY: string = import.meta.env.VITE_BRUBRU_SANDBOX_KEY || '';

// What the code snippets show: a visitor's own calls go to the production API whatever this build talks to.
export const PUBLIC_API_ORIGIN = 'https://brubru-production.up.railway.app';

export type ParamKind = 'text' | 'integer' | 'number' | 'boolean' | 'enum' | 'date' | 'datetime' | 'array';

export interface ConsoleParam {
  name: string;
  in: 'path' | 'query';
  required: boolean;
  description: string;
  kind: ParamKind;
  options?: string[];
  defaultValue?: string;
}

export interface ConsoleOperation {
  path: string;
  summary: string;
  description: string;
  folder: string;
  deprecated: boolean;
  params: ConsoleParam[];
  searchText: string;
}

export interface ConsoleFolder {
  id: string;
  operations: ConsoleOperation[];
}

export interface ConsoleCatalogue {
  folders: ConsoleFolder[];
  operations: ConsoleOperation[];
}

export interface ConsolePricing {
  default: { cost_eur: number; label: string };
  routes: Array<{ pattern: string; cost_eur: number; label: string }>;
  sandbox: { calls_per_visitor_per_day: number; calls_per_day_in_total: number; max_limit: number; max_page: number };
}

export interface ConsoleResponse {
  url: string;
  status: number;
  ms: number;
  text: string;
  json: unknown;
  sandboxLeft: number | null;
  requestId: string | null;
}

const FOLDER_ORDER = ['news', 'events', 'legislative', 'parliament', 'commission', 'council', 'funding'];

// The sandbox answers JSON only, so the export format is not offered here.
const HIDDEN_PARAMS = new Set(['format']);

export function normaliseText(text: string): string {
  return text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

// House style has no long dashes; 922 route summaries in the spec still do (register O144). Until the source is
// rewritten, the public page shows them plainly.
function plainDashes(text: string): string {
  return text.replace(/\s*\u2014\s*/g, ': ');
}

function readSchema(schema: any): Pick<ConsoleParam, 'kind' | 'options' | 'defaultValue'> {
  const variants: any[] = Array.isArray(schema?.anyOf)
    ? schema.anyOf.filter((v: any) => v?.type !== 'null')
    : [schema || {}];
  const s = variants[0] || {};
  const rawDefault = schema?.default ?? s.default;
  const defaultValue = rawDefault === undefined || rawDefault === null ? undefined : String(rawDefault);
  if (Array.isArray(s.enum)) return { kind: 'enum', options: s.enum.map(String), defaultValue };
  if (s.type === 'boolean') return { kind: 'boolean', defaultValue };
  if (s.type === 'integer') return { kind: 'integer', defaultValue };
  if (s.type === 'number') return { kind: 'number', defaultValue };
  if (s.type === 'array') return { kind: 'array', defaultValue };
  if (s.format === 'date') return { kind: 'date', defaultValue };
  if (s.format === 'date-time') return { kind: 'datetime', defaultValue };
  return { kind: 'text', defaultValue };
}

export function parseSpec(spec: any): ConsoleCatalogue {
  const operations: ConsoleOperation[] = [];
  for (const [path, item] of Object.entries<any>(spec?.paths || {})) {
    const get = item?.get;
    if (!get || !path.startsWith('/api/v2/')) continue;
    const params: ConsoleParam[] = [];
    for (const p of get.parameters || []) {
      if ((p.in !== 'path' && p.in !== 'query') || HIDDEN_PARAMS.has(p.name)) continue;
      params.push({
        name: p.name,
        in: p.in,
        required: p.in === 'path' || p.required === true,
        description: plainDashes(p.description || p.schema?.description || ''),
        ...readSchema(p.schema),
      });
    }
    params.sort((a, b) => Number(b.required) - Number(a.required));
    const summary: string = plainDashes(get.summary || '');
    const description: string = plainDashes(get.description || '');
    operations.push({
      path,
      summary,
      description,
      folder: path.split('/')[3] || '',
      deprecated: get.deprecated === true,
      params,
      searchText: normaliseText(`${path} ${summary} ${description}`),
    });
  }
  operations.sort((a, b) => a.path.localeCompare(b.path));
  const byFolder = new Map<string, ConsoleOperation[]>();
  for (const op of operations) {
    if (!byFolder.has(op.folder)) byFolder.set(op.folder, []);
    byFolder.get(op.folder)!.push(op);
  }
  const rank = (id: string) => {
    const i = FOLDER_ORDER.indexOf(id);
    return i === -1 ? FOLDER_ORDER.length : i;
  };
  const folders = [...byFolder.entries()]
    .map(([id, ops]) => ({ id, operations: ops }))
    .sort((a, b) => rank(a.id) - rank(b.id) || a.id.localeCompare(b.id));
  return { folders, operations };
}

export function searchOperations(catalogue: ConsoleCatalogue, query: string): ConsoleOperation[] {
  const words = normaliseText(query).split(/\s+/).filter(Boolean);
  if (words.length === 0) return [];
  return catalogue.operations.filter((op) => words.every((w) => op.searchText.includes(w)));
}

// The first values of a form. A small page: the sandbox serves 25 rows at most, and five show the shape.
export function initialValues(op: ConsoleOperation): Record<string, string> {
  return op.params.some((p) => p.name === 'limit' && p.in === 'query') ? { limit: '5' } : {};
}

export function missingRequired(op: ConsoleOperation, values: Record<string, string>): string[] {
  return op.params.filter((p) => p.required && !(values[p.name] || '').trim()).map((p) => p.name);
}

export function buildRequestPath(op: ConsoleOperation, values: Record<string, string>): string {
  let path = op.path;
  const query = new URLSearchParams();
  for (const p of op.params) {
    const raw = (values[p.name] || '').trim();
    if (p.in === 'path') {
      path = path.replace(`{${p.name}}`, encodeURIComponent(raw));
    } else if (raw && p.kind === 'array') {
      raw.split(',').map((v) => v.trim()).filter(Boolean).forEach((v) => query.append(p.name, v));
    } else if (raw) {
      query.append(p.name, raw);
    }
  }
  const qs = query.toString();
  return qs ? `${path}?${qs}` : path;
}

export function priceOf(pathOnly: string, pricing: ConsolePricing | null): number | null {
  if (!pricing) return null;
  for (const route of pricing.routes) {
    try {
      if (new RegExp(route.pattern).test(pathOnly)) return route.cost_eur;
    } catch {
      // A pattern this browser cannot compile falls through to the default; the server still decides.
    }
  }
  return pricing.default.cost_eur;
}

// The same rule the gate applies (services/billing/api_meter.py sandbox_refusal). The gate decides; this only
// spares the visitor a refused call.
export function sandboxServes(pathOnly: string, pricing: ConsolePricing | null): boolean {
  if (/^\/api\/v2\/extract(\/|$)/.test(pathOnly)) return false;
  const price = priceOf(pathOnly, pricing);
  return price === null || pricing === null || price <= pricing.default.cost_eur;
}

export function hasSandbox(): boolean {
  return Boolean(SANDBOX_KEY);
}

let cataloguePromise: Promise<ConsoleCatalogue> | null = null;
let pricingPromise: Promise<ConsolePricing> | null = null;

export function loadCatalogue(): Promise<ConsoleCatalogue> {
  if (!cataloguePromise) {
    cataloguePromise = fetch(`${API_ORIGIN}/api/v2/openapi.json`)
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status));
        return r.json();
      })
      .then(parseSpec)
      .catch((e) => {
        cataloguePromise = null; // allow a retry
        throw e;
      });
  }
  return cataloguePromise;
}

export function loadPricing(): Promise<ConsolePricing> {
  if (!pricingPromise) {
    pricingPromise = fetch(`${API_ORIGIN}/api/v2/pricing`)
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status));
        return r.json();
      })
      .catch((e) => {
        pricingPromise = null;
        throw e;
      });
  }
  return pricingPromise;
}

export async function sendRequest(requestPath: string, signal?: AbortSignal): Promise<ConsoleResponse> {
  const url = `${API_ORIGIN}${requestPath}`;
  const started = performance.now();
  const response = await fetch(url, {
    headers: { 'X-API-Key': SANDBOX_KEY, Accept: 'application/json' },
    signal,
  });
  const text = await response.text();
  const ms = Math.round(performance.now() - started);
  let json: unknown = null;
  try {
    json = JSON.parse(text);
  } catch {
    json = null;
  }
  const left = response.headers.get('X-Brubru-Sandbox-Remaining');
  return {
    url: requestPath,
    status: response.status,
    ms,
    text,
    json,
    sandboxLeft: left === null ? null : Number(left),
    requestId: response.headers.get('X-Request-Id'),
  };
}

// ---- reading a response ------------------------------------------------------------------------------------

export function rowsOf(json: unknown): Record<string, any>[] {
  if (Array.isArray(json)) return json.filter((r) => r && typeof r === 'object');
  if (json && typeof json === 'object') {
    const o = json as Record<string, any>;
    if (Array.isArray(o.data)) return o.data;
    if (Array.isArray(o.items)) return o.items;
    return [o];
  }
  return [];
}

export function isList(json: unknown): boolean {
  return Array.isArray(json) || Boolean(json && typeof json === 'object' && (Array.isArray((json as any).data) || Array.isArray((json as any).items)));
}

export function totalOf(json: unknown): number | null {
  const total = json && typeof json === 'object' ? (json as any).total : null;
  return typeof total === 'number' ? total : null;
}

export function reasonOf(json: unknown): { code: string; message: string } {
  const o: any = json && typeof json === 'object' ? json : {};
  const detail = o.detail && typeof o.detail === 'object' ? o.detail : o;
  const message = typeof detail.error === 'string' ? detail.error : typeof o.detail === 'string' ? o.detail : '';
  return { code: typeof detail.reason_code === 'string' ? detail.reason_code : '', message };
}

export function safeHttpUrl(value: unknown): string | null {
  return typeof value === 'string' && /^https?:\/\//i.test(value) ? value : null;
}

export function shortenedJson(json: unknown, text: string, maxString = 600, maxTotal = 200_000): string {
  const pretty = json === null
    ? text
    : JSON.stringify(json, (_k, v) => (typeof v === 'string' && v.length > maxString ? `${v.slice(0, maxString)}... (${v.length})` : v), 2);
  return pretty.length > maxTotal ? `${pretty.slice(0, maxTotal)}\n...` : pretty;
}

export function curlSnippet(requestPath: string): string {
  return `curl "${PUBLIC_API_ORIGIN}${requestPath}" \\\n  -H "X-API-Key: YOUR_API_KEY"`;
}

export function pythonSnippet(requestPath: string): string {
  return [
    'import requests',
    '',
    'response = requests.get(',
    `    "${PUBLIC_API_ORIGIN}${requestPath}",`,
    '    headers={"X-API-Key": "YOUR_API_KEY"},',
    '    timeout=60,',
    ')',
    'print(response.json())',
  ].join('\n');
}
