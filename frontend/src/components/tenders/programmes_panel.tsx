// frontend/src/components/tenders/programmes_panel.tsx
//
// Phase 5: small panel on the dashboard right rail showing the catalogue
// of EU funding programmes. Click a programme to filter the feed by its
// name. Click "All programmes" to open a modal with the full list.

import { useEffect, useState } from 'react';
import { useAuth } from '../../hooks/use_auth';
import './programmes_panel.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface Programme {
  programme_code: string;
  name: string;
  parent_framework: string | null;
  budget_total: number | null;
  budget_currency: string | null;
  period_start: string | null;
  period_end: string | null;
  description: string | null;
  source_url: string;
}

interface ProgrammesPanelProps {
  onPickProgramme: (programme: Programme) => void;
}

const TOP_CODES = ['HE', 'DEP', 'LIFE', 'CEF', 'EU4H', 'ERASMUS'];

const formatBudget = (value: number | null, currency: string | null): string => {
  if (!value) return '';
  const c = currency || 'EUR';
  if (value >= 1e9) return `${(value / 1e9).toFixed(1)}B ${c}`;
  if (value >= 1e6) return `${(value / 1e6).toFixed(0)}M ${c}`;
  return `${value} ${c}`;
};

const periodLabel = (start: string | null, end: string | null): string => {
  if (!start && !end) return '';
  const sy = start ? new Date(start).getFullYear() : '';
  const ey = end ? new Date(end).getFullYear() : '';
  return `${sy}-${ey}`;
};

export const ProgrammesPanel = ({ onPickProgramme }: ProgrammesPanelProps) => {
  const { token } = useAuth();
  const [items, setItems] = useState<Programme[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    fetch(`${API_URL}/api/tenders/programmes`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : { items: [] }))
      .then((d) => setItems(d.items || []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [token]);

  if (!loading && items.length === 0) return null;

  const visible = showAll ? items : items.filter((p) => TOP_CODES.includes(p.programme_code));

  return (
    <div className="programmes-panel">
      <div className="programmes-panel__header">
        <span className="mdi mdi-shape-outline" aria-hidden="true" />
        EU funding programmes
      </div>

      {loading && (
        <div className="programmes-panel__loading">
          <span className="mdi mdi-loading mdi-spin" aria-hidden="true" />
        </div>
      )}

      {!loading && visible.length > 0 && (
        <ul className="programmes-panel__list">
          {visible.map((p) => (
            <li key={p.programme_code} className="programmes-panel__item">
              <button
                type="button"
                className="programmes-panel__item-button"
                onClick={() => onPickProgramme(p)}
                title={p.description || p.name}
              >
                <span className="programmes-panel__code">{p.programme_code}</span>
                <span className="programmes-panel__body">
                  <span className="programmes-panel__name">{p.name}</span>
                  <span className="programmes-panel__meta">
                    {formatBudget(p.budget_total, p.budget_currency)}
                    {periodLabel(p.period_start, p.period_end) && (
                      <span className="programmes-panel__period">
                        {' '}
                        {periodLabel(p.period_start, p.period_end)}
                      </span>
                    )}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {!loading && items.length > TOP_CODES.length && (
        <button
          type="button"
          className="programmes-panel__toggle"
          onClick={() => setShowAll((v) => !v)}
        >
          {showAll ? 'Show fewer' : `Show all ${items.length} programmes`}
          <span
            className={`mdi ${showAll ? 'mdi-chevron-up' : 'mdi-chevron-down'}`}
            aria-hidden="true"
          />
        </button>
      )}
    </div>
  );
};

export type { Programme };
