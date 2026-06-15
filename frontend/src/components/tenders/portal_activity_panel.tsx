// frontend/src/components/tenders/portal_activity_panel.tsx
//
// Sidebar panel showing the EU Funding & Tenders Portal's latest news + next
// upcoming events. Sits in the dashboard right rail above BodiesPanel. Data
// from /api/tenders/portal-activity (economy_items body_code='ftportal').

import { useEffect, useState } from 'react';
import { useAuth } from '../../hooks/use_auth';
import './portal_activity_panel.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface PortalItem {
  id: number;
  title: string;
  summary: string | null;
  document_date: string | null;
  source_url: string;
}

const formatDate = (iso: string | null, shortLabel = false): string => {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: shortLabel ? 'short' : 'long',
    year: 'numeric',
  });
};

export const PortalActivityPanel = () => {
  const { token } = useAuth();
  const [news, setNews] = useState<PortalItem[]>([]);
  const [events, setEvents] = useState<PortalItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    fetch(`${API_URL}/api/tenders/portal-activity?news_limit=5&events_limit=5`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : { news: [], events: [] }))
      .then((d) => {
        setNews(d.news || []);
        setEvents(d.events || []);
      })
      .catch(() => {
        setNews([]);
        setEvents([]);
      })
      .finally(() => setLoading(false));
  }, [token]);

  if (!loading && news.length === 0 && events.length === 0) return null;

  return (
    <div className="portal-activity-panel">
      <div className="portal-activity-panel__header">
        <span className="mdi mdi-newspaper-variant-outline" aria-hidden="true" />
        F&amp;T Portal activity
      </div>

      {loading && (
        <div className="portal-activity-panel__loading">
          <span className="mdi mdi-loading mdi-spin" aria-hidden="true" />
        </div>
      )}

      {!loading && events.length > 0 && (
        <div className="portal-activity-panel__section">
          <div className="portal-activity-panel__subheader">
            <span className="mdi mdi-calendar-clock-outline" aria-hidden="true" />
            Upcoming events
          </div>
          <ul className="portal-activity-panel__list">
            {events.map((it) => (
              <li key={`ev-${it.id}`} className="portal-activity-panel__item">
                <a
                  className="portal-activity-panel__link"
                  href={it.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={it.summary || it.title}
                >
                  <span className="portal-activity-panel__date">
                    {formatDate(it.document_date, true)}
                  </span>
                  <span className="portal-activity-panel__title">{it.title}</span>
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      {!loading && news.length > 0 && (
        <div className="portal-activity-panel__section">
          <div className="portal-activity-panel__subheader">
            <span className="mdi mdi-rss" aria-hidden="true" />
            Latest news
          </div>
          <ul className="portal-activity-panel__list">
            {news.map((it) => (
              <li key={`nw-${it.id}`} className="portal-activity-panel__item">
                <a
                  className="portal-activity-panel__link"
                  href={it.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={it.summary || it.title}
                >
                  <span className="portal-activity-panel__date">
                    {formatDate(it.document_date, true)}
                  </span>
                  <span className="portal-activity-panel__title">{it.title}</span>
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
