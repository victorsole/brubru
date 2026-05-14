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
    summary="European Parliament questions to Commission, Council or ECB — with answers",
    description="""**What it does**
Returns parliamentary questions submitted by MEPs to the Commission, Council, or ECB — written questions, oral questions, priority questions, and Question Time. Each row includes the original question text, the answering institution's reply when published, the asking MEPs, the answering commissioner (when applicable), related procedure/CELEX cross-references, and the canonical citizen URL on doceo.

**When to use it**
To track what MEPs are asking on a given policy area, find the official Commission position on an emerging topic before formal legislation drops, or build a "what's been asked about X" timeline. The `procedure_ref` filter lets you scope to questions related to a specific legislative file.

**Input**
- `q` — substring search on subject + question text + answer text.
- `question_type` — `written` / `oral` / `priority` / `question_time`.
- `parliamentary_term` — integer (current: 10).
- `asking_mep_id` — filter to questions asked by a specific MEP.
- `answering_institution` — `COMMISSION` / `COUNCIL` / `ECB`.
- `procedure_ref` — OEIL reference (e.g. `2026/0419(COD)`).
- `committee` — 4-letter committee code (e.g. `ENVI`).
- `published_from`, `published_to` — date filter on `submitted_date`.
- `updated_from` — incremental sync (rows where `last_updated >= value`).
- `limit` (default 50, max 100), `page` (1-indexed).

**Try it**
```
GET /api/v1/parliamentary-questions?q=AI%20Act&limit=10
GET /api/v1/parliamentary-questions?committee=ENVI&published_from=2026-01-01
```

**You get back**
A `PaginatedResponse[ParliamentaryQuestionItem]` envelope. Each item carries `question_reference` (e.g. `E-001234/2026`), `question_type`, `subject`, `text_question`, `text_answer`, dates, asking-MEP arrays, `procedure_ref`, `related_celex`, `policy_areas`, `source_url`, `answer_url`, `body_txt` + `body_html` (semantic article with Question + Answer sections), plus the 5 envelope-level datapoints.

**Data freshness**
Synced once per day at 04:00 UTC (daily tier) from europarl.europa.eu/plenary/en/parliamentary-questions.html. New questions appear on doceo within hours of being tabled; answers can take days to weeks (Commission has up to 6 weeks under Rule 138). Scraper queued; endpoint returns empty result until ingestion completes.""",
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
    summary="Look up one parliamentary question by its reference (e.g. E-001234/2026)",
    description="""**What it does**
Fetches a single parliamentary question by its reference. Returns the same shape as the list endpoint, including the original question text, the official answer when published, and the citizen URL on doceo.

**When to use it**
After locating a question via the list endpoint, use this to get the full text + answer in a deeper-link context (e.g. embedding in a chat response). Common pattern: `q` search → pick a reference → fetch detail.

**Input**
- `question_reference` (path) — e.g. `E-001234/2026` for a written question or `O-000123/2026` for an oral question. Format: `<TYPE>-<NUMBER>/<YEAR>` where TYPE ∈ {E, O, P, QT}.

**Try it**
```
GET /api/v1/parliamentary-questions/E-001234/2026
```

**You get back**
A single `ParliamentaryQuestionItem` (same shape as the list endpoint's `data[i]`), or HTTP 404 with `reason_code: not_found` if no question with that reference exists in our mirror.

**Data freshness**
Same as the list endpoint — daily 04:00 UTC sync from europarl.europa.eu. If a question exists on doceo but not in our DB, it means it hasn't been picked up by the latest sync yet (max ~24h lag).""",
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
    summary="Commission officials' meetings with interest representatives (Transparency Initiative)",
    description="""**What it does**
Returns the meetings between Commission officials (Commissioners, Heads of Cabinet, Directors-General) and external interest representatives — lobbyists, NGOs, trade bodies, member-state representatives — as published under the Transparency Initiative. Each row carries the host (UUID + name + role + DG/cabinet), the meeting date + location + subject, the organisation met, its Transparency Register ID, the participating representatives, and policy-area + related-CELEX tags.

**When to use it**
To audit who lobbied which Commissioner on a given topic, build a "meetings on Topic X" view for an advocacy campaign, or cross-reference a known lobbyist against the meetings register. Combined with `/api/v1/specialised/transparency-register`, it lets you trace lobbying activity end-to-end (who is registered → who they met → what was discussed).

**Input**
- `host_uuid` — filter to a specific Commissioner/Cabinet host (UUID from commission.europa.eu).
- `host_dg` — filter to a specific DG (e.g. `COMP`, `CLIMA`).
- `organisation_met` — substring match on the organisation name (e.g. `Microsoft`).
- `transparency_register_id` — filter to a specific registered entity.
- `q` — substring search on the meeting subject.
- `published_from`, `published_to` — date filter on `meeting_date`.
- `updated_from` — incremental sync.
- `limit` (default 50, max 100), `page` (1-indexed).

**Try it**
```
GET /api/v1/meetings?host_dg=COMP&q=AI
GET /api/v1/meetings?organisation_met=BusinessEurope&limit=20
```

**You get back**
A `PaginatedResponse[TransparencyMeetingItem]` envelope. Each item carries `host_uuid`, `host_name`, `host_role`, `host_dg`, `host_cabinet`, `meeting_date`, `location`, `subject`, `organisation_met`, `transparency_register_id`, `organisation_type`, `representatives` (array of names), `source_url`, `policy_areas`, `related_celex`, plus a composed `body_txt`/`body_html` (subject + participants + organisation) and the 5 envelope-level datapoints.

**Data freshness**
Synced once per day at 04:00 UTC (daily tier) from ec.europa.eu/transparencyinitiative/meetings/. Cabinet officials are required to publish meetings within ~2 weeks; daily sync catches them inside that window. Seed host UUIDs: ca175ad3... (President), a2c7c963... (Ribera), 9fd4662a... (Hoekstra).""",
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
    summary="Look up one Transparency Initiative meeting by its internal UUID",
    description="""**What it does**
Fetches a single Transparency Initiative meeting record by its Brubru-internal UUID. Returns the same shape as the list endpoint.

**When to use it**
After locating a meeting via the list endpoint, use this to deep-link into a specific record (e.g. embedded in an advocacy report or a chat answer).

**Input**
- `meeting_id` (path) — Brubru UUID of the meeting (returned in `id` from the list endpoint).

**Try it**
```
GET /api/v1/meetings/<uuid>
```

**You get back**
A single `TransparencyMeetingItem` (same shape as the list endpoint's `data[i]`), or HTTP 404 with `reason_code: not_found` if no meeting with that UUID exists.

**Data freshness**
Same as the list endpoint — daily 04:00 UTC sync from ec.europa.eu/transparencyinitiative/meetings/.""",
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
    summary="Regulatory Scrutiny Board opinions on Commission impact assessments + evaluations",
    description="""**What it does**
Returns opinions of the Regulatory Scrutiny Board — the independent body within the Commission that scrutinises impact assessments, evaluations, and fitness checks before they're submitted to the College. Each opinion carries the target initiative (the proposed regulation being assessed), the target DG, the procedure reference, the opinion type (`impact_assessment` / `evaluation` / `fitness_check`), and the verdict (`positive` / `positive_with_reservations` / `negative`).

**When to use it**
A negative RSB opinion is a red flag that a forthcoming proposal has methodological gaps — often a leading indicator that the College will delay adoption, send the file back for re-work, or amend the impact assessment. Use this endpoint to monitor RSB output on the policy files you care about, or to filter for "all negative opinions on environment files in 2026" as a quality signal.

**Input**
- `target_dg` — DG code (e.g. `CLIMA`, `ENVI`).
- `procedure_ref` — OEIL reference.
- `verdict` — `positive` / `positive_with_reservations` / `negative` / `unknown`.
- `opinion_type` — `impact_assessment` / `evaluation` / `fitness_check`.
- `q` — substring search on title + summary.
- `published_from`, `published_to` — date filter on `opinion_date`.
- `updated_from` — incremental sync.
- `limit` (default 50, max 100), `page` (1-indexed).

**Try it**
```
GET /api/v1/rsb-opinions?verdict=negative&target_dg=CLIMA
GET /api/v1/rsb-opinions?q=AI%20Act
```

**You get back**
A `PaginatedResponse[RSBOpinionItem]` envelope. Each item carries `opinion_reference`, `title`, `target_initiative`, `target_dg`, `procedure_ref`, `opinion_type`, `verdict`, `opinion_date`, `summary`, `pdf_url`, `source_url`, `policy_areas`, `last_updated`.

**Data freshness**
Synced once per week (Sunday 05:00 UTC, weekly tier) from commission.europa.eu/law/law-making-process/regulatory-scrutiny-board/. RSB publishes a handful of opinions per month; weekly sync is appropriate. Scraper queued; endpoint returns empty until ingestion completes.""",
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
    summary="Look up one Regulatory Scrutiny Board opinion by its reference",
    description="""**What it does**
Fetches a single RSB opinion by its reference. Returns the same shape as the list endpoint.

**When to use it**
After locating an RSB opinion via the list endpoint, use this to deep-link into a specific record. Common pattern: list with `verdict=negative` to surface red-flag opinions, then drill into each one.

**Input**
- `opinion_reference` (path) — the RSB opinion reference (format varies; check the list endpoint for examples in the current data).

**Try it**
```
GET /api/v1/rsb-opinions/<reference>
```

**You get back**
A single `RSBOpinionItem` (same shape as the list endpoint's `data[i]`), or HTTP 404 with `reason_code: not_found`.

**Data freshness**
Same as the list endpoint — weekly Sunday 05:00 UTC sync from commission.europa.eu/law/law-making-process/regulatory-scrutiny-board/.""",
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
    # Tier-2 fallback: draft delegated/implementing acts that haven't been
    # published in OJ yet (no CELEX, no text_body) — compose a structured
    # metadata body so the contract never returns empty.
    if not body_text:
        import html as _html
        title = r.title or r.reference or "(untitled delegated act)"
        lines = [title]
        parts_html = [f"<h2>{_html.escape(title)}</h2>"]
        for k, v in [
            ("Reference", r.reference),
            ("Type", r.act_type.value if hasattr(r.act_type, "value") else r.act_type),
            ("Status", r.status.value if hasattr(r.status, "value") else r.status),
            ("Parent CELEX", r.parent_celex),
            ("Parent procedure", r.parent_procedure_ref),
            ("Proposing DG", r.proposing_dg),
            ("Published", r.publication_date),
            ("Objection deadline", r.objection_deadline),
            ("Policy areas", ", ".join(r.policy_areas or []) or None),
        ]:
            if v in (None, ""):
                continue
            lines.append(f"{k}: {v}")
            parts_html.append(f"<p><strong>{_html.escape(k)}:</strong> {_html.escape(str(v))}</p>")
        if r.description:
            lines.append(r.description[:1000])
            parts_html.append(f"<p>{_html.escape(r.description[:1000])}</p>")
        body_text = "\n".join(lines)
        body_html = "<article>" + "".join(parts_html) + "</article>"
    # Derive canonical citizen URL. Preference ladder:
    #   1) EUR-Lex CELEX page when CELEX is known (citizen-friendly canonical).
    #   2) Specific regdel record page (webgate /regdel/#/delegatedActs/<id>).
    #      Lands on the act's scrutiny status / metadata page.
    #   3) Direct PDF URL — only if it's NOT a Cellar /resource/celex/ URL
    #      whose CELEX has been nulled (those 404). Same for source_url.
    #   4) Last resort: EUR-Lex search-by-reference (always 200; lets the
    #      citizen find the act once Cellar has indexed it).
    def _is_dead_celex_url(u: str) -> bool:
        return bool(u) and (
            "eur-lex.europa.eu/legal-content/" in u and "CELEX:" in u
            or "publications.europa.eu/resource/celex/" in u
        )

    if r.celex:
        public_url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{r.celex}"
    elif getattr(r, "regdel_id", None):
        public_url = f"https://webgate.ec.europa.eu/regdel/#/delegatedActs/{r.regdel_id}?lang=en"
    elif r.pdf_url and not _is_dead_celex_url(r.pdf_url):
        public_url = r.pdf_url
    elif r.source_url and not _is_dead_celex_url(r.source_url):
        public_url = r.source_url
    else:
        # Search EUR-Lex by the C-number reference (e.g. C(2026)1567). The
        # search page always loads; if Cellar has indexed the act by the
        # time the citizen clicks, the top hit is the published regulation.
        from urllib.parse import quote
        public_url = (
            f"https://eur-lex.europa.eu/search.html?text={quote(r.reference or r.title or '')}"
            if (r.reference or r.title) else None
        )
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
    summary="Commission delegated acts — secondary legislation under Article 290 TFEU",
    description="""**What it does**
Returns Commission delegated acts — secondary legislation adopted by the Commission under powers delegated by a basic legislative act (Article 290 TFEU). Each row carries the act reference (e.g. `C(2026)1234`), the parent CELEX (the basic act granting the delegation), the parent procedure reference, the status, the proposing DG, the publication date, the EP/Council objection deadline (typically 2-3 months), the EP scrutiny status, the Council scrutiny status, the CELEX if adopted, plus body text + the 5 envelope-level datapoints.

**When to use it**
To monitor secondary legislation flowing from a flagship regulation (e.g. all delegated acts under the AI Act), track the EP/Council objection window for delegated acts you might want to scrutinise, or audit which DGs are most active in delegated-act production. The `parent_celex` filter scopes to a specific parent act.

**Input**
- `parent_celex` — CELEX of the parent (basic) act granting the delegation (e.g. `32024R1689` for AI Act).
- `proposing_dg` — DG code.
- `status` — `proposed` / `scrutiny` / `adopted` / `objected` / `withdrawn` (status enum).
- `q` — substring search on title + description.
- `published_from`, `published_to` — date filter on `publication_date`.
- `updated_from` — incremental sync.
- `limit` (default 50, max 100), `page` (1-indexed).

**Try it**
```
GET /api/v1/delegated-acts?parent_celex=32024R1689&limit=20
GET /api/v1/delegated-acts?proposing_dg=CNECT&status=scrutiny
```

**You get back**
A `PaginatedResponse[SecondaryActItem]` envelope. Each item carries `reference`, `title`, `description`, `parent_celex`, `parent_procedure_ref`, `status`, `proposing_dg`, `publication_date`, `objection_deadline`, `ep_scrutiny` (dict with EP rapporteur / motion status), `council_scrutiny` (dict), `celex` (if adopted), `source_url`, `pdf_url`, `policy_areas`, body fields, and the 5 envelope-level datapoints.

**Data freshness**
Synced once per day at 04:00 UTC (daily tier) from the RegDel register + EUR-Lex C-series. New delegated acts appear on a steady drumbeat; daily sync catches them. Backed by `backend/scripts/backfill_eu_comitology.py`.""",
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
    summary="Look up one delegated act by its Commission reference (e.g. C(2026)1234)",
    description="""**What it does**
Fetches a single delegated act by its Commission reference. Returns the same shape as the list endpoint, with body text composed from the publication PDF when ingested.

**When to use it**
After locating a delegated act via the list endpoint, use this to fetch the full record (including body text + scrutiny details) in a deeper-link context.

**Input**
- `reference` (path) — the Commission reference, format `C(YYYY)NNNN`. The `:path` matcher means the parentheses are accepted verbatim — no URL-encoding needed.

**Try it**
```
GET /api/v1/delegated-acts/C(2026)1234
```

**You get back**
A single `SecondaryActItem` (same shape as the list endpoint's `data[i]`), or HTTP 404 with `reason_code: not_found`.

**Data freshness**
Same as the list endpoint — daily 04:00 UTC sync from the RegDel register + EUR-Lex C-series.""",
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
    summary="Look up one implementing act by its Commission reference (e.g. C(2026)0234)",
    description="""**What it does**
Fetches a single Commission implementing act by its reference. Implementing acts (Article 291 TFEU) lay down uniform conditions for the implementation of EU legislation across Member States. Returns the same shape as the list endpoint, with body text composed from the publication PDF when ingested.

**When to use it**
After locating an implementing act via the list endpoint, use this to fetch the full record in a deeper-link context. Note: the difference between delegated acts (Art. 290, modify or supplement the basic act) and implementing acts (Art. 291, uniform implementation) is constitutionally significant for legal-affairs work.

**Input**
- `reference` (path) — the Commission reference, format `C(YYYY)NNNN`. Path-matching accepts parentheses verbatim.

**Try it**
```
GET /api/v1/implementing-acts/C(2026)0234
```

**You get back**
A single `SecondaryActItem` (same shape as the list endpoint's `data[i]`), or HTTP 404 with `reason_code: not_found`.

**Data freshness**
Same as the list endpoint — daily 04:00 UTC sync from the Comitology Register + EUR-Lex C-series.""",
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
    summary="Commission implementing acts — uniform implementation of EU law (Article 291 TFEU)",
    description="""**What it does**
Returns Commission implementing acts — secondary legislation adopted by the Commission under Article 291 TFEU to ensure uniform conditions for implementation of EU law (typically with a comitology committee opinion). Each row carries the act reference (e.g. `C(2026)0234`), the parent CELEX, the parent procedure reference, the status, the proposing DG, the publication date, the comitology examination/advisory procedure outcome, the CELEX if adopted, plus body text + the 5 envelope-level datapoints.

**When to use it**
To monitor secondary legislation flowing from a flagship regulation (e.g. all implementing acts under MDR, REACH, CRR), track comitology committee outcomes (e.g. SCoPAFF votes on pesticides), or audit which DGs are most active in implementing-act production. The `parent_celex` filter scopes to a specific parent act.

**Input**
- `parent_celex` — CELEX of the parent (basic) act (e.g. `32016R0679` for GDPR).
- `proposing_dg` — DG code.
- `status` — implementing-act status enum.
- `q` — substring search on title + description.
- `published_from`, `published_to` — date filter on `publication_date`.
- `updated_from` — incremental sync.
- `limit` (default 50, max 100), `page` (1-indexed).

**Try it**
```
GET /api/v1/implementing-acts?proposing_dg=SANTE&q=glyphosate
GET /api/v1/implementing-acts?parent_celex=32016R0679&limit=20
```

**You get back**
A `PaginatedResponse[SecondaryActItem]` envelope. Each item carries `reference`, `title`, `description`, `parent_celex`, `parent_procedure_ref`, `status`, `proposing_dg`, `publication_date`, `ep_scrutiny`, `council_scrutiny`, `celex`, `source_url`, `pdf_url`, `policy_areas`, body fields, and the 5 envelope-level datapoints.

**Data freshness**
Synced once per day at 04:00 UTC (daily tier) from the Comitology Register + EUR-Lex C-series.""",
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
    # The 5 mandatory Brubru v1 datapoints. TRIS source_url is the canonical
    # citizen URL (technical-regulation-information-system.ec.europa.eu); when
    # all the source text fields are null the body composer falls back to a
    # title + country + notification-date + sector composition.
    public_url: Optional[str] = Field(None, description="Canonical citizen URL — TRIS notification page (source_url).")
    document_date: Optional[date] = Field(None, description="Notification date (alias of notification_date).")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested this row (alias of last_updated).")


def _tris_to_item(r, body_threshold: int = DEFAULT_HAS_BODY_THRESHOLD) -> TRISNotificationItem:
    from ._body import compose_html_from_sections
    body_html, body_text, has_body = compose_html_from_sections([
        ("Main content", r.main_content),
        ("Full text summary", r.full_text_summary),
        ("Short summary", r.short_summary),
    ], threshold=body_threshold)
    # Tier-2 fallback when source text is all null — at least surface the
    # structured row so partners see a meaningful body.
    if not body_text:
        import html as _html
        lines_txt = [r.title or "?"]
        parts_html = [f"<h2>{_html.escape(r.title or '?')}</h2>"]
        kv = []
        if r.notification_number: kv.append(("Notification", r.notification_number))
        if r.notifying_country: kv.append(("Country", r.notifying_country))
        if r.notification_date: kv.append(("Notified", str(r.notification_date)))
        if r.standstill_until: kv.append(("Standstill until", str(r.standstill_until)))
        if r.sector: kv.append(("Sector", r.sector))
        if r.products_or_services: kv.append(("Products / services", r.products_or_services))
        for k, v in kv:
            lines_txt.append(f"{k}: {v}")
            parts_html.append(f"<p><strong>{_html.escape(k)}:</strong> {_html.escape(str(v))}</p>")
        body_text = "\n".join(lines_txt) if lines_txt else None
        body_html = "<article>" + "".join(parts_html) + "</article>" if parts_html else None
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
        # 5 mandatory datapoints
        public_url=r.source_url or r.pdf_url,
        document_date=r.notification_date,
        creation_date=r.last_updated,
    )


@tris_router.get(
    "",
    response_model=PaginatedResponse[TRISNotificationItem],
    summary="Member State notifications of national technical regulations (TRIS, Directive 2015/1535)",
    description="""**What it does**
Returns notifications submitted by EU Member States under Directive 2015/1535 — the obligation to notify the Commission of draft national technical regulations that could create barriers to the Single Market (in goods and information-society services). Each row carries the notification reference (e.g. `2026/0123/FR`), the notifying country, the sector, the title + short summary + main content, the standstill period, and the Commission's reaction (detailed opinion / comment / no-reaction).

**When to use it**
Critical for anyone tracking single-market barriers — a French draft law on packaging waste, a German tax on plastic bags, a Polish ban on a specific chemical — all surface here BEFORE they become national law. The 3-month standstill window gives industry and other Member States time to flag incompatibilities. Trade associations, single-market advocates, and product-compliance teams should monitor this continuously.

**Input**
- `notifying_country` — ISO-3166-1 alpha-2 (e.g. `FR`, `DE`).
- `sector` — TRIS sector code (substring).
- `q` — substring search on title + short summary + main content.
- `published_from`, `published_to` — date filter on `notification_date`.
- `updated_from` — incremental sync.
- `limit` (default 50, max 100), `page` (1-indexed).

**Try it**
```
GET /api/v1/tris-notifications?notifying_country=FR&q=packaging
GET /api/v1/tris-notifications?sector=N40&published_from=2026-01-01
```

**You get back**
A `PaginatedResponse[TRISNotificationItem]` envelope. Each item carries `notification_number`, `notifying_country`, `sector`, `title`, `short_summary`, `main_content`, `notification_date`, `standstill_period`, `commission_reaction`, `source_url`, `pdf_url`, `policy_areas`, `related_celex`, body fields, and the 5 envelope-level datapoints.

**Data freshness**
Synced once per day at 04:00 UTC (daily tier) from technical-regulation-information-system.ec.europa.eu/. Member States submit notifications throughout the day; daily sync catches them. Backed by `services/scrapers/dg_grow/dg_grow_sync_service.py::sync_tris()`.""",
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
    summary="Look up one TRIS notification by its number (e.g. 2026/0123/FR)",
    description="""**What it does**
Fetches a single TRIS notification by its reference. Returns the same shape as the list endpoint.

**When to use it**
After locating a TRIS notification via the list endpoint, use this to fetch the full record (including the main content of the draft national regulation) in a deeper-link context — useful for compliance teams analysing whether a specific national draft impacts their product.

**Input**
- `notification_number` (path) — the TRIS reference, format `YYYY/NNNN/CC` where CC is the ISO country code (e.g. `2026/0123/FR`).

**Try it**
```
GET /api/v1/tris-notifications/2026/0123/FR
```

**You get back**
A single `TRISNotificationItem` (same shape as the list endpoint's `data[i]`), or HTTP 404 with `reason_code: not_found`.

**Data freshness**
Same as the list endpoint — daily 04:00 UTC sync from TRIS.""",
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
