/**
 * Analytics Tab Component
 *
 * Displays analytics, charts, and engagement metrics.
 * Part of My EU Bubble - Phase 3: Frontend
 */

import { useEffect, useState, useMemo, useRef } from 'react';
import Icon from '@mdi/react';
import { mdiChartBar, mdiBookOpen, mdiClockOutline, mdiTextBox, mdiOpenInNew } from '@mdi/js';
import { useBubble } from '../../hooks/use_bubble';
import './analytics_tab.css';

export const AnalyticsTab = () => {
  const {
    userStats,
    documentStats,
    fetchUserStats,
    fetchDocumentStats,
  } = useBubble();

  useEffect(() => {
    fetchUserStats();
    fetchDocumentStats();
  }, []);

  // EU Law Analytics (static snapshot)
  type Snapshot = {
    totals_by_type: Record<string, number>;
    years: number[];
    per_year: Record<string, { Regulation: number; Directive: number; total: number }>;
    policy_areas: string[];
    per_policy_area: Record<string, { Regulation: number; Directive: number; total: number }>;
    min_year?: number;
    max_year?: number;
  };

  const [euSnapshot, setEuSnapshot] = useState<Snapshot | null>(null);
  const [selectedAreas, setSelectedAreas] = useState<string[]>([]);
  const [lightbox, setLightbox] = useState<null | { src: string; title: string }>(null);
  const closeBtnRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    // Load pre-rendered snapshot from public assets
    fetch('/analytics/eu_law_snapshot.json')
      .then((r) => r.json())
      .then((data: Snapshot) => {
        setEuSnapshot(data);
        setSelectedAreas(data.policy_areas || []);
      })
      .catch(() => {
        // no-op if snapshot not available
      });
  }, []);

  // Lightbox: keyboard close on ESC and focus management
  useEffect(() => {
    if (!lightbox) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setLightbox(null);
    };
    window.addEventListener('keydown', onKey);
    // focus close button after opening
    const t = setTimeout(() => closeBtnRef.current?.focus(), 0);
    return () => {
      window.removeEventListener('keydown', onKey);
      clearTimeout(t);
    };
  }, [lightbox]);

  const areaRows = useMemo(() => {
    if (!euSnapshot) return [];
    const max = Math.max(
      1,
      ...euSnapshot.policy_areas.map((a) => euSnapshot.per_policy_area[a]?.total || 0)
    );
    return (euSnapshot.policy_areas || []).map((a) => {
      const v = euSnapshot.per_policy_area[a]?.total || 0;
      return { area: a, total: v, pct: Math.min(100, (v / max) * 100) };
    });
  }, [euSnapshot]);

  const visibleRows = useMemo(() => {
    if (!euSnapshot) return [];
    const set = new Set(selectedAreas);
    return areaRows.filter((r) => set.has(r.area));
  }, [euSnapshot, areaRows, selectedAreas]);

  const readingTimeMinutes = userStats?.average_reading_time_seconds
    ? Math.round(userStats.average_reading_time_seconds / 60)
    : 0;

  return (
    <div className="analytics-tab">
      <h2>Analytics & Insights</h2>

      {/* Key Metrics */}
      <div className="analytics-tab__metrics-grid">
        <div className="analytics-tab__metric-card">
          <div className="analytics-tab__metric-icon">
            <Icon path={mdiChartBar} size={1.5} color="#0693E3" />
          </div>
          <div className="analytics-tab__metric-value">
            {documentStats?.total_documents || 0}
          </div>
          <div className="analytics-tab__metric-label">Total Documents</div>
        </div>

        <div className="analytics-tab__metric-card">
          <div className="analytics-tab__metric-icon">
            <Icon path={mdiBookOpen} size={1.5} color="#0693E3" />
          </div>
          <div className="analytics-tab__metric-value">
            {userStats?.total_reads || 0}
          </div>
          <div className="analytics-tab__metric-label">Articles Read</div>
        </div>

        <div className="analytics-tab__metric-card">
          <div className="analytics-tab__metric-icon">
            <Icon path={mdiClockOutline} size={1.5} color="#0693E3" />
          </div>
          <div className="analytics-tab__metric-value">
            {readingTimeMinutes}m
          </div>
          <div className="analytics-tab__metric-label">Avg. Reading Time</div>
        </div>

        <div className="analytics-tab__metric-card">
          <div className="analytics-tab__metric-icon">
            <Icon path={mdiTextBox} size={1.5} color="#0693E3" />
          </div>
          <div className="analytics-tab__metric-value">
            {documentStats?.total_word_count?.toLocaleString() || 0}
          </div>
          <div className="analytics-tab__metric-label">Total Words Written</div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="analytics-tab__charts-grid">
        {/* Documents by Type */}
        <div className="analytics-tab__chart-card">
          <h3 className="analytics-tab__chart-title">Documents by Type</h3>
          <div className="analytics-tab__chart">
            {documentStats && Object.keys(documentStats.by_type || {}).length > 0 ? (
              <div className="analytics-tab__bar-chart">
                {Object.entries(documentStats.by_type || {}).map(([type, count]) => {
                  const percentage = (count / (documentStats.total_documents || 1)) * 100;
                  return (
                    <div key={type} className="analytics-tab__bar-row">
                      <div className="analytics-tab__bar-label">{type}</div>
                      <div className="analytics-tab__bar-container">
                        <div
                          className="analytics-tab__bar-fill"
                          style={{ width: `${percentage}%` }}
                          data-type={type}
                        />
                      </div>
                      <div className="analytics-tab__bar-value">{count}</div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="analytics-tab__chart-empty">
                No data available yet
              </div>
            )}
          </div>
        </div>

        {/* Top Policy Areas */}
        <div className="analytics-tab__chart-card">
          <h3 className="analytics-tab__chart-title">Top Policy Areas</h3>
          <div className="analytics-tab__chart">
            {documentStats && Object.keys(documentStats.by_policy_area || {}).length > 0 ? (
              <div className="analytics-tab__policy-list">
                {Object.entries(documentStats.by_policy_area || {})
                  .sort(([, a], [, b]) => b - a)
                  .slice(0, 8)
                  .map(([area, count], idx) => (
                    <div key={area} className="analytics-tab__policy-row">
                      <div className="analytics-tab__policy-rank">{idx + 1}</div>
                      <div className="analytics-tab__policy-name">{area}</div>
                      <div className="analytics-tab__policy-count">{count}</div>
                    </div>
                  ))}
              </div>
            ) : (
              <div className="analytics-tab__chart-empty">
                No policy area data yet
              </div>
            )}
          </div>
        </div>
      </div>

      {/* EU Law Analytics (Static) */}
      <div className="analytics-tab__section">
        <h3>
          EU Law Analytics (Regulations & Directives)
          <a
            href="/analytics/eu_law_linguistics.html"
            target="_blank"
            rel="noopener noreferrer"
            className="analytics-tab__linguistics-link"
          >
            <Icon path={mdiOpenInNew} size={0.7} />
            Linguistic Patterns
          </a>
        </h3>
        <div className="analytics-tab__static-grid">
          <div className="analytics-tab__static-card">
            <h4>By Year</h4>
            <button
              className="analytics-tab__img-button"
              onClick={() => setLightbox({ src: '/analytics/eu_law_by_year.svg', title: 'EU Law by Year' })}
              aria-label="Enlarge EU law by year chart"
            >
              <img src="/analytics/eu_law_by_year.svg" alt="EU law by year" />
            </button>
          </div>
          <div className="analytics-tab__static-card">
            <h4>By Policy Area (All)</h4>
            <button
              className="analytics-tab__img-button"
              onClick={() => setLightbox({ src: '/analytics/eu_law_by_policy_area.svg', title: 'EU Law by Policy Area' })}
              aria-label="Enlarge EU law by policy area chart"
            >
              <img src="/analytics/eu_law_by_policy_area.svg" alt="EU law by policy area" />
            </button>
          </div>
          <div className="analytics-tab__static-card">
            <h4>Heatmap</h4>
            <button
              className="analytics-tab__img-button"
              onClick={() => setLightbox({ src: '/analytics/eu_law_heatmap.svg', title: 'EU Law Heatmap' })}
              aria-label="Enlarge EU law heatmap"
            >
              <img src="/analytics/eu_law_heatmap.svg" alt="EU law heatmap" />
            </button>
          </div>
        </div>
      </div>

      {/* Interactive Policy Areas (snapshot-driven) */}
      {euSnapshot && (
        <div className="analytics-tab__section">
          <h3>Policy Areas Selector</h3>
          <div className="analytics-tab__selector">
            <div className="analytics-tab__selector-actions">
              <button onClick={() => setSelectedAreas(euSnapshot.policy_areas)}>Select All</button>
              <button onClick={() => setSelectedAreas([])}>Clear All</button>
            </div>
            <div className="analytics-tab__selector-list">
              {(euSnapshot.policy_areas || []).map((a) => (
                <label key={a} className="analytics-tab__selector-item">
                  <input
                    type="checkbox"
                    checked={selectedAreas.includes(a)}
                    onChange={(e) => {
                      setSelectedAreas((prev) =>
                        e.target.checked ? [...prev, a] : prev.filter((x) => x !== a)
                      );
                    }}
                  />
                  <span>{a}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="analytics-tab__barlist">
            {visibleRows.map((row) => (
              <div key={row.area} className="analytics-tab__barrow">
                <div className="analytics-tab__barrow-label">{row.area}</div>
                <div className="analytics-tab__barrow-bar">
                  <div
                    className="analytics-tab__barrow-fill"
                    style={{ width: `${row.pct}%` }}
                    title={`${row.total} acts`}
                  />
                </div>
                <div className="analytics-tab__barrow-value">{row.total}</div>
              </div>
            ))}
            {visibleRows.length === 0 && (
              <div className="analytics-tab__chart-empty">No policy areas selected</div>
            )}
          </div>
        </div>
      )}

      {/* Lightbox overlay */}
      {lightbox && (
        <div
          className="analytics-tab__lightbox"
          role="dialog"
          aria-modal="true"
          aria-label={lightbox.title}
          onClick={() => setLightbox(null)}
        >
          <div className="analytics-tab__lightbox-inner" onClick={(e) => e.stopPropagation()}>
            <div className="analytics-tab__lightbox-header">
              <div className="analytics-tab__lightbox-title">{lightbox.title}</div>
              <button
                ref={closeBtnRef}
                className="analytics-tab__lightbox-close"
                onClick={() => setLightbox(null)}
                aria-label="Close"
              >
                ✕
              </button>
            </div>
            <div className="analytics-tab__lightbox-body">
              <img src={lightbox.src} alt={lightbox.title} />
            </div>
          </div>
        </div>
      )}

      {/* Activity Summary */}
      <div className="analytics-tab__activity">
        <h3>Feed Activity Summary</h3>
        <div className="analytics-tab__activity-grid">
          <div className="analytics-tab__activity-card">
            <div className="analytics-tab__activity-label">Active Subscriptions</div>
            <div className="analytics-tab__activity-value">
              {userStats?.active_subscriptions || 0}
              <span className="analytics-tab__activity-total">
                / {userStats?.total_subscriptions || 0}
              </span>
            </div>
          </div>

          <div className="analytics-tab__activity-card">
            <div className="analytics-tab__activity-label">Saved Articles</div>
            <div className="analytics-tab__activity-value">
              {userStats?.total_saves || 0}
            </div>
          </div>
        </div>

        {/* Favorite Sources */}
        {userStats && userStats.favorite_sources.length > 0 && (
          <div className="analytics-tab__favorites">
            <h4>Your Favorite News Sources</h4>
            <div className="analytics-tab__source-chips">
              {userStats.favorite_sources.map((source, idx) => (
                <div key={idx} className="analytics-tab__source-chip">
                  {source}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Most Read Categories */}
        {userStats && userStats.most_read_categories.length > 0 && (
          <div className="analytics-tab__favorites">
            <h4>Most Read Categories</h4>
            <div className="analytics-tab__source-chips">
              {userStats.most_read_categories.map((category, idx) => (
                <div key={idx} className="analytics-tab__category-chip">
                  {category}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Export Section */}
      <div className="analytics-tab__export">
        <h3>Export Your Data</h3>
        <p>Download your documents and reading history</p>
        <div className="analytics-tab__export-buttons">
          <button className="analytics-tab__export-btn">
            Export Documents (PDF)
          </button>
          <button className="analytics-tab__export-btn">
            Export Reading List (CSV)
          </button>
          <button className="analytics-tab__export-btn">
            Export Analytics Report
          </button>
        </div>
      </div>
    </div>
  );
};
