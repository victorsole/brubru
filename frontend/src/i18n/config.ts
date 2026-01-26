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
  es: 'Espanol',
  ca: 'Catala',
  fr: 'Francais',
  it: 'Italiano',
  nl: 'Nederlands',
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
