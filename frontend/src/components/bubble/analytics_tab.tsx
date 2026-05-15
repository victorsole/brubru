/**
 * Analytics Tab Component
 *
 * Displays deep dives, EU law analytics, and engagement metrics.
 * Part of My EU Bubble - Phase 3: Frontend
 */

import { useEffect, useState, useMemo, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import {
  mdiChartBar, mdiBookOpen, mdiClockOutline, mdiTextBox,
  mdiOpenInNew, mdiBookOpenPageVariantOutline, mdiChevronDown, mdiChevronUp,
  mdiLinkVariant, mdiLibraryShelves,
} from '@mdi/js';
import { useBubble } from '../../hooks/use_bubble';
import { DEEP_DIVES, getDeepDiveUrl, LANG_LABELS } from '../../utils/deep_dive_map';
import { useCoverageStats } from '../../hooks/use_legal_intelligence';
import { TopicSpikesPanel } from './topic_spikes_panel';
import './analytics_tab.css';

export const AnalyticsTab = () => {
  const { t } = useTranslation();
  const { data: coverage } = useCoverageStats();
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
  const [policyOpen, setPolicyOpen] = useState(false);
  const closeBtnRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    fetch('/analytics/eu_law_snapshot.json')
      .then((r) => r.json())
      .then((data: Snapshot) => {
        setEuSnapshot(data);
        setSelectedAreas(data.policy_areas || []);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!lightbox) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setLightbox(null);
    };
    window.addEventListener('keydown', onKey);
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

  const totalActs = useMemo(() => {
    if (!euSnapshot) return 0;
    return areaRows.reduce((sum, r) => sum + r.total, 0);
  }, [areaRows, euSnapshot]);

  const readingTimeMinutes = userStats?.average_reading_time_seconds
    ? Math.round(userStats.average_reading_time_seconds / 60)
    : 0;

  // Check if user has any activity data worth showing
  const hasActivity = (documentStats?.total_documents || 0) > 0
    || (userStats?.total_reads || 0) > 0
    || (userStats?.active_subscriptions || 0) > 0
    || (userStats?.total_saves || 0) > 0;

  // Most recent deep dive gets a "NEW" badge
  const newestIdx = DEEP_DIVES.length - 1;

  return (
    <div className="analytics-tab">
      <h2>{t('analyticsTab.title')}</h2>

      {/* ---- 0. TOPIC SPIKES (live, last 7 days) ---- */}
      <TopicSpikesPanel />

      {/* ---- 1. DEEP DIVE LIBRARY (hero section) ---- */}
      <div className="analytics-tab__section analytics-tab__section--hero">
        <h3>
          <Icon path={mdiBookOpenPageVariantOutline} size={0.9} />
          {' '}{t('analyticsTab.deepDiveLibrary')}
        </h3>
        <p className="analytics-tab__section-subtitle">
          {t('analyticsTab.deepDiveSubtitle')}
        </p>
        <div className="analytics-tab__deep-dive-grid">
          {DEEP_DIVES.map((dd, idx) => (
            <div key={dd.procedureRef} className="analytics-tab__deep-dive-card" style={{ borderTopColor: dd.color }}>
              <div className="analytics-tab__deep-dive-header">
                <span className="analytics-tab__deep-dive-icon" style={{ color: dd.color }}>
                  <span className={`mdi ${dd.icon}`} />
                </span>
                <span className="analytics-tab__deep-dive-ref">{dd.comReference}</span>
                {idx === newestIdx && (
                  <span className="analytics-tab__deep-dive-badge">{t('analyticsTab.newBadge')}</span>
                )}
              </div>
              <h4 className="analytics-tab__deep-dive-title">{dd.title}</h4>
              <p className="analytics-tab__deep-dive-procedure">{dd.procedureRef}</p>
              <div className="analytics-tab__deep-dive-langs">
                {dd.languages.map((lang) => (
                  <a
                    key={lang}
                    href={getDeepDiveUrl(dd, lang)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="analytics-tab__deep-dive-lang"
                    style={{ borderColor: dd.color, color: dd.color }}
                  >
                    {LANG_LABELS[lang] || lang.toUpperCase()}
                  </a>
                ))}
              </div>
              <a
                href={getDeepDiveUrl(dd, 'en')}
                target="_blank"
                rel="noopener noreferrer"
                className="analytics-tab__deep-dive-cta"
                style={{ backgroundColor: dd.color }}
              >
                <Icon path={mdiOpenInNew} size={0.7} />
                {t('analyticsTab.readAnalysis')}
              </a>
            </div>
          ))}
        </div>
        {/* Link to the EU Canon library (public deep-dive index, SEO-only surface) */}
        <a
          href="/eucanon/"
          target="_blank"
          rel="noopener noreferrer"
          className="analytics-tab__eucanon-link"
          aria-label={t('analyticsTab.euCanonLinkCta')}
        >
          <Icon path={mdiLibraryShelves} size={0.8} />
          <span>{t('analyticsTab.euCanonLink')}</span>
          <Icon path={mdiOpenInNew} size={0.7} />
        </a>
      </div>

      {/* ---- 2. EU LAW ANALYTICS (static charts) ---- */}
      <div className="analytics-tab__section">
        <h3>
          {t('analyticsTab.euLawAnalytics')}
          <a
            href="/analytics/eu_law_linguistics.html"
            target="_blank"
            rel="noopener noreferrer"
            className="analytics-tab__linguistics-link"
          >
            <Icon path={mdiOpenInNew} size={0.7} />
            {t('analyticsTab.linguisticPatterns')}
          </a>
        </h3>
        <div className="analytics-tab__static-grid">
          <div className="analytics-tab__static-card">
            <h4>{t('analyticsTab.byYear')}</h4>
            <button
              className="analytics-tab__img-button"
              onClick={() => setLightbox({ src: '/analytics/eu_law_by_year.svg', title: t('analyticsTab.altByYear') })}
              aria-label={t('analyticsTab.enlargeByYear')}
            >
              <img src="/analytics/eu_law_by_year.svg" alt={t('analyticsTab.altByYear')} />
            </button>
          </div>
          <div className="analytics-tab__static-card">
            <h4>{t('analyticsTab.byPolicyArea')}</h4>
            <button
              className="analytics-tab__img-button"
              onClick={() => setLightbox({ src: '/analytics/eu_law_by_policy_area.svg', title: t('analyticsTab.altByArea') })}
              aria-label={t('analyticsTab.enlargeByArea')}
            >
              <img src="/analytics/eu_law_by_policy_area.svg" alt={t('analyticsTab.altByArea')} />
            </button>
          </div>
          <div className="analytics-tab__static-card">
            <h4>{t('analyticsTab.heatmap')}</h4>
            <button
              className="analytics-tab__img-button"
              onClick={() => setLightbox({ src: '/analytics/eu_law_heatmap.svg', title: t('analyticsTab.altHeatmap') })}
              aria-label={t('analyticsTab.enlargeHeatmap')}
            >
              <img src="/analytics/eu_law_heatmap.svg" alt={t('analyticsTab.altHeatmap')} />
            </button>
          </div>
        </div>
      </div>

      {/* ---- LEGAL-TEXT INTELLIGENCE COVERAGE ---- */}
      {coverage && (
        <div className="analytics-tab__section">
          <h3>
            <Icon path={mdiLinkVariant} size={0.9} style={{ marginRight: 6, verticalAlign: 'middle' }} />
            {t('analyticsTab.legalTextIntelligence')}
          </h3>
          <p style={{ fontSize: '0.85rem', color: '#6b7280', marginTop: 0 }}>
            {t('analyticsTab.legalTextSubtitle')}
          </p>

          <div className="analytics-tab__static-grid">
            <div className="analytics-tab__static-card">
              <h4>{t('analyticsTab.trackedLaws')}</h4>
              <div style={{ fontSize: '2rem', fontWeight: 700, color: '#0693e3', lineHeight: 1.1 }}>
                {coverage.tracked.with_recital_map}
                <span style={{ fontSize: '0.95rem', fontWeight: 400, color: '#6b7280' }}>
                  {' '}/ {coverage.tracked.total}
                </span>
              </div>
              <div style={{ fontSize: '0.78rem', color: '#6b7280' }}>
                {t('analyticsTab.withRecitalMapsCached')}
              </div>
              <div style={{ fontSize: '0.78rem', color: '#6b7280', marginTop: '0.35rem' }}>
                {t('analyticsTab.withStatutoryDefs', { n: coverage.tracked.with_defined_terms, total: coverage.tracked.total })}
              </div>
            </div>

            <div className="analytics-tab__static-card">
              <h4>{t('analyticsTab.allLaws')}</h4>
              <div style={{ fontSize: '2rem', fontWeight: 700, color: '#059669', lineHeight: 1.1 }}>
                {coverage.global.with_recital_map.toLocaleString()}
                <span style={{ fontSize: '0.95rem', fontWeight: 400, color: '#6b7280' }}>
                  {' '}/ {coverage.global.total_laws.toLocaleString()}
                </span>
              </div>
              <div style={{ fontSize: '0.78rem', color: '#6b7280' }}>
                {t('analyticsTab.withRecitalMaps')}
              </div>
              <div style={{ fontSize: '0.78rem', color: '#6b7280', marginTop: '0.35rem' }}>
                {t('analyticsTab.withDefinitions', { n: coverage.global.with_defined_terms.toLocaleString() })}
              </div>
            </div>

            <div className="analytics-tab__static-card">
              <h4>{t('analyticsTab.aggregateLinks')}</h4>
              <div style={{ fontSize: '2rem', fontWeight: 700, color: '#9b51e0', lineHeight: 1.1 }}>
                {coverage.aggregates.total_recital_links.toLocaleString()}
              </div>
              <div style={{ fontSize: '0.78rem', color: '#6b7280' }}>
                {t('analyticsTab.semanticLinks')}
              </div>
              <div style={{ fontSize: '0.78rem', color: '#6b7280', marginTop: '0.35rem' }}>
                {t('analyticsTab.statutoryTermsIndexed', { n: coverage.aggregates.total_defined_terms.toLocaleString() })}
              </div>
            </div>
          </div>

          {coverage.top_laws_by_links.length > 0 && (
            <div style={{ marginTop: '1rem' }}>
              <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.5rem' }}>
                {t('analyticsTab.mostLinkedLaws')}
              </h4>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0, fontSize: '0.85rem' }}>
                {coverage.top_laws_by_links.map((law) => (
                  <li
                    key={law.celex}
                    style={{
                      display: 'flex',
                      gap: '0.5rem',
                      alignItems: 'baseline',
                      padding: '0.35rem 0',
                      borderBottom: '1px solid #f3f4f6',
                    }}
                  >
                    <span
                      style={{
                        fontFamily: 'monospace',
                        fontSize: '0.78rem',
                        color: '#0693e3',
                        minWidth: 95,
                      }}
                    >
                      {law.celex}
                    </span>
                    <span style={{ flex: 1, color: '#374151' }}>{law.title}</span>
                    <span
                      style={{
                        fontWeight: 700,
                        color: '#9b51e0',
                        minWidth: 60,
                        textAlign: 'right',
                      }}
                    >
                      {law.link_count} {t('analyticsTab.linksLabel')}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* ---- 3. POLICY AREAS EXPLORER (collapsible) ---- */}
      {euSnapshot && (
        <div className="analytics-tab__section">
          <button
            className="analytics-tab__collapsible-header"
            onClick={() => setPolicyOpen(!policyOpen)}
            aria-expanded={policyOpen}
          >
            <h3>{t('analyticsTab.policyExplorer')}</h3>
            <span className="analytics-tab__collapsible-summary">
              {t('analyticsTab.policyAreasSummary', { areas: euSnapshot.policy_areas.length, acts: totalActs.toLocaleString() })}
            </span>
            <Icon path={policyOpen ? mdiChevronUp : mdiChevronDown} size={1} />
          </button>

          {policyOpen && (
            <>
              <div className="analytics-tab__selector">
                <div>
                  <div className="analytics-tab__selector-actions">
                    <button onClick={() => setSelectedAreas(euSnapshot.policy_areas)}>{t('analyticsTab.selectAll')}</button>
                    <button onClick={() => setSelectedAreas([])}>{t('analyticsTab.clearAll')}</button>
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
                <div />
              </div>

              <div className="analytics-tab__barlist">
                {visibleRows.map((row) => (
                  <div key={row.area} className="analytics-tab__barrow">
                    <div className="analytics-tab__barrow-label">{row.area}</div>
                    <div className="analytics-tab__barrow-bar">
                      <div
                        className="analytics-tab__barrow-fill"
                        style={{ width: `${row.pct}%` }}
                        title={t('analyticsTab.actsCount', { n: row.total })}
                      />
                    </div>
                    <div className="analytics-tab__barrow-value">{row.total}</div>
                  </div>
                ))}
                {visibleRows.length === 0 && (
                  <div className="analytics-tab__chart-empty">{t('analyticsTab.noPolicyAreas')}</div>
                )}
              </div>
            </>
          )}
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
                aria-label={t('common.close')}
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

      {/* ---- 4. YOUR ACTIVITY (only if user has data) ---- */}
      {hasActivity ? (
        <div className="analytics-tab__section">
          <h3>{t('analyticsTab.yourActivity')}</h3>
          <div className="analytics-tab__metrics-grid">
            {(documentStats?.total_documents || 0) > 0 && (
              <div className="analytics-tab__metric-card">
                <div className="analytics-tab__metric-icon">
                  <Icon path={mdiChartBar} size={1.5} color="#0693E3" />
                </div>
                <div className="analytics-tab__metric-value">
                  {documentStats?.total_documents || 0}
                </div>
                <div className="analytics-tab__metric-label">{t('analyticsTab.totalDocuments')}</div>
              </div>
            )}

            {(userStats?.total_reads || 0) > 0 && (
              <div className="analytics-tab__metric-card">
                <div className="analytics-tab__metric-icon">
                  <Icon path={mdiBookOpen} size={1.5} color="#0693E3" />
                </div>
                <div className="analytics-tab__metric-value">
                  {userStats?.total_reads || 0}
                </div>
                <div className="analytics-tab__metric-label">{t('analyticsTab.articlesRead')}</div>
              </div>
            )}

            {readingTimeMinutes > 0 && (
              <div className="analytics-tab__metric-card">
                <div className="analytics-tab__metric-icon">
                  <Icon path={mdiClockOutline} size={1.5} color="#0693E3" />
                </div>
                <div className="analytics-tab__metric-value">
                  {readingTimeMinutes}m
                </div>
                <div className="analytics-tab__metric-label">{t('analyticsTab.avgReadingTime')}</div>
              </div>
            )}

            {(documentStats?.total_word_count || 0) > 0 && (
              <div className="analytics-tab__metric-card">
                <div className="analytics-tab__metric-icon">
                  <Icon path={mdiTextBox} size={1.5} color="#0693E3" />
                </div>
                <div className="analytics-tab__metric-value">
                  {documentStats?.total_word_count?.toLocaleString() || 0}
                </div>
                <div className="analytics-tab__metric-label">{t('analyticsTab.totalWordsWritten')}</div>
              </div>
            )}
          </div>

          {/* Charts Row */}
          <div className="analytics-tab__charts-grid">
            {documentStats && Object.keys(documentStats.by_type || {}).length > 0 && (
              <div className="analytics-tab__chart-card">
                <h3 className="analytics-tab__chart-title">{t('analyticsTab.documentsByType')}</h3>
                <div className="analytics-tab__chart">
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
                </div>
              </div>
            )}

            {documentStats && Object.keys(documentStats.by_policy_area || {}).length > 0 && (
              <div className="analytics-tab__chart-card">
                <h3 className="analytics-tab__chart-title">{t('analyticsTab.topPolicyAreas')}</h3>
                <div className="analytics-tab__chart">
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
                </div>
              </div>
            )}
          </div>

          {/* Feed Activity */}
          <div className="analytics-tab__activity-grid" style={{ marginTop: '1rem' }}>
            {(userStats?.active_subscriptions || 0) > 0 && (
              <div className="analytics-tab__activity-card">
                <div className="analytics-tab__activity-label">{t('analyticsTab.activeSubscriptions')}</div>
                <div className="analytics-tab__activity-value">
                  {userStats?.active_subscriptions || 0}
                  <span className="analytics-tab__activity-total">
                    / {userStats?.total_subscriptions || 0}
                  </span>
                </div>
              </div>
            )}
            {(userStats?.total_saves || 0) > 0 && (
              <div className="analytics-tab__activity-card">
                <div className="analytics-tab__activity-label">{t('analyticsTab.savedArticles')}</div>
                <div className="analytics-tab__activity-value">
                  {userStats?.total_saves || 0}
                </div>
              </div>
            )}
          </div>

          {/* Favorite Sources */}
          {userStats && userStats.favorite_sources.length > 0 && (
            <div className="analytics-tab__favorites">
              <h4>{t('analyticsTab.favouriteSources')}</h4>
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
              <h4>{t('analyticsTab.mostReadCategories')}</h4>
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
      ) : (
        <div className="analytics-tab__section">
          <div className="analytics-tab__empty-state">
            <h3>{t('analyticsTab.yourActivity')}</h3>
            <p>{t('analyticsTab.emptyActivityHint')}</p>
          </div>
        </div>
      )}

      {/* ---- 5. EXPORT (only if user has data) ---- */}
      <div className={`analytics-tab__export ${!hasActivity ? 'analytics-tab__export--disabled' : ''}`}>
        <h3>{t('analyticsTab.exportData')}</h3>
        <p>{t('analyticsTab.exportSubtitle')}</p>
        <div className="analytics-tab__export-buttons">
          <button className="analytics-tab__export-btn" disabled={!hasActivity}>
            {t('analyticsTab.exportDocsPdf')}
          </button>
          <button className="analytics-tab__export-btn" disabled={!hasActivity}>
            {t('analyticsTab.exportReadingCsv')}
          </button>
          <button className="analytics-tab__export-btn" disabled={!hasActivity}>
            {t('analyticsTab.exportAnalyticsReport')}
          </button>
        </div>
      </div>
    </div>
  );
};
