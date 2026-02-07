/**
 * Text Adopted Card Component
 *
 * Displays a single adopted text in a card format.
 * Used in the Texts Adopted sub-tab of My Tracked Files.
 *
 * Created: February 2026
 */

import Icon from '@mdi/react';
import {
  mdiOpenInNew,
  mdiFileDocumentOutline,
  mdiAccountTieOutline,
  mdiCalendarOutline,
} from '@mdi/js';
import type { TextAdopted } from '../../hooks/use_texts_adopted';
import { TEXT_TYPE_INFO } from '../../hooks/use_texts_adopted';
import './text_adopted_card.css';

interface TextAdoptedCardProps {
  item: TextAdopted;
}

export const TextAdoptedCard = ({ item }: TextAdoptedCardProps) => {
  const typeInfo = TEXT_TYPE_INFO[item.text_type] || { name: item.text_type, color: '#6b7280' };

  const epUrl = item.full_text_url || item.source_url;
  const oeilUrl = item.procedure_ref
    ? `https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=${encodeURIComponent(item.procedure_ref)}`
    : null;

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
          Term {item.parliamentary_term}
        </span>
      </div>

      <h4 className="text-adopted-card__title">
        {item.title}
      </h4>

      <div className="text-adopted-card__meta">
        <span className="text-adopted-card__ref">
          {item.ta_reference}
        </span>
        <span className="text-adopted-card__date">
          <Icon path={mdiCalendarOutline} size={0.55} />
          {new Date(item.adoption_date).toLocaleDateString('en-GB', {
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
        {epUrl && (
          <a
            href={epUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-adopted-card__action-btn"
          >
            <Icon path={mdiFileDocumentOutline} size={0.7} />
            View Text
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
      </div>
    </div>
  );
};
