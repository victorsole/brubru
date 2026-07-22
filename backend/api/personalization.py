"""
Personalization API

Endpoints for personalised experiences such as greeting generation. The
greeting now ships with 0 to 2 policy hooks: short, clickable chips that
turn the empty chat state into a proactive opener.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc, text
from sqlalchemy.orm import Session

from api.auth import get_current_user
from core.database import get_db
from models.daily_brief import DailyBrief
from models.user import User
from services.personalization.greeting_service import (
    compose_hooks_from_brief_headlines,
    compose_hooks_from_briefings,
    generate_personalized_greeting,
    resolve_greeting_language,
)


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/personalization", tags=["personalization"])


class PolicyHook(BaseModel):
    label: str
    spoken: str
    suggested_query: str
    source: str


class GreetingResponse(BaseModel):
    message: str
    metadata: Dict[str, str]
    policy_hooks: List[PolicyHook] = []


# Localised fragments for the welcome-back recap, in Brubru's 6 languages.
# Keys: today / yesterday anchors, weekday names (Mon..Sun), month names
# (Jan..Dec, with the preposition where the language needs one), sentence
# templates, and carriage-status labels.
_RECAP_I18N = {
    "en": {
        "today": "earlier today", "yesterday": "yesterday",
        "weekdays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "months": ["January", "February", "March", "April", "May", "June", "July",
                   "August", "September", "October", "November", "December"],
        "date_fmt": "{day} {month}",
        "single": "Since {anchor}: your file '{title}' moved to {status}.",
        "multi": "Since {anchor}: {n} of your tracked files moved. {titles}.",
        "status": {},
    },
    "ca": {
        "today": "avui mateix", "yesterday": "ahir",
        "weekdays": ["dilluns", "dimarts", "dimecres", "dijous", "divendres", "dissabte", "diumenge"],
        "months": ["de gener", "de febrer", "de març", "d'abril", "de maig", "de juny", "de juliol",
                   "d'agost", "de setembre", "d'octubre", "de novembre", "de desembre"],
        "date_fmt": "el {day} {month}",
        "single": "Des de {anchor}: el teu expedient '{title}' ha passat a {status}.",
        "multi": "Des de {anchor}: {n} dels expedients que segueixes s'han mogut. {titles}.",
        "status": {
            "announced": "anunciat", "tabled": "presentat", "in committee": "en comissió",
            "close to adoption": "a prop de l'adopció", "adopted": "adoptat",
            "completed": "completat", "rejected": "rebutjat", "withdrawn": "retirat",
        },
    },
    "es": {
        "today": "hoy mismo", "yesterday": "ayer",
        "weekdays": ["el lunes", "el martes", "el miércoles", "el jueves", "el viernes", "el sábado", "el domingo"],
        "months": ["de enero", "de febrero", "de marzo", "de abril", "de mayo", "de junio", "de julio",
                   "de agosto", "de septiembre", "de octubre", "de noviembre", "de diciembre"],
        "date_fmt": "el {day} {month}",
        "single": "Desde {anchor}: tu expediente '{title}' ha pasado a {status}.",
        "multi": "Desde {anchor}: {n} de los expedientes que sigues se han movido. {titles}.",
        "status": {
            "announced": "anunciado", "tabled": "presentado", "in committee": "en comisión",
            "close to adoption": "cerca de la adopción", "adopted": "adoptado",
            "completed": "completado", "rejected": "rechazado", "withdrawn": "retirado",
        },
    },
    "fr": {
        "today": "plus tôt aujourd'hui", "yesterday": "hier",
        "weekdays": ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
        "months": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
                   "août", "septembre", "octobre", "novembre", "décembre"],
        "date_fmt": "le {day} {month}",
        "single": "Depuis {anchor} : votre dossier '{title}' est passé à {status}.",
        "multi": "Depuis {anchor} : {n} de vos dossiers suivis ont évolué. {titles}.",
        "status": {
            "announced": "annoncé", "tabled": "déposé", "in committee": "en commission",
            "close to adoption": "proche de l'adoption", "adopted": "adopté",
            "completed": "clos", "rejected": "rejeté", "withdrawn": "retiré",
        },
    },
    "it": {
        "today": "oggi stesso", "yesterday": "ieri",
        "weekdays": ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"],
        "months": ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
                   "agosto", "settembre", "ottobre", "novembre", "dicembre"],
        "date_fmt": "il {day} {month}",
        "single": "Da {anchor}: il tuo fascicolo '{title}' è passato a {status}.",
        "multi": "Da {anchor}: {n} dei fascicoli che segui si sono mossi. {titles}.",
        "status": {
            "announced": "annunciato", "tabled": "presentato", "in committee": "in commissione",
            "close to adoption": "vicino all'adozione", "adopted": "adottato",
            "completed": "completato", "rejected": "respinto", "withdrawn": "ritirato",
        },
    },
    "nl": {
        "today": "eerder vandaag", "yesterday": "gisteren",
        "weekdays": ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"],
        "months": ["januari", "februari", "maart", "april", "mei", "juni", "juli",
                   "augustus", "september", "oktober", "november", "december"],
        "date_fmt": "{day} {month}",
        "single": "Sinds {anchor}: je dossier '{title}' is nu {status}.",
        "multi": "Sinds {anchor}: {n} van je gevolgde dossiers zijn in beweging. {titles}.",
        "status": {
            "announced": "aangekondigd", "tabled": "ingediend", "in committee": "in de commissie",
            "close to adoption": "dicht bij vaststelling", "adopted": "vastgesteld",
            "completed": "afgerond", "rejected": "verworpen", "withdrawn": "ingetrokken",
        },
    },
}


def _compose_welcome_back_recap(
    db: Session, user: User, previous_last_login: datetime
) -> Optional[str]:
    """
    Build a "since we last spoke" portfolio diff for the welcome-back tail,
    in the user's profile language (falls back to English).

    Reads status changes on the user's tracked carriages between
    previous_last_login and now. Returns a short spoken sentence or None
    when there is nothing portfolio-specific to say.
    """
    if not user or not previous_last_login:
        return None
    try:
        rows = db.execute(
            text(
                """
                SELECT lc.title, h.status, h.changed_at
                FROM user_carriage_tracks uct
                JOIN legislative_carriages lc ON lc.id = uct.carriage_id
                JOIN carriage_status_history h ON h.carriage_id = lc.id
                WHERE uct.user_id = :uid
                  AND h.changed_at > :since
                ORDER BY h.changed_at DESC
                LIMIT 3
                """
            ),
            {"uid": str(user.id), "since": previous_last_login},
        ).mappings().all()
    except Exception as exc:
        logger.warning("welcome-back recap query failed: %s", exc)
        db.rollback()
        return None

    if not rows:
        return None

    lang = resolve_greeting_language(getattr(user, "language", None))
    L = _RECAP_I18N.get(lang, _RECAP_I18N["en"])

    # Format the gap as a relative time anchor ("since Friday" / "des de
    # divendres", "since 14 May" / "des del 14 de maig") in the user's language.
    now = datetime.now(previous_last_login.tzinfo) if previous_last_login.tzinfo else datetime.utcnow()
    gap_days = (now - previous_last_login).days
    if gap_days <= 0:
        anchor = L["today"]
    elif gap_days == 1:
        anchor = L["yesterday"]
    elif gap_days < 7:
        anchor = L["weekdays"][previous_last_login.weekday()]
    else:
        anchor = L["date_fmt"].format(
            day=previous_last_login.day,
            month=L["months"][previous_last_login.month - 1],
        )

    if len(rows) == 1:
        r = rows[0]
        status_en = str(r["status"]).replace("_", " ").lower()
        status_label = L["status"].get(status_en, status_en)
        return L["single"].format(anchor=anchor, title=r["title"], status=status_label)
    titles = "; ".join(r["title"] for r in rows[:3])
    return L["multi"].format(anchor=anchor, n=len(rows), titles=titles)


def _latest_onboarding_policy_area(db: Session, pre_user_id: str) -> Optional[Dict[str, str]]:
    """
    Look up the policy area the pre-user picked in onboarding Q1.

    Returns {"slug": ..., "label": ...} or None if the user has not
    answered Q1 yet. The event is fired by the InlineOnboardingTour
    component in chat.
    """
    if not pre_user_id:
        return None
    try:
        row = db.execute(
            text(
                """
                SELECT event_metadata
                FROM pre_user_events
                WHERE pre_user_id = :pid
                  AND event_type = 'onboarding_interest_chosen'
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"pid": pre_user_id},
        ).first()
    except Exception as exc:
        logger.warning("onboarding lookup failed: %s", exc)
        db.rollback()
        return None
    if not row or not row[0]:
        return None
    meta = row[0]
    if not isinstance(meta, dict):
        return None
    slug = meta.get("slug")
    label = meta.get("label")
    if not slug or not label:
        return None
    return {"slug": str(slug), "label": str(label)}


def _recent_brief_headlines(db: Session, limit: int = 2) -> List[DailyBrief]:
    """
    Return the top headlines from the most recent daily_briefs date that has
    any rows. Falls back through today, yesterday, and most recent.
    """
    today = date.today()
    for d in (today, today - timedelta(days=1)):
        items = (
            db.query(DailyBrief)
            .filter(DailyBrief.brief_date == d)
            .order_by(DailyBrief.priority, DailyBrief.created_at)
            .limit(limit)
            .all()
        )
        if items:
            return items
    latest = (
        db.query(DailyBrief.brief_date)
        .order_by(desc(DailyBrief.brief_date))
        .first()
    )
    if not latest:
        return []
    return (
        db.query(DailyBrief)
        .filter(DailyBrief.brief_date == latest[0])
        .order_by(DailyBrief.priority, DailyBrief.created_at)
        .limit(limit)
        .all()
    )


def _compose_alert_hooks(db: Session, user: User, limit: int = 2) -> List[Dict[str, str]]:
    """Surface unread saved-search alerts (the user's own subscriptions) and
    GAC-agenda-hawk hits as greeting hooks. Highest priority hook source —
    these are signals the user explicitly subscribed to, so they should
    win over generic briefings / daily-brief headlines.
    """
    try:
        from sqlalchemy import text
        rows = db.execute(
            text(
                """
                SELECT title, message, action_url, notification_type, priority,
                       notif_metadata
                FROM notifications
                WHERE user_id = :uid
                  AND is_read = FALSE
                  AND notification_type IN ('saved_search_alert','gac_agenda_hawk')
                ORDER BY
                    CASE priority
                        WHEN 'urgent' THEN 0
                        WHEN 'high'   THEN 1
                        WHEN 'normal' THEN 2
                        WHEN 'low'    THEN 3
                        ELSE 4 END,
                    created_at DESC
                LIMIT :lim
                """
            ),
            {"uid": user.id, "lim": limit},
        ).mappings().all()
    except Exception as exc:
        logger.warning("alert hook query failed: %s", exc)
        db.rollback()
        return []

    hooks: List[Dict[str, str]] = []
    for r in rows:
        meta = r["notif_metadata"] or {}
        sub_label = meta.get("subscription_label") or (
            "Council agenda watch" if r["notification_type"] == "gac_agenda_hawk" else "Saved search"
        )
        title = (r["title"] or "")[:120]
        spoken = (
            f"New for your '{sub_label}' watch: {title}"
            if r["notification_type"] == "saved_search_alert"
            else f"GAC alert: {title}"
        )
        hooks.append(
            {
                "label": sub_label,
                "spoken": spoken[:240],
                "suggested_query": f"Brief me on this alert: {title[:100]}",
                "source": "alert" if r["notification_type"] == "saved_search_alert" else "gac_hawk",
            }
        )
    return hooks


def _compute_user_hooks(
    db: Session, user: User, previous_last_login: Optional[datetime] = None
) -> List[Dict[str, str]]:
    """
    For an authenticated user, prefer in priority order:
    1. Unread saved-search alerts / GAC-hawk events (the user's own subs)
    2. Proactive briefings (tracked file movement, amendment surge, etc)
    3. Public daily_brief headlines (so the chip strip is never empty)
    """
    # 1. Alerts the user explicitly subscribed to always win.
    hooks = _compose_alert_hooks(db, user, limit=2)
    if hooks:
        return hooks

    # 2. Proactive briefings
    try:
        from services.proactive.trigger_engine import compute_pending_briefings

        briefings = compute_pending_briefings(
            db, user, previous_last_login=previous_last_login
        )
        hooks = compose_hooks_from_briefings(briefings)
    except Exception as exc:
        logger.warning("greeting hook briefing computation failed: %s", exc)
        db.rollback()
        hooks = []

    if hooks:
        return hooks

    # 3. Daily brief fallback
    try:
        items = _recent_brief_headlines(db, limit=2)
        hooks = compose_hooks_from_brief_headlines(items)
    except Exception as exc:
        logger.warning("greeting hook brief fallback failed: %s", exc)
        db.rollback()
        hooks = []
    return hooks


@router.get("/greeting", response_model=GreetingResponse)
async def get_greeting(
    previous_last_login: Optional[str] = Query(
        None,
        description="ISO datetime of user's previous login (from login response)",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate a personalised greeting for the authenticated user, plus up
    to two policy hooks Brubru wants to mention proactively.
    """
    prev_login = None
    if previous_last_login:
        try:
            prev_login = datetime.fromisoformat(previous_last_login)
        except (ValueError, TypeError):
            pass

    result = generate_personalized_greeting(
        first_name=current_user.first_name,
        preferred_name=current_user.preferred_name,
        timezone=current_user.timezone,
        language=current_user.language,
        full_name=current_user.full_name,
        previous_last_login=prev_login,
    )

    # Replace the generic welcome-back tail with a real portfolio diff
    # when the user has tracked file movement since their previous login.
    # The generic tail is one of two strings produced by greeting_service.
    if prev_login:
        recap = _compose_welcome_back_recap(db, current_user, prev_login)
        if recap:
            # The greeting service reports which (localised) welcome-back tail
            # it used via metadata; swap that exact string for the recap.
            generic_tail = result.metadata.get("welcome_back") or ""
            if generic_tail and generic_tail in result.message:
                result.message = result.message.replace(generic_tail, recap)
            else:
                # No generic tail to swap in: append the recap as a fresh sentence.
                result.message = f"{result.message.rstrip('.')}. {recap}"
            result.metadata = {**result.metadata, "welcome_back_recap": "true"}

    hooks = _compute_user_hooks(db, current_user, previous_last_login=prev_login)
    return GreetingResponse(
        message=result.message,
        metadata=result.metadata,
        policy_hooks=[PolicyHook(**h) for h in hooks],
    )


@router.get("/greeting/public", response_model=GreetingResponse)
async def get_public_greeting(
    pre_user_id: Optional[str] = Query(
        None,
        description="Browser-generated pre_user_id (UUID from localStorage). When provided, the greeting reads the user's onboarding Q1 answer and personalises the message.",
    ),
    db: Session = Depends(get_db),
):
    """
    Generate a generic greeting for pre-users (no auth). Hooks come from
    the public daily_brief so a first-time visitor still sees Brubru
    speaking, not just waiting. When the user has answered onboarding
    Q1, the message also names the policy area they picked, closing
    the "I heard you" loop.
    """
    result = generate_personalized_greeting(
        first_name=None,
        preferred_name=None,
        timezone=None,
        language=None,
        full_name=None,
        previous_last_login=None,
    )
    # For pre-users the resolved name is "there"; drop the awkward ", there".
    result.message = result.message.replace(", there.", ".", 1)

    # If the pre-user told us what they watch in onboarding Q1, name it
    # back to them. This is the smallest companion gesture: ask, then
    # show that you remembered.
    interest = _latest_onboarding_policy_area(db, pre_user_id) if pre_user_id else None
    if interest:
        result.message = (
            f"{result.message.rstrip('.')}. You said you watch "
            f"{interest['label']}. Here is what is moving today."
        )
        result.metadata = {**result.metadata, "policy_area": interest["slug"]}

    hooks: List[Dict[str, str]] = []
    try:
        items = _recent_brief_headlines(db, limit=2)
        hooks = compose_hooks_from_brief_headlines(items)
    except Exception as exc:
        logger.warning("public greeting hook fallback failed: %s", exc)
        db.rollback()
        hooks = []

    return GreetingResponse(
        message=result.message,
        metadata=result.metadata,
        policy_hooks=[PolicyHook(**h) for h in hooks],
    )
