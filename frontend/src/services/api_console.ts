// frontend/src/services/api_console.ts
// The API Console reads everything from the live API: the catalogue from the OpenAPI spec and the prices from
// /api/v2/pricing, never from a list kept by hand. Nothing here calls a metered route until the visitor presses Send.

const API_ORIGIN: string = import.meta.env.VITE_API_URL || '';
const SANDBOX_KEY: string = import.meta.env.VITE_BRUBRU_SANDBOX_KEY || '';

// What the code snippets show: a visitor's own calls go to the production API whatever this build talks to.
export const PUBLIC_API_ORIGIN = 'https://brubru-production.up.railway.app';

export type ParamKind = 'text' | 'integer' | 'number' | 'boolean' | 'enum' | 'date' | 'datetime' | 'array';

// Where a field's choices come from when the spec only describes them in words.
export type FieldSource = 'bodies' | 'families' | 'committees' | 'countries';

export interface ConsoleParam {
  name: string;
  in: 'path' | 'query';
  required: boolean;
  description: string;
  kind: ParamKind;
  options?: string[];
  optionNotes?: Record<string, string>;
  openList?: boolean;
  source?: FieldSource;
  // A form whose list holds only what this feed has.
  feed?: 'consultations';
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
  wordsKey: string;
  bundles: string[];
}

export interface ConsoleFolder {
  id: string;
  operations: ConsoleOperation[];
}

export interface ConsoleCatalogue {
  folders: ConsoleFolder[];
  operations: ConsoleOperation[];
}

export interface PickLists {
  bodies: Array<{ code: string; name: string }>;
  families: Array<{ slug: string; label: string }>;
  committees: Array<{ code: string; name: string }>;
  consultations?: { bodies: Array<{ code: string; name: string }>; families: Array<{ slug: string; label: string }> };
  oj_days?: string[];
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
  costEur: string | null;
  balanceEur: string | null;
}

const FOLDER_ORDER = ['news', 'events', 'legislative', 'parliament', 'commission', 'council', 'funding'];

// The sandbox answers JSON only, so the export format is not offered here.
const HIDDEN_PARAMS = new Set(['format']);

export function normaliseText(text: string): string {
  return text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

// House style has no long dashes; 922 route summaries in the spec still do (register O144). Until the source is
// rewritten, the public page shows them plainly.
// Made from the route's English words, the same way as frontend/scripts/translate_console_words.py makes it: when the English
// changes, the key no longer matches and the console shows English until the translation is run again.
export function routeWordsKey(summary: string, description: string): string {
  let h = 0x811c9dc5;
  for (const ch of `${summary}\n${description}`) {
    h ^= ch.codePointAt(0) as number;
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0).toString(16).padStart(8, '0');
}

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

// 486 fields declare a plain string and list their values in words: "recent | oldest | title. Page by ...". A person
// should choose from those, so the list is read from the description, which is what the API's own docs promise.
// A segment counts only if it starts with one word followed by the end, a colon, a full stop, a comma or a bracket:
// "the latest deadline first (default)" describes the default and is not a value. "..." means the list is not complete.
export function parseOptions(description: string): Pick<ConsoleParam, 'options' | 'optionNotes' | 'openList'> | null {
  const text = (description || '').replace(/`/g, '').trim();
  const inline = text.match(/\(([\w-]+(?:\|[\w-]+)+)\)/);
  if (inline) return { options: inline[1].split('|') };
  if (!/\s\|\s/.test(text)) return null;
  const options: string[] = [];
  const optionNotes: Record<string, string> = {};
  // "e.g. Grant | Procurement": examples, so other values are allowed.
  let openList = /\be\.g\./.test(text);
  text.split(/\s\|\s/).forEach((raw, i) => {
    let segment = raw.trim();
    if (segment.startsWith('...')) {
      openList = true;
      return;
    }
    if (i === 0) {
      // A lead-in before the first value: "Normalised kind: draft_report".
      const lead = segment.match(/^(.*\s.*):\s+([\w-]+)$/) || segment.match(/^(.*\be\.g\.)\s+([\w-]+)$/);
      if (lead) segment = lead[2];
    }
    const match = segment.match(/^([A-Za-z0-9][\w-]*)(?=$|[.:,;]|\s+\()/);
    if (!match) return;
    options.push(match[1]);
    const rest = segment.slice(match[1].length);
    const note = rest.match(/^:\s*(.+)$/)?.[1] || rest.match(/^\s+\((.+)\)\s*\.?$/)?.[1];
    if (note) optionNotes[match[1]] = note.replace(/\.$/, '');
  });
  if (options.length < 2) return null;
  return { options, optionNotes, openList };
}

const COUNTRY_FIELDS = new Set(['country', 'ms', 'member_state', 'buyer_country', 'coordinator_country']);

function sourceOf(name: string, description: string, path: string): FieldSource | undefined {
  if (name === 'family' && /famil/i.test(description)) return 'families';
  if (name === 'body' && /body codes/i.test(description)) return 'bodies';
  if (name === 'committee' && (!description || /committee/i.test(description))) return 'committees';
  if (COUNTRY_FIELDS.has(name) && (/iso|two letters|member state/i.test(description) || path === '/api/v2/parliament/meps')) return 'countries';
  return undefined;
}

export function parseSpec(spec: any): ConsoleCatalogue {
  const operations: ConsoleOperation[] = [];
  for (const [path, item] of Object.entries<any>(spec?.paths || {})) {
    const get = item?.get;
    if (!get || !path.startsWith('/api/v2/')) continue;
    const params: ConsoleParam[] = [];
    for (const p of get.parameters || []) {
      if ((p.in !== 'path' && p.in !== 'query') || HIDDEN_PARAMS.has(p.name)) continue;
      const description = plainDashes(p.description || p.schema?.description || '');
      const schema = readSchema(p.schema);
      params.push({
        name: p.name,
        in: p.in,
        required: p.in === 'path' || p.required === true,
        description,
        ...schema,
        ...(schema.kind === 'text' ? parseOptions(description) || {} : {}),
        source: sourceOf(p.name, description, path),
        feed: /^\/api\/v2\/consultations\//.test(path) ? 'consultations' : undefined,
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
      wordsKey: routeWordsKey(get.summary || '', get.description || ''),
      bundles: Array.isArray(get['x-brubru-bundles']) ? get['x-brubru-bundles'] : [],
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

// The bundles in the order a user reads them (backend: services/api_keys/bundles.py). Names are in the locales.
export const BUNDLE_ORDER = [
  'official-journal', 'legislation', 'funding-procurement', 'news-events', 'agencies-bodies',
  'people', 'consultations', 'enforcement-markets', 'research-data',
];

// The route a bundle opens on: a list of real rows, not a folder's directory.
const BUNDLE_START: Record<string, string> = {
  'official-journal': '/api/v2/legislative/eur-lex/oj/daily',
  legislation: '/api/v2/legislative/eur-lex/laws',
  'funding-procurement': '/api/v2/funding/opportunities',
  'news-events': '/api/v2/news/all',
  'agencies-bodies': '/api/v2/ema/news',
  people: '/api/v2/who-is-who/officials',
  consultations: '/api/v2/consultations/all',
  'enforcement-markets': '/api/v2/commission/infringements',
  'research-data': '/api/v2/open-data/datasets',
};

// Where a person starts: what they want, not how the API is arranged. `main` is the fields shown first, in this order;
// `prefill` is a real example that answers rows; `examples` are one-click values. Words are in the locales, by `id`.
export interface ConsoleTask {
  id: string;
  icon: string;
  path: string;
  bundle: string;
  main: string[];
  prefill: Record<string, string>;
  examples?: Record<string, string[]>;
  options?: Record<string, string[]>;
  // Ways of naming one thing: filling one clears the others, or "batteries" with the common name GDPR finds nothing.
  eitherOr?: string[];
  // Pressing this example also empties these fields: an example has to find something, and "energy" among what is
  // open today finds nothing. A word the person types keeps their filters, and the empty answer offers to drop them.
  exampleClears?: Record<string, string[]>;
}

export const TASKS: ConsoleTask[] = [
  {
    id: 'laws', icon: 'mdi-scale-balance', path: '/api/v2/legislative/eur-lex/laws', bundle: 'legislation',
    main: ['q', 'alias', 'doc_type', 'in_force', 'published_from', 'published_to'],
    prefill: { alias: 'GDPR' },
    examples: { q: ['batteries', 'artificial intelligence', 'food safety'], alias: ['GDPR', 'AI Act', 'Digital Services Act'] },
    options: { doc_type: ['regulation', 'directive', 'decision'] },
    eitherOr: ['q', 'alias'],
  },
  {
    id: 'procedures', icon: 'mdi-file-tree-outline', path: '/api/v2/legislative/oeil/procedures', bundle: 'legislation',
    main: ['q', 'committee', 'status', 'reference'],
    prefill: { q: 'climate' },
    examples: { q: ['climate', 'artificial intelligence', 'migration'], reference: ['2021/0106(COD)'] },
    eitherOr: ['q', 'reference'],
  },
  {
    id: 'oj', icon: 'mdi-newspaper-variant-outline', path: '/api/v2/legislative/eur-lex/oj/daily', bundle: 'official-journal',
    main: ['date', 'series'],
    prefill: {},
    options: { series: ['L', 'C'] },
  },
  {
    id: 'funding', icon: 'mdi-hand-coin-outline', path: '/api/v2/funding/opportunities', bundle: 'funding-procurement',
    main: ['q', 'status', 'item_type', 'country', 'programme', 'deadline_from', 'deadline_to'],
    prefill: { q: 'hydrogen', status: 'open' },
    examples: { q: ['hydrogen', 'cybersecurity', 'health'], programme: ['Horizon Europe'] },
  },
  {
    id: 'news', icon: 'mdi-bullhorn-outline', path: '/api/v2/news/all', bundle: 'news-events',
    main: ['q', 'body', 'family', 'kind', 'days'],
    prefill: { q: 'energy', days: '30' },
    examples: { q: ['energy', 'enlargement', 'data protection'], days: ['7', '30', '90'] },
  },
  {
    id: 'events', icon: 'mdi-calendar-month-outline', path: '/api/v2/events/all', bundle: 'news-events',
    main: ['q', 'when', 'body', 'family', 'from', 'to'],
    prefill: { when: 'upcoming', order: 'soonest' },
    examples: { q: ['hearing', 'conference', 'plenary'] },
  },
  {
    id: 'consultations', icon: 'mdi-forum-outline', path: '/api/v2/consultations/all', bundle: 'consultations',
    main: ['q', 'status', 'body', 'family'],
    prefill: { status: 'open' },
    examples: { q: ['energy', 'digital', 'food'] },
    exampleClears: { q: ['status'] },
  },
  {
    id: 'people', icon: 'mdi-account-group-outline', path: '/api/v2/parliament/meps', bundle: 'people',
    main: ['name', 'country', 'group'],
    prefill: { country: 'BE' },
    options: { group: ['EPP', 'S&D', 'PfE', 'ECR', 'Renew', 'Greens/EFA', 'The Left', 'ESN', 'NI'] },
  },
  {
    id: 'enforcement', icon: 'mdi-gavel', path: '/api/v2/commission/infringements', bundle: 'enforcement-markets',
    main: ['q', 'member_state', 'active', 'policy_area'],
    prefill: { member_state: 'BE' },
    examples: { q: ['waste', 'air quality', 'data protection'] },
  },
  {
    id: 'research', icon: 'mdi-flask-outline', path: '/api/v2/parliament/eprs', bundle: 'research-data',
    main: ['q', 'publication_type', 'committee', 'published_from', 'published_to'],
    prefill: { q: 'energy' },
    examples: { q: ['energy', 'defence', 'artificial intelligence'] },
  },
];

// A required field with no obvious value gets a real one to click. Every value here answers rows on the live API.
export const ROUTE_EXAMPLES: Record<string, Record<string, string[]>> = {
  '/api/v2/legislative/eur-lex/laws/resolve': { id: ['GDPR', '32016R0679', 'AI Act'] },
  '/api/v2/legislative/eur-lex/identify': { q: ['32016R0679', 'ECLI:EU:C:2014:317'] },
  '/api/v2/legislative/eur-lex/identify/scan': { text: ['See 32016R0679 and ECLI:EU:C:2014:317'] },
  '/api/v2/legislative/eurovoc/concepts/search': { q: ['energy', 'agriculture'] },
  '/api/v2/funding/partners': { q: ['hydrogen', 'cybersecurity'] },
  '/api/v2/proprietary/tender-docs/comply-clusters': { template_id: ['cef-digital', 'cef-energy'] },
  '/api/v2/parliament/committees/{code}/work-items': { code: ['ENVI', 'LIBE', 'ITRE'] },
  '/api/v2/parliament/committees/{code}/minutes': { code: ['ENVI', 'LIBE', 'ITRE'] },
};

export function taskOf(path: string): ConsoleTask | undefined {
  return TASKS.find((task) => task.path === path);
}

export type FieldGroup = 'main' | 'more' | 'developer';

// For keeping a copy in sync, or older names kept for existing integrations. Real, but not where anyone starts.
const DEVELOPER_FIELDS = new Set([
  'updated_from', 'updated_to', 'updated_end', 'created_from', 'created_to', 'published_end', 'body_threshold',
  'include_orphans', 'include_other_sources', 'include_removed', 'type', 'sector',
]);
const GENERIC_MAIN = [
  'q', 'name', 'status', 'when', 'kind', 'item_type', 'country', 'ms', 'member_state', 'body', 'family', 'committee',
  'date', 'days', 'from', 'to', 'since', 'until', 'published_from', 'published_to', 'deadline_from', 'deadline_to',
];
const MAX_GENERIC_MAIN = 6;

// Which group a field sits in on this route. Every field of the route is in exactly one group.
export function groupFields(op: ConsoleOperation): Record<FieldGroup, ConsoleParam[]> {
  const task = taskOf(op.path);
  const hasPublished = op.params.some((p) => p.name === 'published_from');
  const isAlias = (p: ConsoleParam) => hasPublished && ['since', 'until', 'from', 'to'].includes(p.name);
  const wanted = task ? task.main : GENERIC_MAIN;
  const main: ConsoleParam[] = [];
  for (const p of op.params) if (p.required) main.push(p);
  for (const name of wanted) {
    const p = op.params.find((x) => x.name === name && !x.required);
    if (p && !isAlias(p) && !DEVELOPER_FIELDS.has(p.name) && (task || main.length < MAX_GENERIC_MAIN)) main.push(p);
  }
  // On a list, the full text is a choice worth seeing: it is what makes a call slow.
  const body = op.params.find((p) => p.name === 'include_body');
  if (body && !main.includes(body)) main.push(body);
  const developer = op.params.filter((p) => !main.includes(p) && (DEVELOPER_FIELDS.has(p.name) || isAlias(p)));
  const more = op.params.filter((p) => !main.includes(p) && !developer.includes(p));
  // How many results comes last among the rest.
  more.sort((a, b) => Number(['limit', 'page'].includes(a.name)) - Number(['limit', 'page'].includes(b.name)));
  return { main, more, developer };
}

// The route's own first sentence on what it does, for a route with no card of its own.
export function whatItDoes(op: ConsoleOperation): string {
  const match = op.description.match(/\*\*What it does\*\*:?\s*([\s\S]+?)(?:\n\s*\n|\*\*When|$)/);
  // A route documented in one plain paragraph has no such heading: its own first sentence says the same.
  const source = match ? match[1] : (op.description || '').split('\n\n')[0];
  const text = source.replace(/[`*]/g, '').replace(/\s+/g, ' ').trim();
  if (!text) return '';
  const firstStop = firstSentenceEnd(text);
  return firstStop > 40 ? text.slice(0, firstStop + 1) : text.slice(0, 260);
}

// The first full stop that ends a sentence, not the one in "e.g." or "No.". Written as a loop: a lookbehind in a regular
// expression stops the whole page from loading on Safari before 16.4.
function firstSentenceEnd(text: string): number {
  const stops = /\.\s/g;
  let found = stops.exec(text);
  while (found) {
    if (!/(?:^|[\s(])(?:e\.g|i\.e|etc|No|nr|vs|Art)$/.test(text.slice(0, found.index))) return found.index;
    found = stops.exec(text);
  }
  return -1;
}

export function isItemRoute(op: ConsoleOperation): boolean {
  return op.params.some((p) => p.in === 'path');
}

// The list a person picks an item from: /a/b for /a/b/{id}. Nothing for a route whose parent is not a route.
export function parentList(catalogue: ConsoleCatalogue, op: ConsoleOperation): ConsoleOperation | undefined {
  let path = op.path;
  while (path.includes('{')) {
    path = path.replace(/\/[^/]*$/, '');
    const parent = catalogue.operations.find((o) => o.path === path);
    if (parent && !parent.path.includes('{')) return parent;
  }
  return undefined;
}

export function bundleCount(catalogue: ConsoleCatalogue, bundle: string): number {
  return catalogue.operations.filter((op) => op.bundles.includes(bundle)).length;
}

export function startOfBundle(catalogue: ConsoleCatalogue, bundle: string): ConsoleOperation | undefined {
  const inside = catalogue.operations.filter((op) => op.bundles.includes(bundle));
  return inside.find((op) => op.path === BUNDLE_START[bundle])
    || inside.find((op) => !op.path.includes('{') && op.path.split('/').length > 4)
    || inside[0];
}

export function searchOperations(catalogue: ConsoleCatalogue, query: string, routeWords: RouteWordsMap = {}): ConsoleOperation[] {
  const words = normaliseText(query).split(/\s+/).filter(Boolean);
  if (words.length === 0) return [];
  // In the visitor's language too: "leyes" should find what "laws" finds.
  return catalogue.operations.filter((op) => {
    const own = wordsFor(op, routeWords);
    const text = own ? `${op.searchText} ${normaliseText(`${own.s || ''} ${own.w || ''}`)}` : op.searchText;
    return words.every((w) => text.includes(w));
  });
}

export interface RouteWords { k: string; s?: string; w?: string; d?: string }
export type RouteWordsMap = Record<string, RouteWords>;

// This route's translation, if there is one and it was made from the English the route has now.
export function wordsFor(op: ConsoleOperation, routeWords: RouteWordsMap): RouteWords | null {
  const own = routeWords[op.path];
  return own && own.k === op.wordsKey ? own : null;
}

export function summaryIn(op: ConsoleOperation, routeWords: RouteWordsMap): string {
  return wordsFor(op, routeWords)?.s || op.summary;
}

export function whatItDoesIn(op: ConsoleOperation, routeWords: RouteWordsMap): string {
  return wordsFor(op, routeWords)?.w || whatItDoes(op);
}

const routeWordsPromises = new Map<string, Promise<RouteWordsMap>>();

// Each language's words, read once. Static files beside the page: if one does not arrive, the console stays in English.
// `full` is the long descriptions, read only when someone opens them.
export function loadRouteWords(language: string, full = false): Promise<RouteWordsMap> {
  const code = language.slice(0, 2);
  if (!['fr', 'nl', 'es', 'ca', 'it'].includes(code)) return Promise.resolve({});
  const name = full ? `${code}_full` : code;
  let found = routeWordsPromises.get(name);
  if (!found) {
    found = fetch(`/api/console_words/${name}.json`)
      .then((r) => (r.ok ? r.json() : {}))
      .catch(() => {
        routeWordsPromises.delete(name);
        return {};
      });
    routeWordsPromises.set(name, found as Promise<RouteWordsMap>);
  }
  return found as Promise<RouteWordsMap>;
}

function isoDaysAgo(days: number, today: Date): string {
  const d = new Date(today);
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString().slice(0, 10);
}

function workingDaysAgo(days: number, today: Date): string {
  const d = new Date(today);
  for (let left = days; left > 0;) {
    d.setUTCDate(d.getUTCDate() - 1);
    if (d.getUTCDay() !== 0 && d.getUTCDay() !== 6) left -= 1;
  }
  return d.toISOString().slice(0, 10);
}

// The first values of a form. A small page: the sandbox serves 25 rows at most, and five show the shape.
// A required date is filled in, or the Official Journal would open on a form with nothing to try: the last day it came out,
// from `ojDays`. Until that has loaded, three working days back, which a holiday can make an empty day (2 Nov 2026 had no
// issue). Full texts run to megabytes and make a list slow, and a sandbox answer over 3 MB is refused, so a list starts
// without them. One item keeps its text: that is what opening it is for.
export function initialValues(op: ConsoleOperation, today: Date = new Date(), ojDays: string[] = []): Record<string, string> {
  const values: Record<string, string> = {};
  for (const p of op.params) {
    if (p.in !== 'query') continue;
    if (p.name === 'limit') values.limit = '5';
    else if (p.required && (p.kind === 'date' || p.name === 'date')) {
      const lastIssue = op.path.endsWith('/oj/daily') ? ojDays[0] : undefined;
      values[p.name] = p.name === 'date' ? lastIssue || workingDaysAgo(3, today) : isoDaysAgo(7, today);
    }
  }
  if (!isItemRoute(op) && op.params.some((p) => p.name === 'include_body')) values.include_body = 'false';
  const task = taskOf(op.path);
  if (task) Object.assign(values, task.prefill);
  return values;
}

// The last working days, for a form that needs a date: one click instead of guessing which days the Journal came out.
export function recentWorkingDays(count: number, today: Date = new Date()): string[] {
  return Array.from({ length: count }, (_, i) => workingDaysAgo(i + 1, today));
}

// Whether this call asked for the bodies, so that an empty one reads as "not requested" and not as a missing text.
export function bodiesRequested(op: ConsoleOperation, values: Record<string, string>): boolean {
  const param = op.params.find((p) => p.name === 'include_body');
  if (!param) return true;
  return (values.include_body || param.defaultValue || 'true') !== 'false';
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

// Whether pressing a card can run its example now. If not, the card opens its form, and the form says why.
export function cardCanSend(op: ConsoleOperation, values: Record<string, string>, pricing: ConsolePricing | null, sandboxLeft: number | null): boolean {
  return hasSandbox() && sandboxLeft !== 0 && sandboxServes(op.path.replace(/\{[^}]+\}/g, 'x'), pricing) && missingRequired(op, values).length === 0;
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

let pickListsPromise: Promise<PickLists | null> | null = null;

// Free, and the form works without it: a field whose list did not arrive stays a text box.
export function loadPickLists(): Promise<PickLists | null> {
  if (!pickListsPromise) {
    pickListsPromise = fetch(`${API_ORIGIN}/api/v2/pick-lists`)
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null);
  }
  return pickListsPromise;
}

export async function sendRequest(requestPath: string, signal?: AbortSignal, ownKey = ''): Promise<ConsoleResponse> {
  const url = `${API_ORIGIN}${requestPath}`;
  const started = performance.now();
  const response = await fetch(url, {
    headers: { 'X-API-Key': ownKey || SANDBOX_KEY, Accept: 'application/json' },
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
    costEur: response.headers.get('X-Brubru-Cost-Eur'),
    balanceEur: response.headers.get('X-Brubru-Balance-Eur'),
  };
}

// ---- your own key ------------------------------------------------------------------------------------------

// For this tab only, unless the person asks to be remembered. A key remembered here or on /api/docs/reference.html is the same
// key: that page keeps it under this name.
const KEY_THIS_TAB = 'brubru_console_key';
const KEY_REMEMBERED = 'brubru_api_key';

export function savedOwnKey(): string {
  try {
    return (sessionStorage.getItem(KEY_THIS_TAB) || localStorage.getItem(KEY_REMEMBERED) || '').trim();
  } catch {
    return '';
  }
}

export function keepOwnKey(key: string, remember: boolean): void {
  try {
    sessionStorage.setItem(KEY_THIS_TAB, key);
    if (remember) localStorage.setItem(KEY_REMEMBERED, key);
  } catch {
    // Blocked storage: the key lasts until the page closes.
  }
}

export function forgetOwnKey(): void {
  try {
    sessionStorage.removeItem(KEY_THIS_TAB);
    localStorage.removeItem(KEY_REMEMBERED);
  } catch {
    // Nothing was kept.
  }
}

// Only that it could be a whole key: the API decides, on the first search the person chooses to make.
export function keyLooksWhole(key: string): boolean {
  return key.length >= 16 && !/\s/.test(key);
}

export function keyEnding(key: string): string {
  return key.slice(-4);
}

export function formatEuro(value: string | number, language: string): string {
  return Number(value).toLocaleString(language, { style: 'currency', currency: 'EUR', minimumFractionDigits: 2, maximumFractionDigits: 6 });
}

// ---- reading a response ------------------------------------------------------------------------------------

// An address on the API itself is not an institution's page.
export function isOurAddress(url: unknown): boolean {
  return typeof url === 'string' && /^https?:\/\/(brubru-production\.up\.railway\.app|brubru\.beresol\.eu)\//i.test(url);
}

export function rowsOf(json: unknown): Record<string, any>[] {
  if (Array.isArray(json)) return json.filter((r) => r && typeof r === 'object');
  if (json && typeof json === 'object') {
    const o = json as Record<string, any>;
    if (Array.isArray(o.data)) return o.data.filter((r: unknown) => r && typeof r === 'object');
    if (Array.isArray(o.items)) return o.items.filter((r: unknown) => r && typeof r === 'object');
    // A map's features: what names each one sits in its properties.
    if (o.type === 'FeatureCollection' && Array.isArray(o.features)) {
      return o.features.filter((f: any) => f && typeof f === 'object').map((f: any) => ({ ...(f.properties || {}) }));
    }
    // One collection with its recent items: the collection is what was asked for, not its longest list.
    if (o.collection && typeof o.collection === 'object' && !Array.isArray(o.collection)) return [o.collection];
    // A lookup answers under its own name ("bodies", "folders"): its longest list of records is what it holds.
    const lists = Object.values(o).filter((v): v is Record<string, any>[] => (
      Array.isArray(v) && v.length > 0 && v.every((r) => r && typeof r === 'object' && !Array.isArray(r))
    ));
    if (lists.length > 0 && !hasDatapoints(o)) return lists.sort((a, b) => b.length - a.length)[0];
    return [o];
  }
  return [];
}

function hasDatapoints(row: Record<string, any>): boolean {
  return 'public_url' in row || 'updated_date' in row || 'document_date' in row || 'body_txt' in row;
}

export function isList(json: unknown): boolean {
  if (Array.isArray(json)) return true;
  if (!json || typeof json !== 'object') return false;
  const o = json as Record<string, any>;
  if (Array.isArray(o.data) || Array.isArray(o.items)) return true;
  return !hasDatapoints(o) && Object.values(o).some((v) => Array.isArray(v) && v.length > 0 && v.every((r) => r && typeof r === 'object' && !Array.isArray(r)));
}

const TITLE_FIELDS = [
  'title', 'full_name', 'name', 'label', 'official_name', 'protected_name', 'original_name', 'case_title', 'pref_label',
  'programme', 'subject', 'headline', 'reference', 'oeil_procedure_ref', 'procedure_ref', 'celex', 'code', 'slug',
  'category', 'theme', 'managing_body', 'org_type', 'registration_category', 'notation', 'value', 'id',
];

export function rowTitle(row: Record<string, any>): string {
  for (const key of TITLE_FIELDS) {
    const value = row[key];
    if ((typeof value === 'string' && value.trim()) || typeof value === 'number') return String(value);
  }
  // A record names its title in its own way: case_title, display_name, legal_name.
  for (const [key, value] of Object.entries(row)) {
    if (/(title|name|label|subject)$/i.test(key) && typeof value === 'string' && value.trim() && !/^https?:/i.test(value)) return value;
  }
  // A route in a bundle has no name of its own: what it does names it.
  if (typeof row.summary === 'string' && row.summary.trim() && row.summary.length <= 200) return row.summary;
  return '';
}

// What a person looks at first on a row, in this order. Anything else with a short value follows, up to the limit.
const FACT_FIELDS = [
  'status', 'current_status', 'stage', 'deadline', 'submission_deadline', 'amount_eur', 'estimated_value', 'body_name',
  'institution', 'contracting_authority', 'member_state_name', 'buyer_country', 'country', 'group', 'role', 'item_type',
  'consultation_type', 'event_type', 'venue', 'publication_type', 'case_type', 'infringement_number',
  'latest_decision_type', 'oeil_procedure_ref', 'procedure_ref', 'celex', 'lead_committee', 'committee_code', 'doc_type',
  'document_type', 'programme', 'topic_id', 'start_date', 'end_date', 'date', 'published_date', 'publication_date',
  'feedback_count', 'in_force', 'active_case', 'in_office', 'language', 'acronym', 'code', 'category', 'count',
];
const NOT_A_FACT = new Set([
  ...TITLE_FIELDS, 'public_url', 'self', 'body_txt', 'body_html', 'document_date', 'creation_date', 'updated_date',
  'summary', 'description', 'text', 'body', 'html', 'content', 'ai_summary', 'url', 'source_url', 'pdf_url', 'html_url',
  'file_id', 'notice_id', 'group_id', 'user_id', 'last_synced_at', 'updated_at', 'created_at', 'last_updated', 'first_seen',
  'scraped_at', 'public_url_kind', 'has_body', 'same_as', 'source', 'body_code', 'source_kind', 'case_dg', 'case_aid_category',
]);
// A date already among what a row shows, under its own name.
const OWN_DATE_FIELDS = [
  'deadline', 'submission_deadline', 'start_date', 'end_date', 'date', 'published_date', 'publication_date', 'adopted_on',
  'meeting_date', 'decision_date',
];
// The route's own name already says a row is news or an event; only funding mixes kinds in one list.
const KINDS_WORTH_SAYING = new Set(['tender', 'grant', 'cascade_call', 'eoi_call', 'startup_funding']);
const MAX_FACTS = 6;
const MAX_FACT_LENGTH = 90;

function factValue(value: unknown): string | boolean | number | null {
  if (typeof value === 'boolean' || typeof value === 'number') return value;
  if (typeof value === 'string') {
    const text = value.trim();
    if (!text || text.length > MAX_FACT_LENGTH || /^https?:/i.test(text) || /^[{[]/.test(text)) return null;
    return text;
  }
  if (Array.isArray(value) && value.length > 0 && value.every((v) => typeof v === 'string' || typeof v === 'number')) {
    const text = value.slice(0, 3).join(', ') + (value.length > 3 ? ` +${value.length - 3}` : '');
    return text.length > MAX_FACT_LENGTH ? null : text;
  }
  return null;
}

export function rowFacts(row: Record<string, any>): Array<{ key: string; value: string | boolean | number }> {
  const facts: Array<{ key: string; value: string | boolean | number }> = [];
  const add = (key: string) => {
    if (facts.length >= MAX_FACTS || facts.some((f) => f.key === key)) return;
    if (key === 'item_type' && !KINDS_WORTH_SAYING.has(String(row[key]))) return;
    const value = factValue(row[key]);
    if (value !== null) facts.push({ key, value });
  };
  // A date is the first thing a person looks for on almost any result.
  if (!OWN_DATE_FIELDS.some((key) => row[key]) && !row.full_name) {
    const day = factValue(row.document_date);
    if (day !== null) facts.push({ key: 'document_date', value: day });
  }
  FACT_FIELDS.forEach((key) => { if (!NOT_A_FACT.has(key) || key === 'code' || key === 'procedure_ref' || key === 'oeil_procedure_ref' || key === 'celex') add(key); });
  // The title may itself be the reference, and two fields may hold one value (a deadline under two names): say it once.
  const title = rowTitle(row);
  const seen = new Set([title]);
  const once = (f: { value: string | boolean | number }) => {
    const text = String(f.value);
    if (typeof f.value !== 'string' || !seen.has(text)) {
      seen.add(text);
      return true;
    }
    return false;
  };
  const shown = facts.filter(once);
  facts.length = 0;
  facts.push(...shown);
  Object.keys(row).forEach((key) => {
    if (NOT_A_FACT.has(key) || facts.length >= MAX_FACTS) return;
    // Our own bookkeeping, and moments the source gives as a bare count of milliseconds, mean nothing on a card.
    if (/uuid$/i.test(key) || key === 'item_type' || (typeof row[key] === 'number' && row[key] > 1e11)) return;
    const value = factValue(row[key]);
    if (value !== null && !facts.some((f) => f.key === key) && once({ value })) facts.push({ key, value });
  });
  return facts;
}

// Text Brubru composed from the row's own fields ("Title: Mr Country: BEL Role: MEMBER ...") only says the facts again.
function isComposed(text: string): boolean {
  return (text.slice(0, 400).match(/(^|\n|\s)[A-Z][A-Za-z -]{1,28}: /g) || []).length >= 3;
}

export function rowText(row: Record<string, any>): string {
  for (const key of ['summary', 'description', 'ai_summary', 'body_txt', 'text']) {
    const value = row[key];
    if (typeof value === 'string' && value.trim() && !(key === 'body_txt' && isComposed(value))) return value.trim();
  }
  return '';
}

function routeMatchers(catalogue: ConsoleCatalogue): Array<{ op: ConsoleOperation; regex: RegExp; names: string[] }> {
  return catalogue.operations
    .filter((op) => op.path.includes('{'))
    .map((op) => {
      const names: string[] = [];
      // The last value may hold slashes: a procedure reference such as 2021/0106(COD).
      const pattern = op.path.replace(/[.*+?^$()|[\]\\]/g, '\\$&').replace(/\{([^}]+)\}(\/?)/g, (_m, name: string, slash: string) => {
        names.push(name);
        return slash ? '([^/]+)/' : '(.+)';
      });
      return { op, regex: new RegExp(`^${pattern}$`), names };
    })
    .sort((a, b) => b.op.path.split('/').length - a.op.path.split('/').length || a.names.length - b.names.length);
}

let matcherCache: { catalogue: ConsoleCatalogue; matchers: ReturnType<typeof routeMatchers> } | null = null;

// Which route of the catalogue an address belongs to, and the values in it.
export function routeFromUrl(catalogue: ConsoleCatalogue, url: string): { op: ConsoleOperation; values: Record<string, string> } | null {
  let pathname: string;
  try {
    pathname = new URL(url, PUBLIC_API_ORIGIN).pathname;
  } catch {
    return null;
  }
  const exact = catalogue.operations.find((op) => op.path === pathname);
  if (exact) return { op: exact, values: {} };
  if (!matcherCache || matcherCache.catalogue !== catalogue) matcherCache = { catalogue, matchers: routeMatchers(catalogue) };
  for (const { op, regex, names } of matcherCache.matchers) {
    const match = pathname.match(regex);
    if (match) {
      const values: Record<string, string> = {};
      names.forEach((name, i) => {
        try {
          values[name] = decodeURIComponent(match[i + 1]);
        } catch {
          values[name] = match[i + 1];
        }
      });
      return { op, values };
    }
  }
  return null;
}

// Where one row opens: its own `self` if it carries one, else the route below this list with the row's id.
export function itemOfRow(
  catalogue: ConsoleCatalogue, row: Record<string, any>, list: ConsoleOperation,
): { op: ConsoleOperation; values: Record<string, string> } | null {
  if (typeof row.self === 'string' && row.self) {
    const found = routeFromUrl(catalogue, row.self);
    if (found && found.op.path !== list.path) return found;
  }
  if (list.path.includes('{')) return null;
  const child = catalogue.operations.find((op) => {
    const m = op.path.match(/^(.*)\/\{([^}]+)\}$/);
    return m && m[1] === list.path;
  });
  if (!child) return null;
  const name = child.path.match(/\{([^}]+)\}$/)![1];
  const reference = row[name] ?? row.id;
  if (reference === undefined || reference === null || reference === '') return null;
  return { op: child, values: { [name]: String(reference) } };
}

export interface PageInfo {
  page: number;
  limit: number;
  hasMore: boolean;
}

export function pageInfo(json: unknown, values: Record<string, string>): PageInfo | null {
  if (!json || typeof json !== 'object' || Array.isArray(json)) return null;
  const o = json as Record<string, any>;
  const page = typeof o.page === 'number' ? o.page : Number(values.page || 1);
  const limit = typeof o.limit === 'number' ? o.limit : Number(values.limit || 0);
  const total = typeof o.total === 'number' ? o.total : null;
  const hasMore = o.has_more === true || (total !== null && limit > 0 && page * limit < total);
  return { page, limit, hasMore };
}

// A refusal in the framework's own shape: {"detail": [{"loc": ["query", "date"], "msg": "..."}]}.
export function fieldErrorsOf(json: unknown): Array<{ field: string; message: string }> {
  const detail = json && typeof json === 'object' ? (json as any).detail : null;
  if (!Array.isArray(detail)) {
    // The API's own form of the same refusal: "Invalid query: updated_from: Input should be a valid datetime or date".
    const words = json && typeof json === 'object' ? (json as any).error : null;
    const match = typeof words === 'string' ? words.match(/^Invalid query: ([a-z_]+): (.+)$/) : null;
    return match ? [{ field: match[1], message: match[2] }] : [];
  }
  return detail
    .filter((d) => d && typeof d === 'object')
    .map((d) => ({ field: Array.isArray(d.loc) ? String(d.loc[d.loc.length - 1]) : '', message: String(d.msg || '') }));
}

// ---- choices: names for a person, codes for the API ---------------------------------------------------------

const COUNTRY_CODES = [
  'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'EL', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL',
  'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE',
];
const FRIENDLY_REGION: Record<string, string> = { EL: 'GR', UK: 'GB' };

export function countryChoices(language: string): Array<{ value: string; label: string }> {
  let names: Intl.DisplayNames | null = null;
  try {
    names = new Intl.DisplayNames([language], { type: 'region' });
  } catch {
    names = null;
  }
  return COUNTRY_CODES
    .map((code) => ({ value: code, label: names?.of(FRIENDLY_REGION[code] || code) || code }))
    .sort((a, b) => a.label.localeCompare(b.label, language));
}

export function choicesOf(param: ConsoleParam, lists: PickLists | null, language: string): Array<{ value: string; label: string }> | null {
  if (param.source === 'countries') return countryChoices(language);
  if (!lists) return null;
  // An empty scope means it could not be read: the full list, as before.
  const scope = param.feed === 'consultations' ? lists.consultations : undefined;
  if (param.source === 'bodies') return (scope?.bodies.length ? scope.bodies : lists.bodies).map((b) => ({ value: b.code, label: b.name }));
  if (param.source === 'families') return (scope?.families.length ? scope.families : lists.families).map((f) => ({ value: f.slug, label: f.label }));
  if (param.source === 'committees') return lists.committees.map((c) => ({ value: c.code, label: `${c.code}: ${c.name.replace(/^Committee on (the )?/, '')}` }));
  return null;
}

// "Belgium" typed where the API wants BE: if what was typed is the name of exactly one choice, use its code.
export function codeForTyped(typed: string, choices: Array<{ value: string; label: string }> | null): string {
  const text = normaliseText(typed).trim();
  if (!text || !choices) return typed;
  const byCode = choices.find((c) => normaliseText(c.value) === text);
  if (byCode) return byCode.value;
  const exact = choices.filter((c) => normaliseText(c.label) === text);
  if (exact.length === 1) return exact[0].value;
  const partial = choices.filter((c) => normaliseText(c.label).includes(text));
  return partial.length === 1 ? partial[0].value : typed;
}

const PROCEDURE_FIELDS = new Set(['reference', 'procedure', 'procedure_ref', 'procedure_reference', 'interinstitutional_ref']);

// Something that looks wrong for this field, to say before a call is spent. Advice only: the API decides.
// A refusal about a date is answered in a person's words, whatever the validator said.
export function isDateRefusal(message: string): boolean {
  return /\b(datetime|date)\b/i.test(message);
}

export function fieldHint(param: ConsoleParam, value: string): string | null {
  const text = value.trim();
  if (!text) return null;
  if (param.kind === 'datetime' && !/^\d{4}-\d{2}-\d{2}([T ].*)?$/.test(text)) return 'hintMoment';
  if (param.name === 'celex' && !/^[0-9CE][0-9A-Z()/_.-]{4,}$/.test(text)) return 'hintCelex';
  if (PROCEDURE_FIELDS.has(param.name) && !/^\d{4}\/\d{1,4}/.test(text)) return 'hintProcedure';
  if (param.source === 'countries' && !/^[A-Za-z]{2,3}(,\s*[A-Za-z]{2,3})*$/.test(text)) return 'hintCountry';
  if (param.source === 'committees' && !/^[A-Za-z0-9-]{3,6}$/.test(text)) return 'hintCommittee';
  return null;
}

// Two dates the wrong way round answer nothing: say so instead of spending a call.
const DATE_PAIRS: Array<[string, string]> = [
  ['published_from', 'published_to'], ['from', 'to'], ['since', 'until'], ['deadline_from', 'deadline_to'],
  ['updated_from', 'updated_to'], ['created_from', 'created_to'], ['decision_from', 'decision_to'], ['date_from', 'date_to'],
];

export function dateRangeProblem(values: Record<string, string>): [string, string] | null {
  for (const [from, to] of DATE_PAIRS) {
    if (values[from] && values[to] && values[from] > values[to]) return [from, to];
  }
  return null;
}

// What the sandbox would refuse on this form. It costs no call, but a person should not have to press to find out.
export function sandboxLimitProblem(values: Record<string, string>, pricing: ConsolePricing | null): { name: string; top: number } | null {
  if (!pricing) return null;
  if (Number(values.limit) > pricing.sandbox.max_limit) return { name: 'limit', top: pricing.sandbox.max_limit };
  if (Number(values.page) > pricing.sandbox.max_page) return { name: 'page', top: pricing.sandbox.max_page };
  return null;
}

// A field name as words, when the locales have none for it: council_configuration -> Council configuration.
export function humanise(name: string): string {
  const words = name.replace(/[_-]+/g, ' ').trim();
  if (!words) return name;
  if (words === words.toUpperCase()) return words;
  const spelled = words.replace(/\b(dg|eu|ms|oj|url|uri|id|ep|pe|ted|cpv|vat|pic|sme|iso|fte|rsb|tris)\b/gi, (w) => w.toUpperCase());
  return spelled.charAt(0).toUpperCase() + spelled.slice(1);
}

const LEFT_KEY = 'brubru.console.left';

// A convenience only: how many free calls this browser was last told it has today. The API keeps the real count.
export function rememberedCallsLeft(today: string = new Date().toISOString().slice(0, 10)): number | null {
  try {
    const saved = JSON.parse(localStorage.getItem(LEFT_KEY) || 'null');
    // Zero is not remembered: the visitor may be on another connection by now, and only the API can say no.
    return saved && saved.date === today && typeof saved.left === 'number' && saved.left > 0 ? saved.left : null;
  } catch {
    return null;
  }
}

export function rememberCallsLeft(left: number, today: string = new Date().toISOString().slice(0, 10)): void {
  try {
    localStorage.setItem(LEFT_KEY, JSON.stringify({ date: today, left }));
  } catch {
    // Private windows and blocked storage: the count simply starts again from the next answer.
  }
}

// A live source with no count: the API answers what it has read plus one more page, and the number grows as you page.
// Other routes with partial coverage give a real count, so the shape of the number decides, not the flag alone.
export function totalIsEstimate(json: unknown, rowsShown: number, page: number, limit: number): boolean {
  const o: any = json && typeof json === 'object' ? json : {};
  return o.coverage_complete === false && o.has_more === true && o.total === (page - 1) * limit + rowsShown + limit;
}

export function totalOf(json: unknown): number | null {
  const total = json && typeof json === 'object' ? (json as any).total : null;
  return typeof total === 'number' ? total : null;
}

export function reasonOf(json: unknown): { code: string; message: string } {
  const o: any = json && typeof json === 'object' ? json : {};
  const detail = o.detail && typeof o.detail === 'object' ? o.detail : o;
  const message = typeof detail.error === 'string' ? detail.error
    : typeof o.detail === 'string' ? o.detail
      : typeof detail.message === 'string' ? detail.message : '';
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
