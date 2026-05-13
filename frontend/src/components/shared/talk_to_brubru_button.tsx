/**
 * Talk to Brubru button — shared chat hand-off that any My EU Bubble tab
 * can drop into its header. Navigates to /main with the suggested prompt
 * pre-filled and auto-fired (so the answer streams without an extra click).
 *
 * Hidden for unauthenticated users (Brubru Chat requires sign-in for
 * meaningful personalised answers).
 */

import { useNavigate } from 'react-router-dom';
import Icon from '@mdi/react';
import { mdiMessageOutline, mdiArrowRight } from '@mdi/js';

import { useAuth } from '../../hooks/use_auth';
import './talk_to_brubru_button.css';

interface TalkToBrubruButtonProps {
  prompt: string;
  /** Visual variant. Defaults to `inline`; use `pill` for header chips. */
  variant?: 'inline' | 'pill';
  /** Override the label. Defaults to "Talk to Brubru about this". */
  label?: string;
  /** Set false to disable auto-fire (just pre-fill). Default true. */
  autoFire?: boolean;
}

export const TalkToBrubruButton = ({
  prompt,
  variant = 'inline',
  label = 'Talk to Brubru about this',
  autoFire = true,
}: TalkToBrubruButtonProps) => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated || !prompt) {
    return null;
  }

  const onClick = () => {
    const params = new URLSearchParams({ q: prompt });
    if (autoFire) params.set('autofire', '1');
    navigate(`/main?${params.toString()}`);
  };

  return (
    <button
      type="button"
      className={`talk-to-brubru talk-to-brubru--${variant}`}
      onClick={onClick}
    >
      <Icon path={mdiMessageOutline} size={0.75} />
      {label}
      <Icon path={mdiArrowRight} size={0.7} />
    </button>
  );
};
