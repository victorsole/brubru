"""EU sanctions listings read from the Official Journal, for the gap the Commission list leaves.

Why this exists (1 October 2026): the Commission's consolidated financial sanctions list
(webgate.ec.europa.eu/fsd/fsf, mirrored in `eu_sanctions`) was last published on
22 September 2026 and carries no legal act newer than 23 July 2026. Every format and the
list's own RSS feed say the same. Between 24 July and 28 September the Official Journal
published 20 restrictive-measures regulations that add, delete, replace or amend listings
(Russia, Belarus, Iran, the terrorist list, ISIL/Al-Qaida, DRC, Afghanistan, Libya ...).
Nobody republishes the consolidated list faster, and the Council's sanctions map reuses it.

So this reads the listings from the acts themselves: each annex block is classified by
its lead sentence ("the following persons are added ...", "the entries ... are deleted",
"... are replaced by the following", "the identifying data ... is amended", or a whole
list set out in the annex), and each entry is stored with the FULL text of its source row.
The parsed name is a convenience; the body is the evidence.

Only REGULATIONS are read. The asset freeze binds through the regulation's annex, and the
paired CFSP decision repeats the same entries, so reading both would double every listing.

Nothing here is a derived identifier: an entry is keyed by the act's CELEX, the annex block
and the entry's position in it, all read from the source.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from bs4 import BeautifulSoup

_REG_REF = re.compile(
    r"Regulation\s+\((?:EC|EU)(?:,\s*Euratom)?\)\s+(?:No\s+)?(\d{1,4}/\d{2,4})", re.I)
_ANNEX_REF = re.compile(r"\bAnnex\s+([IVX]+[a-z]?)\b")
_DATE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
_ENTRY_NO = re.compile(r"^[‘'\"“]?\s*(\d{1,5})\s*\.?\s*$")
_PARA_ENTRY = re.compile(r"^[‘'\"“]?\s*(?:\((\d{1,4})\)|(\d{1,4})\.)\s+(.+)$", re.S)


def _action(lead: str) -> Optional[str]:
    """Classify an annex block by its lead sentence. None = not a listing block."""
    s = lead.lower()
    if re.search(r"\bis set out in the annex\b|\blist of .* is replaced by the following\b", s):
        return "list_replaced"
    if "identifying data" in s and "amended" in s:
        return "amended"
    if "replaced by the following" in s or "is replaced by" in s:
        return "replaced"
    if re.search(r"\bdeleted\b", s):
        return "deleted"
    if re.search(r"\b(?:are|is)\s+added\b|\badded (?:to|under)\b|following entr(?:y|ies) (?:is|are) added", s):
        return "added"
    return None


def _subject(text: str) -> Optional[str]:
    s = text.lower()
    if re.search(r"vessel", s):
        return "V"
    if re.search(r"legal persons|entities|entity|bodies|groups", s) and not re.search(
            r"natural persons|persons and entit", s):
        return "E"
    if re.search(r"natural persons|\bpersons\b|individuals|\bperson\b", s):
        return "P"
    return None


def _subject_from_lead(text: str) -> Optional[str]:
    quotes = re.findall(r"‘([^’]{2,200})’", text or "")
    for q in reversed(quotes):
        sub = _subject(q)
        if sub:
            return sub
    return _subject(text)


def _listing_date(text: str) -> Optional[date]:
    m = None
    for m in _DATE.finditer(text or ""):
        pass
    if not m:
        return None
    d, mo, y = (int(x) for x in m.groups())
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def _name_from_text(text: str) -> str:
    """Best-effort name: the text before the first parenthesis, comma or 'Date of birth'."""
    t = re.sub(r"^[‘'\"“\s]+", "", text or "")
    t = re.sub(r"^Name:\s*", "", t)
    t = re.split(r"\s(?:Listed on|IMO\b)", t, 1)[0]
    t = re.split(r"\s(?:Russian|Belarusian|Ukrainian|Persian|Farsi|Arabic|Chinese|Georgian|Burmese|Korean)\s*:|\s(?:original script)\b", t, 1)[0]
    t = re.split(r"\s(?=[\u0400-\u04FF\u0600-\u06FF\u4E00-\u9FFF\u10A0-\u10FF])", t, 1)[0]
    t = re.split(r"\s*(?:\(|,|;|\bDate of birth\b|\bD\.O\.B\b|\bborn\b|\bFunction\b|\bDesignation:)", t, 1)[0]
    return t.strip(" .:’'\"”")[:300]


@dataclass
class Entry:
    block: int
    position: int
    action: str
    base_regulation: Optional[str]
    annex: Optional[str]
    heading: str
    subject_type: Optional[str]
    entry_number: Optional[str]
    name: str
    identifying_info: Optional[str]
    reasons: Optional[str]
    date_of_listing: Optional[date]
    body_txt: str
    body_html: str


@dataclass
class ParsedAct:
    celex: str
    entries: list[Entry] = field(default_factory=list)
    blocks: list[tuple[str, str]] = field(default_factory=list)   # (action, lead sentence)
    notes: list[str] = field(default_factory=list)


_INLINE_ENTRY = re.compile(r"(?:^\s*[‘'\"“]?|(?<=\.)\s+)(\d{1,4})\.\s+(?=[A-Z])")


def _split_inline(tail: str):
    """Split '‘45. NAME ... 46. NAME ...’' into (number, text) pairs."""
    hits = list(_INLINE_ENTRY.finditer(tail))
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(tail)
        body = tail[m.end():end].strip().rstrip("’';. ")
        if body:
            yield m.group(1), body


_ENUM = re.compile(r"^[‘'\"“]?\s*\(?([0-9]{1,5}|[a-z]{1,3}|[ivx]{1,5})[.)]?\s*$", re.I)


def _units(soup: BeautifulSoup):
    """Document-order units: ('row', cells, html) for leaf table rows, ('p', text, html) else."""
    leaf_rows = set()
    for tr in soup.find_all("tr"):
        if not tr.find("table"):
            leaf_rows.add(id(tr))
    for el in soup.find_all(["p", "tr"]):
        if el.name == "tr":
            if id(el) in leaf_rows:
                cells = [c.get_text(" ", strip=True) for c in el.find_all(["td", "th"], recursive=False)]
                yield ("row", cells, str(el))
            continue
        tr = el.find_parent("tr")
        if tr is not None and id(tr) in leaf_rows:
            continue                      # consumed by its row
        yield ("p", el.get_text(" ", strip=True), str(el))


def parse_act(celex: str, html: str, title: str = "") -> ParsedAct:
    soup = BeautifulSoup(html, "html.parser")
    out = ParsedAct(celex=celex)
    units = list(_units(soup))
    own = re.search(r"\b(\d{4}/\d{1,5})\b", title or "")
    refs = [m for m in _REG_REF.finditer(title or "") if not (own and m.group(1) == own.group(1))]
    title_base = refs[-1] if refs else None
    start = None
    for i, (kind, val, _) in enumerate(units):
        t = val if kind == "p" else " ".join(val)
        if re.fullmatch(r"ANNEX(?:\s+[IVX]+)?", t.strip()):
            start = i
            break
    if start is None:
        out.notes.append("no ANNEX marker found")
        return out

    st = {"base": title_base.group(1) if title_base else None, "annex": None, "action": None,
          "heading": "", "subject": None, "block": -1, "pos": 0, "para": None, "enum": None}
    # A whole list set out in the annex is announced in the ARTICLES, before the annex.
    for kind, val, _ in units[:start]:
        t = val if kind == "p" else " ".join(val)
        if re.search(r"is set out in the Annex to this Regulation", t):
            mr = _REG_REF.search(t)
            st.update(action="list_replaced", block=0, heading=t[:600],
                      base=mr.group(1) if mr else st["base"])
            ma = _ANNEX_REF.search(t)
            st["annex"] = ma.group(1) if ma else None
            out.blocks.append(("list_replaced", t[:300]))
            break

    def flush():
        para = st["para"]
        if para and st["action"]:
            txt = para["text"].strip()
            out.entries.append(Entry(
                block=st["block"], position=st["pos"], action=st["action"], base_regulation=st["base"],
                annex=st["annex"], heading=st["heading"], subject_type=st["subject"],
                entry_number=para["no"], name=_name_from_text(para["first"]), identifying_info=None,
                reasons=None,
                date_of_listing=_listing_date(txt) if "Date of listing" in txt else None,
                body_txt=txt, body_html=para["html"]))
            st["pos"] += 1
        st["para"] = None

    def line(text: str, enum: Optional[str], html_: str):
        """A paragraph-like line: lead sentence, sub-heading, entry start or continuation."""
        if re.match(r"^(?:is|are) replaced by the following", text):
            if st["para"] is not None:
                st["para"]["text"] += "\n" + text
            return
        if re.fullmatch(r"\((\d{1,4}|[a-z]{1,3})\)", text.strip()):
            flush()
            st["enum"] = text.strip()[1:-1]
            return
        is_lead_shape = text.endswith(":") or bool(re.search(r":\s*[‘'\"“]\s*\d{1,4}\.", text)) or "set out in the Annex" in text or text.rstrip().endswith("following")
        lead_part = text.split(":", 1)[0] + ":" if re.search(r":\s*[‘'\"“]\s*\d{1,4}\.", text) else text
        new_action = _action(lead_part) if is_lead_shape and len(lead_part) < 700 else None
        if new_action:
            flush()
            st.update(action=new_action, block=st["block"] + 1, pos=0, heading=text[:600])
            mr = _REG_REF.search(text)
            if mr:
                st["base"] = mr.group(1)
            ma = _ANNEX_REF.search(text)
            if ma:
                st["annex"] = ma.group(1)
            st["subject"] = _subject_from_lead(text) or st["subject"]
            out.blocks.append((new_action, text[:300]))
            # Entries can follow the colon in the same cell (1183/2005 acts).
            tail = text[len(lead_part):] if lead_part != text else ""
            if tail:
                for no, body in _split_inline(tail):
                    st["para"] = {"no": no, "first": body, "text": body, "html": html_}
                    flush()
            return
        if re.search(r"is amended as follows:?$", text) or re.search(r"is amended in accordance with", text):
            flush()
            mr = _REG_REF.search(text)
            if mr:
                st["base"] = mr.group(1)
            ma = _ANNEX_REF.search(text)
            if ma:
                st["annex"] = ma.group(1)
            return
        if len(text) < 90 and re.fullmatch(
                r"(?:[A-Z]\.\s*|[a-z]\)\s*)?(?:Natural persons|Persons|Entities|Legal persons[^.]{0,60}|"
                r"Individuals[^.]{0,60}|Vessels|List of (?:persons|entities)[^.]{0,80})[.:]?", text, re.I):
            flush()
            st["subject"] = _subject(text)
            return
        if not st["action"]:
            return
        if enum is None and st["enum"] is not None:
            enum, st["enum"] = st["enum"], None
        m = _PARA_ENTRY.match(text) if enum is None else None
        if enum is not None:
            flush()
            st["para"] = {"no": enum if re.fullmatch(r"\d{1,5}", enum) else None,
                          "first": text, "text": text, "html": html_}
            return
        if m:
            flush()
            st["para"] = {"no": m.group(1) or m.group(2), "first": m.group(3), "text": text, "html": html_}
            return
        if st["para"] is not None:
            st["para"]["text"] += "\n" + text
            st["para"]["html"] += html_

    for kind, val, html_ in units[start + 1:]:
        first = val if kind == "p" else " ".join(val)
        if re.match(r"^(?:ELI:|ISSN\b)", (first or "").strip()):
            break                                   # end of the act: OJ footer
        if re.fullmatch(r"ANNEX(?:\s+[IVX]+)?", (first or "").strip()):
            flush()                                 # a second annex: keep reading, add nothing
            continue
        if kind == "p":
            if val:
                line(val, None, html_)
            continue
        cells = [c for c in val if c is not None]
        while cells and not cells[0].strip():
            cells = cells[1:]
        if not any(cells):
            continue
        joined = " ".join(cells)
        if re.search(r"\bNames?\b", joined) and re.search(r"Identifying information|Reasons|Date of listing", joined):
            continue
        mno = _ENTRY_NO.match(cells[0]) if cells else None
        if st["action"] and mno and len(cells) >= 3:
            flush()
            rest = cells[1:]
            out.entries.append(Entry(
                block=st["block"], position=st["pos"], action=st["action"], base_regulation=st["base"],
                annex=st["annex"], heading=st["heading"], subject_type=st["subject"], entry_number=mno.group(1),
                name=_name_from_text(rest[0]),
                identifying_info=rest[1] if len(rest) > 1 else None,
                reasons=rest[2] if len(rest) > 2 else None,
                date_of_listing=_listing_date(rest[3]) if len(rest) > 3 else None,
                body_txt="\n".join(cells), body_html=html_))
            st["pos"] += 1
            continue
        if len(cells) == 2 and _ENUM.match(cells[0]):
            line(cells[1], _ENUM.match(cells[0]).group(1), html_)
            continue
        line(joined, None, html_)
    flush()
    return out
