// frontend/src/services/translation_service.ts
import axios from 'axios';
import i18n from '../i18n/config';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface TranslationResponse {
  translations: Record<string, string>;
  target_language: string;
  cached: boolean;
}

/**
 * Translation Service
 * Handles dynamic translation of UI text using Google Translate API via backend
 */
class TranslationService {
  private translationCache: Map<string, Record<string, string>> = new Map();

  /**
   * Load translations for a specific language
   * If translations don't exist, fetch them from backend (which uses Google Translate)
   */
  async loadTranslations(targetLanguage: string): Promise<void> {
    console.log('📥 Loading translations for:', targetLanguage);

    // English is the source language, no need to translate
    if (targetLanguage === 'en') {
      console.log('✅ English selected, no translation needed');
      return;
    }

    // Check if we already have cached translations
    if (this.translationCache.has(targetLanguage)) {
      console.log('💾 Using cached translations for:', targetLanguage);
      const translations = this.translationCache.get(targetLanguage)!;
      i18n.addResourceBundle(targetLanguage, 'translation', translations, true, true);
      return;
    }

    // Check localStorage first
    const cachedTranslations = this.getFromLocalStorage(targetLanguage);
    if (cachedTranslations) {
      console.log('💾 Using localStorage translations for:', targetLanguage);
      this.translationCache.set(targetLanguage, cachedTranslations);
      i18n.addResourceBundle(targetLanguage, 'translation', cachedTranslations, true, true);
      return;
    }

    // Fetch translations from backend
    try {
      console.log('🌐 Fetching translations from backend for:', targetLanguage);
      const englishTranslations = i18n.getResourceBundle('en', 'translation');
      const textsToTranslate = Object.values(englishTranslations);
      const keys = Object.keys(englishTranslations);

      console.log(`📤 Sending ${textsToTranslate.length} texts to translate`);
      const response = await axios.post<TranslationResponse>(
        `${API_URL}/api/translate`,
        {
          texts: textsToTranslate,
          target_language: targetLanguage,
          source_language: 'en',
        }
      );

      console.log('📥 Received translations from backend');

      // Create translation resource bundle
      const translationBundle: Record<string, string> = {};
      keys.forEach((key, index) => {
        const originalText = String(textsToTranslate[index]);
        translationBundle[key] = response.data.translations[originalText] || originalText;
      });

      // Cache in memory and localStorage
      this.translationCache.set(targetLanguage, translationBundle);
      this.saveToLocalStorage(targetLanguage, translationBundle);

      // Add to i18next
      i18n.addResourceBundle(targetLanguage, 'translation', translationBundle, true, true);
      console.log('✅ Translations loaded and cached for:', targetLanguage);
    } catch (error) {
      console.error(`❌ Failed to load translations for ${targetLanguage}:`, error);
      // Fall back to English if translation fails
      throw error;
    }
  }

  /**
   * Change language and load translations if needed
   */
  async changeLanguage(language: string): Promise<void> {
    console.log('🌐 Translation Service: Changing language to:', language);
    try {
      console.log('🌐 Loading translations for:', language);
      await this.loadTranslations(language);

      console.log('🌐 Changing i18n language to:', language);
      await i18n.changeLanguage(language);

      // Verify the language was changed
      console.log('📍 Current i18n language:', i18n.language);

      // Check if translations are available
      const hasTranslations = i18n.hasResourceBundle(language, 'translation');
      console.log(`📚 Has resource bundle for ${language}:`, hasTranslations);

      if (hasTranslations) {
        const sampleKey = 'header.main';
        const translation = i18n.t(sampleKey);
        console.log(`🔍 Sample translation for '${sampleKey}':`, translation);
      }

      console.log('✅ Language changed successfully to:', language);
    } catch (error) {
      console.error('❌ Failed to change language:', error);
      // Fall back to English
      console.log('🔄 Falling back to English');
      await i18n.changeLanguage('en');
    }
  }

  /**
   * Get current language
   */
  getCurrentLanguage(): string {
    return i18n.language || 'en';
  }

  /**
   * Clear translation cache
   */
  clearCache(): void {
    this.translationCache.clear();
    // Clear localStorage translations
    Object.keys(localStorage).forEach(key => {
      if (key.startsWith('brubru_translations_')) {
        localStorage.removeItem(key);
      }
    });
  }

  /**
   * Save translations to localStorage
   */
  private saveToLocalStorage(language: string, translations: Record<string, string>): void {
    try {
      const key = `brubru_translations_${language}`;
      const data = {
        translations,
        timestamp: Date.now(),
      };
      localStorage.setItem(key, JSON.stringify(data));
    } catch (error) {
      console.error('Failed to save translations to localStorage:', error);
    }
  }

  /**
   * Get translations from localStorage
   * Returns null if not found or expired (older than 7 days)
   */
  private getFromLocalStorage(language: string): Record<string, string> | null {
    try {
      const key = `brubru_translations_${language}`;
      const data = localStorage.getItem(key);
      if (!data) return null;

      const parsed = JSON.parse(data);
      const age = Date.now() - parsed.timestamp;
      const maxAge = 7 * 24 * 60 * 60 * 1000; // 7 days

      if (age > maxAge) {
        localStorage.removeItem(key);
        return null;
      }

      return parsed.translations;
    } catch (error) {
      console.error('Failed to get translations from localStorage:', error);
      return null;
    }
  }
}

export const translationService = new TranslationService();
