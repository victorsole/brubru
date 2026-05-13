/**
 * Personalised Impact block — "what this means for you" briefing for a
 * specific legislative file. Pulls /api/impact/{procedure_ref}; renders an
 * empty state and CTA when the user has not supplied enough profile.
 *
 * Never renders mock content: if the backend says profile is partial, this
 * component shows the honest "complete your profile" prompt.
 */

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import Icon from '@mdi/react';
import {
  mdiAccountCircleOutline,
  mdiArrowRight,
  mdiCompassOutline,
  mdiTargetVariant,
  mdiBinoculars,
  mdiLightbulbOutline,
} from '@mdi/js';

import { useAuth } from '../../hooks/use_auth';
import './personalised_impact.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface ActionLink {
  label: string;
  path: string;
  rationale: string;
}

interface ImpactBlock {
  procedure_ref: string | null;
  title: string;
  headline: string;
  what_it_is: string;
  why_it_touches_you: string;
  what_to_watch: string;
  actions_you_can_take: ActionLink[];
  matched_policy_areas: string[];
  matched_sectors: string[];
  user_profile_was_partial: boolean;
}

interface PersonalisedImpactProps {
  procedureRef: string;
}

export const PersonalisedImpact = ({ procedureRef }: PersonalisedImpactProps) => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  const [block, setBlock] = useState<ImpactBlock | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated || !procedureRef) {
      return;
    }
    const token = useAuth.getState().token;
    if (!token) {
      return;
    }
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    axios
      .get<ImpactBlock>(
        `${API_URL}/api/impact/${encodeURIComponent(procedureRef)}`,
        { headers: { Authorization: `Bearer ${token}` } },
      )
      .then((response) => {
        if (!cancelled) {
          setBlock(response.data);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          const detail = err?.response?.data?.detail || 'Could not load impact briefing.';
          setError(typeof detail === 'string' ? detail : 'Could not load impact briefing.');
          setIsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, procedureRef]);

  if (!isAuthenticated) {
    return null;
  }

  if (isLoading) {
    return (
      <section className="personalised-impact personalised-impact--loading">
        <p>Composing your impact briefing…</p>
      </section>
    );
  }

  if (error || !block) {
    return null;
  }

  return (
    <section className="personalised-impact" aria-label="What this means for you">
      <header className="personalised-impact__header">
        <Icon path={mdiTargetVariant} size={1} color="#0693E3" />
        <div>
          <h3 className="personalised-impact__title">What this means for you</h3>
          <p className="personalised-impact__subtitle">{block.headline}</p>
        </div>
      </header>

      <div className="personalised-impact__sections">
        <article className="personalised-impact__section">
          <h4>
            <Icon path={mdiCompassOutline} size={0.8} color="#0570a8" />
            What it is
          </h4>
          <p>{block.what_it_is}</p>
        </article>

        <article
          className={`personalised-impact__section ${
            block.user_profile_was_partial
              ? 'personalised-impact__section--partial'
              : ''
          }`}
        >
          <h4>
            <Icon path={mdiAccountCircleOutline} size={0.8} color="#0570a8" />
            Why it touches you
          </h4>
          <p>{block.why_it_touches_you}</p>
          {block.user_profile_was_partial && (
            <button
              type="button"
              className="personalised-impact__profile-cta"
              onClick={() => navigate('/profile')}
            >
              Complete your profile
              <Icon path={mdiArrowRight} size={0.7} />
            </button>
          )}
          {(block.matched_policy_areas.length > 0 ||
            block.matched_sectors.length > 0) && (
            <ul className="personalised-impact__chips">
              {block.matched_policy_areas.map((tag) => (
                <li
                  key={`pa-${tag}`}
                  className="personalised-impact__chip personalised-impact__chip--policy"
                >
                  {tag}
                </li>
              ))}
              {block.matched_sectors.map((tag) => (
                <li
                  key={`s-${tag}`}
                  className="personalised-impact__chip personalised-impact__chip--sector"
                >
                  {tag.replace(/_/g, ' ')}
                </li>
              ))}
            </ul>
          )}
        </article>

        <article className="personalised-impact__section">
          <h4>
            <Icon path={mdiBinoculars} size={0.8} color="#0570a8" />
            What to watch
          </h4>
          <p>{block.what_to_watch}</p>
        </article>

        <article className="personalised-impact__section">
          <h4>
            <Icon path={mdiLightbulbOutline} size={0.8} color="#0570a8" />
            Actions you can take
          </h4>
          <ul className="personalised-impact__actions">
            {block.actions_you_can_take.map((action) => (
              <li key={action.label}>
                <button
                  type="button"
                  className="personalised-impact__action"
                  onClick={() => navigate(action.path)}
                  title={action.rationale}
                >
                  {action.label}
                  <Icon path={mdiArrowRight} size={0.65} />
                </button>
                {action.rationale && (
                  <p className="personalised-impact__action-rationale">
                    {action.rationale}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </article>
      </div>
    </section>
  );
};
