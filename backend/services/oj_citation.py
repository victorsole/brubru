"""The Official Journal citation of an act, written as EU acts cite each other.

One copy for every writer of eu_laws.oj_reference (the daily OJ sync, fill_eu_laws_oj_reference.py) and for the
lookup route that reads it (v2 /eur-lex/oj/{series}/{year}/{number}). Until 17 Oct 2026 the column held five shapes
from three writers ("L 119/1", "L 2025/40, p. 1", "OJ L, 2026/1672, 10.9.2026", "P 065/1173", empty), and the route
found none of the 3,565 acts stored as "L 2025/40, p. 1" (PPWR, the Data Act).

The forms, as the acts' own texts print them (read 17 Oct 2026 in the stored texts of the GDPR, PPWR and others):
  - act-by-act publication (OJ L and OJ C since 1 October 2023): "OJ L, 2025/40, 22.1.2025": series, the act's
    OJ year and number, publication date; no page;
  - an issue (until 30 September 2023): "OJ L 119, 4.5.2016, p. 1": series, issue number, publication date, first
    page; a supplement issue keeps its letter after a space: "OJ L 445 I, 13.12.2021, p. 1";
  - before 1968 the OJ had no L and C series: "OJ 56, 4.4.1964, p. 850".
Cellar states the parts. An act-by-act act carries official-journal-act_* on its own work; an older act links its
issue (resource_legal_published_in_official-journal), whose work_id_document "oj:JOL_2022_322_I" names series
(JOL, JOC, JOP), year, issue number and supplement (R: the regular issue). The publication date is the issue's
publication_general_date_publication: the date in the act's Formex file is its adoption (GDPR 27.4.2016, published
4.5.2016).
"""
from __future__ import annotations

import re
from datetime import date
from typing import Optional, Tuple, Union

Num = Union[int, str]

# work_id_document of an OJ issue: "oj:JOL_2016_119_R" (regular issue), "oj:JOC_2021_052_I" (supplement I),
# "oj:JOP_1962_013_R" (before 1968, no series letter)
_OJ_ID = re.compile(r"^(?:oj:)?JO([LCP])_(\d{4})_0*(\d+)_([A-Z]{1,2})$")

# the citations this module writes, nothing else
OFFICIAL = re.compile(r"^OJ (?:[LC], \d{4}/\d+, \d{1,2}\.\d{1,2}\.\d{4}"
                      r"|(?:[LC] )?\d+(?: [A-Z]{1,2})?, \d{1,2}\.\d{1,2}\.\d{4}(?:, p\. \d+)?)$")
# the same test in PostgreSQL (ARE): no \d, no non-capturing groups
OFFICIAL_SQL = (r"^OJ ([LC], [0-9]{4}/[0-9]+, [0-9]{1,2}\.[0-9]{1,2}\.[0-9]{4}"
                r"|([LC] )?[0-9]+( [A-Z]{1,2})?, [0-9]{1,2}\.[0-9]{1,2}\.[0-9]{4}(, p\. [0-9]+)?)$")


def _day(d: date) -> str:
    return f"{d.day}.{d.month}.{d.year}"


def act_citation(series: str, year: Num, number: Num, published: date) -> str:
    """Act-by-act publication: "OJ L, 2025/40, 22.1.2025"."""
    return f"OJ {series}, {int(year)}/{int(number)}, {_day(published)}"


def issue_citation(series: str, issue: Num, published: date, page: Optional[Num] = None, supplement: str = "") -> str:
    """An issue: "OJ L 119, 4.5.2016, p. 1"; series "" before 1968: "OJ 56, 4.4.1964, p. 850"."""
    head = f"OJ {series} {int(issue)}" if series else f"OJ {int(issue)}"
    if supplement:
        head += f" {supplement}"
    first = str(page).lstrip("0") if page is not None else ""
    return f"{head}, {_day(published)}" + (f", p. {first}" if first.isdigit() else "")


def parse_oj_id(oj_id: str) -> Optional[Tuple[str, int, int, str]]:
    """"oj:JOL_2022_322_I" -> ("L", 2022, 322, "I"); "oj:JOP_1962_013_R" -> ("", 1962, 13, ""); else None."""
    m = _OJ_ID.match(oj_id or "")
    if not m:
        return None
    series = "" if m.group(1) == "P" else m.group(1)
    return series, int(m.group(2)), int(m.group(3)), ("" if m.group(4) == "R" else m.group(4))


# the shapes written before 17 Oct 2026, kept readable for a row the fill could not resolve
_EXPORT_ISSUE = re.compile(r"^([LCP]) 0*(\d+)([A-Z]{0,2})/(\d+)$")      # "L 119/1", "L 322I/614", "P 065/1173"


def export_issue_parts(stored: Optional[str]) -> Optional[Tuple[str, int, str, int]]:
    """The export's "L 119/1" -> ("L", 119, "", 1); "L 322I/614" -> ("L", 322, "I", 614); "P 065/1173" -> ("", 65, "", 1173)."""
    m = _EXPORT_ISSUE.match(stored or "")
    if not m:
        return None
    return ("" if m.group(1) == "P" else m.group(1)), int(m.group(2)), m.group(3), int(m.group(4))
