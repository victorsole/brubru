/**
 * Future-Comply preview — surfaces, for an in-flight proposal, a structured
 * "what to prepare for if this passes" block. When the file is already
 * adopted, the component nudges the user toward the existing Comply
 * gap-analysis flow rather than rendering a fabricated preview.
 */

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import Icon from '@mdi/react';
import {
  mdiShieldCheckOutline,
  mdiArrowRight,
  mdiShieldAlertOutline,
} from '@mdi/js';

import { useAuth } from '../../hooks/use_auth';
import './future_comply_preview.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface PreviewItem {
  label: string;
  rationale: string;
}

interface FutureComplyPreviewData {
  procedure_ref: string | null;
  title: string;
  stage: 'proposal' | 'adopted' | 'other';
  status: string;
  headline: string;
  summary: string;
  likely_obligation_areas: PreviewItem[];
  recommended_next_steps: PreviewItem[];
  deferred_to_adopted_flow: boolean;
  matched_policy_areas: string[];
}

interface FutureComplyPreviewProps {
  procedureRef: string;
}

export const FutureComplyPreview = ({ procedureRef }: FutureComplyPreviewProps) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [data, setData] = useState<FutureComplyPreviewData | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!isAuthenticated || !procedureRef) return;
    const token = useAuth.getState().token;
    if (!token) return;

    let cancelled = false;
    setIsLoading(true);
    axios
      .get<FutureComplyPreviewData>(
        `${API_URL}/api/eu-law-comply/future-preview/${encodeURIComponent(procedureRef)}`,
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

  if (!isAuthenticated || !data) return null;
  if (isLoading) {
    return (
      <section className="future-comply-preview future-comply-preview--loading">
        <p>{t('shared.composeFutureComply', 'Composing future-comply preview…')}</p>
      </section>
    );
  }

  if (data.stage === 'adopted') {
    return (
      <section className="future-comply-preview future-comply-preview--adopted">
        <header className="future-comply-preview__header">
          <Icon path={mdiShieldCheckOutline} size={1} color="#2e7d32" />
          <div>
            <h3>EU Law Comply</h3>
            <p className="future-comply-preview__subtitle">{data.headline}</p>
          </div>
        </header>
        <p>{data.summary}</p>
        <button
          type="button"
          className="future-comply-preview__cta"
          onClick={() => navigate('/eulawcomply')}
        >
          {t('futureComply.openComply', 'Open EU Law Comply')}
          <Icon path={mdiArrowRight} size={0.7} />
        </button>
      </section>
    );
  }

  if (data.stage === 'other') {
    return null;
  }

  return (
    <section className="future-comply-preview future-comply-preview--proposal">
      <header className="future-comply-preview__header">
        <Icon path={mdiShieldAlertOutline} size={1} color="#b56500" />
        <div>
          <h3>{t('shared.futureComplyPreview', 'Future-Comply preview')}</h3>
          <p className="future-comply-preview__subtitle">{data.headline}</p>
        </div>
      </header>

      <p className="future-comply-preview__summary">{data.summary}</p>

      <div className="future-comply-preview__sections">
        <article>
          <h4>{t('shared.likelyObligations', 'Likely obligation areas if this passes')}</h4>
          <ul>
            {data.likely_obligation_areas.map((item) => (
              <li key={item.label}>
                <strong>{item.label}.</strong> {item.rationale}
              </li>
            ))}
          </ul>
        </article>
        <article>
          <h4>{t('shared.recommendedNextSteps', 'Recommended next steps')}</h4>
          <ul>
            {data.recommended_next_steps.map((step) => (
              <li key={step.label}>
                <strong>{step.label}.</strong> {step.rationale}
              </li>
            ))}
          </ul>
        </article>
      </div>
    </section>
  );
};
