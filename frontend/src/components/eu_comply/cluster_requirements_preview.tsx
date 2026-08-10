// frontend/src/components/eu_comply/cluster_requirements_preview.tsx
//
// "What will be checked", shown in the workspace before anything is uploaded.
//
// GET /eu-law-comply/clusters/{id}/requirements has existed and worked since
// the feature was built, and was called by nothing. So the flow asked a user to
// hand over internal policy documents without being able to see a single one of
// the obligations they would be measured against. For a paying compliance
// customer that is a trust problem, not a missing nicety -- and the data was
// already one fetch away.

import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../hooks/use_auth';
import './cluster_requirements_preview.css';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const INITIAL_VISIBLE = 8;

interface PreviewRequirement {
  id: number;
  article_number: string;
  requirement_text: string;
  criticality: string;
  law_celex: string;
  law_title: string;
  deadline: string | null;
  extra_metadata?: { addressee?: string } | null;
}

// Who the obligation binds, tagged on the requirement row by
// scripts/enrich_requirement_metadata.py. Worth surfacing: a package of 38
// obligations where 3 bind Member States is a different proposition from one
// where all 38 bind you, and the old UI could not tell the difference.
const ADDRESSEE_LABEL: Record<string, string> = {
  member_state: 'Member States',
  commission: 'European Commission',
  pro: 'Producer responsibility organisations',
  online_platform: 'Online platform providers',
  fulfilment_service: 'Fulfilment service providers',
  national_authority: 'Competent national authorities',
  notified_body: 'Notified bodies',
};

const addresseeOf = (r: PreviewRequirement): string =>
  r.extra_metadata?.addressee || 'economic_operator';

interface Props {
  clusterId: number;
  requirementCount: number;
}

export const ClusterRequirementsPreview = ({ clusterId, requirementCount }: Props) => {
  const { t } = useTranslation();
  const [items, setItems] = useState<PreviewRequirement[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [visible, setVisible] = useState(INITIAL_VISIBLE);
  const [criticality, setCriticality] = useState<string>('all');

  // One fetch per cluster, tracked in a ref rather than in state.
  //
  // The first version guarded on `loading` AND listed it as a dependency. So
  // setLoading(true) re-ran the effect, the previous run's cleanup set
  // cancelled = true on the request that was still in flight, its response was
  // thrown away, and the guard then blocked any retry: the list never
  // appeared. Depend only on what genuinely identifies the request.
  const fetchedFor = useRef<number | null>(null);

  useEffect(() => {
    if (!open || fetchedFor.current === clusterId) return;
    const token = useAuth.getState().token;
    if (!token) return;
    fetchedFor.current = clusterId;
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const r = await fetch(
          `${API_BASE_URL}/api/eu-law-comply/clusters/${clusterId}/requirements`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        if (!r.ok) throw new Error(String(r.status));
        const d = await r.json();
        if (!cancelled) setItems(Array.isArray(d) ? d : []);
      } catch {
        if (!cancelled) {
          setError(t('comply.preview.error', 'Could not load the obligation list.'));
          fetchedFor.current = null;  // let a re-expand try again
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [open, clusterId, t]);

  const counts = useMemo(() => {
    const c: Record<string, number> = { critical: 0, important: 0, recommended: 0 };
    items.forEach((i) => { if (i.criticality in c) c[i.criticality] += 1; });
    return c;
  }, [items]);

  const filtered = useMemo(
    () => (criticality === 'all' ? items : items.filter((i) => i.criticality === criticality)),
    [items, criticality],
  );

  const withDeadline = useMemo(() => items.filter((i) => i.deadline).length, [items]);
  const bindElsewhere = useMemo(
    () => items.filter((i) => addresseeOf(i) !== 'economic_operator').length,
    [items],
  );

  return (
    <section className={`cluster-preview${open ? ' is-open' : ''}`}>
      <button
        type="button"
        className="cluster-preview__toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className={`mdi ${open ? 'mdi-chevron-down' : 'mdi-chevron-right'}`}></span>
        <span className="cluster-preview__toggle-text">
          {t('comply.preview.title', 'See what will be checked')}
        </span>
        <span className="cluster-preview__count">
          {t('comply.preview.count', {
            defaultValue: '{{count}} obligations',
            count: requirementCount,
          })}
        </span>
      </button>

      {open && (
        <div className="cluster-preview__body">
          {loading && (
            <p className="cluster-preview__status">
              <span className="mdi mdi-loading mdi-spin"></span>
              {t('comply.preview.loading', 'Loading obligations')}
            </p>
          )}

          {error && <p className="cluster-preview__status is-error">{error}</p>}

          {!loading && !error && items.length > 0 && (
            <>
              <p className="cluster-preview__intro">
                {t('comply.preview.intro',
                  'These are the obligations your documents will be measured against. Nothing is uploaded until you choose to run the analysis.')}
                {bindElsewhere > 0 && ' ' + t('comply.preview.boundElsewhere', {
                  defaultValue:
                    '{{count}} of them bind another actor, such as Member States, and are shown for context rather than scored against you.',
                  count: bindElsewhere,
                })}
              </p>

              <div className="cluster-preview__filters" role="group">
                {(['all', 'critical', 'important', 'recommended'] as const).map((k) => (
                  <button
                    key={k}
                    type="button"
                    className={`cluster-preview__chip${criticality === k ? ' is-active' : ''}`}
                    onClick={() => { setCriticality(k); setVisible(INITIAL_VISIBLE); }}
                  >
                    {k === 'all'
                      ? t('comply.report.filterAll')
                      : t(`comply.report.criticality${k[0].toUpperCase()}${k.slice(1)}`)}
                    {' '}({k === 'all' ? items.length : counts[k] ?? 0})
                  </button>
                ))}
                {withDeadline > 0 && (
                  <span className="cluster-preview__deadline-note">
                    <span className="mdi mdi-calendar-clock"></span>
                    {t('comply.preview.withDeadline', {
                      defaultValue: '{{count}} with a dated deadline',
                      count: withDeadline,
                    })}
                  </span>
                )}
              </div>

              <ul className="cluster-preview__list">
                {filtered.slice(0, visible).map((r) => (
                  <li key={r.id} className="cluster-preview__item">
                    <div className="cluster-preview__item-head">
                      <code>{r.article_number}</code>
                      <span className={`cluster-preview__crit criticality-${r.criticality}`}>
                        {r.criticality}
                      </span>
                      {r.deadline && (
                        <span className="cluster-preview__deadline">
                          <span className="mdi mdi-calendar-clock"></span>
                          {new Date(r.deadline).toLocaleDateString()}
                        </span>
                      )}
                      {addresseeOf(r) !== 'economic_operator' && (
                        <span className="cluster-preview__addressee">
                          <span className="mdi mdi-account-arrow-right-outline"></span>
                          {ADDRESSEE_LABEL[addresseeOf(r)] || addresseeOf(r)}
                        </span>
                      )}
                      <span className="cluster-preview__celex">{r.law_celex}</span>
                    </div>
                    <p className="cluster-preview__text">{r.requirement_text}</p>
                  </li>
                ))}
              </ul>

              {filtered.length > visible && (
                <button
                  type="button"
                  className="cluster-preview__more"
                  onClick={() => setVisible((v) => v + 20)}
                >
                  <span className="mdi mdi-chevron-down"></span>
                  {t('comply.browser.showMore', {
                    defaultValue: 'Show {{count}} more',
                    count: filtered.length - visible,
                  })}
                </button>
              )}
            </>
          )}

          {!loading && !error && items.length === 0 && (
            <p className="cluster-preview__status">
              {t('comply.preview.empty', 'This package has no obligations recorded yet.')}
            </p>
          )}
        </div>
      )}
    </section>
  );
};
