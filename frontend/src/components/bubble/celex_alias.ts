/**
 * Small client-side CELEX → friendly label resolver.
 *
 * Covers the heaviest-traffic EU instruments so cards in the Documents tab
 * can display a recognisable alias next to the raw CELEX (e.g.
 * "Regulation (EU) 2016/679 — GDPR"). Falls back to formatting the CELEX
 * itself when no alias is known.
 *
 * The source of truth for the curated list is
 * backend/knowledge_base/institutions/legislation_acronyms_manual.json;
 * keep this map in rough sync with that file for the top items.
 */

interface CelexAlias {
  formal: string;
  alias?: string;
}

const ALIAS_MAP: Record<string, CelexAlias> = {
  '32016R0679': { formal: 'Regulation (EU) 2016/679', alias: 'GDPR' },
  '32024R1689': { formal: 'Regulation (EU) 2024/1689', alias: 'AI Act' },
  '32022R2065': { formal: 'Regulation (EU) 2022/2065', alias: 'DSA' },
  '32022R1925': { formal: 'Regulation (EU) 2022/1925', alias: 'DMA' },
  '32013R0575': { formal: 'Regulation (EU) 575/2013', alias: 'CRR' },
  '32023R1114': { formal: 'Regulation (EU) 2023/1114', alias: 'MiCA' },
  '32022L2555': { formal: 'Directive (EU) 2022/2555', alias: 'NIS2' },
  '32024L1760': { formal: 'Directive (EU) 2024/1760', alias: 'CSDDD' },
  '32022L2464': { formal: 'Directive (EU) 2022/2464', alias: 'CSRD' },
  '32023R1115': { formal: 'Regulation (EU) 2023/1115', alias: 'EUDR' },
  '32023R0956': { formal: 'Regulation (EU) 2023/956', alias: 'CBAM' },
  '32024R1252': { formal: 'Regulation (EU) 2024/1252', alias: 'CRMA' },
  '32023R1781': { formal: 'Regulation (EU) 2023/1781', alias: 'Chips Act' },
  '32014L0065': { formal: 'Directive 2014/65/EU', alias: 'MiFID II' },
  '32018R1725': { formal: 'Regulation (EU) 2018/1725', alias: 'EUDPR' },
  '32020R0852': { formal: 'Regulation (EU) 2020/852', alias: 'Taxonomy' },
  '32024R1183': { formal: 'Regulation (EU) 2024/1183', alias: 'eIDAS 2' },
  '32022R0868': { formal: 'Regulation (EU) 2022/868', alias: 'Data Governance Act' },
  '32023R2854': { formal: 'Regulation (EU) 2023/2854', alias: 'Data Act' },
  '32024R1735': { formal: 'Regulation (EU) 2024/1735', alias: 'Net Zero Industry Act' },
  '32022R2554': { formal: 'Regulation (EU) 2022/2554', alias: 'DORA' },
  // Commission proposals (sector 5) — pre-adoption files. Brubru users
  // frequently work on these in the Amendator.
  '52026PC0321': { formal: 'COM(2026) 321', alias: 'EU Inc.' },
  '52024PC0064': { formal: 'COM(2024) 64', alias: 'EU Insolvency' },
  '52021PC0206': { formal: 'COM(2021) 206', alias: 'AI Act proposal' },
};

/**
 * Format a CELEX into a normalised label "Type (EU) YYYY/N — Alias" when known,
 * otherwise return the CELEX as-is.
 */
export function formatCelexLabel(celex?: string | null): string {
  if (!celex) return '';
  const hit = ALIAS_MAP[celex.toUpperCase()];
  if (hit) {
    return hit.alias ? `${hit.formal} — ${hit.alias}` : hit.formal;
  }
  // Generic fallback: parse the CELEX shape.
  const m = /^([0-9])(\d{4})([A-Z]{1,2})(\d{4})$/.exec(celex);
  if (m) {
    const [, sector, year, type, num] = m;
    const cleanedNum = num.replace(/^0+/, '') || '0';
    // Sector 5 = Commission preparatory acts. PC = proposal for codecision,
    // DC = communication, JC = joint communication, SC = staff working
    // document, etc. Render as "COM(YYYY) NNN" so users see the familiar
    // pre-adoption identifier, not raw CELEX.
    if (sector === '5') {
      const proposalKinds: Record<string, string> = {
        PC: 'Commission proposal',
        DC: 'Commission communication',
        JC: 'Joint communication',
        SC: 'Staff working document',
        FC: 'Commission opinion',
      };
      const label = proposalKinds[type] || 'Commission act';
      return `${label} COM(${year}) ${cleanedNum}`;
    }
    const adoptedKinds: Record<string, string> = {
      R: 'Regulation',
      L: 'Directive',
      D: 'Decision',
      H: 'Recommendation',
      F: 'Framework decision',
      A: 'Agreement',
    };
    const kind = adoptedKinds[type] || type;
    return `${kind} (EU) ${year}/${cleanedNum}`;
  }
  return celex;
}

export function aliasOnly(celex?: string | null): string | undefined {
  if (!celex) return undefined;
  return ALIAS_MAP[celex.toUpperCase()]?.alias;
}
