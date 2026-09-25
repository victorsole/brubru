"""EESC and CoR opinion models (migrations 064, 065).

The two advisory committees the Treaties require the Commission, Parliament and Council to
consult. Both tables are filled by `scripts/backfill_eu_{eesc,cor}.py` from Cellar and their
full text by `scripts/fetch_general_publication_bodies.py`; until 25 September 2026 nothing
read them, so 4,518 opinions averaging over 20,000 characters were held and served to nobody.

The schemas are near-identical: the committee-specific columns are `section` and
`co_rapporteur` for the EESC, `commission_code` and the rapporteur's country and political
group for the CoR.
"""
from sqlalchemy import (BigInteger, Boolean, Column, Date, DateTime, Integer, String, Text)
from sqlalchemy.dialects.postgresql import ARRAY

from core.database import Base


class _OpinionBase:
    id = Column(BigInteger, primary_key=True)
    celex = Column(String(40))
    work_uri = Column(Text)
    title = Column(Text)
    document_date = Column(Date, index=True)
    adopted_date = Column(Date)
    document_type = Column(String(40))
    resource_type_uri = Column(Text)
    resource_type_label = Column(String(100))
    rapporteur = Column(Text)
    session_label = Column(Text)
    session_date = Column(Date)
    vote_for = Column(Integer)
    vote_against = Column(Integer)
    vote_abstain = Column(Integer)
    adopted = Column(Boolean)
    related_celex = Column(String(40))
    related_com_ref = Column(String(40))
    own_initiative = Column(Boolean, nullable=False)
    available_languages = Column(ARRAY(Text))
    eurovoc_concepts = Column(ARRAY(Text))
    eurlex_url = Column(Text)
    has_body = Column(Boolean, nullable=False)
    body_html = Column(Text)
    body_text = Column(Text)
    body_source = Column(String(40))
    fetched_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))


class EuEescOpinion(_OpinionBase, Base):
    __tablename__ = "eu_eesc_opinions"
    section = Column(String(16))
    co_rapporteur = Column(Text)
    eesc_url = Column(Text)


class EuCorOpinion(_OpinionBase, Base):
    __tablename__ = "eu_cor_opinions"
    commission_code = Column(String(8))
    rapporteur_country = Column(String(2))
    rapporteur_group = Column(String(16))
    cor_url = Column(Text)
