/**
 * Hot This Week Widget
 *
 * Surfaces the top legislative files with recent activity (last 14 days)
 * at the top of the My Tracked Files tab. Anonymous-friendly: pulls from the
 * public /api/legislative-train/hot-this-week endpoint.
 *
 * Click a card to track the file (uses parent-supplied trackHandler).
 * Designed responsive: horizontal scroll on desktop/tablet, stacked on mobile.
 */

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import { mdiFire, mdiPlus, mdiOpenInNew, mdiLoading } from '@mdi/js';
import axios from 'axios';
import './hot_this_week_widget.css';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface HotItem {
  id: string;
  carriage_id: string;
  file_id: string;
  title: string;
  current_status: string;
  oeil_procedure_ref: string | null;
  celex_numbers: string[];
  lead_committee: string | null;
  last_updated: string | null;
  days_in_current_status: number | null;
  is_recently_updated: boolean;
}

interface HotThisWeekWidgetProps {
  onTrack?: (file: HotItem) => void | Promise<void>;
  isAuthenticated?: boolean;
}

const formatStatus = (s: string) => s.replace(/_/g, ' ');

/**
 * Pull a human-friendly first line out of a possibly-verbose carriage title.
 * Many carriage titles begin with a long preamble like "Implementation of the
 * Union's international obligations, as referred to in Article 15(2) of
 * Regulation (EU) No 1380/2013, …" — the user can't read that on a card.
 * Strategy: if the title has a comma and the first chunk is reasonably short,
 * show the first chunk + ellipsis. Otherwise show the first 110 chars.
 */
const cleanTitle = (raw: string): string => {
  if (!raw) return '';
  const t = raw.trim();
  if (t.length <= 110) return t;
  const firstComma = t.indexOf(', ');
  if (firstComma > 30 && firstComma < 100) {
    return t.slice(0, firstComma) + '…';
  }
  return t.slice(0, 107).trimEnd() + '…';
};

const formatRelative = (iso: string | null): string => {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (days === 0) return 'today';
  if (days === 1) return 'yesterday';
  if (days < 7) return `${days}d ago`;
  return `${Math.floor(days / 7)}w ago`;
};

export const HotThisWeekWidget = ({ onTrack, isAuthenticated = false }: HotThisWeekWidgetProps) => {
  const { t } = useTranslation();
  const [items, setItems] = useState<HotItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [trackingId, setTrackingId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await axios.get(`${API_BASE}/api/legislative-train/hot-this-week?limit=10`);
        if (!cancelled) setItems(res.data.items || []);
      } catch (e: unknown) {
        const ax = e as { message?: string };
        if (!cancelled) setError(ax.message || 'Failed to load hot files');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const handleTrack = async (item: HotItem) => {
    if (!onTrack) return;
    setTrackingId(item.carriage_id);
    try {
      await onTrack(item);
    } finally {
      setTrackingId(null);
    }
  };

  if (loading) {
    return (
      <div className="hot-this-week-widget hot-this-week-widget--loading">
        <Icon path={mdiLoading} size={0.9} spin /> Loading hot files…
      </div>
    );
  }

  if (error) {
    return null; // Fail-quiet: do not block the page
  }

  if (items.length === 0) {
    return null;
  }

  return (
    <div className="hot-this-week-widget">
      <h3 className="hot-this-week-widget__title">
        <Icon path={mdiFire} size={0.9} />
        {t('hotWeek.title')}
        <span className="hot-this-week-widget__subtitle">
          {t('hotWeek.subtitle')}
        </span>
      </h3>

      <div className="hot-this-week-widget__scroll" role="list">
        {items.map((item) => (
          <div key={item.carriage_id} className="hot-this-week-widget__card" role="listitem">
            <div className="hot-this-week-widget__card-meta">
              {item.oeil_procedure_ref && (
                <span className="hot-this-week-widget__ref">{item.oeil_procedure_ref}</span>
              )}
              {item.lead_committee && (
                <span className="hot-this-week-widget__committee">{item.lead_committee}</span>
              )}
            </div>
            <h4 className="hot-this-week-widget__card-title" title={item.title}>
              {cleanTitle(item.title)}
            </h4>
            <div className="hot-this-week-widget__card-status">
              <span className="hot-this-week-widget__status-pill" data-status={item.current_status}>
                {formatStatus(item.current_status)}
              </span>
              {item.last_updated && (
                <span className="hot-this-week-widget__last-updated">
                  {formatRelative(item.last_updated)}
                </span>
              )}
            </div>
            <div className="hot-this-week-widget__card-actions">
              {isAuthenticated && onTrack && (
                <button
                  className="hot-this-week-widget__track-btn"
                  onClick={() => handleTrack(item)}
                  disabled={trackingId === item.carriage_id}
                >
                  {trackingId === item.carriage_id ? (
                    <><Icon path={mdiLoading} size={0.6} spin /> {t('hotWeek.tracking')}</>
                  ) : (
                    <><Icon path={mdiPlus} size={0.6} /> {t('hotWeek.track')}</>
                  )}
                </button>
              )}
              {item.oeil_procedure_ref && (
                <a
                  className="hot-this-week-widget__open-btn"
                  href={`https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference=${encodeURIComponent(item.oeil_procedure_ref)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={t('hotWeek.openInOeil')}
                >
                  <Icon path={mdiOpenInNew} size={0.6} /> OEIL
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
