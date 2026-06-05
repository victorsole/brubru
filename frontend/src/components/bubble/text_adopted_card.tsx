/**
 * Text Adopted Card Component
 *
 * Displays a single adopted text in a card format.
 * Used in the Texts Adopted sub-tab of My Tracked Files.
 *
 * Created: February 2026
 */

import Icon from '@mdi/react';
import { useTranslation } from 'react-i18next';
import {
  mdiOpenInNew,
  mdiFileDocumentOutline,
  mdiAccountTieOutline,
  mdiCalendarOutline,
  mdiPlaylistPlus,
  mdiTrashCanOutline,
} from '@mdi/js';
import type { TextAdopted } from '../../hooks/use_texts_adopted';
import { TEXT_TYPE_INFO } from '../../hooks/use_texts_adopted';
import { getEultUrl } from '../../utils/eu_links';
import './text_adopted_card.css';

interface TextAdoptedCardProps {
  item: TextAdopted;
  isTracked?: boolean;
  onViewDetail?: () => void;
  onTrack?: () => void;
  onUntrack?: () => void;
}

export const TextAdoptedCard = ({ item, isTracked, onViewDetail, onTrack, onUntrack }: TextAdoptedCardProps) => {
  const { t, i18n } = useTranslation();
  const typeInfo = TEXT_TYPE_INFO[item.text_type] || { name: item.text_type, color: '#6b7280' };
  const locale = i18n.language || 'en';

  const epUrl = item.full_text_url || item.source_url;
  const oeilUrl = item.procedure_ref
    ? `https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=${encodeURIComponent(item.procedure_ref)}`
    : null;
  const eultUrl = item.procedure_ref ? getEultUrl(item.procedure_ref) : null;

  return (
    <div className="text-adopted-card">
      <div className="text-adopted-card__header">
        <span
          className="text-adopted-card__type"
          style={{ backgroundColor: typeInfo.color }}
        >
          {typeInfo.name}
        </span>
        <span className="text-adopted-card__term">
          {t('textAdopted.term', { n: item.parliamentary_term })}
        </span>
      </div>

      <h4
        className="text-adopted-card__title"
        onClick={onViewDetail}
        style={onViewDetail ? { cursor: 'pointer' } : undefined}
      >
        {item.title}
      </h4>

      <div className="text-adopted-card__meta">
        <span className="text-adopted-card__ref">
          {item.ta_reference}
        </span>
        <span className="text-adopted-card__date">
          <Icon path={mdiCalendarOutline} size={0.55} />
          {new Date(item.adoption_date).toLocaleDateString(locale, {
            day: 'numeric',
            month: 'short',
            year: 'numeric',
          })}
        </span>
        {item.procedure_ref && (
          <span className="text-adopted-card__procedure">
            {item.procedure_ref}
          </span>
        )}
      </div>

      {(item.committees?.length > 0 || item.rapporteur_name) && (
        <div className="text-adopted-card__details">
          {item.committees?.length > 0 && (
            <span className="text-adopted-card__committees">
              {item.committees.join(', ')}
            </span>
          )}
          {item.rapporteur_name && (
            <span className="text-adopted-card__rapporteur">
              <Icon path={mdiAccountTieOutline} size={0.55} />
              {item.rapporteur_name}
            </span>
          )}
        </div>
      )}

      <div className="text-adopted-card__actions">
        {onViewDetail && (
          <button
            type="button"
            className="text-adopted-card__action-btn text-adopted-card__action-btn--primary"
            onClick={onViewDetail}
          >
            <Icon path={mdiFileDocumentOutline} size={0.7} />
            {t('myFilesTab.viewDetails')}
          </button>
        )}
        {isTracked ? (
          onUntrack && (
            <button
              type="button"
              className="text-adopted-card__action-btn text-adopted-card__action-btn--danger"
              onClick={onUntrack}
            >
              <Icon path={mdiTrashCanOutline} size={0.7} />
              {t('myFilesTab.saved')}
            </button>
          )
        ) : (
          onTrack && (
            <button
              type="button"
              className="text-adopted-card__action-btn text-adopted-card__action-btn--track"
              onClick={onTrack}
            >
              <Icon path={mdiPlaylistPlus} size={0.7} />
              {t('myFilesTab.save')}
            </button>
          )
        )}
        {epUrl && (
          <a
            href={epUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-adopted-card__action-btn"
          >
            <Icon path={mdiFileDocumentOutline} size={0.7} />
            {t('textAdopted.viewText')}
          </a>
        )}
        {oeilUrl && (
          <a
            href={oeilUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-adopted-card__action-btn"
          >
            <Icon path={mdiOpenInNew} size={0.7} />
            OEIL
          </a>
        )}
        {eultUrl && (
          <a
            href={eultUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-adopted-card__action-btn"
          >
            <Icon path={mdiOpenInNew} size={0.7} />
            EU Law Tracker
          </a>
        )}
      </div>
    </div>
  );
};
