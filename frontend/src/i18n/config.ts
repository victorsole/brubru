// frontend/src/i18n/config.ts
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

// Static translation imports
import en from './locales/en.json';
import es from './locales/es.json';
import ca from './locales/ca.json';
import fr from './locales/fr.json';
import it from './locales/it.json';
import nl from './locales/nl.json';

// Supported languages (6 total - human-reviewed translations)
export const SUPPORTED_LANGUAGES = ['en', 'es', 'ca', 'fr', 'it', 'nl'] as const;
export type SupportedLanguage = typeof SUPPORTED_LANGUAGES[number];

export const LANGUAGE_NAMES: Record<SupportedLanguage, string> = {
  en: 'English',
  es: 'Español',
  ca: 'Català',
  fr: 'Français',
  it: 'Italiano',
  nl: 'Nederlands',
};

// BCP 47 locales for date/number formatting, keyed by UI language.
// Used instead of hardcoded 'en-GB' so "22 July 2026" renders as
// "22 de juliol del 2026" when the app is in Catalan, etc.
const DATE_LOCALES: Record<SupportedLanguage, string> = {
  en: 'en-GB',
  es: 'es-ES',
  ca: 'ca-ES',
  fr: 'fr-FR',
  it: 'it-IT',
  nl: 'nl-NL',
};

/** Current BCP 47 locale for toLocaleDateString / Intl formatters. */
export const uiDateLocale = (): string => {
  const lang = (i18n.language || 'en').split('-')[0] as SupportedLanguage;
  return DATE_LOCALES[lang] || 'en-GB';
};

/**
 * Apply a user's stored profile language to the UI. Called after login /
 * auth restore so `users.language` actually drives the interface instead
 * of silently falling back to English. No-ops on unknown or already-active
 * languages.
 */
export const applyUserLanguage = (lang: string | null | undefined): void => {
  if (!lang) return;
  const code = lang.toLowerCase().split('-')[0] as SupportedLanguage;
  if (!SUPPORTED_LANGUAGES.includes(code)) return;
  if (i18n.language === code) return;
  void i18n.changeLanguage(code);
};

// Initialize i18next with static resources
i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      es: { translation: es },
      ca: { translation: ca },
      fr: { translation: fr },
      it: { translation: it },
      nl: { translation: nl },
    },
    fallbackLng: 'en',
    supportedLngs: SUPPORTED_LANGUAGES as unknown as string[],

    // Language detection - only from localStorage, not from browser
    detection: {
      order: ['localStorage'],
      caches: ['localStorage'],
      lookupLocalStorage: 'i18nextLng',
    },

    interpolation: {
      escapeValue: false, // React already escapes
    },

    react: {
      useSuspense: false,
      bindI18n: 'languageChanged loaded',
      bindI18nStore: 'added removed',
      transEmptyNodeValue: '',
      transSupportBasicHtmlNodes: true,
      transKeepBasicHtmlNodesFor: ['br', 'strong', 'i', 'p'],
    },
  });

export default i18n;
