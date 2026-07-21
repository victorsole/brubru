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
  learn_about_you: 'Set up your watchlist',
  conversation_recall: 'Pick up where you left off',
  weekly_digest: 'Your week on Brubru',
};

const OPEN_LABEL: Record<ProactiveTriggerSource, string> = {
  morning_brief: 'Open My EU Calendar',
  new_file_match: 'Open My Files',
  tracked_file_movement: 'Open My Files',
  amendment_surge: 'Open Amendments',
  learn_about_you: 'Open profile',
  conversation_recall: 'Open chat history',
  weekly_digest: 'Open dashboard',
};

// Primary CTA label. Defaults to "Tell me more" (which opens Chat with the
// suggested query). Overridden per trigger where the primary action is NOT a
// chat query — e.g. learn_about_you routes to the profile setup.
const PRIMARY_LABEL: Partial<Record<ProactiveTriggerSource, string>> = {
  learn_about_you: 'Set up your watchlist',
};

/**
 * A briefing is a "stub" when its suggested_query is a fill-in-the-blank
 * prompt (e.g. learn_about_you's "I follow the following EU files and topics:")
 * rather than a complete, send-ready question. Stubs must NEVER be auto-fired
 * into Chat: they reach Brubru as an empty request and waste the user's first
 * interaction. Two real leads (Guiomar Ibáñez, Julia Svets) were lost this way
 * in Jun/Jul 2026 — they clicked the CTA and Brubru sent a half-sentence in
 * their name. Route stubs to the profile/watchlist setup instead.
 */
const isStubBriefing = (b: ProactiveBriefing): boolean => {
  const q = (b.suggested_query || '').trim();
  return b.trigger_source === 'learn_about_you' || q === '' || q.endsWith(':');
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
    // Never auto-fire an incomplete stub into Chat — send it to the setup
    // destination instead (defaults to /profile). See isStubBriefing.
    if (isStubBriefing(b)) {
      navigate(b.drill_down_path || '/profile');
      return;
    }
    navigate(
      `/chat?q=${encodeURIComponent(b.suggested_query)}&autofire=1`,
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
                {PRIMARY_LABEL[b.trigger_source] || 'Tell me more'}
                <Icon path={mdiArrowRight} size={0.7} />
              </button>
              {b.drill_down_path && !isStubBriefing(b) && (
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
