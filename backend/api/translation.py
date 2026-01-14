# backend/api/translation.py
from fastapi import APIRouter, HTTPException
from schemas.translation_schemas import TranslationRequest, TranslationResponse
from services.translation_service import translation_service

router = APIRouter(prefix="/api/translate", tags=["Translation"])

@router.post("", response_model=TranslationResponse)
async def translate(request: TranslationRequest):
    """
    Translate texts to target language using Google Translate API

    - **texts**: List of texts to translate
    - **target_language**: Target language code (e.g., 'es', 'fr', 'de')
    - **source_language**: Source language code (default: 'en')

    Returns dictionary mapping original texts to translated texts
    """
    try:
        # Check if we have cached translations
        cached = False
        if request.target_language in translation_service.translation_cache:
            cache = translation_service.translation_cache[request.target_language]
            if all(text in cache for text in request.texts):
                cached = True

        # Get translations (from cache or API)
        translations = translation_service.translate_texts(
            texts=request.texts,
            target_language=request.target_language,
            source_language=request.source_language
        )

        return TranslationResponse(
            translations=translations,
            target_language=request.target_language,
            cached=cached
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Translation failed: {str(e)}"
        )

@router.delete("/cache")
async def clear_translation_cache(language_code: str = None):
    """
    Clear translation cache

    - **language_code**: Optional language code to clear specific language cache
    """
    try:
        translation_service.clear_cache(language_code)
        message = f"Cleared cache for {language_code}" if language_code else "Cleared all translation cache"
        return {"message": message}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear cache: {str(e)}"
        )
