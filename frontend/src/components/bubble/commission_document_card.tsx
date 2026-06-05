/**
 * Commission Document Card Component
 *
 * Displays a single Commission document in a card format.
 * Used in the Commission Docs sub-tab of My Tracked Files.
 *
 * Created: February 2026
 */

import Icon from '@mdi/react';
import { useTranslation } from 'react-i18next';
import {
  mdiOpenInNew,
  mdiCalendarOutline,
  mdiDomain,
  mdiPlaylistPlus,
  mdiTrashCanOutline,
} from '@mdi/js';
import type { CommissionDocItem } from '../../hooks/use_commission_documents';
import { DOC_TYPE_INFO } from '../../hooks/use_commission_documents';
import { getEultUrl } from '../../utils/eu_links';
import './commission_document_card.css';

interface CommissionDocumentCardProps {
  item: CommissionDocItem;
  isTracked?: boolean;
  onTrack?: () => void;
  onUntrack?: () => void;
}

export const CommissionDocumentCard = ({ item, isTracked, onTrack, onUntrack }: CommissionDocumentCardProps) => {
  const { t, i18n } = useTranslation();
  const typeInfo = DOC_TYPE_INFO[item.doc_type] || { name: item.doc_type, color: '#6b7280' };
  const locale = i18n.language || 'en';

  const oeilUrl = item.procedure_ref
    ? `https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=${encodeURIComponent(item.procedure_ref)}`
    : null;
  const eultUrl = item.procedure_ref ? getEultUrl(item.procedure_ref) : null;

  return (
    <div className="commission-document-card">
      <div className="commission-document-card__header">
        <span
          className="commission-document-card__type"
          style={{ backgroundColor: typeInfo.color }}
        >
          {typeInfo.name}
        </span>
        {item.dg_responsible && (
          <span className="commission-document-card__dg">
            <Icon path={mdiDomain} size={0.5} />
            {item.dg_responsible}
          </span>
        )}
      </div>

      <h4
        className="commission-document-card__title"
        onClick={item.portal_url ? () => window.open(item.portal_url, '_blank', 'noopener,noreferrer') : undefined}
        style={item.portal_url ? { cursor: 'pointer' } : undefined}
      >
        {item.title}
      </h4>

      <div className="commission-document-card__meta">
        <span className="commission-document-card__ref">
          {item.reference}
        </span>
        {item.publication_date && (
          <span className="commission-document-card__date">
            <Icon path={mdiCalendarOutline} size={0.55} />
            {new Date(item.publication_date).toLocaleDateString(locale, {
              day: 'numeric',
              month: 'short',
              year: 'numeric',
            })}
          </span>
        )}
        {item.procedure_ref && (
          <span className="commission-document-card__procedure">
            {item.procedure_ref}
          </span>
        )}
      </div>

      <div className="commission-document-card__actions">
        {isTracked ? (
          onUntrack && (
            <button
              type="button"
              className="commission-document-card__action-btn commission-document-card__action-btn--danger"
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
              className="commission-document-card__action-btn commission-document-card__action-btn--track"
              onClick={onTrack}
            >
              <Icon path={mdiPlaylistPlus} size={0.7} />
              {t('myFilesTab.save')}
            </button>
          )
        )}
        {item.portal_url && (
          <a
            href={item.portal_url}
            target="_blank"
            rel="noopener noreferrer"
            className="commission-document-card__action-btn"
          >
            <Icon path={mdiOpenInNew} size={0.7} />
            {t('commissionDoc.viewInEurlex')}
          </a>
        )}
        {oeilUrl && (
          <a
            href={oeilUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="commission-document-card__action-btn"
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
            className="commission-document-card__action-btn"
          >
            <Icon path={mdiOpenInNew} size={0.7} />
            EU Law Tracker
          </a>
        )}
      </div>
    </div>
  );
};
