// frontend/src/components/eu_comply/run_diff.tsx
//
// "What changed since last time" -- the difference between this run and the
// previous completed run of the same package.
//
// This is the reason a workspace is worth having. A single compliance score is
// a number with no direction: 47% tells you nothing about whether the last
// quarter's remediation work landed. The diff does, obligation by obligation.
//
// Three buckets, and the third one matters. `improved` and `regressed` compare
// positions on the gap -> partial -> met scale. Anything moving to or from
// `not_applicable` is NOT on that scale -- a requirement that stops applying to
// you has not been "fixed" -- so it is reported separately as `reclassified`.
// Reporting those as improvements is exactly how a compliance report flatters
// its reader.

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../hooks/use_auth';
import './run_diff.css';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface DiffEntry {
  requirement_id: number;
  article: string;
  requirement_text: string;
  from: string;
  to: string;
}

interface DiffResponse {
  comparable: boolean;
  reason?: string;
  analysis_id: number;
  compared_with?: { analysis_id: number; ran_at: string | null; score: number | null };
  score_delta?: number | null;
  counts?: Record<string, number>;
  improved?: DiffEntry[];
  regressed?: DiffEntry[];
  reclassified?: DiffEntry[];
}

interface RunDiffProps {
  analysisId: number;
}

const STATUS_ICON: Record<string, string> = {
  met: 'mdi-check-circle',
  partial: 'mdi-alert-circle',
  gap: 'mdi-close-circle',
  not_applicable: 'mdi-minus-circle',
};

export const RunDiff = ({ analysisId }: RunDiffProps) => {
  const { t } = useTranslation();
  const [diff, setDiff] = useState<DiffResponse | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const token = useAuth.getState().token;
    if (!token || !analysisId) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(
          `${API_BASE_URL}/api/eu-law-comply/analysis/${analysisId}/diff`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        if (!r.ok) return;
        const d = await r.json();
        if (!cancelled) setDiff(d);
      } catch { /* the report below is unaffected */ }
    })();
    return () => { cancelled = true; };
  }, [analysisId]);

  // A first run has nothing to compare against, and saying so in a banner adds
  // nothing the user does not already know.
  if (!diff || !diff.comparable) return null;

  const counts = diff.counts || {};
  const improved = diff.improved || [];
  const regressed = diff.regressed || [];
  const reclassified = diff.reclassified || [];
  const delta = diff.score_delta;
  const changed = improved.length + regressed.length + reclassified.length;

  const label = (s: string) => t(`comply.report.status_${s}`, s.replace('_', ' '));

  const row = (e: DiffEntry, kind: string) => (
    <li className={`run-diff__row run-diff__row--${kind}`} key={`${kind}-${e.requirement_id}`}>
      <code className="run-diff__article">{e.article}</code>
      <span className="run-diff__move">
        <span className={`run-diff__status status-${e.from}`}>
          <span className={`mdi ${STATUS_ICON[e.from] || 'mdi-circle-small'}`}></span>
          {label(e.from)}
        </span>
        <span className="mdi mdi-arrow-right run-diff__arrow"></span>
        <span className={`run-diff__status status-${e.to}`}>
          <span className={`mdi ${STATUS_ICON[e.to] || 'mdi-circle-small'}`}></span>
          {label(e.to)}
        </span>
      </span>
      <span className="run-diff__text">{e.requirement_text}</span>
    </li>
  );

  return (
    <section className="run-diff">
      <button
        type="button"
        className="run-diff__toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className={`mdi ${open ? 'mdi-chevron-down' : 'mdi-chevron-right'}`}></span>
        <span className="run-diff__toggle-text">
          {t('comply.diff.heading', 'What changed since your last check')}
        </span>

        {delta != null && (
          <span className={`run-diff__delta${delta > 0 ? ' is-up' : delta < 0 ? ' is-down' : ''}`}>
            <span className={`mdi ${delta > 0 ? 'mdi-trending-up' : delta < 0 ? 'mdi-trending-down' : 'mdi-trending-neutral'}`}></span>
            {delta > 0 ? '+' : ''}{delta} {t('comply.diff.points', 'pts')}
          </span>
        )}

        <span className="run-diff__summary">
          {improved.length > 0 && (
            <span className="run-diff__pill is-improved">
              {improved.length} {t('comply.diff.improved', 'improved')}
            </span>
          )}
          {regressed.length > 0 && (
            <span className="run-diff__pill is-regressed">
              {regressed.length} {t('comply.diff.regressed', 'slipped')}
            </span>
          )}
          {reclassified.length > 0 && (
            <span className="run-diff__pill is-reclassified">
              {reclassified.length} {t('comply.diff.reclassified', 'reclassified')}
            </span>
          )}
          {changed === 0 && (
            <span className="run-diff__pill">
              {t('comply.diff.noChange', 'nothing changed')}
            </span>
          )}
        </span>
      </button>

      {open && (
        <div className="run-diff__body">
          <p className="run-diff__context">
            {t('comply.diff.comparedWith', 'Compared with your run of')}{' '}
            <strong>
              {diff.compared_with?.ran_at
                ? new Date(diff.compared_with.ran_at).toLocaleDateString()
                : t('comply.diff.earlier', 'an earlier date')}
            </strong>
            {diff.compared_with?.score != null && (
              <> ({Math.round(diff.compared_with.score)}%)</>
            )}
            {counts.unchanged != null && (
              <>
                {' '}&middot; {counts.unchanged} {t('comply.diff.unchanged', 'unchanged')}
              </>
            )}
            {counts.not_in_previous_run ? (
              <>
                {' '}&middot; {counts.not_in_previous_run}{' '}
                {t('comply.diff.newRequirements', 'not checked last time')}
              </>
            ) : null}
          </p>

          {regressed.length > 0 && (
            <>
              <h4 className="run-diff__group is-regressed">
                <span className="mdi mdi-arrow-down-bold-circle-outline"></span>
                {t('comply.diff.regressedHeading', 'Slipped back')}
              </h4>
              <ul className="run-diff__rows">{regressed.map((e) => row(e, 'regressed'))}</ul>
            </>
          )}

          {improved.length > 0 && (
            <>
              <h4 className="run-diff__group is-improved">
                <span className="mdi mdi-arrow-up-bold-circle-outline"></span>
                {t('comply.diff.improvedHeading', 'Improved')}
              </h4>
              <ul className="run-diff__rows">{improved.map((e) => row(e, 'improved'))}</ul>
            </>
          )}

          {reclassified.length > 0 && (
            <>
              <h4 className="run-diff__group is-reclassified">
                <span className="mdi mdi-swap-horizontal"></span>
                {t('comply.diff.reclassifiedHeading', 'Reclassified')}
              </h4>
              <p className="run-diff__note">
                {t(
                  'comply.diff.reclassifiedNote',
                  'These moved to or from "not applicable". That is a change in whether the obligation binds you, not progress on it.',
                )}
              </p>
              <ul className="run-diff__rows">{reclassified.map((e) => row(e, 'reclassified'))}</ul>
            </>
          )}
        </div>
      )}
    </section>
  );
};

export default RunDiff;
