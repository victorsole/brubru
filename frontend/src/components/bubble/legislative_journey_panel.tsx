// frontend/src/components/bubble/legislative_journey_panel.tsx
//
// AI comparative analysis of a dossier's text journey through the committee
// stage: Commission proposal -> rapporteur's draft report -> MEPs' amendments
// -> compromise amendments -> final voting list (a resolution skips the
// proposal layer). "All the EU, with AI." Non-Anthropic engine, precomputed for
// tracked files and cached.
//
// Two modes:
//   compact - a short summary + a CTA into Position Analysis (file-detail modal)
//   full    - the per-layer detailed analysis (Position Analysis)
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import {
  mdiTimelineTextOutline, mdiFilePdfBox, mdiOpenInNew, mdiArrowRightCircleOutline,
  mdiCreation, mdiLoading, mdiAlertOutline, mdiSwordCross,
} from '@mdi/js';
import { positionService } from '../../services/position_service';
import type { JourneyResponse, JourneyLayer } from '../../services/position_service';
import './legislative_journey_panel.css';

const LAYER_I18N: Record<string, string> = {
  proposal: 'journey.layerProposal',
  draft_report: 'journey.layerDraftReport',
  amendment: 'journey.layerAmendments',
  compromise_amendments: 'journey.layerCompromise',
  voting_list: 'journey.layerVotingList',
};

function LayerCard({ layer }: { layer: JourneyLayer }) {
  const { t } = useTranslation();
  const href = layer.pdf_url || layer.source_url || undefined;
  return (
    <div className="journey-layer">
      <div className="journey-layer__head">
        <span className="journey-layer__label">{t(LAYER_I18N[layer.kind] || '', layer.label)}</span>
        {layer.committee_code && <span className="journey-layer__cmt">{layer.committee_code}</span>}
        {layer.meeting_date && <span className="journey-layer__date">{layer.meeting_date}</span>}
        {href && (
          <a className="journey-layer__pdf" href={href} target="_blank" rel="noopener noreferrer"
            title={t('journey.openSource', 'Open source document (PDF)') as string}>
            <Icon path={mdiFilePdfBox} size={0.65} /><Icon path={mdiOpenInNew} size={0.5} />
          </a>
        )}
      </div>
      {layer.summary
        ? <p className="journey-layer__summary">{layer.summary}</p>
        : <p className="journey-layer__summary is-empty">{t('journey.noLayerText', 'No analysable text for this layer.')}</p>}
      {layer.truncated && (
        <p className="journey-layer__trunc">
          <Icon path={mdiAlertOutline} size={0.55} /> {t('journey.truncated', 'Long document: analysis based on the leading portion of the text.')}
        </p>
      )}
    </div>
  );
}

export default function LegislativeJourneyPanel({ carriageId, mode = 'full', onOpenFullAnalysis }: {
  carriageId: string;
  mode?: 'compact' | 'full';
  onOpenFullAnalysis?: () => void;
}) {
  const { t } = useTranslation();
  const [data, setData] = useState<JourneyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    positionService.journey(carriageId)
      .then((r) => { if (alive) setData(r); })
      .catch(() => { if (alive) setData({ status: 'error' }); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [carriageId]);

  const generate = async (force = false) => {
    setGenerating(true);
    try {
      const r = await positionService.generateJourney(carriageId, force);
      setData(r);
    } catch {
      setData({ status: 'error' });
    } finally {
      setGenerating(false);
    }
  };

  if (loading) return null;
  if (!data) return null;

  const ready = data.status === 'ready';
  const absent = data.status === 'absent';
  const errored = data.status === 'error';

  // ---- compact (file-detail modal): summary + CTA ----
  if (mode === 'compact') {
    if (!ready && !generating) {
      if (absent) {
        return (
          <div className="journey-panel journey-panel--compact">
            <div className="journey-panel__head">
              <Icon path={mdiTimelineTextOutline} size={0.9} />
              <h4>{t('journey.title', 'Legislative journey')}</h4>
            </div>
            <p className="journey-panel__note">{t('journey.absentBlurb', 'See how this file changed from the Commission proposal through to the committee vote, analysed with AI.')}</p>
            <button className="journey-panel__gen" onClick={() => generate(false)}>
              <Icon path={mdiCreation} size={0.8} /> {t('journey.generate', 'Generate AI analysis')}
            </button>
          </div>
        );
      }
      return null; // error / generating-elsewhere: stay quiet in compact
    }
    if (generating) {
      return (
        <div className="journey-panel journey-panel--compact">
          <div className="journey-panel__generating">
            <Icon path={mdiLoading} size={0.9} spin /> {t('journey.generating', 'Analysing the documents...')}
          </div>
        </div>
      );
    }
    return (
      <div className="journey-panel journey-panel--compact">
        <div className="journey-panel__head">
          <Icon path={mdiTimelineTextOutline} size={0.9} />
          <h4>{t('journey.title', 'Legislative journey')}</h4>
          <span className="journey-panel__ai">{t('journey.aiTag', 'AI')}</span>
        </div>
        <p className="journey-panel__summary">{data.summary}</p>
        {onOpenFullAnalysis && (
          <button className="journey-panel__cta" onClick={onOpenFullAnalysis}>
            {t('journey.cta', 'See the full comparison in Position Analysis')}
            <Icon path={mdiArrowRightCircleOutline} size={0.8} />
          </button>
        )}
      </div>
    );
  }

  // ---- full (Position Analysis) ----
  if (absent || errored) {
    return (
      <div className="journey-panel">
        <div className="journey-panel__head">
          <Icon path={mdiTimelineTextOutline} size={1} />
          <h3>{t('journey.title', 'Legislative journey')}</h3>
          <span className="journey-panel__ai">{t('journey.aiTag', 'AI')}</span>
        </div>
        <p className="journey-panel__note">{t('journey.absentBlurb', 'See how this file changed from the Commission proposal through to the committee vote, analysed with AI.')}</p>
        <button className="journey-panel__gen" onClick={() => generate(false)} disabled={generating}>
          <Icon path={generating ? mdiLoading : mdiCreation} size={0.8} spin={generating} />
          {generating ? t('journey.generating', 'Analysing the documents...') : t('journey.generate', 'Generate AI analysis')}
        </button>
      </div>
    );
  }

  const cmp = data.comparison;
  return (
    <div className="journey-panel">
      <div className="journey-panel__head">
        <Icon path={mdiTimelineTextOutline} size={1} />
        <h3>{t('journey.title', 'Legislative journey')}</h3>
        <span className="journey-panel__ai">{t('journey.aiTag', 'AI')}</span>
        {data.stale && <span className="journey-panel__stale">{t('journey.stale', 'New documents since')}</span>}
      </div>

      {data.summary && <p className="journey-panel__summary">{data.summary}</p>}
      {cmp?.overview && <p className="journey-panel__overview">{cmp.overview}</p>}

      <div className="journey-panel__layers">
        {(data.layers || []).map((l) => <LayerCard key={l.kind} layer={l} />)}
      </div>

      {cmp?.where_the_fight_is && (
        <div className="journey-panel__fight">
          <h4><Icon path={mdiSwordCross} size={0.7} /> {t('journey.whereFight', 'Where the fight is')}</h4>
          <p>{cmp.where_the_fight_is}</p>
          {cmp.contested_points?.length > 0 && (
            <ul className="journey-panel__contested">
              {cmp.contested_points.map((c, i) => <li key={i}>{c}</li>)}
            </ul>
          )}
        </div>
      )}

      {cmp?.caveats && <p className="journey-panel__caveats">{cmp.caveats}</p>}

      <div className="journey-panel__foot">
        <span>{t('journey.builtWith', 'Analysed with')} {data.engine || 'AI'}{data.generated_at ? ` · ${new Date(data.generated_at).toLocaleDateString()}` : ''}</span>
        <button className="journey-panel__regen" onClick={() => generate(true)} disabled={generating}>
          <Icon path={generating ? mdiLoading : mdiCreation} size={0.6} spin={generating} />
          {generating ? t('journey.generating', 'Analysing the documents...') : t('journey.regenerate', 'Refresh analysis')}
        </button>
      </div>
    </div>
  );
}
