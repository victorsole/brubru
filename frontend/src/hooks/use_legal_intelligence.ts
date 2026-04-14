// frontend/src/hooks/use_legal_intelligence.ts
//
// React hooks for the legal-text intelligence layer. Wrap the three backend
// endpoints under /api/legislation/* with in-memory caching so a law's
// recital-article map and defined-terms are fetched at most once per session.
//
// Exposed:
//   useRecitalArticleMap(celex)  -> recitals linked to each article
//   useDefinedTerms(celex)       -> statutory definitions from Articles 3/4
//   useAnnotatedTexts(celex, texts)  -> legal text with cross-refs + definitions wrapped
//   useCoverageStats()           -> aggregate numbers for Analytics tab
//

import { useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from './use_auth';

const API_BASE = `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api`;

const _authHeaders = (): Record<string, string> => {
  const token = useAuth.getState().token;
  return token ? { Authorization: `Bearer ${token}` } : {};
};

// ------------------------------------------------------------------
// Types
// ------------------------------------------------------------------

export interface RecitalLink {
  recital_number: string;
  score: number;
  snippet: string;
}

export type RecitalArticleMap = Record<string, RecitalLink[]>;

export interface DefinedTerm {
  term: string;
  definition: string;
  article: string;
  point?: string;
}

export type DefinedTermsMap = Record<string, DefinedTerm>;

export interface CoverageStats {
  global: {
    total_laws: number;
    with_recital_map: number;
    with_defined_terms: number;
  };
  tracked: {
    total: number;
    with_recital_map: number;
    with_defined_terms: number;
  };
  aggregates: {
    total_article_buckets: number;
    total_recital_links: number;
    total_defined_terms: number;
  };
  top_laws_by_links: Array<{ celex: string; title: string; link_count: number }>;
}

// ------------------------------------------------------------------
// Per-session caches. Kept module-scoped to survive component unmounts.
// ------------------------------------------------------------------

const _recitalMapCache = new Map<string, RecitalArticleMap>();
const _definedTermsCache = new Map<string, DefinedTermsMap>();
const _annotateCache = new Map<string, string>();

const _mkKey = (celex: string | undefined, text: string) => `${celex || ''}::${text}`;

// ------------------------------------------------------------------
// Hooks
// ------------------------------------------------------------------

export function useRecitalArticleMap(celex: string | undefined) {
  const [data, setData] = useState<RecitalArticleMap | null>(
    celex ? _recitalMapCache.get(celex) ?? null : null,
  );
  const [loading, setLoading] = useState(!!celex && !_recitalMapCache.has(celex || ''));

  useEffect(() => {
    if (!celex) {
      setData(null);
      setLoading(false);
      return;
    }
    if (_recitalMapCache.has(celex)) {
      setData(_recitalMapCache.get(celex)!);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    fetch(`${API_BASE}/legislation/${encodeURIComponent(celex)}/recital-article-map`, {
      headers: _authHeaders(),
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((json) => {
        if (cancelled) return;
        const map = (json?.map || null) as RecitalArticleMap | null;
        if (map) _recitalMapCache.set(celex, map);
        setData(map);
      })
      .catch(() => setData(null))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [celex]);

  return { data, loading };
}

export function useDefinedTerms(celex: string | undefined) {
  const [data, setData] = useState<DefinedTermsMap | null>(
    celex ? _definedTermsCache.get(celex) ?? null : null,
  );
  const [loading, setLoading] = useState(!!celex && !_definedTermsCache.has(celex || ''));

  useEffect(() => {
    if (!celex) {
      setData(null);
      setLoading(false);
      return;
    }
    if (_definedTermsCache.has(celex)) {
      setData(_definedTermsCache.get(celex)!);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    fetch(`${API_BASE}/legislation/${encodeURIComponent(celex)}/defined-terms`, {
      headers: _authHeaders(),
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((json) => {
        if (cancelled) return;
        const map = (json?.terms || null) as DefinedTermsMap | null;
        if (map) _definedTermsCache.set(celex, map);
        setData(map);
      })
      .catch(() => setData(null))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [celex]);

  return { data, loading };
}

/**
 * Annotate an array of raw legal-text paragraphs with cross-references,
 * acronym links and defined-term spans. Returns an array of HTML strings in
 * the same order as the input.
 *
 * Behaviour:
 * - Identical (text, celex) pairs are memoised, so re-renders are free.
 * - Texts already present in cache short-circuit the network call.
 * - On network failure, the original raw text is returned (no annotation, but
 *   the UI still renders correctly).
 */
export function useAnnotatedTexts(celex: string | undefined, texts: string[]) {
  const textsKey = useMemo(() => texts.map((t) => _mkKey(celex, t)).join('\u0001'), [celex, texts]);
  const [data, setData] = useState<string[] | null>(null);
  const [loading, setLoading] = useState(false);
  const ref = useRef({ texts, celex });
  ref.current = { texts, celex };

  useEffect(() => {
    if (!texts.length) {
      setData([]);
      return;
    }
    // Serve fully from cache if possible
    const cached = texts.map((t) => _annotateCache.get(_mkKey(celex, t)));
    if (cached.every((v): v is string => v !== undefined)) {
      setData(cached);
      return;
    }
    let cancelled = false;
    setLoading(true);
    fetch(`${API_BASE}/legislation/annotate-text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ..._authHeaders() },
      body: JSON.stringify({ texts, celex: celex || null }),
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((json) => {
        if (cancelled) return;
        const htmls = Array.isArray(json?.html) ? (json.html as string[]) : null;
        if (htmls && htmls.length === texts.length) {
          htmls.forEach((h, i) => _annotateCache.set(_mkKey(celex, texts[i]), h));
          setData(htmls);
        } else {
          setData(texts); // fallback: raw
        }
      })
      .catch(() => !cancelled && setData(texts))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [textsKey]);

  return { data, loading };
}

/**
 * One-shot fetch of the aggregate coverage stats used by the Analytics tab.
 */
export function useCoverageStats(autoFetch = true) {
  const [data, setData] = useState<CoverageStats | null>(null);
  const [loading, setLoading] = useState(autoFetch);

  const refresh = () => {
    setLoading(true);
    fetch(`${API_BASE}/legislation/coverage-stats`, { headers: _authHeaders() })
      .then((r) => (r.ok ? r.json() : null))
      .then((json) => setData(json as CoverageStats | null))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (autoFetch) refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoFetch]);

  return { data, loading, refresh };
}
