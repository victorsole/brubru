"""
Official Journal daily-view scraper (the MEUB "My OJ" feature).

NO LLM / NO Anthropic. Pure HTML parsing of the EUR-Lex OJ daily views, which
are WAF-walled (the caller fetches them through WafBrowserFetcher).

Source pages (one per series per day):
    https://eur-lex.europa.eu/oj/daily-view/L-series/default.html?ojDate=DDMMYYYY
    https://eur-lex.europa.eu/oj/daily-view/C-series/default.html?ojDate=DDMMYYYY

DOM (both series share it): a category (Regulations / Decisions / ...) contains
act-type sub-groups ("Implementing Regulation of the Commission"), each listing
acts as:

    <div class="col-md-2"><div class="section-level-3">2026/1144</div></div>
    <div class="col-md-7 defaultUnderlined">
      <a href="./../../../legal-content/EN/TXT/?uri=OJ:L_202601144">
        Commission Implementing Regulation (EU) 2026/1144 of 28 May 2026 laying down ...
      </a>
    </div>

From each act we get: the OJ number (2026/1144), the OJ id (L_202601144), the
EUR-Lex URL, and a title that states the act type + institution + subject. We
derive the CELEX (for L-series legislation) so an act can be matched back to a
tracked legislative carriage / adopted text in MEUB.
"""

from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

OJ_BASE = "https://eur-lex.europa.eu"
_DAILY = OJ_BASE + "/oj/daily-view/{series}-series/default.html?ojDate={d}"

_TAG_RE = re.compile(r"<[^>]+>")
# One act row: OJ number cell + linked title cell.
_ROW_RE = re.compile(
    r'<div class="section-level-3">\s*((?:[A-Z]/)?[0-9]{4}/[0-9]+)\s*</div>.*?'
    r'<a\s+href="([^"]+)"[^>]*>(.*?)</a>',
    re.S,
)
_OJID_RE = re.compile(r"uri=OJ:([A-Z]_\d+)", re.I)


def daily_view_url(d: date, series: str) -> str:
    return _DAILY.format(series=series.upper(), d=f"{d.day:02d}{d.month:02d}{d.year}")


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(_TAG_RE.sub("", s or ""))).replace("\xa0", " ").strip()


def _absolute(href: str) -> str:
    href = _html.unescape(href or "")
    if href.startswith("http"):
        return href
    return OJ_BASE + "/" + href.lstrip("./")


# ---- title -> structured facets ------------------------------------------

def derive_act_type(title: str) -> str:
    t = title.lower()
    if "implementing regulation" in t: return "Implementing Regulation"
    if "delegated regulation" in t: return "Delegated Regulation"
    if "regulation" in t: return "Regulation"
    if "implementing decision" in t: return "Implementing Decision"
    if "delegated decision" in t: return "Delegated Decision"
    if "decision" in t: return "Decision"
    if "directive" in t: return "Directive"
    if "recommendation" in t: return "Recommendation"
    if "guideline" in t: return "Guideline"
    if "communication" in t: return "Communication"
    if "opinion" in t: return "Opinion"
    if "resolution" in t: return "Resolution"
    if "notice" in t or "call for" in t: return "Notice"
    if "agreement" in t or "protocol" in t: return "Agreement"
    if "corrigendum" in t: return "Corrigendum"
    return "Other"


def derive_institution(title: str) -> str:
    # Anchor on the ENACTING institution, which leads the title. Titles often
    # CITE other acts ("... of Regulation (EU) No 952/2013 of the European
    # Parliament and of the Council ..."), so scanning the whole string misfires.
    head = (title or "").lower()[:70]
    if head.startswith("commission") or head.startswith("eu–") or "commission implementing" in head \
            or "commission delegated" in head:
        return "Commission"
    if head.startswith("council") or "political and security committee" in head:
        return "Council"
    if head.startswith("european central bank") or "(ecb" in head:
        return "European Central Bank"
    if "court of justice" in head or "general court" in head or "court of auditors" in head:
        return "Court of Justice"
    if head.startswith("european parliament"):
        return "European Parliament"
    # Prefix-less Regulation/Directive/Decision = co-legislated act of the
    # European Parliament and of the Council.
    if head.startswith(("regulation", "directive", "decision")):
        return "European Parliament and Council"
    return "Other EU body"


def category_for(act_type: str, series: str) -> str:
    if series.upper() == "C":
        return "Information and notices"
    return {
        "Regulation": "Regulations", "Implementing Regulation": "Regulations",
        "Delegated Regulation": "Regulations",
        "Decision": "Decisions", "Implementing Decision": "Decisions",
        "Delegated Decision": "Decisions",
        "Directive": "Directives",
    }.get(act_type, "Other acts")


_CELEX_LETTER = {
    "Regulation": "R", "Implementing Regulation": "R", "Delegated Regulation": "R",
    "Directive": "L",
    "Decision": "D", "Implementing Decision": "D", "Delegated Decision": "D",
    "Recommendation": "H",
}


def derive_celex(oj_number: str, act_type: str, series: str) -> Optional[str]:
    """L-series legislation -> a 3xxxx CELEX (the join key to MEUB carriages)."""
    if series.upper() != "L":
        return None
    letter = _CELEX_LETTER.get(act_type)
    m = re.match(r"(\d{4})/(\d+)", oj_number or "")
    if not letter or not m:
        return None
    year, num = m.group(1), int(m.group(2))
    return f"3{year}{letter}{num:04d}"


# What the act DOES to the legal order — parsed from the title verb. Order =
# priority (an act that "renews an authorisation ... repealing the old one" is
# primarily a renewal). This is the "what it changes" tag.
_CHANGE_RULES = [
    ("corrects", ("corrigendum", "correcting", "rectifying")),
    ("renews", ("renewal of the authorisation", "renewing", "renewal of authorisation")),
    ("repeals", ("repealing", "repeals")),
    ("amends", ("amending", "amends")),
    ("extends", ("extending", "prolonging")),
    ("suspends", ("suspending",)),
]

# Plain-language topic clusters (first match wins). Keyword -> theme.
_THEME_RULES = [
    ("Feed additives", ("feed additive", "feed additives", "as a feed additive")),
    ("Plant protection", ("active substance", "plant protection", "1107/2009", "pesticide", "maximum residue")),
    ("Fisheries", ("fish", "fisher", "aquacult", "fishing", "marine", "maritime")),
    ("Customs & tariffs", ("customs", "tariff", "common customs", "duties", "tariff quota")),
    ("Sanctions (CFSP)", ("(cfsp)", "restrictive measures", "sanction")),
    ("State aid", ("state aid", "articles 107 and 108")),
    ("Animal health", ("african swine fever", "animal health", "disease control", "veterinary")),
    ("Trade defence", ("anti-dumping", "anti-subsidy", "countervailing", "definitive duty")),
    ("Biocides", ("biocidal", "biocide")),
    ("Food safety", ("foodstuff", "novel food", "contaminant", "food additive", "food safety", "hygiene")),
    ("Agriculture & CAP", ("agricultural", "eafrd", "eagf", "cap strategic", "rural development", "wine", "organic")),
    ("Financial & monetary", ("european central bank", "(ecb", "monetary", "credit institution", "prudential")),
    ("Justice & security", ("schengen", "search portal", "europol", "judicial", "police")),
    ("Migration & borders", ("asylum", "migration", "border", "visa")),
]


def derive_change_kind(title: str) -> str:
    t = (title or "").lower()
    for kind, kws in _CHANGE_RULES:
        if any(k in t for k in kws):
            return kind
    return "new"


def derive_theme(title: str) -> str:
    t = (title or "").lower()
    for theme, kws in _THEME_RULES:
        if any(k in t for k in kws):
            return theme
    return "Other"


@dataclass
class OjAct:
    oj_number: str
    oj_id: Optional[str]
    title: str
    url: str
    act_type: str
    category: str
    institution: str
    celex: Optional[str]
    series: str
    change_kind: str = "new"
    theme: str = "Other"


def parse_daily_view(html: str, series: str) -> List[OjAct]:
    """Parse one OJ daily-view page into a de-duplicated list of acts."""
    acts: List[OjAct] = []
    seen: set = set()
    for m in _ROW_RE.finditer(html or ""):
        oj_number, href, title_html = m.group(1), m.group(2), m.group(3)
        title = _clean(title_html)
        if not title:
            continue
        oj_id_m = _OJID_RE.search(href)
        oj_id = oj_id_m.group(1) if oj_id_m else None
        key = oj_id or oj_number
        if key in seen:
            continue
        seen.add(key)
        act_type = derive_act_type(title)
        acts.append(OjAct(
            oj_number=oj_number,
            oj_id=oj_id,
            title=title,
            url=_absolute(href),
            act_type=act_type,
            category=category_for(act_type, series),
            institution=derive_institution(title),
            celex=derive_celex(oj_number, act_type, series),
            series=series.upper(),
            change_kind=derive_change_kind(title),
            theme=derive_theme(title),
        ))
    return acts
