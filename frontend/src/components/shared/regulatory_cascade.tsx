/**
 * Regulatory Cascade — tier-2+ view of a primary EU act.
 *
 * For an adopted law, surfaces the implementing + delegated acts that
 * extend it, plus related in-flight files in the same policy areas. When
 * the underlying file is still a proposal (no adopted celex matched on
 * secondary_acts.parent_celex), the branches are honestly empty.
 *
 * Member State transposition deadlines and CEN/CENELEC standard
 * revisions are surfaced as explicit "data coming soon" panes when the
 * backend reports they are not yet ingested. Never fabricates.
 */

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import Icon from '@mdi/react';
import {
  mdiSitemap,
  mdiArrowRight,
  mdiAlertCircleOutline,
  mdiClockOutline,
  mdiLinkVariant,
  mdiInformationOutline,
} from '@mdi/js';

import { useAuth } from '../../hooks/use_auth';
import './regulatory_cascade.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface SecondaryAct {
  id: string;
  act_type: 'implementing' | 'delegated' | string;
  reference: string | null;
  title: string;
  status: 'adopted' | 'draft' | null;
  publication_date: string | null;
  objection_deadline: string | null;
  pdf_url: string | null;
  source_url: string | null;
  proposing_dg: string | null;
}

interface RelatedFile {
  carriage_id: string;
  title: string;
  procedure_ref: string | null;
  current_status: string | null;
  lead_committee: string | null;
  shared_policy_areas: string[];
  first_seen: string | null;
}

interface CascadeData {
  procedure_ref: string | null;
  title: string;
  celex_numbers: string[];
  counts: {
    implementing_adopted: number;
    implementing_draft: number;
    delegated_adopted: number;
    delegated_draft: number;
    related_in_flight: number;
  };
  implementing_acts: SecondaryAct[];
  delegated_acts: SecondaryAct[];
  related_files: RelatedFile[];
  transposition_data_available: boolean;
  cen_standards_data_available: boolean;
}

interface RegulatoryCascadeProps {
  procedureRef: string;
}

const formatDate = (iso: string | null) => {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return '';
  }
};

const statusBadgeClass = (status: string | null) => {
  if (status === 'adopted') return 'regulatory-cascade__status regulatory-cascade__status--adopted';
  if (status === 'draft') return 'regulatory-cascade__status regulatory-cascade__status--draft';
  return 'regulatory-cascade__status';
};

const SecondaryActRow = ({ act }: { act: SecondaryAct }) => {
  return (
    <li className="regulatory-cascade__act">
      <div className="regulatory-cascade__act-head">
        {act.status && (
          <span className={statusBadgeClass(act.status)}>{act.status}</span>
        )}
        {act.reference && (
          <span className="regulatory-cascade__act-ref">{act.reference}</span>
        )}
        {act.proposing_dg && (
          <span className="regulatory-cascade__act-dg">{act.proposing_dg}</span>
        )}
      </div>
      <div className="regulatory-cascade__act-title">{act.title}</div>
      <div className="regulatory-cascade__act-meta">
        {act.publication_date && (
          <span>published {formatDate(act.publication_date)}</span>
        )}
        {act.objection_deadline && (
          <span>
            <Icon path={mdiClockOutline} size={0.6} /> objection deadline{' '}
            {formatDate(act.objection_deadline)}
          </span>
        )}
        {act.source_url && (
          <a
            href={act.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="regulatory-cascade__act-link"
          >
            <Icon path={mdiLinkVariant} size={0.65} /> source
          </a>
        )}
        {act.pdf_url && (
          <a
            href={act.pdf_url}
            target="_blank"
            rel="noopener noreferrer"
            className="regulatory-cascade__act-link"
          >
            <Icon path={mdiLinkVariant} size={0.65} /> pdf
          </a>
        )}
      </div>
    </li>
  );
};

export const RegulatoryCascade = ({ procedureRef }: RegulatoryCascadeProps) => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [data, setData] = useState<CascadeData | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!isAuthenticated || !procedureRef) return;
    const token = useAuth.getState().token;
    if (!token) return;
    let cancelled = false;
    setIsLoading(true);
    axios
      .get<CascadeData>(
        `${API_URL}/api/eu-law-comply/cascade/${encodeURIComponent(procedureRef)}`,
        { headers: { Authorization: `Bearer ${token}` } },
      )
      .then((response) => {
        if (!cancelled) {
          setData(response.data);
          setIsLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, procedureRef]);

  if (!isAuthenticated) return null;
  if (isLoading) {
    return (
      <section className="regulatory-cascade regulatory-cascade--loading">
        <p>Composing the regulatory cascade…</p>
      </section>
    );
  }
  if (!data) return null;

  const hasAnySecondary =
    data.implementing_acts.length > 0 || data.delegated_acts.length > 0;
  const hasRelated = data.related_files.length > 0;
  const cascadeIsEmpty = !hasAnySecondary && !hasRelated;

  return (
    <section
      className="regulatory-cascade"
      aria-label="Regulatory cascade for this file"
    >
      <header className="regulatory-cascade__header">
        <Icon path={mdiSitemap} size={1} color="#563ea3" />
        <div>
          <h3>Regulatory cascade</h3>
          <p className="regulatory-cascade__subtitle">
            What else hangs off this file: implementing acts, delegated acts,
            and related in-flight work.
          </p>
        </div>
      </header>

      {cascadeIsEmpty && (
        <div className="regulatory-cascade__empty">
          <Icon path={mdiInformationOutline} size={0.9} color="#666" />
          <span>
            No secondary acts or recent related files found.
            {data.celex_numbers.length === 0
              ? ' This file is still pre-adoption — secondary acts emerge only after the primary act is adopted.'
              : ' Brubru will surface them automatically once they are published.'}
          </span>
        </div>
      )}

      {hasAnySecondary && (
        <div className="regulatory-cascade__counts">
          <span className="regulatory-cascade__count regulatory-cascade__count--impl">
            <strong>{data.counts.implementing_adopted + data.counts.implementing_draft}</strong>{' '}
            implementing
            {data.counts.implementing_draft > 0 && (
              <em> ({data.counts.implementing_draft} draft)</em>
            )}
          </span>
          <span className="regulatory-cascade__count regulatory-cascade__count--deleg">
            <strong>{data.counts.delegated_adopted + data.counts.delegated_draft}</strong>{' '}
            delegated
            {data.counts.delegated_draft > 0 && (
              <em> ({data.counts.delegated_draft} draft)</em>
            )}
          </span>
          {data.counts.related_in_flight > 0 && (
            <span className="regulatory-cascade__count regulatory-cascade__count--related">
              <strong>{data.counts.related_in_flight}</strong> in-flight files in
              the same policy area
            </span>
          )}
        </div>
      )}

      {data.implementing_acts.length > 0 && (
        <div className="regulatory-cascade__branch">
          <h4>Implementing acts ({data.implementing_acts.length})</h4>
          <ul className="regulatory-cascade__list">
            {data.implementing_acts.map((act) => (
              <SecondaryActRow key={act.id} act={act} />
            ))}
          </ul>
        </div>
      )}

      {data.delegated_acts.length > 0 && (
        <div className="regulatory-cascade__branch">
          <h4>Delegated acts ({data.delegated_acts.length})</h4>
          <ul className="regulatory-cascade__list">
            {data.delegated_acts.map((act) => (
              <SecondaryActRow key={act.id} act={act} />
            ))}
          </ul>
        </div>
      )}

      {hasRelated && (
        <div className="regulatory-cascade__branch">
          <h4>Related in-flight files ({data.related_files.length})</h4>
          <ul className="regulatory-cascade__related-list">
            {data.related_files.map((r) => (
              <li key={r.carriage_id} className="regulatory-cascade__related">
                <button
                  type="button"
                  className="regulatory-cascade__related-link"
                  onClick={() =>
                    navigate(
                      `/my-eu-bubble?tab=legislative&procedure=${encodeURIComponent(r.procedure_ref || r.carriage_id)}`,
                    )
                  }
                >
                  {r.title}
                  <Icon path={mdiArrowRight} size={0.65} />
                </button>
                <div className="regulatory-cascade__related-meta">
                  {r.procedure_ref && <span>{r.procedure_ref}</span>}
                  {r.current_status && (
                    <span className="regulatory-cascade__related-status">
                      {r.current_status.replace(/_/g, ' ')}
                    </span>
                  )}
                  {r.lead_committee && <span>{r.lead_committee}</span>}
                  {r.shared_policy_areas.length > 0 && (
                    <span className="regulatory-cascade__related-tags">
                      shares: {r.shared_policy_areas.slice(0, 3).join(', ')}
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {!data.transposition_data_available && (
        <div className="regulatory-cascade__not-yet">
          <Icon path={mdiAlertCircleOutline} size={0.85} color="#b56500" />
          <div>
            <strong>Member State transposition deadlines</strong>
            <p>
              Brubru does not yet ingest national transposition data for every
              Member State. When this data is available, deadlines will appear
              here per country.
            </p>
          </div>
        </div>
      )}

      {!data.cen_standards_data_available && (
        <div className="regulatory-cascade__not-yet">
          <Icon path={mdiAlertCircleOutline} size={0.85} color="#b56500" />
          <div>
            <strong>CEN / CENELEC standards</strong>
            <p>
              Standard revisions linked to this act are not yet ingested. Once
              connected to the CEN/CENELEC work programme, related standard
              revisions will appear here.
            </p>
          </div>
        </div>
      )}
    </section>
  );
};
