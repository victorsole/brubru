/**
 * Compliance Maturity card — 4-axis 0-100 score with a tier badge and the
 * top 3 highest-lift next steps. Surfaced at the top of the EU Law Comply
 * landing page. Designed to be screenshot-shareable (one self-contained
 * card with the score, axes bars, tier label).
 *
 * Honest empty state when the user has no activity (score = 0): instead
 * of fabricating a generic message, the card shows the actual zero and
 * names the cheapest first action to take.
 */

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import Icon from '@mdi/react';
import {
  mdiTrophyOutline,
  mdiArrowRight,
  mdiCheckCircleOutline,
} from '@mdi/js';

import { useAuth } from '../../hooks/use_auth';
import './compliance_maturity.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface AxisScore {
  name: string;
  score: number;
  max_score: number;
  signals: Record<string, unknown>;
  rationale: string;
}

interface MaturityRecommendation {
  axis: string;
  action: string;
  rationale: string;
  expected_lift: number;
}

interface MaturityData {
  score: number;
  max_score: number;
  tier: 'beginner' | 'intermediate' | 'advanced' | 'expert';
  tier_label: string;
  axes: AxisScore[];
  recommendations: MaturityRecommendation[];
  profile_complete: boolean;
  has_any_activity: boolean;
}

const AXIS_LABEL: Record<string, string> = {
  awareness: 'Awareness',
  impact_analysis: 'Impact analysis',
  advocacy: 'Advocacy',
  follow_through: 'Follow-through',
};

const TIER_COLOUR: Record<MaturityData['tier'], string> = {
  beginner: '#9e9e9e',
  intermediate: '#0693e3',
  advanced: '#563ea3',
  expert: '#b56500',
};

const recommendationPath = (axis: string): string => {
  switch (axis) {
    case 'awareness':
      return '/profile';
    case 'impact_analysis':
      return '/my-eu-bubble?tab=position_analysis';
    case 'advocacy':
      return '/amendator';
    case 'follow_through':
      return '/eulawcomply';
    default:
      return '/my-eu-bubble';
  }
};

export const ComplianceMaturity = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [data, setData] = useState<MaturityData | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) return;
    const token = useAuth.getState().token;
    if (!token) return;
    let cancelled = false;
    setIsLoading(true);
    axios
      .get<MaturityData>(`${API_URL}/api/eu-law-comply/maturity`, {
        headers: { Authorization: `Bearer ${token}` },
      })
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
  }, [isAuthenticated]);

  if (!isAuthenticated) return null;
  if (isLoading) {
    return (
      <section className="compliance-maturity compliance-maturity--loading">
        <p>Composing your compliance maturity score…</p>
      </section>
    );
  }
  if (!data) return null;

  const tierColour = TIER_COLOUR[data.tier];
  const sortedAxes = [...data.axes];

  return (
    <section
      className="compliance-maturity"
      aria-label="Your compliance maturity score"
    >
      <header className="compliance-maturity__header">
        <Icon path={mdiTrophyOutline} size={1.1} color={tierColour} />
        <div className="compliance-maturity__header-text">
          <h2>Your compliance maturity</h2>
          <p>{data.tier_label}</p>
        </div>
        <div
          className="compliance-maturity__score"
          style={{ color: tierColour }}
        >
          <span className="compliance-maturity__score-value">{data.score}</span>
          <span className="compliance-maturity__score-max">/{data.max_score}</span>
        </div>
      </header>

      <div className="compliance-maturity__tier-badge" style={{ background: tierColour }}>
        {data.tier}
      </div>

      <div className="compliance-maturity__axes">
        {sortedAxes.map((axis) => {
          const pct = Math.round((axis.score / axis.max_score) * 100);
          return (
            <div className="compliance-maturity__axis" key={axis.name}>
              <div className="compliance-maturity__axis-head">
                <span className="compliance-maturity__axis-name">
                  {AXIS_LABEL[axis.name] || axis.name}
                </span>
                <span className="compliance-maturity__axis-score">
                  {axis.score}/{axis.max_score}
                </span>
              </div>
              <div className="compliance-maturity__bar">
                <div
                  className="compliance-maturity__bar-fill"
                  style={{
                    width: `${pct}%`,
                    background: tierColour,
                  }}
                />
              </div>
              <div className="compliance-maturity__axis-rationale">
                {axis.rationale}
              </div>
            </div>
          );
        })}
      </div>

      {data.recommendations.length > 0 && (
        <div className="compliance-maturity__recommendations">
          <h3>Highest-lift next steps</h3>
          <ul>
            {data.recommendations.map((rec) => (
              <li key={rec.axis + rec.action}>
                <div className="compliance-maturity__rec-head">
                  <span className="compliance-maturity__rec-lift">
                    +{rec.expected_lift} pts
                  </span>
                  <strong>{rec.action}</strong>
                </div>
                <p className="compliance-maturity__rec-rationale">
                  {rec.rationale}
                </p>
                <button
                  type="button"
                  className="compliance-maturity__rec-cta"
                  onClick={() => navigate(recommendationPath(rec.axis))}
                >
                  Take me there
                  <Icon path={mdiArrowRight} size={0.65} />
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {data.recommendations.length === 0 && data.score === data.max_score && (
        <div className="compliance-maturity__perfect">
          <Icon path={mdiCheckCircleOutline} size={0.9} color="#2e7d32" />
          <span>You are at maximum maturity. Keep going.</span>
        </div>
      )}

      {!data.has_any_activity && !data.profile_complete && (
        <div className="compliance-maturity__intro">
          You are at zero because Brubru does not yet have signals on your
          activity. The recommendations above each unlock 5–10 points the
          moment you act on them.
        </div>
      )}
    </section>
  );
};
