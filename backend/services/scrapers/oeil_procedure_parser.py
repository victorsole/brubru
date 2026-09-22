"""Parse an OEIL procedure page into the fields `legislative_carriages` needs.

Why (D4, 27 Aug 2026)
---------------------
For `2025/2081(INI)`, *Impact of social media and the online environment on young
people*, Brubru recorded the lead committee as **IMCO**. OEIL says the committee
responsible is **CULT**; IMCO holds an OPINION, alongside LIBE and FEMM. The
rapporteur, **Sandro RUOTOLO (S&D)**, appointed 14 April 2025, was recorded as
NULL. Both errors would have shipped in a public post.

The cause is not a subtle mapping bug. `oeil_sync_service` sets

    lead_committee = item.committees[0]

-- whichever committee happens to come first in a flat list from the OEIL XML
feed, which does not distinguish *responsible* from *for opinion* at all. Measured
across the fleet:

    rapporteur_mep_id populated ...........      0 / 2,789
    lead_committee populated ..............  1,038 / 2,789
    opinion_committees non-empty ..........      1 / 2,789
    committees non-empty ..................      1 / 2,789

So this is not one bad row: two columns were never written, and a third was
written from a list whose order carries no meaning.

The distinction DOES exist on the procedure page, under the headings "Committee
responsible" and "Committee for opinion" -- and Brubru already stores that page
for 892 carriages in `oeil_text_body`. This module reads what we already have
rather than re-fetching OEIL 2,789 times.

The same page keeps "Key events" (what HAPPENED) and "Forecasts" (what is
EXPECTED) in separate sections. Flattening them turns an indicative plenary date
into a committee vote that already happened, which is the second half of D4.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

# EP committee codes. Deliberately explicit rather than "any 4 capitals", which
# would also match S&D group names, country codes and document-type markers.
_COMMITTEE_CODES = {
    "AFET", "DEVE", "INTA", "BUDG", "CONT", "ECON", "EMPL", "ENVI", "ITRE",
    "IMCO", "TRAN", "REGI", "AGRI", "PECH", "CULT", "JURI", "LIBE", "AFCO",
    "FEMM", "PETI", "DROI", "SEDE", "SANT", "FISC", "PEGA", "INGE", "BECA",
    "ANIT", "AIDA", "COVI", "ECCC", "EUDS", "SPRT",
}

_DATE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")


@dataclass
class ProcedureFacts:
    responsible_committee: Optional[str] = None
    # True when OEIL heads the block "Joint committee responsible" (Rule 58):
    # two committees share responsibility and each has its own rapporteur, so
    # `responsible_committee` is the FIRST of two, not the only one.
    joint_committee: bool = False
    opinion_committees: List[str] = field(default_factory=list)
    rapporteur_name: Optional[str] = None
    rapporteur_appointed: Optional[date] = None
    key_events: List[dict] = field(default_factory=list)
    forecasts: List[dict] = field(default_factory=list)

    @property
    def all_committees(self) -> List[str]:
        out = ([self.responsible_committee] if self.responsible_committee else [])
        return out + [c for c in self.opinion_committees if c != self.responsible_committee]


def _section(text: str, start_label: str, end_labels: tuple[str, ...]) -> str:
    """Text between one heading and the next. Returns "" when absent.

    An absent section must yield "" and NOT the rest of the document, or a page
    without forecasts would have its key events parsed as forecasts.
    """
    i = text.find(start_label)
    if i < 0:
        return ""
    i += len(start_label)
    ends = [text.find(lbl, i) for lbl in end_labels]
    ends = [e for e in ends if e >= 0]
    return text[i: min(ends)] if ends else text[i:]


def _codes_in(chunk: str) -> List[str]:
    """Committee codes in order of appearance, de-duplicated."""
    out: List[str] = []
    for tok in re.findall(r"\b([A-Z]{4})\b", chunk):
        if tok in _COMMITTEE_CODES and tok not in out:
            out.append(tok)
    return out


def _parse_date(s: str) -> Optional[date]:
    m = _DATE.search(s)
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def parse_procedure_text(text: str) -> ProcedureFacts:
    """Extract committees, rapporteur and the event/forecast split.

    `text` is the flattened procedure page (`legislative_carriages.oeil_text_body`).
    """
    facts = ProcedureFacts()
    if not text:
        return facts

    flat = " ".join(text.split())

    # --- committees -------------------------------------------------------
    # "Committee responsible" runs until "Committee for opinion" (or the next
    # heading). The FIRST committee code inside that block is the responsible
    # one; codes under the opinion heading are opinions.
    # A Rule 58 file headed "JOINT committee responsible" was invisible here.
    #
    # `_section` matches a literal, and the joint heading spells the word with a
    # lowercase c, so "Committee responsible" never matched. The section came
    # back "", no responsible committee and no rapporteur were recorded, and the
    # backfill counted the page under "no heading at all" -- an expected bucket,
    # so it never looked like a parser failure. Measured 22 September 2026:
    # **95 carriages** carry the joint heading, among them the Cloud and AI
    # Development Act (2026/0138(COD)), which has had TWO co-rapporteurs since
    # 24 June 2026 while Brubru recorded none and its guide said the referral was
    # still pending.
    resp = _section(flat, "Committee responsible",
                    ("Committee for opinion", "Key events", "Forecasts",
                     "Technical information", "Documentation gateway"))
    if not resp:
        resp = _section(flat, "Joint committee responsible",
                        ("Committee for opinion", "Key events", "Forecasts",
                         "Technical information", "Documentation gateway"))
        facts.joint_committee = bool(resp)
    opin = _section(flat, "Committee for opinion",
                    ("Key events", "Forecasts", "Technical information",
                     "Documentation gateway", "European Commission"))

    resp_codes = _codes_in(resp)
    if resp_codes:
        facts.responsible_committee = resp_codes[0]
    facts.opinion_committees = [
        c for c in _codes_in(opin) if c != facts.responsible_committee
    ]

    # --- rapporteur -------------------------------------------------------
    # OEIL renders "SURNAME Firstname (GROUP) DD/MM/YYYY" inside the responsible
    # block. Take the FIRST such match: later ones are shadow rapporteurs, and
    # attributing a shadow's name to the file is its own fabrication.
    if resp:
        head = resp.split("Shadow rapporteur")[0]
        m = re.search(r"\b([A-ZÀ-Þ][A-ZÀ-Þ'\-]{1,}(?:\s+[A-ZÀ-Þ'\-]{2,})*)\s+"
                      r"([A-ZÀ-Þ][a-zà-ÿ'\-]+(?:\s+[A-ZÀ-Þ][a-zà-ÿ'\-]+)*)\s*\(", head)
        if m:
            facts.rapporteur_name = f"{m.group(1).strip()} {m.group(2).strip()}"
            facts.rapporteur_appointed = _parse_date(head[m.end():m.end() + 40])

    # --- events vs forecasts ---------------------------------------------
    # Two different claims about the world. "Key events" is what HAPPENED;
    # "Forecasts" is what is EXPECTED. Merging them presents an indicative
    # plenary date as a committee vote that has already taken place.
    facts.key_events = _parse_rows(
        _section(flat, "Key events", ("Forecasts", "Technical information",
                                      "Documentation gateway")))
    facts.forecasts = _parse_rows(
        _section(flat, "Forecasts", ("Technical information",
                                     "Documentation gateway", "Key events")))
    return facts


def _parse_rows(chunk: str) -> List[dict]:
    """Rows of "DD/MM/YYYY <subject>" from an OEIL table rendered as text."""
    if not chunk:
        return []
    rows: List[dict] = []
    parts = _DATE.split(chunk)
    # split() yields [pre, dd, mm, yyyy, text, dd, mm, yyyy, text, ...]
    for i in range(1, len(parts) - 3, 4):
        try:
            d = date(int(parts[i + 2]), int(parts[i + 1]), int(parts[i]))
        except (ValueError, IndexError):
            continue
        subject = " ".join(parts[i + 3].split())[:200].strip() if i + 3 < len(parts) else ""
        subject = re.sub(r"^(Date|Subject|Event|Reference|Summary)\s+", "", subject)
        if subject:
            rows.append({"date": d.isoformat(), "event_type": subject})
    return rows


# ---------------------------------------------------------------------------
# Status inference and carriage mapping for a LIVE procedure page (15 Sep 2026)
# ---------------------------------------------------------------------------
# Status values are the `CarriageStatusEnum` VALUES, kept as strings so this
# module stays free of ORM imports.
STATUS_RANK = {
    "announced": 0,
    "legislative_initiative": 1,
    "tabled": 2,
    "close_to_adoption": 3,
    "completed": 4,
    "adopted": 5,
    # blocked / withdrawn are outside the progression
}


def infer_carriage_status(event_types, stage: Optional[str] = None) -> Optional[str]:
    """The most advanced carriage status the OEIL key events (and stage) prove.

    Strongest signal wins. Matching is by substring on OEIL's own wording
    ("Decision by Parliament, 1st reading", "Final act published in Official
    Journal", ...).

    One rule changed on 15 Sep 2026: "Decision by Parliament" used to mean
    COMPLETED. While the parser was reading garbage that rule rarely fired; with
    the real event table it would have fired on every file with a first-reading
    vote. That is wrong -- 2025/0207(COD) had its Parliament vote on 29/04/2026
    and was referred straight back for trilogues; 2023/0156(COD) is in second
    reading. COMPLETED is the carriage twin of OEIL's "Procedure completed", and
    the script only ever advances a status, so a false COMPLETED would be
    permanent. A Parliament decision now proves CLOSE_TO_ADOPTION; COMPLETED
    needs the Council's adoption of the act or OEIL's own "Procedure completed".
    """
    ets = [(e or "").lower() for e in (event_types or [])]
    st = (stage or "").lower()

    def has(*needles: str) -> bool:
        return any(n in e for e in ets for n in needles)

    if has("final act signed", "final act published", "entry into force"):
        return "adopted"
    if has("act adopted by council") or "procedure completed" in st:
        return "completed"
    if has("decision by parliament", "committee report", "vote in committee",
           "committee recommendation tabled", "approval in committee of the text agreed"):
        return "close_to_adoption"
    if has("legislative proposal", "committee referral"):
        return "tabled"
    return None


def advance_status(current: Optional[str], inferred: Optional[str]) -> Optional[str]:
    """`inferred` when it is strictly further along than `current`, else None.

    A status outside the progression (blocked, withdrawn) is never overwritten.
    """
    if not inferred:
        return None
    cur = (current or "").lower()
    if cur and cur not in STATUS_RANK:
        return None
    if STATUS_RANK.get(inferred, -1) > STATUS_RANK.get(cur, -1):
        return inferred
    return None


_GIVES_OPINION = ("opinion", "budgetary_assessment", "opinion_associated",
                  "budgetary_assessment_associated", "responsible_associated")


def carriage_fields_from_procedure(procedure) -> dict:
    """Map an `OEILProcedure` (parsed live page) to `legislative_carriages` columns.

    Only fields the page actually states are returned. A committee that "decided
    not to give an opinion" is not an opinion committee. Former committees are
    already dropped by the parser.
    """
    out: dict = {}
    kp = procedure.key_players
    cr = kp.committee_responsible
    if cr is not None:
        out["lead_committee"] = cr.code
        if cr.rapporteur is not None:
            out["rapporteur_name"] = cr.rapporteur.name
            out["rapporteur_mep_id"] = cr.rapporteur.mep_id
            out["rapporteur_appointed"] = cr.date_announced
        opinions: List[str] = []
        for c in list(kp.committees_opinion) + list(kp.committees_associated):
            if c.role in _GIVES_OPINION and c.code != cr.code and c.code not in opinions:
                opinions.append(c.code)
        out["opinion_committees"] = opinions
        out["committees"] = [cr.code] + opinions
    out["oeil_key_events"] = [
        {"date": e.date.isoformat() if e.date else None,
         "event_type": e.event_type,
         "description": e.description}
        for e in procedure.key_events.events
    ]
    out["oeil_forecasts"] = [
        {"date": f.forecast_date.isoformat() if f.forecast_date else None,
         "event_type": f.event_type}
        for f in procedure.forecasts.forecasts
    ]
    return out
