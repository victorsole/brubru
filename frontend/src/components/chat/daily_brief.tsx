// frontend/src/components/chat/daily_brief.tsx
// Dashboard grid: combines daily headlines, example prompts, and knowledge stats
import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
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

interface ExamplePrompt {
  id: string;
  text: string;
}

interface DailyBriefProps {
  onQueryClick: (query: string) => void;
  examplePrompts: ExamplePrompt[];
  onExampleClick: (example: ExamplePrompt) => void;
}

const CARD_ICONS = [
  'mdi-newspaper-variant-outline',
  'mdi-account-group',
  'mdi-magnify',
  'mdi-gavel',
];

const CARD_COLOURS = ['blue', 'purple', 'green', 'amber'] as const;

export const DailyBrief = ({ onQueryClick, examplePrompts, onExampleClick }: DailyBriefProps) => {
  const { t, i18n } = useTranslation();
  const [items, setItems] = useState<BriefItem[]>([]);
  const [stats, setStats] = useState<BriefStats | null>(null);
  const [briefDate, setBriefDate] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [expandedHeadlines, setExpandedHeadlines] = useState(false);
  const [activeStatIndex, setActiveStatIndex] = useState(0);

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

  // Rotating stats ticker
  useEffect(() => {
    if (!stats) return;
    const interval = setInterval(() => {
      setActiveStatIndex((prev) => (prev + 1) % 3);
    }, 4000);
    return () => clearInterval(interval);
  }, [stats]);

  if (loading) return null;

  const formatDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr + 'T00:00:00');
      return d.toLocaleDateString(i18n.language || 'en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
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

  // Build the 4 cards: first is always "Today in Brussels" with top headline,
  // remaining 3 are from example prompts
  const topHeadline = items[0];
  const remainingHeadlines = items.slice(1);

  const statLines = stats ? [
    t('brief.statGuides', { count: stats.total_guides }),
    t('brief.statFiles', { count: stats.total_files.toLocaleString() }),
    stats.last_trained ? t('brief.statUpdated', { date: formatDate(stats.last_trained) }) : t('brief.statUpdatedToday'),
  ] : [];

  return (
    <div className="dashboard-welcome">
      {/* 2x2 Card Grid */}
      <div className="dashboard-welcome__grid">
        {/* Card 1: Today in Brussels */}
        <button
          type="button"
          className="dashboard-welcome__card dashboard-welcome__card--blue"
          onClick={() => {
            if (topHeadline) {
              onQueryClick(topHeadline.suggested_query || t('brief.tellMeAbout', { topic: topHeadline.headline }));
            }
          }}
          disabled={!topHeadline}
        >
          <div className="dashboard-welcome__card-icon">
            <span className="mdi mdi-newspaper-variant-outline" />
          </div>
          <div className="dashboard-welcome__card-content">
            <span className="dashboard-welcome__card-label">{t('chat.todayInBrussels')}</span>
            <span className="dashboard-welcome__card-text">
              {topHeadline ? topHeadline.headline : t('brief.loadingHeadlines')}
            </span>
          </div>
          <span className="mdi mdi-arrow-right dashboard-welcome__card-arrow" />
        </button>

        {/* Cards 2-4: Example prompts */}
        {examplePrompts.slice(0, 3).map((ex, i) => (
          <button
            key={ex.id}
            type="button"
            className={`dashboard-welcome__card dashboard-welcome__card--${CARD_COLOURS[i + 1]}`}
            onClick={() => onExampleClick(ex)}
          >
            <div className="dashboard-welcome__card-icon">
              <span className={`mdi ${CARD_ICONS[i + 1]}`} />
            </div>
            <div className="dashboard-welcome__card-content">
              <span className="dashboard-welcome__card-label">
                {i === 0 ? t('brief.epPlenary') : i === 1 ? t('brief.askAnything') : t('brief.policyIntelligence')}
              </span>
              <span className="dashboard-welcome__card-text">{ex.text}</span>
            </div>
            <span className="mdi mdi-arrow-right dashboard-welcome__card-arrow" />
          </button>
        ))}
      </div>

      {/* Expandable headlines */}
      {remainingHeadlines.length > 0 && (
        <div className={`dashboard-welcome__more-headlines ${expandedHeadlines ? 'dashboard-welcome__more-headlines--open' : ''}`}>
          <button
            type="button"
            className="dashboard-welcome__more-toggle"
            onClick={() => setExpandedHeadlines(!expandedHeadlines)}
          >
            <span className="mdi mdi-newspaper" />
            <span>{expandedHeadlines ? t('brief.hide') : t('brief.moreHeadlines', { count: remainingHeadlines.length })} {t('brief.headlines')}{briefDate ? ` ${t('brief.forDate', { date: formatDate(briefDate) })}` : ''}</span>
            <span className={`mdi ${expandedHeadlines ? 'mdi-chevron-up' : 'mdi-chevron-down'} dashboard-welcome__more-chevron`} />
          </button>
          {expandedHeadlines && (
            <div className="dashboard-welcome__headline-list">
              {remainingHeadlines.map((item, i) => (
                <button
                  key={i}
                  type="button"
                  className="dashboard-welcome__headline-item"
                  onClick={() => onQueryClick(item.suggested_query || t('brief.tellMeAbout', { topic: item.headline }))}
                >
                  <span className={`mdi ${categoryIcon(item.category)} dashboard-welcome__headline-icon`} />
                  <span className="dashboard-welcome__headline-text">{item.headline}</span>
                  <span className="mdi mdi-arrow-right dashboard-welcome__headline-arrow" />
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Animated stats ticker */}
      {stats && statLines.length > 0 && (
        <div className="dashboard-welcome__stats">
          <span className="mdi mdi-brain dashboard-welcome__stats-icon" />
          <div className="dashboard-welcome__stats-ticker">
            {statLines.map((line, i) => (
              <span
                key={i}
                className={`dashboard-welcome__stats-line ${i === activeStatIndex ? 'dashboard-welcome__stats-line--active' : ''}`}
              >
                {line}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
