/**
 * Proactive opener — surfaces briefings Brubru wants to start the
 * conversation with. Renders 0–3 briefing cards above Chat / the
 * Dashboard. Each opener clicks through to Chat with the suggested query
 * pre-loaded.
 *
 * No mocks: empty briefings → renders nothing.
 */

import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Icon from '@mdi/react';
import {
  mdiBellRingOutline,
  mdiArrowRight,
  mdiClose,
  mdiMessageOutline,
} from '@mdi/js';

import { useAuth } from '../../hooks/use_auth';
import {
  useProactive,
  type ProactiveBriefing,
  type ProactiveTriggerSource,
} from '../../hooks/use_proactive';
import './proactive_opener.css';

const TRIGGER_LABEL: Record<ProactiveTriggerSource, string> = {
  morning_brief: 'Morning brief',
  new_file_match: 'New for you',
  tracked_file_movement: 'Your tracked files',
  amendment_surge: 'Amendment surge',
};

const OPEN_LABEL: Record<ProactiveTriggerSource, string> = {
  morning_brief: 'Open My EU Calendar',
  new_file_match: 'Open My Files',
  tracked_file_movement: 'Open My Files',
  amendment_surge: 'Open Amendments',
};

interface ProactiveOpenerProps {
  /** Where the opener is mounted, used for styling variants. */
  surface?: 'chat' | 'dashboard';
}

export const ProactiveOpener = ({ surface = 'chat' }: ProactiveOpenerProps) => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const { briefings, dismissedTitles, fetchPending, dismiss } = useProactive();

  useEffect(() => {
    if (isAuthenticated) {
      void fetchPending();
    }
  }, [isAuthenticated, fetchPending]);

  if (!isAuthenticated) {
    return null;
  }

  const visible = briefings.filter((b) => !dismissedTitles.has(b.title));
  if (visible.length === 0) {
    return null;
  }

  const onAct = (b: ProactiveBriefing) => {
    navigate(
      `/main?q=${encodeURIComponent(b.suggested_query)}&autofire=1`,
    );
  };

  return (
    <section
      className={`proactive-opener proactive-opener--${surface}`}
      role="region"
      aria-label="Brubru briefings"
    >
      <header className="proactive-opener__header">
        <Icon path={mdiBellRingOutline} size={0.9} color="#0693E3" />
        <h3>Brubru raised this for you</h3>
      </header>
      <div className="proactive-opener__cards">
        {visible.map((b) => (
          <article key={b.title} className="proactive-opener__card">
            <div className="proactive-opener__card-tag">
              {TRIGGER_LABEL[b.trigger_source] || 'Briefing'}
            </div>
            <h4 className="proactive-opener__card-title">{b.title}</h4>
            <p className="proactive-opener__card-summary">{b.summary}</p>
            <div className="proactive-opener__card-actions">
              <button
                type="button"
                className="proactive-opener__cta"
                onClick={() => onAct(b)}
              >
                <Icon path={mdiMessageOutline} size={0.7} />
                Tell me more
                <Icon path={mdiArrowRight} size={0.7} />
              </button>
              {b.drill_down_path && (
                <button
                  type="button"
                  className="proactive-opener__cta proactive-opener__cta--secondary"
                  onClick={() => navigate(b.drill_down_path as string)}
                >
                  {OPEN_LABEL[b.trigger_source] || 'Open'}
                </button>
              )}
              <button
                type="button"
                className="proactive-opener__dismiss"
                onClick={() => dismiss(b.title)}
                aria-label="Dismiss briefing"
              >
                <Icon path={mdiClose} size={0.7} />
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
};
