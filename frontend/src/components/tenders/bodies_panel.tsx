// frontend/src/components/tenders/bodies_panel.tsx
//
// Step 5 (All EU, with AI): right-rail panel listing the EU agencies that
// publish their own procurement on `economy_items` (the data behind the
// Tenderator's `source=agency` chip). Click an agency row to filter the
// feed to that body. Companion to ProgrammesPanel.

import { useEffect, useState } from 'react';
import { useAuth } from '../../hooks/use_auth';
import './bodies_panel.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface Body {
  body_code: string;
  acronym: string;
  name: string;
  total: number;
  open_count: number;
}

interface BodiesPanelProps {
  onPickBody: (body: Body) => void;
  activeBodyCode?: string;
}

export const BodiesPanel = ({ onPickBody, activeBodyCode = '' }: BodiesPanelProps) => {
  const { token } = useAuth();
  const [items, setItems] = useState<Body[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    fetch(`${API_URL}/api/tenders/bodies`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : { items: [] }))
      .then((d) => setItems(d.items || []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [token]);

  if (!loading && items.length === 0) return null;

  // Default view: top 5 by open_count; "Show all" expands the rest.
  const visible = showAll ? items : items.slice(0, 5);

  return (
    <div className="bodies-panel">
      <div className="bodies-panel__header">
        <span className="mdi mdi-office-building-outline" aria-hidden="true" />
        EU agencies Brubru watches
      </div>

      {loading && (
        <div className="bodies-panel__loading">
          <span className="mdi mdi-loading mdi-spin" aria-hidden="true" />
        </div>
      )}

      {!loading && visible.length > 0 && (
        <ul className="bodies-panel__list">
          {visible.map((b) => {
            const isActive = activeBodyCode === b.body_code;
            return (
              <li key={b.body_code} className="bodies-panel__item">
                <button
                  type="button"
                  className={`bodies-panel__item-button ${isActive ? 'bodies-panel__item-button--active' : ''}`}
                  onClick={() => onPickBody(b)}
                  title={b.name}
                >
                  <span className="bodies-panel__acronym">{b.acronym}</span>
                  <span className="bodies-panel__body">
                    <span className="bodies-panel__name">{b.name}</span>
                    <span className="bodies-panel__count">
                      {b.open_count > 0
                        ? `${b.open_count} open`
                        : `${b.total} archived`}
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {!loading && items.length > 5 && (
        <button
          type="button"
          className="bodies-panel__toggle"
          onClick={() => setShowAll((v) => !v)}
        >
          {showAll ? 'Show fewer' : `Show all ${items.length} agencies`}
          <span
            className={`mdi ${showAll ? 'mdi-chevron-up' : 'mdi-chevron-down'}`}
            aria-hidden="true"
          />
        </button>
      )}
    </div>
  );
};

export type { Body };
