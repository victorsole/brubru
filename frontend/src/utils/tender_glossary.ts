// Which terms the Tenderator glossary shows, in which order, under which
// heading.
//
// Structure lives here; the words live in the locale files under
// `tenderator.glossary.terms.*`. That split is deliberate: definitions are
// prose and have to reach all six of Brubru's languages through the normal
// i18n route, whereas ordering and grouping are presentation and should not be
// duplicated six times. It also avoids repeating the mistake `code_glossary.ts`
// documents about itself, where the expansions are English-only "as a
// fallback" and have stayed that way.
//
// `codes` ties an entry back to the machine values the API still returns, so
// the glossary and the decoded labels cannot describe different things.

export type GlossaryCategory = 'procurement' | 'funding' | 'eic';

export interface GlossaryEntry {
  /** i18n key under tenderator.glossary.terms */
  key: string;
  category: GlossaryCategory;
  /** eForms / portal codes this entry explains, matched when searching. */
  codes?: string[];
}

export const GLOSSARY_CATEGORIES: GlossaryCategory[] = ['procurement', 'funding', 'eic'];

export const GLOSSARY_ENTRIES: GlossaryEntry[] = [
  // Public procurement (the TED side)
  { key: 'ted', category: 'procurement', codes: ['TED'] },
  { key: 'cpv', category: 'procurement', codes: ['CPV'] },
  { key: 'nuts', category: 'procurement', codes: ['NUTS'] },
  { key: 'contractingAuthority', category: 'procurement' },
  { key: 'lot', category: 'procurement' },
  { key: 'frameworkAgreement', category: 'procurement', codes: ['framework'] },
  { key: 'awardCriteria', category: 'procurement', codes: ['price', 'cost', 'quality', 'best-value'] },
  { key: 'espd', category: 'procurement', codes: ['ESPD'] },
  { key: 'openProcedure', category: 'procurement', codes: ['open', 'open-1step', 'open-2step'] },
  { key: 'restrictedProcedure', category: 'procurement', codes: ['restricted'] },
  { key: 'negotiatedProcedure', category: 'procurement', codes: ['neg-w-call', 'neg-wo-call'] },
  { key: 'competitiveDialogue', category: 'procurement', codes: ['comp-dial', 'comp-tend'] },
  { key: 'innovationPartnership', category: 'procurement', codes: ['innovation'] },
  { key: 'contractNotice', category: 'procurement' },
  { key: 'estimatedValue', category: 'procurement' },

  // EU funding (the Funding & Tenders Portal side)
  { key: 'callForProposals', category: 'funding' },
  { key: 'callForTenders', category: 'funding' },
  { key: 'topicId', category: 'funding' },
  { key: 'typeOfAction', category: 'funding', codes: ['RIA', 'IA', 'CSA'] },
  { key: 'workProgramme', category: 'funding' },
  { key: 'consortium', category: 'funding' },
  { key: 'coordinator', category: 'funding' },
  { key: 'pic', category: 'funding', codes: ['PIC'] },
  { key: 'trl', category: 'funding', codes: ['TRL'] },
  { key: 'lumpSum', category: 'funding' },
  { key: 'mga', category: 'funding', codes: ['MGA', 'AGA'] },
  { key: 'sealOfExcellence', category: 'funding' },
  { key: 'coFinancingRate', category: 'funding' },

  // European Innovation Council
  { key: 'eic', category: 'eic', codes: ['EIC'] },
  { key: 'eicAccelerator', category: 'eic', codes: ['ACCELERATOR'] },
  { key: 'eicPathfinder', category: 'eic', codes: ['PATHFINDER'] },
  { key: 'eicTransition', category: 'eic', codes: ['TRANSITION'] },
  { key: 'stepScaleUp', category: 'eic', codes: ['STEP', 'SCALEUP'] },
  { key: 'blendedFinance', category: 'eic' },
];
