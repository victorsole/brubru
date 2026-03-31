"""
Catalan Translation Database Model

Stores metadata for Catalan EU legislation translations.
HTML content remains on SiteGround (static files); this table
serves the catalogue API (search, pagination, category filtering).

Created: March 2026
"""

from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, Index
from sqlalchemy.sql import func
from core.database import Base


class CatalanTranslation(Base):
    """
    Catalan EU Legislation Translation

    Metadata record for a translated EU act. The actual HTML translation
    is served as a static file on SiteGround at:
        brubru.beresol.eu/legislacio-ue-catala/{celex}/index.html

    This table enables:
    - Dynamic landing page with search/pagination
    - Category filtering
    - Statistics (total translated, per-category counts)
    - Future: SFTP deployment tracking
    """

    __tablename__ = "catalan_translations"

    id = Column(Integer, primary_key=True, index=True)

    # Identifiers
    celex = Column(String(30), unique=True, nullable=False, index=True)

    # Metadata
    title_en = Column(Text, nullable=False)          # Original English title
    title_ca = Column(Text, nullable=False)           # Translated Catalan title
    short_name = Column(String(100))                  # e.g. "GDPR", "AI Act", "MiFID II"
    doc_type = Column(String(50), index=True)         # "regulation", "directive", "decision", "delegated", "implementing"

    # Classification (landing page categories)
    category = Column(String(100), index=True)        # e.g. "Transformacio digital"
    category_en = Column(String(100))                 # English category name

    # Translation stats
    articles_count = Column(Integer, default=0)
    recitals_count = Column(Integer, default=0)
    html_size_bytes = Column(Integer, default=0)

    # Translation details
    engine = Column(String(30), default="softcatala")  # "softcatala" or "sonnet"
    source_format = Column(String(30))                 # "formex", "consolidated_html", "cellar"
    source_file = Column(Text)                         # Path to source XML/HTML

    # SiteGround deployment
    siteground_url = Column(Text)                      # Full URL on SiteGround
    deployed_at = Column(TIMESTAMP)                    # When last deployed to SiteGround

    # Timestamps
    translated_at = Column(TIMESTAMP, server_default=func.now())
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<CatalanTranslation(celex={self.celex}, short_name={self.short_name})>"

    def to_dict(self):
        return {
            'id': self.id,
            'celex': self.celex,
            'title_en': self.title_en,
            'title_ca': self.title_ca,
            'short_name': self.short_name,
            'doc_type': self.doc_type,
            'category': self.category,
            'category_en': self.category_en,
            'articles_count': self.articles_count,
            'recitals_count': self.recitals_count,
            'html_size_bytes': self.html_size_bytes,
            'engine': self.engine,
            'source_format': self.source_format,
            'siteground_url': self.siteground_url,
            'deployed_at': self.deployed_at.isoformat() if self.deployed_at else None,
            'translated_at': self.translated_at.isoformat() if self.translated_at else None,
        }

    def to_catalogue_dict(self):
        """Lightweight dict for landing page listings."""
        return {
            'celex': self.celex,
            'title_ca': self.title_ca,
            'short_name': self.short_name,
            'doc_type': self.doc_type,
            'category': self.category,
            'articles_count': self.articles_count,
            'recitals_count': self.recitals_count,
            'url': f'/legislacio-ue-catala/{self.celex}/',
        }


# Indexes
Index('idx_catalan_translations_category', CatalanTranslation.category)
Index('idx_catalan_translations_doc_type', CatalanTranslation.doc_type)
