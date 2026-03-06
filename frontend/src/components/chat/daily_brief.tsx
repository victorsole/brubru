// frontend/src/components/chat/daily_brief.tsx
import { useState, useEffect } from 'react';
import './daily_brief.css';

const API_BASE_URL = import.meta.env?.VITE_API_URL || (window as any).REACT_APP_API_URL || 'http://localhost:8000';

interface BriefItem {
  headline: string;
  url: string;
  source: string;
  category: string;
  snippet: string | null;
  suggested_query: string | null;
}

interface BriefStats {
  total_guides: number;
  total_files: number;
  last_trained: string | null;
}

interface DailyBriefProps {
  onQueryClick: (query: string) => void;
}

export const DailyBrief = ({ onQueryClick }: DailyBriefProps) => {
  const [items, setItems] = useState<BriefItem[]>([]);
  const [stats, setStats] = useState<BriefStats | null>(null);
  const [briefDate, setBriefDate] = useState<string>('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchBrief = async () => {
      try {
        const [briefRes, statsRes] = await Promise.all([
          fetch(`${API_BASE_URL}/api/daily-brief?limit=5`),
          fetch(`${API_BASE_URL}/api/daily-brief/stats`),
        ]);

        if (briefRes.ok) {
          const data = await briefRes.json();
          setItems(data.items || []);
          setBriefDate(data.date || '');
        }

        if (statsRes.ok) {
          setStats(await statsRes.json());
        }
      } catch (err) {
        console.error('Failed to fetch daily brief:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchBrief();
  }, []);

  if (loading) return null;
  if (items.length === 0 && !stats) return null;

  const formatDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr + 'T00:00:00');
      return d.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    } catch {
      return dateStr;
    }
  };

  const categoryIcon = (cat: string) => {
    switch (cat) {
      case 'ec': return 'mdi-domain';
      case 'ep': return 'mdi-account-group';
      case 'council': return 'mdi-shield-crown';
      case 'ecb': return 'mdi-bank';
      default: return 'mdi-newspaper';
    }
  };

  return (
    <div className="daily-brief">
      {/* Knowledge stats badge */}
      {stats && (
        <div className="daily-brief__stats">
          <span className="mdi mdi-brain" />
          <span>
            {stats.total_guides} knowledge guides
            {' '}&middot;{' '}
            {stats.total_files.toLocaleString()} legislative files tracked
            {stats.last_trained && (
              <>{' '}&middot;{' '}Last updated: {formatDate(stats.last_trained)}</>
            )}
          </span>
        </div>
      )}

      {/* Daily Brief headlines */}
      {items.length > 0 && (
        <div className="daily-brief__card">
          <div className="daily-brief__header">
            <span className="mdi mdi-newspaper-variant-outline" />
            <h3>Today in Brussels</h3>
            {briefDate && (
              <span className="daily-brief__date">{formatDate(briefDate)}</span>
            )}
          </div>

          <div className="daily-brief__items">
            {items.map((item, i) => (
              <button
                key={i}
                type="button"
                className="daily-brief__item"
                onClick={() => onQueryClick(item.suggested_query || `Tell me about: ${item.headline}`)}
                title={`Ask Brubru about this: ${item.headline}`}
              >
                <span className={`mdi ${categoryIcon(item.category)} daily-brief__item-icon`} />
                <span className="daily-brief__item-text">
                  {item.headline}
                </span>
                <span className="mdi mdi-arrow-right daily-brief__item-arrow" />
              </button>
            ))}
          </div>

          <p className="daily-brief__hint">
            Click any headline to ask Brubru about it
          </p>
        </div>
      )}
    </div>
  );
};
