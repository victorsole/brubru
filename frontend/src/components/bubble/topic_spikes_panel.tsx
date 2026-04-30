/**
 * Topic Spikes Panel
 *
 * Shows the top topic clusters from the last 7 days, aggregated across
 * daily_briefs + eprs_publications + legislative_carriages. Lives at the top
 * of the Analytics tab so users can see what is moving in the EU right now
 * without searching.
 */

import { useEffect, useState } from 'react';
import Icon from '@mdi/react';
import { mdiTrendingUp, mdiNewspaperVariantOutline, mdiBookOpenBlankVariant, mdiFileTreeOutline, mdiLoading } from '@mdi/js';
import './topic_spikes_panel.css';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface TopicSpike {
  topic: string;
  weight: number;
  brief_count: number;
  eprs_count: number;
  carriage_count: number;
  sample_titles: string[];
}

interface TopicSpikesResponse {
  period_start: string;
  period_end: string;
  items: TopicSpike[];
}

const formatDate = (iso: string) => {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
};

export const TopicSpikesPanel = () => {
  const [data, setData] = useState<TopicSpikesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/analytics/public/topic-spikes?days=7&top=5`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const body = await res.json();
        if (!cancelled) setData(body);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load topic spikes');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="topic-spikes-panel topic-spikes-panel--loading">
        <Icon path={mdiLoading} size={0.9} spin /> Loading topic spikes…
      </div>
    );
  }

  if (error || !data) return null;
  if (data.items.length === 0) return null;

  const maxWeight = Math.max(1, ...data.items.map((i) => i.weight));

  return (
    <div className="topic-spikes-panel">
      <div className="topic-spikes-panel__header">
        <h3 className="topic-spikes-panel__title">
          <Icon path={mdiTrendingUp} size={0.9} />
          Topic spikes: what moved this week
        </h3>
        <span className="topic-spikes-panel__period">
          {formatDate(data.period_start)} → {formatDate(data.period_end)}
        </span>
      </div>

      <p className="topic-spikes-panel__intro">
        Each row groups Brubru&rsquo;s scraper output for the last 7 days into a topic.
        The bar shows relative activity (longest = most things happened). The three
        counts on the right tell you <em>where</em> that activity came from.
      </p>

      <div className="topic-spikes-panel__legend-keys">
        <span className="topic-spikes-panel__legend-key" title="Daily-brief headlines surfaced by Brubru's news scraper">
          <Icon path={mdiNewspaperVariantOutline} size={0.7} />
          <span>News headlines</span>
        </span>
        <span className="topic-spikes-panel__legend-key" title="EPRS / STOA / JRC / ART research publications synced this week">
          <Icon path={mdiBookOpenBlankVariant} size={0.7} />
          <span>Research publications</span>
        </span>
        <span className="topic-spikes-panel__legend-key" title="Legislative files updated in OEIL or EUR-Lex this week">
          <Icon path={mdiFileTreeOutline} size={0.7} />
          <span>Legislative files</span>
        </span>
      </div>

      <ul className="topic-spikes-panel__list">
        {data.items.map((item, idx) => (
          <li key={item.topic} className="topic-spikes-panel__row">
            <div className="topic-spikes-panel__row-rank">{idx + 1}</div>

            <div className="topic-spikes-panel__row-main">
              <div className="topic-spikes-panel__row-topic">{item.topic}</div>
              {item.sample_titles.length > 0 && (
                <div className="topic-spikes-panel__row-samples">
                  {item.sample_titles.slice(0, 2).map((t, i) => (
                    <span key={i} className="topic-spikes-panel__sample" title={t}>
                      &ldquo;{t.length > 80 ? t.slice(0, 80) + '…' : t}&rdquo;
                    </span>
                  ))}
                </div>
              )}

              <div className="topic-spikes-panel__bar-wrap" aria-hidden="true">
                <div
                  className="topic-spikes-panel__bar"
                  style={{ width: `${(item.weight / maxWeight) * 100}%` }}
                />
              </div>
            </div>

            <div className="topic-spikes-panel__row-counts">
              <span title={`${item.brief_count} news headline${item.brief_count === 1 ? '' : 's'} this week`}>
                <Icon path={mdiNewspaperVariantOutline} size={0.6} />
                <span className="topic-spikes-panel__count-num">{item.brief_count}</span>
                <span className="topic-spikes-panel__count-label">news</span>
              </span>
              <span title={`${item.eprs_count} research publication${item.eprs_count === 1 ? '' : 's'} this week`}>
                <Icon path={mdiBookOpenBlankVariant} size={0.6} />
                <span className="topic-spikes-panel__count-num">{item.eprs_count}</span>
                <span className="topic-spikes-panel__count-label">research</span>
              </span>
              <span title={`${item.carriage_count} legislative file${item.carriage_count === 1 ? '' : 's'} updated this week`}>
                <Icon path={mdiFileTreeOutline} size={0.6} />
                <span className="topic-spikes-panel__count-num">{item.carriage_count}</span>
                <span className="topic-spikes-panel__count-label">files</span>
              </span>
            </div>
          </li>
        ))}
      </ul>

      <p className="topic-spikes-panel__legend">
        Composite score: 1 × news headline + 2 × EPRS publication + 3 × legislative-file update.
        Aggregated daily from Brubru&rsquo;s scrapers.
      </p>
    </div>
  );
};
