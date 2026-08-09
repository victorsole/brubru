// Carrying "where you came from" into Chat.
//
// Asking Brubru about a dossier used to be a one-way trip: the only
// discoverable route back was the header, which lands on My EU Bubble's
// default tab with the file modal gone. These helpers put the origin in the
// URL -- not router state -- so the way back survives a reload and a shared
// link, and so Chat can name the place it will return you to.

/** Max characters kept from a caller-supplied label, to bound URL length. */
const MAX_LABEL = 72;

/**
 * Paths a return link is allowed to point at. The value arrives from the
 * query string, so it is attacker-controllable in a shared link: without an
 * allowlist this is an open redirect. Same-origin relative paths only.
 */
const ALLOWED_PREFIXES = ['/my-eu-bubble', '/amendator', '/eulawcomply', '/tenderator'];

export interface ChatReturn {
  /** Relative path to navigate back to, already validated. */
  href: string;
  /** Human label for the button, or null to fall back to a generic one. */
  label: string | null;
}

/**
 * Build the `from`/`fromLabel` pair for a /chat URL.
 * Pass the location you want the user sent back to, plus what to call it.
 */
export const chatReturnParams = (href: string, label?: string | null): Record<string, string> => {
  const params: Record<string, string> = {};
  if (!isSafeReturnPath(href)) return params;
  params.from = href;
  const clean = (label || '').trim().replace(/\s+/g, ' ');
  if (clean) params.fromLabel = clean.slice(0, MAX_LABEL);
  return params;
};

/**
 * A return target must be a same-origin relative path on a known product.
 * Rejects absolute URLs, protocol-relative `//evil.com`, and backslash
 * variants that some browsers normalise to a scheme separator.
 */
export const isSafeReturnPath = (value: string | null | undefined): boolean => {
  if (!value) return false;
  const v = value.trim();
  if (!v.startsWith('/')) return false;
  if (v.startsWith('//') || v.startsWith('/\\')) return false;
  if (v.includes('://')) return false;
  const path = v.split('?')[0].split('#')[0];
  return ALLOWED_PREFIXES.some((p) => path === p || path.startsWith(`${p}/`) || path.startsWith(`${p}?`));
};

/** Read a validated return target out of the current query string. */
export const readChatReturn = (search: URLSearchParams): ChatReturn | null => {
  const from = search.get('from');
  if (!isSafeReturnPath(from)) return null;
  const label = (search.get('fromLabel') || '').trim();
  return { href: from as string, label: label ? label.slice(0, MAX_LABEL) : null };
};
