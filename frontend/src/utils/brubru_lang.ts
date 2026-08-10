// Which of Brubru's six languages a request should be served in.
//
// Brubru speaks EN, FR, NL, ES, CA and IT. Not 23. i18next hands back tags
// like "en-GB" or "ca-ES", and the API wants the bare code, so every caller
// was writing the same slice-and-check by hand. One copy, so a seventh
// language is one edit rather than a search.

import i18n from 'i18next';

export const BRUBRU_LANGS = ['en', 'es', 'ca', 'fr', 'it', 'nl'] as const;

export type BrubruLang = (typeof BRUBRU_LANGS)[number];

/** The active UI language as an API-ready code, falling back to English. */
export const currentApiLang = (): BrubruLang => {
  const raw = (i18n.language || 'en').slice(0, 2).toLowerCase();
  return (BRUBRU_LANGS as readonly string[]).includes(raw) ? (raw as BrubruLang) : 'en';
};
