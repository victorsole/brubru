# backend/services/translation_service.py
from google.cloud import translate_v2 as translate
from typing import List, Dict, Optional
import os
import json
import html
from pathlib import Path
from backend.core.config import settings

class TranslationService:
    """
    Service for translating text using Google Cloud Translation API
    Includes in-memory and file-based caching to reduce API calls
    """

    def __init__(self):
        """Initialize the translation client and cache"""
        # Initialize Google Translate client
        # Try multiple authentication methods in order of preference
        self.client = None

        # Method 1: Try service account credentials (most secure)
        if settings.GOOGLE_APPLICATION_CREDENTIALS:
            try:
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = settings.GOOGLE_APPLICATION_CREDENTIALS
                self.client = translate.Client()
                print("✅ Google Translate client initialized with service account")
            except Exception as e:
                print(f"⚠️ Service account auth failed: {e}")

        # Method 2: Try API key (simpler, works for development)
        if self.client is None and settings.GOOGLE_API_KEY:
            try:
                # For API key authentication, we need to use it differently
                # Set as environment variable for the client to pick up
                os.environ['GOOGLE_API_KEY'] = settings.GOOGLE_API_KEY
                # Try creating client - it may work with ADC if project is set
                from google.oauth2 import service_account
                from google.auth import credentials as auth_credentials

                # For API key, we'll use a simple approach: just set the key and try
                # The translate_v2.Client works best with service accounts
                # For API keys, we might need to fall back to REST API
                print("⚠️ API key authentication requires service account credentials")
                print("   Please create service account credentials from Google Cloud Console")
            except Exception as e:
                print(f"⚠️ API key auth failed: {e}")

        # No authentication method worked
        if self.client is None:
            print("⚠️ Warning: Google Translate requires service account credentials")
            print("   The system will work, but translations won't happen automatically")
            print("   To enable translations:")
            print("   1. Go to Google Cloud Console")
            print("   2. Enable Cloud Translation API")
            print("   3. Create a service account with 'Cloud Translation API User' role")
            print("   4. Download JSON credentials")
            print("   5. Set GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json in .env")

        # In-memory cache: {language_code: {original_text: translated_text}}
        self.translation_cache: Dict[str, Dict[str, str]] = {}

        # Cache directory
        self.cache_dir = Path("backend/cache/translations")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Load cache from disk
        self._load_cache_from_disk()

    def translate_texts(
        self,
        texts: List[str],
        target_language: str,
        source_language: str = "en"
    ) -> Dict[str, str]:
        """
        Translate a list of texts to target language

        Args:
            texts: List of texts to translate
            target_language: Target language code (e.g., 'es', 'fr')
            source_language: Source language code (default: 'en')

        Returns:
            Dictionary mapping original text to translated text
        """
        # If no translation needed (same language)
        if target_language == source_language:
            return {text: text for text in texts}

        # If client is not available, return original texts
        if self.client is None:
            print(f"Translation client not available, returning original texts")
            return {text: text for text in texts}

        # Initialize cache for this language if not exists
        if target_language not in self.translation_cache:
            self.translation_cache[target_language] = {}

        results = {}
        texts_to_translate = []

        # Check cache first
        for text in texts:
            if text in self.translation_cache[target_language]:
                results[text] = self.translation_cache[target_language][text]
            else:
                texts_to_translate.append(text)

        # Translate uncached texts
        if texts_to_translate:
            try:
                translations = self.client.translate(
                    texts_to_translate,
                    target_language=target_language,
                    source_language=source_language
                )

                # Handle both single translation and batch translations
                if not isinstance(translations, list):
                    translations = [translations]

                # Add to results and cache
                for original_text, translation_result in zip(texts_to_translate, translations):
                    # Decode HTML entities (e.g., &#39; -> ', &nbsp; -> space)
                    translated_text = html.unescape(translation_result['translatedText'])
                    results[original_text] = translated_text
                    self.translation_cache[target_language][original_text] = translated_text

                # Save cache to disk
                self._save_cache_to_disk(target_language)

            except Exception as e:
                print(f"Translation error: {e}")
                # On error, return original texts for untranslated items
                for text in texts_to_translate:
                    results[text] = text

        return results

    def _load_cache_from_disk(self):
        """Load translation cache from disk"""
        try:
            cache_files = list(self.cache_dir.glob("*.json"))
            for cache_file in cache_files:
                language_code = cache_file.stem
                with open(cache_file, 'r', encoding='utf-8') as f:
                    self.translation_cache[language_code] = json.load(f)
            print(f"Loaded translation cache for {len(self.translation_cache)} languages")
        except Exception as e:
            print(f"Failed to load translation cache: {e}")

    def _save_cache_to_disk(self, language_code: str):
        """Save translation cache for a specific language to disk"""
        try:
            cache_file = self.cache_dir / f"{language_code}.json"
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.translation_cache[language_code], f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save translation cache for {language_code}: {e}")

    def clear_cache(self, language_code: Optional[str] = None):
        """Clear translation cache"""
        if language_code:
            # Clear specific language
            if language_code in self.translation_cache:
                del self.translation_cache[language_code]

            cache_file = self.cache_dir / f"{language_code}.json"
            if cache_file.exists():
                cache_file.unlink()
        else:
            # Clear all
            self.translation_cache.clear()
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()

# Singleton instance
translation_service = TranslationService()
