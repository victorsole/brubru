/**
 * Plain-language procedure-type family (doc-06 §7 Axis A).
 *
 * Maps an OEIL procedure suffix (e.g. "2024/0176(COD)") to an i18n key under
 * `myFilesTab.*` so a non-expert reads "New EU law" instead of "(COD)". Returns
 * null for housekeeping types (IMM, REG, ...) that should carry no badge.
 *
 * Shared by My Tracked Files and the Hot This Week widget so both speak the same
 * plain language.
 */
export function plainLanguageTypeKey(ref?: string | null): string | null {
  if (!ref) return null;
  const m = ref.match(/\(([A-Z]+)\)/);
  if (!m) return null;
  const code = m[1];
  if (['COD', 'CNS', 'APP'].includes(code)) return 'typeNewLaw';
  if (['INI', 'INL', 'RSP'].includes(code)) return 'typeParliamentPosition';
  if (code === 'NLE') return 'typeAgreement';
  if (['DEA', 'RPS'].includes(code)) return 'typeScrutiny';
  if (['BUD', 'DEC'].includes(code)) return 'typeBudget';
  return null;
}
