/**
 * Shared archive UI for My EU Bubble surfaces.
 *
 *  - <ArchiveToggle>  : an "Active | Archived" segmented switch for a tracked list.
 *  - <ArchiveButton>  : a per-item Dismiss (archive) / Restore icon button.
 *
 * Both are i18n-driven and fully responsive (touch-sized targets, no overflow).
 * Styles live in archive_controls.css.
 */
import React from 'react';
import Icon from '@mdi/react';
import { mdiArchiveArrowDownOutline, mdiArchiveArrowUpOutline } from '@mdi/js';
import { useTranslation } from 'react-i18next';
import './archive_controls.css';

export type ArchiveView = 'active' | 'archived';

interface ArchiveToggleProps {
  value: ArchiveView;
  onChange: (v: ArchiveView) => void;
  /** Optional count badge for the archived side. */
  archivedCount?: number;
  className?: string;
}

export const ArchiveToggle: React.FC<ArchiveToggleProps> = ({ value, onChange, archivedCount, className }) => {
  const { t } = useTranslation();
  return (
    <div className={`archive-toggle ${className || ''}`} role="tablist" aria-label={t('archive.viewLabel', 'Archive view')}>
      <button
        role="tab"
        aria-selected={value === 'active'}
        className={value === 'active' ? 'is-active' : ''}
        onClick={() => onChange('active')}
      >
        {t('archive.active', 'Active')}
      </button>
      <button
        role="tab"
        aria-selected={value === 'archived'}
        className={value === 'archived' ? 'is-active' : ''}
        onClick={() => onChange('archived')}
      >
        {t('archive.archived', 'Archived')}
        {typeof archivedCount === 'number' && archivedCount > 0 && (
          <span className="archive-toggle__count">{archivedCount}</span>
        )}
      </button>
    </div>
  );
};

interface ArchiveButtonProps {
  /** true = item is archived (show Restore); false = active (show Dismiss). */
  archived: boolean;
  onClick: (e: React.MouseEvent) => void;
  busy?: boolean;
  /** 'icon' (compact, default) or 'full' (icon + label). */
  variant?: 'icon' | 'full';
  className?: string;
}

export const ArchiveButton: React.FC<ArchiveButtonProps> = ({ archived, onClick, busy, variant = 'icon', className }) => {
  const { t } = useTranslation();
  const label = archived ? t('archive.restore', 'Restore') : t('archive.dismiss', 'Archive');
  return (
    <button
      type="button"
      className={`archive-btn ${archived ? 'archive-btn--restore' : ''} ${className || ''}`}
      onClick={onClick}
      disabled={busy}
      title={label}
      aria-label={label}
    >
      <Icon path={archived ? mdiArchiveArrowUpOutline : mdiArchiveArrowDownOutline} size={0.75} />
      {variant === 'full' && <span className="archive-btn__label">{label}</span>}
    </button>
  );
};
