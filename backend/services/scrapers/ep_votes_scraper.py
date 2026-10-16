"""
EP vote scraper — committee + plenary roll-call parsers.

NO LLM / NO Anthropic. Pure HTML/text parsing of doceo documents (which are
WAF-walled, so the caller fetches them through WafBrowserFetcher).

Two sources, two structures (both group-bucketed by +/-/0):

COMMITTEE  — the doceo committee report ``A-<term>-<year>-<seq>_EN.html``.
    Parsed from the chrome-stripped *text* (renders fully). Layout:

        Result of final vote
        +:
        –:
        0:
        78
        11
        5
        ...
        FINAL VOTE BY ROLL CALL BY THE COMMITTEE RESPONSIBLE
        78
        +
        ECR
        <comma-separated names>
        PPE
        <names>
        ...
        Key to symbols:

PLENARY    — the doceo roll-call minutes ``PV-<term>-<date>-RCV_EN.html``.
    The per-MEP detail is in the raw *HTML* (visually collapsed, so inner_text
    does NOT surface it — we parse ``result.html``). Layout per sub-item:

        ...dossier_1"...>&nbsp;8.&nbsp;...>EU-Canada Agreement ...        (item heading)
        ...dossier_2"...toggleRCV('div192529'...>&nbsp;8.1.&nbsp;...>
            A10-0144/2026 – Strack-Zimmermann, Budka – Draft Council decision   (sub-item)
        <td ...white_td_center">466</td><td ...grey_td_center"><span ...>+</span></td>
        <td ...><span ...bold">ECR&nbsp;:</span></td><td>Bartulica, Berlato, ...</td>
        ... (then the 169 "-" block and the 14 "0" block)
"""

from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

DOCEO_BASE = "https://www.europarl.europa.eu/doceo/document/"

# Known EP political-group codes (so we can tell a group header from a names
# line in the committee text layout). Includes current EP10 groups + a few
# historical/edge labels.
EP_GROUPS = frozenset({
    "PPE", "S&D", "Renew", "Verts/ALE", "ECR", "PfE", "The Left",
    "ESN", "NI", "GUE/NGL", "ID", "Greens/EFA", "NA",
})

# Subjects that mark the decisive (final) vote on a dossier, in priority order.
# Subjects of votes on part of a text or on procedure: "Am 2", "Am 14= 15= 16=", "§ 3/2",
# "Recital C", "Proposal to vote on amendments", "Motion for adjournment of the vote".
_NOT_A_FINAL_VOTE = re.compile(
    r"(?i)^\s*(am\b|amendment|§|recital|citation|after\b|before\b|proposal to vote on amendments"
    r"|motion for adjournment|proposal for rejection|request\b|split\b|separate\b|unamended\))")

_FINAL_SUBJECT_HINTS = (
    "draft council decision", "commission proposal", "provisional agreement",
    "legislative resolution", "text as a whole", "single vote",
    "proposal for a", "motion for a resolution", "draft decision",
)


# --------------------------------------------------------------------------
# data shapes
# --------------------------------------------------------------------------

@dataclass
class VoteRecord:
    name: str
    group: Optional[str]
    choice: str  # '+', '-', '0'


@dataclass
class ParsedVote:
    votes_for: Optional[int] = None
    votes_against: Optional[int] = None
    votes_abstention: Optional[int] = None
    result: Optional[str] = None      # 'adopted' | 'rejected'
    vote_type: str = "rcv"
    records: List[VoteRecord] = field(default_factory=list)
    # plenary sub-item extras
    report_ref: Optional[str] = None
    subject: Optional[str] = None
    item_number: Optional[str] = None
    rapporteurs: Optional[str] = None

    @property
    def total_records(self) -> int:
        return len(self.records)

    def group_breakdown(self) -> Dict[str, Dict[str, int]]:
        out: Dict[str, Dict[str, int]] = {}
        for r in self.records:
            g = r.group or "NI"
            out.setdefault(g, {"+": 0, "-": 0, "0": 0})
            if r.choice in out[g]:
                out[g][r.choice] += 1
        return out


# --------------------------------------------------------------------------
# url builders
# --------------------------------------------------------------------------

def committee_report_url(report_ref: str, lang: str = "EN") -> Optional[str]:
    """'A10-0144/2026' -> '.../A-10-2026-0144_EN.html'."""
    m = re.match(r"([A-Z]+)\s*(\d{1,2})-(\d{4})/(\d{4})", (report_ref or "").strip())
    if not m:
        return None
    typ, term, seq, year = m.groups()
    return f"{DOCEO_BASE}{typ}-{term}-{year}-{seq}_{lang}.html"


def rcv_url(sitting: date, term: int = 10, lang: str = "EN") -> str:
    """Roll-call minutes URL for a sitting day."""
    return (
        f"{DOCEO_BASE}PV-{term}-{sitting.year}-{sitting.month:02d}-"
        f"{sitting.day:02d}-RCV_{lang}.html"
    )


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(s: str) -> str:
    return _html.unescape(_TAG_RE.sub(" ", s or "")).replace("\xa0", " ").strip()


def _norm_choice(c: str) -> Optional[str]:
    c = (c or "").strip()
    if c == "+":
        return "+"
    if c in ("-", "–", "—", "−"):  # hyphen / en / em / minus
        return "-"
    if c == "0":
        return "0"
    return None


def _names(raw: str) -> List[str]:
    txt = _strip_tags(raw)
    return [n.strip() for n in txt.split(",") if n.strip()]


def _verdict(for_: Optional[int], against: Optional[int]) -> Optional[str]:
    if for_ is None or against is None:
        return None
    return "adopted" if for_ > against else "rejected"


# --------------------------------------------------------------------------
# committee report parser (text)
# --------------------------------------------------------------------------

def parse_committee_report(text: str) -> Optional[ParsedVote]:
    """Parse the 'Result of final vote' + roll-call from an A-report's text."""
    if not text or "FINAL VOTE BY ROLL CALL" not in text:
        return None

    pv = ParsedVote(vote_type="rcv")

    # --- tally: 3 integers between "Result of final vote" and the next anchor.
    tally_m = re.search(r"Result of final vote(.*?)(?:Date tabled|FINAL VOTE BY ROLL CALL)",
                        text, re.S)
    if tally_m:
        ints = re.findall(r"(?m)^\s*(\d{1,4})\s*$", tally_m.group(1))
        if len(ints) >= 3:
            pv.votes_for, pv.votes_against, pv.votes_abstention = (
                int(ints[0]), int(ints[1]), int(ints[2])
            )

    # --- roll-call: between the LAST header and "Key to symbols".
    start = text.rfind("FINAL VOTE BY ROLL CALL")
    block = text[start:]
    end = block.find("Key to symbols")
    if end != -1:
        block = block[:end]

    current_choice: Optional[str] = None
    current_group: Optional[str] = None
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("FINAL VOTE BY ROLL CALL"):
            continue
        if re.fullmatch(r"\d{1,4}", line):          # the count before a choice
            continue
        ch = _norm_choice(line)
        if ch and len(line) <= 1:                   # a bare +/-/0 choice marker
            current_choice = ch
            current_group = None
            continue
        if line in EP_GROUPS:
            current_group = line
            continue
        if current_choice and current_group:        # a names line
            for nm in _names(line):
                pv.records.append(VoteRecord(name=nm, group=current_group, choice=current_choice))

    # Fall back to counting records if the tally lines were missing.
    if pv.votes_for is None and pv.records:
        pv.votes_for = sum(1 for r in pv.records if r.choice == "+")
        pv.votes_against = sum(1 for r in pv.records if r.choice == "-")
        pv.votes_abstention = sum(1 for r in pv.records if r.choice == "0")

    pv.result = _verdict(pv.votes_for, pv.votes_against)
    return pv if (pv.records or pv.votes_for is not None) else None


# --------------------------------------------------------------------------
# plenary roll-call parser (html)
# --------------------------------------------------------------------------

# An item heading: dossier_1 span -> "8." + title.
_ITEM_RE = re.compile(
    r'dossier_1"[^>]*>\s*<span[^>]*onclick="toggleRCV[^>]*>\s*(?:&nbsp;)*\s*(\d+)\.'
    r'(?:&nbsp;)*\s*</span>\s*<span[^>]*onclick="toggleRCV[^>]*>(.*?)</span>',
    re.S,
)
# A sub-item: dossier_2 span -> "8.1." + label (A-code – rapporteurs – subject).
_SUBITEM_RE = re.compile(
    r"dossier_2\"[^>]*>\s*<span[^>]*onclick=\"toggleRCV\('([^']+)'[^>]*>\s*(?:&nbsp;)*\s*"
    r"([\d.]+?)\.?(?:&nbsp;)+\s*</span>\s*<span[^>]*onclick=\"toggleRCV[^>]*>(.*?)</span>",
    re.S,
)
# Count + choice cell pair.
_COUNT_RE = re.compile(
    r'white_td_center"?\s*>\s*(\d{1,4})\s*</td>\s*<td[^>]*grey_td_center"[^>]*>\s*'
    r'<span[^>]*>\s*([+–—\-0])\s*</span>',
    re.S,
)
# A group row: "<bold>ECR&nbsp;:</bold></td><td>names</td>".
_GROUP_RE = re.compile(
    r'font-weight:bold"\s*>\s*(.*?)\s*(?:&nbsp;)?\s*:\s*</span>\s*</td>\s*<td[^>]*>(.*?)</td>',
    re.S,
)
_REPORT_CODE_RE = re.compile(r"((?:RC|A|B|C)\d{1,2}-\d{4}/\d{4})")


def _parse_rcv_block(block: str) -> ParsedVote:
    """Parse one sub-item detail block: ordered count/choice + group rows."""
    pv = ParsedVote(vote_type="rcv")
    counts = {"+": None, "-": None, "0": None}

    # Walk count-cells and group-rows in document order so each group attaches
    # to the choice that precedes it.
    tokens = []
    for m in _COUNT_RE.finditer(block):
        tokens.append((m.start(), "count", m.group(1), _norm_choice(m.group(2))))
    for m in _GROUP_RE.finditer(block):
        grp = _html.unescape(_strip_tags(m.group(1)))
        tokens.append((m.start(), "group", grp, m.group(2)))
    tokens.sort(key=lambda t: t[0])

    current_choice: Optional[str] = None
    for _, kind, a, b in tokens:
        if kind == "count":
            current_choice = b
            if b in counts:
                counts[b] = int(a)
        elif kind == "group" and current_choice:
            group = a.strip() or "NI"
            for nm in _names(b):
                pv.records.append(VoteRecord(name=nm, group=group, choice=current_choice))

    pv.votes_for = counts["+"] if counts["+"] is not None else sum(1 for r in pv.records if r.choice == "+")
    pv.votes_against = counts["-"] if counts["-"] is not None else sum(1 for r in pv.records if r.choice == "-")
    pv.votes_abstention = counts["0"] if counts["0"] is not None else sum(1 for r in pv.records if r.choice == "0")
    pv.result = _verdict(pv.votes_for, pv.votes_against)
    return pv


def parse_plenary_rcv(html: str) -> Dict[str, dict]:
    """Parse a whole RCV minutes page.

    Returns ``{item_number: {"title": str, "subitems": [ {...}, ... ]}}``
    where each sub-item carries its parsed vote (counts + records).
    """
    if not html:
        return {}

    # Item headings -> {item_no: (pos, title)}.
    items: Dict[str, dict] = {}
    for m in _ITEM_RE.finditer(html):
        no = m.group(1)
        title = _strip_tags(m.group(2))
        items[no] = {"pos": m.start(), "title": title, "subitems": []}

    # Sub-items, with their detail block running to the next anchor.
    anchors = sorted(
        [m.start() for m in _ITEM_RE.finditer(html)]
        + [m.start() for m in _SUBITEM_RE.finditer(html)]
        + [len(html)]
    )
    for m in _SUBITEM_RE.finditer(html):
        div_id, sub_no, label_html = m.group(1), m.group(2), m.group(3)
        label = _strip_tags(label_html)
        block_end = next((a for a in anchors if a > m.start()), len(html))
        block = html[m.start():block_end]

        pv = _parse_rcv_block(block)
        code_m = _REPORT_CODE_RE.search(label)
        pv.report_ref = code_m.group(1) if code_m else None
        # label = "<code> – <rapporteurs> – <subject>"
        parts = [p.strip() for p in re.split(r"\s[–—-]\s", label) if p.strip()]
        if len(parts) >= 3:
            pv.rapporteurs = parts[1]
            pv.subject = parts[-1]
        elif len(parts) == 2:
            pv.subject = parts[-1]
        else:
            pv.subject = label
        pv.item_number = sub_no

        parent = sub_no.split(".")[0]
        items.setdefault(parent, {"pos": 0, "title": "", "subitems": []})
        items[parent]["subitems"].append({
            "subitem_number": sub_no,
            "label": label,
            "report_ref": pv.report_ref,
            "subject": pv.subject,
            "rapporteurs": pv.rapporteurs,
            "vote": pv,
        })

    return items


def rcv_xml_url(sitting: date, term: int = 10) -> str:
    """The sitting's roll-call results as XML (all languages in one file)."""
    return f"{DOCEO_BASE}PV-{term}-{sitting.year}-{sitting.month:02d}-{sitting.day:02d}-RCV_EN.xml"


_CHOICE_TAGS = (("Result.For", "+"), ("Result.Against", "-"), ("Result.Abstention", "0"))


def parse_plenary_rcv_xml(xml: bytes | str) -> Dict[str, dict]:
    """Parse a sitting's RCV XML into the same shape as :func:`parse_plenary_rcv`.

    From some sittings of July 2025 on, the English RCV page is an interactive page
    (filters by group and country) that the HTML parser reads as empty: 37 sitting days
    yielded no vote and the plenary table held nothing between July and December 2025
    but 12 votes (15 Oct 2026). The XML the same page links holds every vote: each
    <RollCallVote.Result> carries a DlvId tying it to a <VoteTitle> (the agenda item, the
    title texts_adopted is matched on), its description ("A10-0192/2025 - rapporteurs -
    subject") and the members under <Result.For/Against/Abstention>, by political group.
    Items are keyed by DlvId; a sub-item is numbered "<DlvId>.<Identifier>".
    """
    import xml.etree.ElementTree as ET

    if not xml:
        return {}
    try:
        root = ET.fromstring(xml if isinstance(xml, bytes) else xml.encode("utf-8"))
    except ET.ParseError:
        return {}

    def local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    titles: Dict[str, str] = {}
    for el in root.iter():
        if local(el.tag) == "VoteTitle" and el.get("DlvId"):
            titles[el.get("DlvId")] = " ".join("".join(el.itertext()).split())

    items: Dict[str, dict] = {}
    for res in root.iter():
        if local(res.tag) != "RollCallVote.Result":
            continue
        dlv = res.get("DlvId") or ""
        label = ""
        pv = ParsedVote(vote_type="rcv")
        counts: Dict[str, Optional[int]] = {"+": None, "-": None, "0": None}
        for child in res:
            name = local(child.tag)
            if name == "RollCallVote.Description.Text":
                label = " ".join("".join(child.itertext()).split())
                continue
            choice = next((c for t, c in _CHOICE_TAGS if t == name), None)
            if choice is None:
                continue
            try:
                counts[choice] = int(child.get("Number"))
            except (TypeError, ValueError):
                counts[choice] = None
            for grp in child:
                if local(grp.tag) != "Result.PoliticalGroup.List":
                    continue
                group = (grp.get("Identifier") or "NI").strip() or "NI"
                for mep in grp:
                    nm = " ".join("".join(mep.itertext()).split())
                    if nm:
                        pv.records.append(VoteRecord(name=nm, group=group, choice=choice))
        pv.votes_for = counts["+"] if counts["+"] is not None else sum(1 for r in pv.records if r.choice == "+")
        pv.votes_against = counts["-"] if counts["-"] is not None else sum(1 for r in pv.records if r.choice == "-")
        pv.votes_abstention = counts["0"] if counts["0"] is not None else sum(1 for r in pv.records if r.choice == "0")
        pv.result = _verdict(pv.votes_for, pv.votes_against)

        code_m = _REPORT_CODE_RE.search(label)
        pv.report_ref = code_m.group(1) if code_m else None
        parts = [x.strip() for x in re.split(r"\s[–—-]\s", label) if x.strip()]
        if len(parts) >= 3:
            pv.rapporteurs = parts[1]
            pv.subject = parts[-1]
        elif len(parts) == 2:
            pv.subject = parts[-1]
        else:
            pv.subject = label
        sub_no = f"{dlv}.{res.get('Identifier') or len(items)}"
        pv.item_number = sub_no
        item = items.setdefault(dlv, {"pos": 0, "title": titles.get(dlv, ""), "subitems": []})
        item["subitems"].append({
            "subitem_number": sub_no, "label": label, "report_ref": pv.report_ref,
            "subject": pv.subject, "rapporteurs": pv.rapporteurs, "vote": pv,
        })
    return items


def pick_final_subitem(subitems: List[dict]) -> Optional[dict]:
    """Choose the decisive vote among an item's sub-items.

    Prefer a subject that names the final/legislative vote; else the sub-item
    with the most MEPs recorded (the whole-house vote, not an amendment).
    """
    if not subitems:
        return None
    # A vote on an amendment, a paragraph or a procedural motion is never the text's
    # vote. The old fallback took the sub-item with the most MEPs recorded, so when the
    # final vote was by show of hands (no roll-call) it chose "Am 2": 40 texts Parliament
    # adopted were served REJECTED, the Kosovo report 252-305 for an adopted 412-174
    # (16 Oct 2026). None is better than a wrong vote.
    candidates = [s for s in subitems if not _NOT_A_FINAL_VOTE.match(s.get("subject") or "")]
    for hint in _FINAL_SUBJECT_HINTS:
        for s in candidates:
            if hint in (s.get("subject") or "").lower():
                return s
    return max(candidates, key=lambda s: s["vote"].total_records) if candidates else None


def subitem_with_counts(items: Dict[str, dict], votes_for, votes_against, votes_abstention) -> Optional[dict]:
    """The sitting's roll-call sub-item with exactly these counts, when one alone has them.

    EP Open Data names the final vote of each adopted text and its counts; the roll-call
    minutes hold that same vote with each MEP's choice. Matching on the three counts finds
    it whatever its title or position (a title match took a competing motion: the Albania
    report read 381-107 for the 483-103 Parliament adopted)."""
    if votes_for is None or votes_against is None or votes_abstention is None:
        return None
    hits = [s for it in (items or {}).values() for s in it.get("subitems") or []
            if (s["vote"].votes_for, s["vote"].votes_against, s["vote"].votes_abstention)
            == (votes_for, votes_against, votes_abstention)]
    return hits[0] if len(hits) == 1 else None
