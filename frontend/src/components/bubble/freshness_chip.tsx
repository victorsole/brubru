/**
 * FreshnessChip — "Updated X ago" indicator for a My EU Bubble feed.
 *
 * Reads /api/sync/freshness (shared module-level cache so many chips on a page
 * make ONE request). Pass a source key, or an array of keys (e.g. the three
 * News scrapers) and it shows the most recently succeeded one. Turns amber
 * when the backend flags the feed as stale.
 */
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import './freshness_chip.css';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface SourceFreshness {
  key: string;
  label: string;
  tier: string;
  status: string;
  last_run_at: string | null;
  last_success_at: string | null;
  stale: boolean;
}

let _cache: { at: number; map: Record<string, SourceFreshness> } | null = null;
let _inflight: Promise<Record<string, SourceFreshness>> | null = null;

async function loadFreshness(): Promise<Record<string, SourceFreshness>> {
  if (_cache && Date.now() - _cache.at < 60_000) return _cache.map;
  if (_inflight) return _inflight;
  _inflight = fetch(`${API_BASE_URL}/api/sync/freshness`)
    .then((r) => r.json())
    .then((j) => {
      const map: Record<string, SourceFreshness> = {};
      (j?.sources || []).forEach((s: SourceFreshness) => { map[s.key] = s; });
      _cache = { at: Date.now(), map };
      _inflight = null;
      return map;
    })
    .catch(() => { _inflight = null; return {}; });
  return _inflight;
}

export const FreshnessChip = ({ sourceKey }: { sourceKey: string | string[] }) => {
  const { t, i18n } = useTranslation();
  const [info, setInfo] = useState<SourceFreshness | null>(null);

  const keyId = Array.isArray(sourceKey) ? sourceKey.join(',') : sourceKey;
  useEffect(() => {
    let on = true;
    loadFreshness().then((map) => {
      if (!on) return;
      const keys = Array.isArray(sourceKey) ? sourceKey : [sourceKey];
      const entries = keys.map((k) => map[k]).filter(Boolean) as SourceFreshness[];
      if (!entries.length) { setInfo(null); return; }
      // Most recent success wins; if none succeeded, keep the first (stale).
      entries.sort((a, b) => (b.last_success_at || '').localeCompare(a.last_success_at || ''));
      setInfo(entries[0]);
    });
    return () => { on = false; };
  }, [keyId]);

  if (!info) return null;

  // Native localised relative time ("2 hours ago" / "hace 2 horas" / ...).
  const rel = (iso: string | null): string => {
    if (!iso) return t('bubble.freshness.notSynced', 'not synced yet');
    const rtf = new Intl.RelativeTimeFormat(i18n.language || 'en', { numeric: 'auto' });
    const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60_000);
    if (mins < 1) return rtf.format(0, 'minute');
    if (mins < 60) return rtf.format(-mins, 'minute');
    const h = Math.round(mins / 60);
    if (h < 24) return rtf.format(-h, 'hour');
    return rtf.format(-Math.round(h / 24), 'day');
  };

  const title = info.last_success_at
    ? `${t('bubble.freshness.updated', 'Updated')} ${new Date(info.last_success_at).toLocaleString('en-GB')}`
    : t('bubble.freshness.notSynced', 'not synced yet');

  return (
    <span
      className={`freshness-chip${info.stale ? ' freshness-chip--stale' : ''}`}
      title={title}
    >
      <span className="freshness-chip__dot" aria-hidden="true" />
      {t('bubble.freshness.updated', 'Updated')} {rel(info.last_success_at)}
    </span>
  );
};
