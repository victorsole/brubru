"""Weekly Parliamentary Questions digest, per Policy Interest.

What the user gets: "This week MEPs asked N questions on your topics", the most
relevant of them, the answers that arrived this week to questions asked earlier,
and the MEP most active on those topics. It lands as an in-app notification
(`pq_digest`), which the existing email channel carries once
NOTIFICATION_EMAIL_ENABLED is on; the Parliamentary Questions tab shows the SAME
set in its "This week" strip, from `week_set()`, so email and product agree.

Proposal: 25 Sep 2026 session MD, item 7.4 A; built 28 Sep 2026.

Rules kept from the proposal:
- only paying users (yellow/blue, or paid off Stripe) with Policy Interests;
- no empty digests: a user with nothing on their topics gets nothing;
- no institutional codes in the prose: the question reference lives in the link;
- "answered this week" is read from `answered_date`, which EP sets, not from the
  answer text, which the text job fills later (on 28 Sep none of the 528 answers
  of the previous five weeks had text yet).
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

TAB_URL = "/main?tab=parliamentary-questions"
MAX_ASKED = 8
MAX_ANSWERED = 5


@dataclass
class WeekSet:
    asked: List[dict] = field(default_factory=list)       # top questions tabled this week
    answered: List[dict] = field(default_factory=list)    # answers that arrived this week
    asked_total: int = 0
    answered_total: int = 0
    most_active: Optional[dict] = None                    # {"name", "count"}
    since: Optional[str] = None
    until: Optional[str] = None
    pi_active: bool = False

    @property
    def empty(self) -> bool:
        return not self.asked_total and not self.answered_total

    def as_dict(self) -> dict:
        return {"asked": self.asked, "answered": self.answered,
                "asked_total": self.asked_total, "answered_total": self.answered_total,
                "most_active": self.most_active, "since": self.since, "until": self.until,
                "pi_active": self.pi_active}


def _kw_re(k: str):
    return re.compile(r"(?<![\w-])" + re.escape(k.lower()) + r"(?![\w-])")


def _score(row, kws: List[str]) -> int:
    """Distinct keywords as whole words: 2 per keyword in the subject, 1 in the text.

    The tab's lens is a substring match, fine for browsing and too loose for an
    email: "reach" (the chemicals law) matched "breach", and "border" matched
    "cross-border" (28 Sep 2026 preview). Whole words, hyphen-bounded.
    """
    subj = (row.subject or "").lower()
    body = (row.text_question or "").lower()
    score = 0
    for k in set(kws):
        rx = _kw_re(k)
        if rx.search(subj):
            score += 2
        elif rx.search(body):
            score += 1
    return score


def relevant(row, kws: List[str]) -> bool:
    """A keyword in the subject, or at least three distinct ones in the text.

    Two text hits were not enough (28 Sep preview): broad interests such as Single
    Market carry phrases ("internal market", "free movement", "competitiveness")
    that appear in the body of questions about seeds, housing or Mexican media."""
    subj = (row.subject or "").lower()
    if any(_kw_re(k).search(subj) for k in set(kws)):
        return True
    body = (row.text_question or "").lower()
    return sum(1 for k in set(kws) if _kw_re(k).search(body)) >= 3


MIN_SCORE = 2   # kept for the ranking; relevance is decided by relevant()


def week_set(db: Session, user, *, days: int = 7, today: Optional[date] = None,
             asked_since: Optional[date] = None, asked_until: Optional[date] = None) -> WeekSet:
    """The questions on this user's Policy Interests for the digest week.

    EP publishes a written question about a week after it is tabled (on 25 Sep
    2026 the newest on EP's own page, E-003755/2026, was dated 18 Sep), so
    "tabled in the last 7 days" is nearly always empty. The ASKED window is
    anchored on the newest question EP has published (asked_until) and runs from
    where this user's previous digest stopped (asked_since); answers arrive
    promptly, so the ANSWERED window is the calendar week to `today`."""
    from api.parliamentary_questions import _apply_pi, _summary
    from models.w4_entities import ParliamentaryQuestion as PQ
    from services.tracking.pi_committee_crosswalk import keywords_for_interests
    from services.tracking.tracked_files_seeder import _interest_list

    today = today or date.today()
    since = today - timedelta(days=days)
    asked_until = asked_until or feed_newest(db) or today
    asked_since = asked_since or (asked_until - timedelta(days=days))
    ws = WeekSet(since=asked_since.isoformat(), until=asked_until.isoformat())
    kws = keywords_for_interests(_interest_list(user) or []) or []

    asked_q, ws.pi_active = _apply_pi(
        db.query(PQ).filter(PQ.submitted_date > asked_since, PQ.submitted_date <= asked_until), user)
    if not ws.pi_active:
        return ws
    asked = [r for r in asked_q.all() if relevant(r, kws)]
    ws.asked_total = len(asked)
    asked.sort(key=lambda r: (-_score(r, kws), -(r.submitted_date.toordinal() if r.submitted_date else 0)))
    ws.asked = [_summary(r) for r in asked[:MAX_ASKED]]

    answered_q, _ = _apply_pi(
        db.query(PQ).filter(PQ.answered_date > since, PQ.answered_date <= today), user)
    answered = [r for r in answered_q.all() if relevant(r, kws)]
    ws.answered_total = len(answered)
    answered.sort(key=lambda r: (-_score(r, kws), -(r.answered_date.toordinal() if r.answered_date else 0)))
    ws.answered = [_summary(r) for r in answered[:MAX_ANSWERED]]
    for item, row in zip(ws.answered, answered[:MAX_ANSWERED]):
        item["answered"] = True          # EP recorded an answer, even before its text is fetched

    authors = Counter(n for r in asked for n in (r.asking_mep_names or []) if n)
    if authors:
        name, count = authors.most_common(1)[0]
        if count >= 2:
            ws.most_active = {"name": name, "count": count}
    return ws


# --------------------------------------------------------------------- wording
_T = {
    "en": {"title": "This week on your topics: {n} new parliamentary question{s}",
           "title_ans": "This week on your topics: {a} answer{sa} to parliamentary questions",
           "asked": "MEPs asked {n} question{s} on your topics.",
           "answered": "{a} earlier question{sa} got an answer.",
           "active": "Most active: {name} ({c} questions).",
           "top": "Top: {subj}"},
    "es": {"title": "Esta semana en sus temas: {n} pregunta{s} parlamentaria{s} nueva{s}",
           "title_ans": "Esta semana en sus temas: {a} respuesta{sa} a preguntas parlamentarias",
           "asked": "Los eurodiputados formularon {n} pregunta{s} sobre sus temas.",
           "answered": "{a} pregunta{sa} anterior{es_a} recibi{o_a} respuesta.",
           "active": "Más activo: {name} ({c} preguntas).",
           "top": "Destacada: {subj}"},
    "ca": {"title": "Aquesta setmana en els vostres temes: {n} {ca_q} {ca_parl} {ca_nova}",
           "title_ans": "Aquesta setmana en els vostres temes: {a} {ca_resp} a preguntes parlamentàries",
           "asked": "Els eurodiputats han formulat {n} {ca_q} sobre els vostres temes.",
           "answered": "{a} {ca_qa} anterior{s_a} ha{n_a} rebut resposta.",
           "active": "Més actiu: {name} ({c} preguntes).",
           "top": "Destacada: {subj}"},
    "fr": {"title": "Cette semaine sur vos sujets : {n} nouvelle{s} question{s} parlementaire{s}",
           "title_ans": "Cette semaine sur vos sujets : {a} réponse{sa} à des questions parlementaires",
           "asked": "Les députés ont posé {n} question{s} sur vos sujets.",
           "answered": "{a} question{sa} antérieure{sa} {ont_a} reçu une réponse.",
           "active": "Le plus actif : {name} ({c} questions).",
           "top": "À la une : {subj}"},
    "it": {"title": "Questa settimana sui tuoi temi: {n} nuov{e_i} interrogazion{i_e} parlamentar{i_e}",
           "title_ans": "Questa settimana sui tuoi temi: {a} rispost{e_a} a interrogazioni parlamentari",
           "asked": "Gli eurodeputati hanno presentato {n} interrogazion{i_e} sui tuoi temi.",
           "answered": "{a} interrogazion{i_ea} precedent{i_ea} {hanno_a} ricevuto risposta.",
           "active": "Più attivo: {name} ({c} interrogazioni).",
           "top": "In evidenza: {subj}"},
    "nl": {"title": "Deze week over uw onderwerpen: {n} nieuwe parlementaire vra{gen}",
           "title_ans": "Deze week over uw onderwerpen: {a} antwoord{en_a} op parlementaire vragen",
           "asked": "Europarlementariërs stelden {n} vra{gen} over uw onderwerpen.",
           "answered": "{a} eerdere vra{gen_a} {kreeg_a} een antwoord.",
           "active": "Meest actief: {name} ({c} vragen).",
           "top": "Uitgelicht: {subj}"},
}


def _forms(lang: str, n: int, a: int) -> dict:
    p, pa = n != 1, a != 1
    return {
        "s": "s" if p else "", "sa": "s" if pa else "",
        "es_a": "es" if pa else "", "o_a": "eron" if pa else "ó",
        "s_a": "s" if pa else "", "n_a": "n" if pa else "",
        "ont_a": "ont" if pa else "a",
        "e_i": "e" if p else "a", "i_e": "i" if p else "e",
        "e_a": "e" if pa else "a", "i_ea": "i" if pa else "e", "hanno_a": "hanno" if pa else "ha",
        "gen": "gen" if p else "ag", "gen_a": "gen" if pa else "ag",
        "en_a": "en" if pa else "", "kreeg_a": "kregen" if pa else "kreeg",
        # Catalan plurals change the vowel (pregunta -> preguntes), so no suffix trick.
        "ca_q": "preguntes" if p else "pregunta", "ca_qa": "preguntes" if pa else "pregunta",
        "ca_parl": "parlamentàries" if p else "parlamentària", "ca_nova": "noves" if p else "nova",
        "ca_resp": "respostes" if pa else "resposta",
    }


def _plain(subject: str) -> str:
    """The subject line as prose: no leading reference codes, bounded length."""
    s = re.sub(r"^\s*[EOP]-\d{6}/\d{4}\s*[-:]\s*", "", subject or "").strip()
    return (s[:117] + "...") if len(s) > 120 else s


def compose(ws: WeekSet, lang: str = "en") -> tuple[str, str]:
    """(title, message) for the notification, in the user's language."""
    t = _T.get((lang or "en")[:2].lower(), _T["en"])
    f = _forms(lang, ws.asked_total, ws.answered_total)
    if ws.asked_total:
        title = t["title"].format(n=ws.asked_total, **f)
    else:
        title = t["title_ans"].format(a=ws.answered_total, **f)
    parts = []
    if ws.asked_total:
        parts.append(t["asked"].format(n=ws.asked_total, **f))
    if ws.answered_total:
        parts.append(t["answered"].format(a=ws.answered_total, **f))
    if ws.most_active:
        parts.append(t["active"].format(name=ws.most_active["name"], c=ws.most_active["count"]))
    if ws.asked:
        parts.append(t["top"].format(subj=_plain(ws.asked[0]["subject"])))
    return title[:480], " ".join(parts)


# --------------------------------------------------------------------- run
def eligible_users(db: Session) -> list:
    """Paying tiers minus internal actors, by the ONE rule /users uses
    (scripts/user_activity_report.INTERNAL_USER_SQL: admins, trainers, unclaimed
    shells, beresol/hellobo/test/example accounts). The six seeded accounts that
    rule leaves pending Victor's decision stay eligible, as they do there."""
    from models.user import User
    from scripts.user_activity_report import INTERNAL_USER_SQL
    from services.notifications.notification_email import is_synthetic
    ids = [r[0] for r in db.execute(text(
        f"SELECT u.id FROM users u WHERE u.subscription_tier IN ('yellow', 'blue') "
        f"AND NOT {INTERNAL_USER_SQL}"))]
    users = db.query(User).filter(User.id.in_(ids)).all() if ids else []
    return [u for u in users if not is_synthetic(u.email or "")]


@dataclass
class RunResult:
    users: int = 0
    with_interests: int = 0
    created: int = 0
    skipped_empty: int = 0
    skipped_recent: int = 0
    previews: List[dict] = field(default_factory=list)


INGEST_MAX_AGE_HOURS = 36     # our ingest must have run cleanly this recently
EP_MAX_AGE_DAYS = 21          # beyond EP's normal ~1 week publishing lag: something is wrong


class StaleFeed(RuntimeError):
    """The questions feed is behind: a digest would tell users "nothing happened"."""


def feed_newest(db: Session) -> Optional[date]:
    return db.execute(text("SELECT max(submitted_date) FROM parliamentary_questions")).scalar()


def feed_problem(db: Session, today: date) -> Optional[str]:
    """Why the feed cannot be trusted this morning, or None.

    Two different failures: OUR ingest not running (no clean `parl_questions`
    run recently), and EP's listing being unusually far behind. A digest built
    on either would look like a quiet week."""
    newest = feed_newest(db)
    if newest is None:
        return "no parliamentary questions stored"
    if (today - newest).days > EP_MAX_AGE_DAYS:
        return f"newest question is {newest}, {(today - newest).days} days old (EP normally lags ~7)"
    ok = db.execute(text(
        "SELECT max(finished_at) FROM sync_runs WHERE source_key = 'parl_questions' "
        "AND status IN ('success', 'degraded') AND coalesce(runner, 'container') <> 'local'")).scalar()
    if ok is None:
        return "the parl_questions ingest has never recorded a clean run"
    ok_utc = ok if ok.tzinfo else ok.replace(tzinfo=timezone.utc)
    age_h = (datetime.now(timezone.utc) - ok_utc).total_seconds() / 3600
    if age_h > INGEST_MAX_AGE_HOURS:
        return f"last clean parl_questions run was {age_h:.0f} h ago (limit {INGEST_MAX_AGE_HOURS} h)"
    return None


def run(db: Session, *, apply: bool, today: Optional[date] = None, only: Optional[set] = None,
        allow_stale: bool = False) -> RunResult:
    """Create one `pq_digest` notification per eligible user with something to say.

    Refuses to run on a stale feed (StaleFeed): on 28 Sep 2026 the newest stored
    question was dated 18 Sep, and a digest built on it would have skipped every
    user as "empty", which reads exactly like a quiet week.
    """
    from models.notification import Notification

    today = today or date.today()
    problem = feed_problem(db, today)
    if problem and not allow_stale:
        raise StaleFeed(f"{problem}: refusing to build a digest that would under-report")
    newest = feed_newest(db)
    res = RunResult()
    cutoff = datetime.now(timezone.utc) - timedelta(days=6)
    for u in eligible_users(db):
        if only and (u.email or "").lower() not in only:
            continue
        res.users += 1
        prev = db.execute(text(
            "SELECT notif_metadata FROM notifications WHERE user_id = :u AND notification_type = 'pq_digest' "
            "ORDER BY created_at DESC LIMIT 1"), {"u": u.id}).scalar()
        prev_until = None
        if isinstance(prev, dict) and prev.get("until"):
            try:
                prev_until = date.fromisoformat(prev["until"])
            except ValueError:
                prev_until = None
        if prev_until and newest and prev_until >= newest:
            res.skipped_recent += 1          # EP has published nothing new since the last digest
            continue
        ws = week_set(db, u, today=today, asked_since=prev_until, asked_until=newest)
        if not ws.pi_active:
            continue
        res.with_interests += 1
        if ws.empty:
            res.skipped_empty += 1
            continue
        recent = db.execute(text(
            "SELECT 1 FROM notifications WHERE user_id = :u AND notification_type = 'pq_digest' "
            "AND created_at >= :c LIMIT 1"), {"u": u.id, "c": cutoff}).first()
        if recent:
            res.skipped_recent += 1
            continue
        title, message = compose(ws, getattr(u, "language", None) or "en")
        res.previews.append({"email": u.email, "lang": getattr(u, "language", None) or "en",
                             "title": title, "message": message, "week": ws.as_dict()})
        if apply:
            db.add(Notification(user_id=u.id, notification_type="pq_digest", title=title,
                                message=message, action_url=TAB_URL, priority="normal",
                                notif_metadata={"since": ws.since, "until": ws.until,
                                                "asked_total": ws.asked_total,
                                                "answered_total": ws.answered_total,
                                                "references": [q["reference"] for q in ws.asked + ws.answered]}))
            db.commit()
            res.created += 1
    return res
