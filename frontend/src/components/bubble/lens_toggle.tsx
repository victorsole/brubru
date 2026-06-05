/**
 * Shared MEUB lens toggle (All / My interests / My files) + tracked badge.
 *
 * The 3-way segmented control every PI-aligned feed tab uses (the pattern first
 * shipped on News). `My interests` shows only when the user has Policy Interests;
 * `My files` shows only when the user tracks files — so the resting state is
 * unchanged for users with neither. Mutually-exclusive lens modes.
 */
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import { mdiStar, mdiStarOutline, mdiBookmarkCheck, mdiBookmarkCheckOutline } from '@mdi/js';
import './lens_toggle.css';

export type LensMode = 'all' | 'pi' | 'files';

export const LensToggle = ({
  mode, onChange, hasPi = true, hasFiles = false,
}: {
  mode: LensMode;
  onChange: (m: LensMode) => void;
  hasPi?: boolean;
  hasFiles?: boolean;
}) => {
  const { t } = useTranslation();
  if (!hasPi && !hasFiles) return null;
  return (
    <div className="lens-toggle">
      <button className={mode === 'all' ? 'is-active' : ''} onClick={() => onChange('all')}>
        {t('bubble.lens.all', 'All')}
      </button>
      {hasPi && (
        <button className={mode === 'pi' ? 'is-active' : ''} onClick={() => onChange('pi')}>
          <Icon path={mode === 'pi' ? mdiStar : mdiStarOutline} size={0.7} /> {t('bubble.lens.interests', 'My interests')}
        </button>
      )}
      {hasFiles && (
        <button className={mode === 'files' ? 'is-active' : ''} onClick={() => onChange('files')}>
          <Icon path={mode === 'files' ? mdiBookmarkCheck : mdiBookmarkCheckOutline} size={0.7} /> {t('bubble.lens.files', 'My files')}
        </button>
      )}
    </div>
  );
};

/** Hard-register chip: "Files you track" (shown on items where matches_tracked). */
export const TrackedBadge = ({ reason }: { reason?: string | null }) => {
  const { t } = useTranslation();
  return (
    <span className="lens-tracked-chip" title={reason || ''}>
      <Icon path={mdiBookmarkCheck} size={0.5} /> {t('bubble.lens.filesYouTrack', 'Files you track')}
    </span>
  );
};
