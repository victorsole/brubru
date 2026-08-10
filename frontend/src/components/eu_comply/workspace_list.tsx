// frontend/src/components/eu_comply/workspace_list.tsx
//
// "Pick up where you left off" -- the packages this user has already worked on.
//
// Migration 209 made a compliance workspace durable: one per user and package,
// carrying every run, the documents each run was performed against, and the
// remediation state of each finding. `GET /workspaces` has been serving all of
// that since 10 August and no client had ever called it, so a returning user
// landed on the same catalogue of 43 packages as a first-time visitor, with no
// trace of the work already done.
//
// Deliberately shown ABOVE the catalogue and only when there is something to
// show: for a first-time user this component renders nothing at all rather than
// an empty-state box explaining a feature they have not used yet.

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../hooks/use_auth';
import './workspace_list.css';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface ComplianceWorkspaceSummary {
  id: number;
  cluster_id: number;
  name: string;
  run_count: number;
  last_run_at: string | null;
  latest_score: number | null;
  open_actions: number;
}

interface WorkspaceListProps {
  /** Opens the package, exactly as selecting it from the catalogue does. */
  onOpen: (clusterId: number) => void;
}

const scoreClass = (score: number | null): string => {
  if (score == null) return '';
  if (score >= 70) return ' is-good';
  if (score >= 40) return ' is-mid';
  return ' is-low';
};

/** "3 days ago" without pulling in a date library for one label. */
const relativeDate = (iso: string | null, t: (k: string, d?: string) => string): string => {
  if (!iso) return '';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const days = Math.floor((Date.now() - then) / 86400000);
  if (days <= 0) return t('comply.workspaces.today', 'today');
  if (days === 1) return t('comply.workspaces.yesterday', 'yesterday');
  if (days < 30) return `${days} ${t('comply.workspaces.daysAgo', 'days ago')}`;
  return new Date(iso).toLocaleDateString();
};

export const WorkspaceList = ({ onOpen }: WorkspaceListProps) => {
  const { t } = useTranslation();
  const [workspaces, setWorkspaces] = useState<ComplianceWorkspaceSummary[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const token = useAuth.getState().token;
    if (!token) { setWorkspaces([]); return; }
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${API_BASE_URL}/api/eu-law-comply/workspaces`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!r.ok) throw new Error(String(r.status));
        const d = await r.json();
        if (!cancelled) setWorkspaces(d.workspaces || []);
      } catch {
        // A failure here must not cost the user the catalogue below it, so the
        // section simply does not render. It is an accelerator, not the page.
        if (!cancelled) { setWorkspaces([]); setFailed(true); }
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (workspaces === null || workspaces.length === 0 || failed) return null;

  return (
    <section className="workspace-list" aria-labelledby="workspace-list-heading">
      <div className="workspace-list__head">
        <h2 className="workspace-list__heading" id="workspace-list-heading">
          <span className="mdi mdi-history"></span>
          {t('comply.workspaces.heading', 'Pick up where you left off')}
        </h2>
        <span className="workspace-list__count">
          {workspaces.length}{' '}
          {workspaces.length === 1
            ? t('comply.workspaces.package', 'package')
            : t('comply.workspaces.packages', 'packages')}
        </span>
      </div>

      <div className="workspace-list__grid">
        {workspaces.map((w) => (
          <button
            key={w.id}
            type="button"
            className="workspace-card"
            onClick={() => onOpen(w.cluster_id)}
          >
            <span className="workspace-card__name">{w.name}</span>

            <span className="workspace-card__metrics">
              {w.latest_score != null && (
                <span className={`workspace-card__score${scoreClass(w.latest_score)}`}>
                  {Math.round(w.latest_score)}%
                </span>
              )}
              <span className="workspace-card__runs">
                {w.run_count}{' '}
                {w.run_count === 1
                  ? t('comply.workspaces.run', 'run')
                  : t('comply.workspaces.runs', 'runs')}
              </span>
              {w.open_actions > 0 && (
                <span className="workspace-card__actions">
                  <span className="mdi mdi-flag-outline"></span>
                  {w.open_actions} {t('comply.workspaces.openActions', 'to fix')}
                </span>
              )}
            </span>

            <span className="workspace-card__foot">
              <span className="workspace-card__when">
                {t('comply.workspaces.lastRun', 'Last checked')}{' '}
                {relativeDate(w.last_run_at, t as (k: string, d?: string) => string)}
              </span>
              <span className="mdi mdi-arrow-right workspace-card__go"></span>
            </span>
          </button>
        ))}
      </div>
    </section>
  );
};

export default WorkspaceList;
