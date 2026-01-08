# backend/schemas/translation_schemas.py
from pydantic import BaseModel, Field
from typing import List, Dict

class TranslationRequest(BaseModel):
    """Request schema for translation"""
    texts: List[str] = Field(..., description="List of texts to translate")
    target_language: str = Field(..., description="Target language code (e.g., 'es', 'fr')")
    source_language: str = Field(default="en", description="Source language code")

class TranslationResponse(BaseModel):
    """Response schema for translation"""
    translations: Dict[str, str] = Field(..., description="Map of original text to translated text")
    target_language: str = Field(..., description="Target language code")
    cached: bool = Field(default=False, description="Whether translations were served from cache")
