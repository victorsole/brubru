/**
 * Talk to Brubru button — shared chat hand-off that any My EU Bubble tab
 * can drop into its header. Navigates to /main with the suggested prompt
 * pre-filled and auto-fired (so the answer streams without an extra click).
 *
 * Hidden for unauthenticated users (Brubru Chat requires sign-in for
 * meaningful personalised answers).
 */

import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import { mdiMessageOutline, mdiArrowRight } from '@mdi/js';

import { useAuth } from '../../hooks/use_auth';
import './talk_to_brubru_button.css';

interface TalkToBrubruButtonProps {
  prompt: string;
  /** Visual variant. `inline`/`pill` are gradient pills; `link` is a quiet text link. */
  variant?: 'inline' | 'pill' | 'link';
  /** Override the label. Defaults to "Talk to Brubru about this". */
  label?: string;
  /** Set false to disable auto-fire (just pre-fill). Default true. */
  autoFire?: boolean;
}

export const TalkToBrubruButton = ({
  prompt,
  variant = 'inline',
  label,
  autoFire = true,
}: TalkToBrubruButtonProps) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const displayLabel = label ?? t('talkToBrubru');

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
      {displayLabel}
      <Icon path={mdiArrowRight} size={0.7} />
    </button>
  );
};
