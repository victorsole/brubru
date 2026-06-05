/**
 * Document "kind" resolution — the real advocacy type lives in tags, not the coarse
 * document_type column (only position papers are typed 'strategy'; the rest are
 * 'note' + a tag). Mirrors My Documents' resolveKind so Strategy Docs and My
 * Documents agree on kinds. Used to make Strategy Docs the advocacy-outputs hub.
 */
import type { UserDocument } from '../hooks/use_bubble';

const TAG_KINDS = [
  'position_paper', 'mep_briefing', 'talking_points', 'resolution', 'petition',
  'ep_question', 'eu_email', 'one_pager', 'press_release', 'stakeholder_map',
  'impact_assessment', 'presentation', 'event_poster', 'consultation_response',
];

export function resolveKind(doc: UserDocument): string {
  if (doc.document_type === 'amendment_carriage') return 'amendment';
  const tags = doc.tags || [];
  for (const k of TAG_KINDS) if (tags.includes(k)) return k;
  return doc.document_type;
}

/** The advocacy artefacts that belong in Strategy Docs (the "what you produce to influence a file" set). */
export const ADVOCACY_KINDS = new Set([
  'strategy', 'position_paper', 'talking_points', 'mep_briefing', 'one_pager',
  'eu_email', 'petition', 'ep_question', 'resolution', 'consultation_response',
  'stakeholder_map', 'amendment',
]);

/** Display order for the kind chips. */
export const KIND_ORDER = [
  'strategy', 'position_paper', 'talking_points', 'mep_briefing', 'one_pager',
  'eu_email', 'petition', 'ep_question', 'resolution', 'consultation_response',
  'stakeholder_map', 'amendment',
];

/** English fallbacks; i18n keys are sd.kind_<kind>. */
export const KIND_LABELS_EN: Record<string, string> = {
  strategy: 'Strategy', position_paper: 'Position paper', talking_points: 'Talking points',
  mep_briefing: 'MEP briefing', one_pager: 'One-pager', eu_email: 'EU email',
  petition: 'EP petition', ep_question: 'EP question', resolution: 'EP resolution',
  consultation_response: 'Consultation response', stakeholder_map: 'Stakeholder map',
  amendment: 'Amendment',
};

export const kindLabel = (t: any, kind: string) => t(`sd.kind_${kind}`, KIND_LABELS_EN[kind] || kind);
