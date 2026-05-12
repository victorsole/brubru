"""
W4 P2 endpoints — partner-grade surfaces for parliamentary-questions, meetings,
rsb-opinions, delegated/implementing acts, tris-notifications.

Tables created by migration 038. Scrapers queued; endpoints return empty
result sets until ingestion ships, but partners can integrate against the
stable surface today.
"""

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from models.w4_entities import (
    ParliamentaryQuestion, RSBOpinion, SecondaryAct, TRISNotification,
    TransparencyMeeting,
)

from ._body import (
    DEFAULT_HAS_BODY_THRESHOLD,
    body_from_pdf_text,
    body_threshold_param,
    deprecated_body,
)
from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

parl_q_router = APIRouter(prefix="/parliamentary-questions", tags=["v1-parliamentary-questions"])
meetings_router = APIRouter(prefix="/meetings", tags=["v1-meetings"])
rsb_router = APIRouter(prefix="/rsb-opinions", tags=["v1-rsb-opinions"])
delegated_router = APIRouter(prefix="/delegated-acts", tags=["v1-delegated-acts"])
implementing_router = APIRouter(prefix="/implementing-acts", tags=["v1-implementing-acts"])
tris_router = APIRouter(prefix="/tris-notifications", tags=["v1-tris-notifications"])


# ============================================================================
# /parliamentary-questions
# ============================================================================


class ParliamentaryQuestionItem(BaseModel):
    id: str
    question_reference: str
    question_type: str
    parliamentary_term: int = 10
    subject: str
    text_question: Optional[str] = None
    text_answer: Optional[str] = None
    submitted_date: Optional[date] = None
    answered_date: Optional[date] = None
    asking_mep_ids: list = Field(default_factory=list)
    asking_mep_names: list = Field(default_factory=list)
    answering_institution: Optional[str] = None
    answering_commissioner: Optional[str] = None
    committees: list = Field(default_factory=list)
    procedure_ref: Optional[str] = None
    related_celex: list = Field(default_factory=list)
    policy_areas: list = Field(default_factory=list)
    source_url: Optional[str] = None
    answer_url: Optional[str] = None
    last_updated: Optional[datetime] = None
    # Body fields composed from text_question + text_answer (typically
    # 1k-3k chars total when both populated). Semantic <article> with
    # "Question" + "Answer" sections.
    has_body: bool = False
    body_html: Optional[str] = None
    body_txt: Optional[str] = None
    # The 5 mandatory Brubru v1 datapoints. public_url is the doceo
    # question page (citizen-facing); document_date is the submission
    # date; creation_date is when Brubru first ingested the row.
    public_url: Optional[str] = Field(None, description="Citizen URL — alias of source_url (the doceo question page).")
    document_date: Optional[date] = Field(None, description="The question's submission date (alias of submitted_date).")
    creation_date: Optional[datetime] = Field(None, description="Time the row was first ingested (alias of last_updated for now).")


def _parl_q_to_item(r, body_threshold: int = DEFAULT_HAS_BODY_THRESHOLD) -> ParliamentaryQuestionItem:
    from ._body import compose_html_from_sections
    body_html, body_text, has_body = compose_html_from_sections([
        ("Question", r.text_question),
        ("Answer", r.text_answer),
    ], threshold=body_threshold)
    return ParliamentaryQuestionItem(
        id=str(r.id),
        question_reference=r.question_reference,
        question_type=r.question_type.value if hasattr(r.question_type, "value") else str(r.question_type),
        parliamentary_term=int(r.parliamentary_term or 10),
        subject=r.subject,
        text_question=r.text_question,
        text_answer=r.text_answer,
        submitted_date=r.submitted_date,
        answered_date=r.answered_date,
        asking_mep_ids=list(r.asking_mep_ids or []),
        asking_mep_names=list(r.asking_mep_names or []),
        answering_institution=r.answering_institution,
        answering_commissioner=r.answering_commissioner,
        committees=list(r.committees or []),
        procedure_ref=r.procedure_ref,
        related_celex=list(r.related_celex or []),
        policy_areas=list(r.policy_areas or []),
        source_url=r.source_url,
        answer_url=r.answer_url,
        last_updated=r.last_updated,
        has_body=has_body,
        body_html=body_html,
        body_txt=body_text,
        # 5 mandatory datapoints
        public_url=r.source_url,
        document_date=r.submitted_date,
        creation_date=r.last_updated,
    )


@parl_q_router.get(
    "",
    response_model=PaginatedResponse[ParliamentaryQuestionItem],
    summary="EP parliamentary questions (written + oral) with answers",
    description=(
        "EP parliamentary questions submitted to Commission/Council and their "
        "answers. Source: europarl.europa.eu/plenary/en/parliamentary-questions.html. "
        "Scraper queued; endpoint returns empty until ingested."
    ),
)
async def list_parliamentary_questions(
    request: Request,
    q: Optional[str] = Query(None, description="Substring on subject + question text"),
    question_type: Optional[str] = Query(None, description="written | oral | priority | question_time"),
    parliamentary_term: Optional[int] = Query(None),
    asking_mep_id: Optional[str] = Query(None),
    answering_institution: Optional[str] = Query(None, description="COMMISSION | COUNCIL | ECB"),
    procedure_ref: Optional[str] = Query(None),
    committee: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None, description="submitted_date >= value"),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ParliamentaryQuestionItem]:
    query = db.query(ParliamentaryQuestion)
    filters = []
    if question_type:
        filters.append(ParliamentaryQuestion.question_type == question_type.lower())
    if parliamentary_term is not None:
        filters.append(ParliamentaryQuestion.parliamentary_term == parliamentary_term)
    if asking_mep_id:
        filters.append(ParliamentaryQuestion.asking_mep_ids.any(asking_mep_id))
    if answering_institution:
        filters.append(ParliamentaryQuestion.answering_institution == answering_institution.upper())
    if procedure_ref:
        filters.append(ParliamentaryQuestion.procedure_ref == procedure_ref)
    if committee:
        filters.append(ParliamentaryQuestion.committees.any(committee.upper()))
    if published_from:
        filters.append(ParliamentaryQuestion.submitted_date >= published_from)
    if published_to:
        filters.append(ParliamentaryQuestion.submitted_date <= published_to)
    if updated_from:
        filters.append(ParliamentaryQuestion.last_updated >= updated_from)
    if q:
        like = f"%{q}%"
        filters.append(or_(
            ParliamentaryQuestion.subject.ilike(like),
            ParliamentaryQuestion.text_question.ilike(like),
            ParliamentaryQuestion.text_answer.ilike(like),
        ))
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    rows = (
        query.order_by(ParliamentaryQuestion.submitted_date.desc().nullslast())
        .offset((page - 1) * limit).limit(limit).all()
    )
    data = [_parl_q_to_item(r, body_threshold=body_threshold) for r in rows]
    return build_envelope(data, total=total, page=page, limit=limit,
                          published_from=published_from, published_to=published_to,
                          updated_from=updated_from)


@parl_q_router.get(
    "/{question_reference:path}",
    response_model=ParliamentaryQuestionItem,
    summary="Single parliamentary question by reference (e.g. E-001234/2026)",
)
async def get_parl_question_detail(
    question_reference: str,
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> ParliamentaryQuestionItem:
    r = db.query(ParliamentaryQuestion).filter(ParliamentaryQuestion.question_reference == question_reference).first()
    if not r:
        raise HTTPException(status_code=404, detail={
            "error": f"Parliamentary question {question_reference} not found",
            "reason_code": "not_found",
            "resource": "parliamentary_question",
            "id": question_reference,
        })
    return _parl_q_to_item(r, body_threshold=body_threshold)


# ============================================================================
# /meetings — Commission Transparency Initiative
# ============================================================================


class TransparencyMeetingItem(BaseModel):
    id: str
    host_uuid: str
    host_name: Optional[str] = None
    host_role: Optional[str] = None
    host_dg: Optional[str] = None
    host_cabinet: Optional[str] = None
    meeting_date: date
    location: Optional[str] = None
    subject: str
    organisation_met: str
    transparency_register_id: Optional[str] = None
    organisation_type: Optional[str] = None
    representatives: Optional[str] = None
    source_url: str
    policy_areas: list = Field(default_factory=list)
    related_celex: list = Field(default_factory=list)
    last_updated: Optional[datetime] = None
    # The 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(None, description="Canonical citizen URL (alias of source_url).")
    body_txt: Optional[str] = Field(None, description="Plain-text body composed from the meeting record: subject + host + organisation met + location + representatives + policy areas.")
    body_html: Optional[str] = Field(None, description="HTML rendering of the same composition (paragraphs + key:value rows).")
    meeting_start_date: Optional[date] = Field(None, description="The meeting date (alias of meeting_date — this IS a meeting endpoint).")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested this row.")


def _compose_meeting_body(r) -> tuple:
    """Build (body_txt, body_html) from a TransparencyMeeting row. Uses every
    informative field on the record so partners get a meaningful body, not
    just the subject line. No upstream HTTP — pure DB row composition.
    """
    import html as _html
    lines_txt: list = []
    lines_html: list = []
    if r.subject:
        lines_txt.append(r.subject)
        lines_html.append(f"<p><strong>Subject:</strong> {_html.escape(r.subject)}</p>")
    rows_kv: list = []
    if r.meeting_date:
        rows_kv.append(("Date", str(r.meeting_date)))
    if r.location:
        rows_kv.append(("Location", r.location))
    host_label = " / ".join(filter(None, [r.host_name, r.host_role, r.host_dg]))
    if host_label:
        rows_kv.append(("Commission host", host_label))
    if r.host_cabinet:
        rows_kv.append(("Cabinet", r.host_cabinet))
    if r.organisation_met:
        rows_kv.append(("Organisation met", r.organisation_met))
    if r.organisation_type:
        rows_kv.append(("Organisation type", r.organisation_type))
    if r.transparency_register_id:
        rows_kv.append(("Transparency Register ID", r.transparency_register_id))
    if r.representatives:
        rows_kv.append(("Representatives", r.representatives))
    if r.policy_areas:
        rows_kv.append(("Policy areas", ", ".join(r.policy_areas)))
    if r.related_celex:
        rows_kv.append(("Related CELEX", ", ".join(r.related_celex)))
    for k, v in rows_kv:
        lines_txt.append(f"{k}: {v}")
        lines_html.append(f"<p><strong>{_html.escape(k)}:</strong> {_html.escape(str(v))}</p>")
    if not lines_txt:
        return None, None
    body_txt = "\n".join(lines_txt)
    body_html = "<article>" + "".join(lines_html) + "</article>"
    return body_txt, body_html


@meetings_router.get(
    "",
    response_model=PaginatedResponse[TransparencyMeetingItem],
    summary="Commission Transparency Initiative meetings register",
    description=(
        "Meetings between Commission cabinet/DG officials and external interest "
        "representatives. Source: ec.europa.eu/transparencyinitiative/meetings/. "
        "Seed host UUIDs from Marcadors: ca175ad3..., a2c7c963..., 9fd4662a...."
    ),
)
async def list_meetings(
    request: Request,
    host_uuid: Optional[str] = Query(None),
    host_dg: Optional[str] = Query(None),
    organisation_met: Optional[str] = Query(None, description="Substring match"),
    transparency_register_id: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Substring on subject"),
    published_from: Optional[date] = Query(None, description="meeting_date >= value"),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[TransparencyMeetingItem]:
    query = db.query(TransparencyMeeting)
    filters = []
    if host_uuid:
        filters.append(TransparencyMeeting.host_uuid == host_uuid)
    if host_dg:
        filters.append(TransparencyMeeting.host_dg == host_dg.upper())
    if organisation_met:
        filters.append(TransparencyMeeting.organisation_met.ilike(f"%{organisation_met}%"))
    if transparency_register_id:
        filters.append(TransparencyMeeting.transparency_register_id == transparency_register_id)
    if q:
        filters.append(TransparencyMeeting.subject.ilike(f"%{q}%"))
    if published_from:
        filters.append(TransparencyMeeting.meeting_date >= published_from)
    if published_to:
        filters.append(TransparencyMeeting.meeting_date <= published_to)
    if updated_from:
        filters.append(TransparencyMeeting.last_updated >= updated_from)
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    rows = (
        query.order_by(TransparencyMeeting.meeting_date.desc())
        .offset((page - 1) * limit).limit(limit).all()
    )
    data: list = []
    for r in rows:
        body_txt, body_html = _compose_meeting_body(r)
        data.append(TransparencyMeetingItem(
            id=str(r.id), host_uuid=r.host_uuid, host_name=r.host_name,
            host_role=r.host_role, host_dg=r.host_dg, host_cabinet=r.host_cabinet,
            meeting_date=r.meeting_date, location=r.location, subject=r.subject,
            organisation_met=r.organisation_met,
            transparency_register_id=r.transparency_register_id,
            organisation_type=r.organisation_type,
            representatives=r.representatives, source_url=r.source_url,
            policy_areas=list(r.policy_areas or []),
            related_celex=list(r.related_celex or []),
            last_updated=r.last_updated,
            public_url=r.source_url,
            body_txt=body_txt,
            body_html=body_html,
            meeting_start_date=r.meeting_date,
            creation_date=getattr(r, "first_seen", None) or getattr(r, "scraped_at", None) or r.last_updated,
        ))
    return build_envelope(data, total=total, page=page, limit=limit,
                          published_from=published_from, published_to=published_to,
                          updated_from=updated_from)


@meetings_router.get(
    "/{meeting_id}",
    response_model=TransparencyMeetingItem,
    summary="Single Transparency Initiative meeting by id (UUID)",
)
async def get_meeting_detail(
    meeting_id: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> TransparencyMeetingItem:
    r = db.query(TransparencyMeeting).filter(TransparencyMeeting.id == meeting_id).first()
    if not r:
        raise HTTPException(status_code=404, detail={
            "error": f"Meeting {meeting_id} not found",
            "reason_code": "not_found",
            "resource": "transparency_meeting",
            "id": meeting_id,
        })
    body_txt, body_html = _compose_meeting_body(r)
    return TransparencyMeetingItem(
        id=str(r.id), host_uuid=r.host_uuid, host_name=r.host_name,
        host_role=r.host_role, host_dg=r.host_dg, host_cabinet=r.host_cabinet,
        meeting_date=r.meeting_date, location=r.location, subject=r.subject,
        organisation_met=r.organisation_met,
        transparency_register_id=r.transparency_register_id,
        organisation_type=r.organisation_type,
        representatives=r.representatives, source_url=r.source_url,
        public_url=r.source_url,
        body_txt=body_txt,
        body_html=body_html,
        meeting_start_date=r.meeting_date,
        creation_date=getattr(r, "first_seen", None) or getattr(r, "scraped_at", None) or r.last_updated,
        policy_areas=list(r.policy_areas or []),
        related_celex=list(r.related_celex or []),
        last_updated=r.last_updated,
    )


# ============================================================================
# /rsb-opinions
# ============================================================================


class RSBOpinionItem(BaseModel):
    id: str
    opinion_reference: str
    title: str
    target_initiative: Optional[str] = None
    target_dg: Optional[str] = None
    procedure_ref: Optional[str] = None
    opinion_type: str
    verdict: str
    opinion_date: date
    summary: Optional[str] = None
    pdf_url: Optional[str] = None
    source_url: str
    policy_areas: list = Field(default_factory=list)
    last_updated: Optional[datetime] = None


@rsb_router.get(
    "",
    response_model=PaginatedResponse[RSBOpinionItem],
    summary="Regulatory Scrutiny Board opinions on Commission impact assessments",
    description=(
        "RSB opinions on impact assessments / evaluations / fitness checks. "
        "Source: commission.europa.eu/law/law-making-process/regulatory-scrutiny-board/. "
        "Verdict can be positive | positive_with_reservations | negative."
    ),
)
async def list_rsb_opinions(
    request: Request,
    target_dg: Optional[str] = Query(None),
    procedure_ref: Optional[str] = Query(None),
    verdict: Optional[str] = Query(None, description="positive | positive_with_reservations | negative | unknown"),
    opinion_type: Optional[str] = Query(None, description="impact_assessment | evaluation | fitness_check"),
    q: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[RSBOpinionItem]:
    query = db.query(RSBOpinion)
    filters = []
    if target_dg:
        filters.append(RSBOpinion.target_dg == target_dg.upper())
    if procedure_ref:
        filters.append(RSBOpinion.procedure_ref == procedure_ref)
    if verdict:
        filters.append(RSBOpinion.verdict == verdict.lower())
    if opinion_type:
        filters.append(RSBOpinion.opinion_type == opinion_type)
    if q:
        like = f"%{q}%"
        filters.append(or_(RSBOpinion.title.ilike(like), RSBOpinion.summary.ilike(like)))
    if published_from:
        filters.append(RSBOpinion.opinion_date >= published_from)
    if published_to:
        filters.append(RSBOpinion.opinion_date <= published_to)
    if updated_from:
        filters.append(RSBOpinion.last_updated >= updated_from)
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    rows = (
        query.order_by(RSBOpinion.opinion_date.desc())
        .offset((page - 1) * limit).limit(limit).all()
    )
    data = [
        RSBOpinionItem(
            id=str(r.id), opinion_reference=r.opinion_reference, title=r.title,
            target_initiative=r.target_initiative, target_dg=r.target_dg,
            procedure_ref=r.procedure_ref, opinion_type=r.opinion_type,
            verdict=r.verdict.value if hasattr(r.verdict, "value") else str(r.verdict),
            opinion_date=r.opinion_date, summary=r.summary,
            pdf_url=r.pdf_url, source_url=r.source_url,
            policy_areas=list(r.policy_areas or []),
            last_updated=r.last_updated,
        )
        for r in rows
    ]
    return build_envelope(data, total=total, page=page, limit=limit,
                          published_from=published_from, published_to=published_to,
                          updated_from=updated_from)


@rsb_router.get(
    "/{opinion_reference}",
    response_model=RSBOpinionItem,
    summary="Single RSB opinion by reference",
)
async def get_rsb_detail(
    opinion_reference: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> RSBOpinionItem:
    r = db.query(RSBOpinion).filter(RSBOpinion.opinion_reference == opinion_reference).first()
    if not r:
        raise HTTPException(status_code=404, detail={
            "error": f"RSB opinion {opinion_reference} not found",
            "reason_code": "not_found",
            "resource": "rsb_opinion",
            "id": opinion_reference,
        })
    return RSBOpinionItem(
        id=str(r.id), opinion_reference=r.opinion_reference, title=r.title,
        target_initiative=r.target_initiative, target_dg=r.target_dg,
        procedure_ref=r.procedure_ref, opinion_type=r.opinion_type,
        verdict=r.verdict.value if hasattr(r.verdict, "value") else str(r.verdict),
        opinion_date=r.opinion_date, summary=r.summary,
        pdf_url=r.pdf_url, source_url=r.source_url,
        policy_areas=list(r.policy_areas or []),
        last_updated=r.last_updated,
    )


# ============================================================================
# /delegated-acts + /implementing-acts (shared backing table secondary_acts)
# ============================================================================


class SecondaryActItem(BaseModel):
    id: str
    act_type: str
    reference: str
    title: str
    description: Optional[str] = None
    parent_celex: Optional[str] = None
    parent_procedure_ref: Optional[str] = None
    status: str
    proposing_dg: Optional[str] = None
    publication_date: Optional[date] = None
    objection_deadline: Optional[date] = None
    ep_scrutiny: dict = Field(default_factory=dict)
    council_scrutiny: dict = Field(default_factory=dict)
    celex: Optional[str] = None
    source_url: str
    pdf_url: Optional[str] = None
    policy_areas: list = Field(default_factory=list)
    last_updated: Optional[datetime] = None
    # The 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(
        None,
        description="Canonical citizen URL — EUR-Lex CELEX URL when available, else pdf_url, else source_url.",
    )
    document_date: Optional[date] = Field(
        None,
        description="The act's publication date (same as publication_date, surfaced under the uniform datapoint name).",
    )
    creation_date: Optional[datetime] = Field(
        None,
        description="When Brubru first ingested this row (secondary_acts.first_seen).",
    )
    # Body fields — secondary acts are PDF-sourced (Cellar PDFs of C(YYYY)NNNN
    # delegated/implementing decisions). body_html stays None per the
    # "no PDF→HTML synthesis" rule.
    has_body: bool = False
    body_html: Optional[str] = None
    body_txt: Optional[str] = None
    # Deprecated alias kept one release.
    body: Optional[str] = None


def _secondary_act_to_item(
    r: SecondaryAct,
    body_threshold: int = DEFAULT_HAS_BODY_THRESHOLD,
) -> SecondaryActItem:
    # Prefer the cached HTML body when present (Cellar XHTML manifestation,
    # backfilled by scripts/backfill_secondary_acts_body.py); fall back to
    # composing one from text_body for PDF-only sources.
    cached_html = (r.body_html or "").strip() or None
    if cached_html:
        body_html = cached_html
        body_text = r.text_body
        has_body = bool(body_text and len(body_text) >= body_threshold)
    else:
        body_html, body_text, has_body = body_from_pdf_text(r.text_body, threshold=body_threshold)
    # Derive canonical citizen URL. Preference ladder:
    #   1) EUR-Lex CELEX page when CELEX is known (citizen-friendly canonical).
    #   2) Specific regdel record page (webgate /regdel/#/delegatedActs/<id>).
    #      This lands on the act's scrutiny status / metadata page, NOT the
    #      generic search results.
    #   3) Direct PDF URL.
    #   4) Original scrape URL (often the regdel search URL — fallback only).
    if r.celex:
        public_url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{r.celex}"
    elif getattr(r, "regdel_id", None):
        public_url = f"https://webgate.ec.europa.eu/regdel/#/delegatedActs/{r.regdel_id}?lang=en"
    elif r.pdf_url:
        public_url = r.pdf_url
    else:
        public_url = r.source_url
    return SecondaryActItem(
        id=str(r.id),
        act_type=r.act_type.value if hasattr(r.act_type, "value") else str(r.act_type),
        reference=r.reference, title=r.title, description=r.description,
        parent_celex=r.parent_celex, parent_procedure_ref=r.parent_procedure_ref,
        status=r.status.value if hasattr(r.status, "value") else str(r.status),
        proposing_dg=r.proposing_dg, publication_date=r.publication_date,
        objection_deadline=r.objection_deadline,
        ep_scrutiny=dict(r.ep_scrutiny or {}),
        council_scrutiny=dict(r.council_scrutiny or {}),
        celex=r.celex, source_url=r.source_url, pdf_url=r.pdf_url,
        policy_areas=list(r.policy_areas or []),
        last_updated=r.last_updated,
        # 5 mandatory datapoints
        public_url=public_url,
        document_date=r.publication_date,
        creation_date=getattr(r, "first_seen", None),
        has_body=has_body,
        body_html=body_html,
        body_txt=body_text,
        body=deprecated_body(body_text, body_html),
    )


def _list_secondary_acts(
    db: Session, act_type: str,
    parent_celex, proposing_dg, status, q,
    published_from, published_to, updated_from,
    limit, page,
    body_threshold: int = DEFAULT_HAS_BODY_THRESHOLD,
) -> PaginatedResponse[SecondaryActItem]:
    query = db.query(SecondaryAct).filter(SecondaryAct.act_type == act_type)
    filters = []
    if parent_celex:
        filters.append(SecondaryAct.parent_celex == parent_celex.upper())
    if proposing_dg:
        filters.append(SecondaryAct.proposing_dg == proposing_dg.upper())
    if status:
        filters.append(SecondaryAct.status == status.lower())
    if q:
        filters.append(or_(SecondaryAct.title.ilike(f"%{q}%"), SecondaryAct.description.ilike(f"%{q}%")))
    if published_from:
        filters.append(SecondaryAct.publication_date >= published_from)
    if published_to:
        filters.append(SecondaryAct.publication_date <= published_to)
    if updated_from:
        filters.append(SecondaryAct.last_updated >= updated_from)
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    rows = (
        query.order_by(SecondaryAct.publication_date.desc().nullslast())
        .offset((page - 1) * limit).limit(limit).all()
    )
    data = [_secondary_act_to_item(r, body_threshold=body_threshold) for r in rows]
    return build_envelope(data, total=total, page=page, limit=limit,
                          published_from=published_from, published_to=published_to,
                          updated_from=updated_from)


@delegated_router.get(
    "",
    response_model=PaginatedResponse[SecondaryActItem],
    summary="Commission delegated acts (RegDel register)",
)
async def list_delegated_acts(
    request: Request,
    parent_celex: Optional[str] = Query(None),
    proposing_dg: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[SecondaryActItem]:
    return _list_secondary_acts(db, "delegated", parent_celex, proposing_dg, status, q,
                                published_from, published_to, updated_from, limit, page,
                                body_threshold=body_threshold)


def _secondary_act_detail(
    db: Session, reference: str, expected_type: str,
    body_threshold: int = DEFAULT_HAS_BODY_THRESHOLD,
) -> SecondaryActItem:
    r = db.query(SecondaryAct).filter(SecondaryAct.reference == reference).first()
    if not r:
        raise HTTPException(status_code=404, detail={
            "error": f"Secondary act {reference} not found",
            "reason_code": "not_found",
            "resource": expected_type,
            "id": reference,
        })
    return _secondary_act_to_item(r, body_threshold=body_threshold)


@delegated_router.get(
    "/{reference:path}",
    response_model=SecondaryActItem,
    summary="Single delegated act by reference (e.g. C(2026)1234)",
)
async def get_delegated_detail(
    reference: str,
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> SecondaryActItem:
    return _secondary_act_detail(db, reference, "delegated_act", body_threshold=body_threshold)


@implementing_router.get(
    "/{reference:path}",
    response_model=SecondaryActItem,
    summary="Single implementing act by reference (e.g. C(2026)0234)",
)
async def get_implementing_detail(
    reference: str,
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> SecondaryActItem:
    return _secondary_act_detail(db, reference, "implementing_act", body_threshold=body_threshold)


@implementing_router.get(
    "",
    response_model=PaginatedResponse[SecondaryActItem],
    summary="Commission implementing acts (comitology register)",
)
async def list_implementing_acts(
    request: Request,
    parent_celex: Optional[str] = Query(None),
    proposing_dg: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[SecondaryActItem]:
    return _list_secondary_acts(db, "implementing", parent_celex, proposing_dg, status, q,
                                published_from, published_to, updated_from, limit, page,
                                body_threshold=body_threshold)


# ============================================================================
# /tris-notifications
# ============================================================================


class TRISNotificationItem(BaseModel):
    id: str
    notification_number: str
    notifying_country: str
    title: str
    short_summary: Optional[str] = None
    full_text_summary: Optional[str] = None
    notification_date: date
    standstill_until: Optional[date] = None
    sector: Optional[str] = None
    products_or_services: Optional[str] = None
    main_content: Optional[str] = None
    commission_observations_url: Optional[str] = None
    member_state_observations: list = Field(default_factory=list)
    detailed_opinions: list = Field(default_factory=list)
    source_url: str
    pdf_url: Optional[str] = None
    policy_areas: list = Field(default_factory=list)
    related_celex: list = Field(default_factory=list)
    last_updated: Optional[datetime] = None
    # Body fields composed from main_content + full_text_summary +
    # short_summary (sections of the TRIS notification text). HTML-source
    # composer wraps each populated field as a labelled section.
    has_body: bool = False
    body_html: Optional[str] = None
    body_txt: Optional[str] = None


def _tris_to_item(r, body_threshold: int = DEFAULT_HAS_BODY_THRESHOLD) -> TRISNotificationItem:
    from ._body import compose_html_from_sections
    body_html, body_text, has_body = compose_html_from_sections([
        ("Main content", r.main_content),
        ("Full text summary", r.full_text_summary),
        ("Short summary", r.short_summary),
    ], threshold=body_threshold)
    return TRISNotificationItem(
        id=str(r.id), notification_number=r.notification_number,
        notifying_country=r.notifying_country, title=r.title,
        short_summary=r.short_summary, full_text_summary=r.full_text_summary,
        notification_date=r.notification_date,
        standstill_until=r.standstill_until,
        sector=r.sector, products_or_services=r.products_or_services,
        main_content=r.main_content,
        commission_observations_url=r.commission_observations_url,
        member_state_observations=list(r.member_state_observations or []),
        detailed_opinions=list(r.detailed_opinions or []),
        source_url=r.source_url, pdf_url=r.pdf_url,
        policy_areas=list(r.policy_areas or []),
        related_celex=list(r.related_celex or []),
        last_updated=r.last_updated,
        has_body=has_body, body_html=body_html, body_txt=body_text,
    )


@tris_router.get(
    "",
    response_model=PaginatedResponse[TRISNotificationItem],
    summary="TRIS notifications (Member State technical regulations)",
    description=(
        "Member State notifications under Directive 2015/1535 of national "
        "technical regulations affecting the Single Market. Source: "
        "technical-regulation-information-system.ec.europa.eu/. Critical for "
        "anyone tracking single-market barriers in member states."
    ),
)
async def list_tris_notifications(
    request: Request,
    notifying_country: Optional[str] = Query(None, description="ISO-3166-1 alpha-2, e.g. FR"),
    sector: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[TRISNotificationItem]:
    query = db.query(TRISNotification)
    filters = []
    if notifying_country:
        filters.append(TRISNotification.notifying_country == notifying_country.upper())
    if sector:
        filters.append(TRISNotification.sector.ilike(f"%{sector}%"))
    if q:
        like = f"%{q}%"
        filters.append(or_(
            TRISNotification.title.ilike(like),
            TRISNotification.short_summary.ilike(like),
            TRISNotification.main_content.ilike(like),
        ))
    if published_from:
        filters.append(TRISNotification.notification_date >= published_from)
    if published_to:
        filters.append(TRISNotification.notification_date <= published_to)
    if updated_from:
        filters.append(TRISNotification.last_updated >= updated_from)
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    rows = (
        query.order_by(TRISNotification.notification_date.desc())
        .offset((page - 1) * limit).limit(limit).all()
    )
    data = [_tris_to_item(r, body_threshold=body_threshold) for r in rows]
    return build_envelope(data, total=total, page=page, limit=limit,
                          published_from=published_from, published_to=published_to,
                          updated_from=updated_from)


@tris_router.get(
    "/{notification_number:path}",
    response_model=TRISNotificationItem,
    summary="Single TRIS notification by number (e.g. 2026/0123/FR)",
)
async def get_tris_detail(
    notification_number: str,
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> TRISNotificationItem:
    r = db.query(TRISNotification).filter(TRISNotification.notification_number == notification_number).first()
    if not r:
        raise HTTPException(status_code=404, detail={
            "error": f"TRIS notification {notification_number} not found",
            "reason_code": "not_found",
            "resource": "tris_notification",
            "id": notification_number,
        })
    return _tris_to_item(r, body_threshold=body_threshold)
