"""
GI geographical-area extractor.

Given an EU geographical indication, resolve its documents, fetch the right one,
and extract the "geographical area" (the demarcation) that a map is drawn from.

Everything here is the distilled result of the 2 Jul 2026 probes (see memory
project_gi_maps_and_gi_folder). The hard-won rules, all encoded below:

  * Merge document links from BOTH the GIView detail API AND eAmbrosia: neither is
    complete on its own (3 Riberas only resolves because GIView carries the OJ link
    eAmbrosia lacks).
  * Prefer the English rendition at fetch time: EUR-Lex serves every act in all 24
    languages, so normalise `/XX/ALL|TXT/` -> `/EN/TXT/`, `uriserv:...` lang -> ENG,
    and accept `data.europa.eu/eli` links (GIView uses those, not eur-lex.europa.eu).
  * The Ares attachment host in the JSON APIs (webgate.ec.europa.eu/eambrosia-api)
    is 500-broken; the working host is the register UI's eambrosia-public-api
    (returns HTTP 202 + %PDF). Retry transient failures.
  * Match the PRECISE demarcation heading, multilingual, never any heading that
    merely contains "geographical area" (that grabs Link / Specificity / Varieties
    / Processing / Packaging / Condition sections). Reject filename and checkbox
    captures. Name-scope multi-GI gazette pages.

Section numbers are unstable across regimes and product types (wine 2024/1143 = 9,
wine 2019/33 = 6, foodstuff = 4 or 4.3, spirit 2019/787 = 1.4), so extraction is
heading-driven, never number-driven.

Playwright is required for EUR-Lex (JS-WAF); PDFs go through requests + pypdf.
"""
from __future__ import annotations

import io
import re
import time

import requests

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

EAMBROSIA_REGISTER = "https://webgate.ec.europa.eu/eambrosia-api/api/v1/geographical-indications"
GIVIEW_DETAIL = "https://www.tmdn.org/giview/api/geographical-indications"
# The WORKING attachment host (the JSON-API host webgate.ec.europa.eu/eambrosia-api 500s).
ATTACHMENT_HOST = "https://ec.europa.eu/geographical-indications-register/eambrosia-public-api/api/v1/attachments"

# --- multilingual demarcation-heading detection (all 24 EU languages) --------
# The geo-area noun phrase in every EU official language, incl. Greek and Cyrillic
# (Bulgarian). Section numbers are unstable across regimes; the LANGUAGE of the
# heading follows the origin country, so the lexicon must be complete. \w with
# re.UNICODE covers Greek/Cyrillic letters.
_GEO_NOUN = re.compile(
    r"("
    r"geographical area|"                                   # EN
    r"zona geogr[áa]fica|[áa]rea geogr[áa]fica|"            # ES / PT
    r"aire g[ée]ographique|zone g[ée]ographique|"          # FR
    r"zona geografica|area geografica|"                     # IT
    r"geografisch\w*\s+gebied|"                             # NL
    r"geograf\w*\s+gebiet|"                                 # DE
    r"γεωγραφικ\w*\s+περιοχ\w*|"  # EL γεωγραφικ* περιοχ*
    r"географск\w*\s+район\w*|"        # BG географск* район*
    r"zem[ěe]pisn\w*\s+oblast\w*|"                          # CS/SK
    r"geograficzn\w*\s+obszar\w*|obszar\w*\s+geograficzn\w*|"  # PL
    r"ari\w*\s+geografic\w*|zon\w*\s+geografic\w*|"         # RO
    r"f[öo]ldrajzi\s+ter[üu]let\w*|"                        # HU
    r"zemljopisn\w*\s+podru[čc]j\w*|"                       # HR
    r"geografsk\w*\s+obmo[čc]j\w*|"                         # SI
    r"geografisk\w*\s+omr[åa]d\w*|"                         # DA/SV
    r"maantieteellis\w*\s+alue\w*|"                         # FI
    r"geograafilin\w*\s+piirkon\w*|"                        # ET
    r"[ģg]eogr[āa]fisk\w*\s+apgabal\w*|"                    # LV
    r"geografin\w*\s+vietov\w*|"                            # LT
    r"[żz]ona\s+[ġg]eografik\w*|"                           # MT
    # WINE single-document (Reg 2019/33) titles the demarcation "delimited/
    # demarcated area" with no "geographical" word -> match it directly.
    r"(?:zona|[áa]rea|aire|zone|regi[óo]n|regione|regi[ãa]o)\s+(?:delimit\w+|d[ée]limit\w+|demarcad\w+)|"
    r"demarcated area|delimited area|covered area|"
    r"abgegrenzt\w*\s+gebiet|afgebakend\s+gebied|"
    r"zon[ăa]\s+delimitat\w*|vymezen[ée]\s+[úu]zem\w*|behat[áa]rolt\s+ter[üu]let|"  # RO/CS/HU wine
    # Greek + Bulgarian (Cyrillic) wine demarcation: "demarcated area" / "defined
    # district" — NOT "geographical area". Foundational Cyrillic pattern for later
    # Macedonian/Russian/Ukrainian (определен/визначений район).
    r"οριοθετημ\w*\s+(?:περιοχ|ζών)\w*|"           # EL ΟΡΙΟΘΕΤΗΜΕΝΗ ΠΕΡΙΟΧΗ/ΖΩΝΗ
    r"οριοθ[έε]τηση\s+τη[ςσ]\s+περιοχ\w*|"        # EL delimitation of the area
    r"определен\w*\s+район\w*|"                   # BG ОПРЕДЕЛЕН РАЙОН
    r"ograni[čc]en\w*\s+podru[čc]j\w*|"           # HR OGRANIČENO PODRUČJE (delimited area)
    r"omejen\w*\s+obmo[čc]j\w*|vymedzen\w*\s+oblas\w*"  # SI omejeno območje / SK vymedzená oblasť
    r")", re.I | re.U)
# Definition / delimitation qualifier (or the heading is standalone-short).
_QUAL = re.compile(
    r"(definition|delimitation|demarcat|defined|define|description|concise|"
    r"d[ée]limitation|d[ée]finition|delimitaci[óo]n|definici[óo]n|descripci[óo]n|"
    r"delimitazione|definizione|descrizione|delimita[çc][ãa]o|defini[çc][ãa]o|"
    r"descri[çc][ãa]o|abgegrenzt|festlegung|bestimmung|beschreibung|abgrenzung|"
    r"afgebakend|omschrijving|definitie|beschrijving|beknopte|sucinta|concisa|breve|brief|"
    r"οριοθετ|καθορισμ|συνοπτικ|ορισμ|περιγραφ|"  # EL οριοθετ/καθορισμ/συνοπτικ/ορισμ/περιγραφ
    r"определ|кратк|описан|"  # BG определ/кратк/описан
    r"vymez\w*|stru[čc]n\w*|definic\w*|okre[śs]len\w*|zwi[ęe]z\w*|wyznacz\w*|"     # CS/SK/PL
    r"delimit\w*|defini\w*|concis\w*|descri\w*|"                                   # RO
    r"meghat[áa]roz\w*|k[öo]r[üu]lhat[áa]rol\w*|le[íi]r[áa]s|"                      # HU
    r"odre[đd]iv\w*|sa[žz]et\w*|opredelit\w*|dolo[čc]it\w*|"                        # HR/SI
    r"afgr[æa]ns\w*|kortfattet|kortfattad|avgr[äa]ns\w*|"                          # DA/SV
    r"raja\w*|m[ää][ää]ritel\w*|tiivistel\w*|m[ää]ratlus|"                          # FI/ET
    r"robe[žz]\w*|kodol[īi]g\w*|apibr[ėe][žz]\w*|glaust\w*|nustatym\w*)", re.I | re.U)
# Sections that ALSO contain the geo-area noun but are NOT the demarcation.
_NEG = re.compile(
    r"(\blink\b|\blien\b|v[íi]nculo|enlace|legame|verband|verbindung|liga[çc][ãa]o|"
    r"leg[ăa]tur\w*|souvislost|zwi[ąa]zek|kapcsolat|povezanost|povezav\w*|"          # link (RO/CS/PL/HU/HR/SI)
    r"δεσμ|връзк|"                        # EL δεσμ / BG връзк (link)
    r"specificit|sp[ée]cificit|especificidad|specificit[àa]|especificidade|"
    r"ιδιαιτερ|специфич|"  # EL ιδιαιτερ / BG специфич
    r"variet|vari[ée]t|variedad|druiven|\bras\b|rebsorte|castas|c[ée]pages|"
    r"odr[ůu]d\w*|odmian\w*|szőlőfajt|sort\w*|ποικιλ|"   # variety (CS/PL/HU/BG/EL ποικιλ)
    r"influen|invloed|einfluss|processing|transformation|transformaci[óo]n|lavorazione|"
    r"verwerking|verarbeitung|packaging|bottling|embotellado|envasado|acondicionamiento|"
    r"conditionnement|transport|\bstep|[ée]tape|\betapa|\bstap|schritt|\bproof|preuve|"
    r"prueba|bewijs|nachweis|\bmethod|m[ée]thode|m[ée]todo|\bmetodo|methode|verfahren|"
    r"inspection|control body|complementari|further condition|requirement|change to|"
    r"derogation|derogare|eltérés|elt[ée]r[ée]s|"                 # derogation (EN/RO/HU)
    r"προϋποθέσ|εθνικ\w*\s+νομοθεσ|μεθοδολογ|"  # EL conditions / national legislation / methodology
    r"feltétel|felt[ée]tel|"                                       # HU condition
    r"condi[țt]i\w*|podmínk\w*|podmienk\w*|warunk\w*|pogoj\w*|"      # condition RO/CS/SK/PL/SI
    r"\bmaps?\b|\bmapa|mappa|\bcarte\b|χάρτ|\bκαρτ|карт)", re.I | re.U)  # maps sub-item (all scripts)
_NEXTH = re.compile(r"^(\d+(\.\d+)*\.?|\([a-z]\)|[a-z]\)|[A-Z]\.)\s+\S")
# Place descriptors across EU languages, for the clean-vs-needs_review confidence call.
_PLACE = re.compile(
    r"municip|provinc|comarca|t[eé]rmino|isla|comunidad|region|r[ée]gion|territ|valle|"
    r"sierra|\br[íi]o\b|border|grens|Land|kingdom|koninkrijk|gemeente|arrondissement|"
    r"d[ée]part|island|entire|whole|"
    r"νομ|δ[ήη]μ|περιφ[έε]ρει|κοιν[όο]τητ|επαρχ|"          # EL prefecture/municipality/region
    r"област|община|"                                       # BG region/municipality
    r"jude[țt]|comun\w*|ora[șs]|"                            # RO county/commune/town
    r"\bkraj\b|okres|\bobec\b|"                              # CS/SK
    r"gmin\w*|powiat|wojew[óo]dztw|"                         # PL
    r"megye|j[áa]r[áa]s|telep[üu]l[ée]s|"                    # HU
    r"op[ćc]in\w*|[žz]upanij\w*|ob[čc]in\w*|"                # HR/SI
    r"kommun\w*|maakun\w*|\bkunta\b|l[äa][äa]n|"             # Nordic/FI
    r"freguesi|villagg|\bilha\b|concello|bundesland|землищ|\btoda?\b|\btutt[oa]\b|"  # PT/IT/BG + whole
    r"comprises|comprende|circunscrit|очертан|constitu[ií]d", re.I | re.U)
# Reject a "heading" that is really a mid-sentence OCR fragment (starts with a preposition).
_FRAG = re.compile(r"^(of|des|della|dell'|van de|van het|της|του|van)\b", re.I | re.U)
# Reject a body that is a competent-authority / control-body address, not a demarcation.
_AUTHORITY = re.compile(
    r"directorate|minist[eèé]r|ministerio|ministero|ministri|directie|dirécción|"
    r"agriculture directorate|competent authorit|control body|inspection body|"
    r"Δ/νση|Διεύθυνση|υπουργ", re.I | re.U)
# Reject a body that opens with a LINK / history / specificity narrative (a generic
# "geographical area" heading whose content is actually the causal-link section).
_LINK_BODY = re.compile(
    r"^(α\.?\s*)?(ιστορικ|ιδιαιτερ|δεσμ|link\b|historical|causal|"
    r"v[íi]nculo|legame|verband|zusammenhang|lien\b|връзка|специфич|особен|"
    r"\(?φεκ|\(?φ\.ε\.κ|αριθ\w*\s+πρωτ)", re.I | re.U)  # + Greek gazette/legal ref (ΦΕΚ...)
# A body that is a hard-wrong section (history / method / product / derogation-proximity /
# amendment / table-of-contents / condition) -> not a demarcation. Mirrors the verification
# pass so the extractor never selects these and the real demarcation wins.
_WRONG_BODY = re.compile(
    r"^\W*(d\)\s*)?(antecedent|alrededor del a[ñn]o|geschicht|storia|"
    r"m[ée]todo\b|method\b|obtention|obtenci[óo]n|processing|trasformazione|transforma[çc]|"
    r"organolept|eigenschap|proprietà|"
    r"d[ée]rogat|derogaz|proximit[éa]|aire de proximit|"
    r"modificat|modification|modifi[ée]|cahier des charges est modifi|standard amendment|ref\.?\s*ares|"
    r"prueba del origen|cadre juridique|type de condition|"
    r"description (of|de) (the|la) condition|descripci[óo]n de la condici[óo]n|"
    r"beschrijving van de voorwaarde)", re.I | re.U)


def _strip_num(line: str) -> str:
    return re.sub(r"^(\d+(\.\d+)*\.?|\([a-z]\)|[a-z]\)|[A-Z]\.)\s*", "",
                  re.sub(r"\s+", " ", line)).strip()


def _is_demarcation_heading(core: str) -> bool:
    low = core.lower()
    if ".doc" in low or ".pdf" in low:          # filename mistaken for a heading
        return False
    if _NEG.search(core) or not _GEO_NOUN.search(core):
        return False
    return bool(_QUAL.search(core)) or len(core) < 45


def extract_geo(text: str, name: str | None = None, is_pdf: bool = False,
                multi_gi: bool = False) -> tuple[str, str] | None:
    """Return (heading, area_text) of the demarcation, or None. Name-scopes ONLY
    genuine multi-GI gazette pages (EUR-Lex :FULL/:TOC, passed via multi_gi) to the
    block for this GI. A large single-GI document (a technical file, or a long
    standard-amendment) is one GI: never scope it, or its demarcation deep in the
    doc (Friuli at line ~1666, Greek wine at ~17k chars) gets truncated away."""
    if name and multi_gi and len(text) > 45000 and name.split()[0] in text:
        i = text.find(name)
        text = text[i:i + 16000]
    lines = [l.strip() for l in text.split("\n")]
    cands: list[tuple[str, str]] = []
    for i, l in enumerate(lines):
        if not l or len(l) > 3000:
            continue
        # Old summary format puts heading AND content on one long line:
        # "4.3 Geographical area: ...covers the departments of Haute-Corse and...".
        # So test the part BEFORE the colon as the heading, take the rest as content.
        # (The len(core) > 90 guard below still rejects non-heading sentences.)
        head_part = l.split(":", 1)[0] if ":" in l else l
        core = _strip_num(head_part)
        if _FRAG.match(core) or len(core) > 90:          # OCR fragment or a full sentence, not a heading
            continue
        if _is_demarcation_heading(core):
            out: list[str] = []
            if ":" in l:
                inline = l.split(":", 1)[1].strip()
                if inline:
                    out.append(inline)
            for l2 in lines[i + 1:i + 45]:
                if not l2:
                    continue
                if _NEXTH.match(l2) and len(l2) < 90:
                    break
                out.append(l2)
                if sum(len(x) for x in out) > 600:
                    break
            body = " ".join(out).strip()
            if re.search(r"☒|☐", body) or len(body) < 20:   # reject checkbox forms / empties
                continue
            if _AUTHORITY.search(body[:120]):            # authority address, not a demarcation
                continue
            if _LINK_BODY.match(body):                   # link/history narrative, not a demarcation
                continue
            if _WRONG_BODY.match(body):                  # method/derogation/amendment/ToC, not a demarcation
                continue
            cands.append((l, body))
    if not cands:
        return None
    best = max(cands, key=lambda hb: (2 if _PLACE.search(hb[1]) else 0) * 1000 + len(hb[1]))
    return best[0][:120], best[1]


def prefer_en(url: str) -> str:
    """Normalise an EUR-Lex / OJ URL to its English full-text rendition."""
    url = re.sub(r"/[A-Z]{2}/(TXT|ALL)", "/EN/TXT", url)
    url = re.sub(r"\.01\.[A-Z]{3}", ".01.ENG", url)
    url = re.sub(r"uriserv:OJ\.([CL])_\.(\d+)\.(\d+)\.(\d+)\.(\d+)\.[A-Z]{3}",
                 r"uriserv:OJ.\1_.\2.\3.\4.\5.ENG", url)
    return url


def confidence_of(area: str) -> str:
    if re.search(r"☒|☐|\.doc|\.pdf", area) or _NEG.search(area[:70]):
        return "needs_review"
    return "clean" if _PLACE.search(area) else "needs_review"


def _pdf_text(data: bytes) -> str | None:
    """Extract PDF text. PyMuPDF preserves reading order far better than pypdf
    (pypdf scrambles multi-column single-document layouts, separating the
    demarcation heading from its content); fall back to pypdf if fitz fails."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=data, filetype="pdf")
        # sort=True orders text blocks by position (top-to-bottom, left-to-right),
        # which keeps a section's content with its heading in multi-column single
        # documents that otherwise scramble (heading flow vs content flow).
        return "\n".join(page.get_text("text", sort=True) for page in doc)
    except Exception:
        try:
            from pypdf import PdfReader
            return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
        except Exception:
            return None


def extract_nuts(text: str) -> list[str]:
    """Pull NUTS region codes the single document states directly (it has a
    'NUTS area' / 'Περιοχή NUTS' field). e.g. GR14, GR133, ITH2, ES52. This is
    machine-readable geography straight from the source, region-level."""
    out: list[str] = []
    lines = text.split("\n")
    for i, l in enumerate(lines):
        if re.search(r"\bNUTS\b|Περιοχ[ήη]\s+NUTS", l, re.I | re.U):
            window = " ".join(lines[i:i + 8])
            for m in re.findall(r"\b([A-Z]{2}\d{1,3}[A-Z0-9]{0,2})\b", window):
                if re.match(r"[A-Z]{2}\d", m) and m not in out:
                    out.append(m)
    return out[:15]


def score_area(area: str) -> int:
    """Rank a candidate demarcation: place-word density wins, wrong-section
    markers lose. Used to pick the best source (OJ vs PDF) for one GI."""
    if not area:
        return -10_000
    s = len(_PLACE.findall(area)) * 100 + min(len(area), 400)
    if _NEG.search(area[:80]) or _AUTHORITY.search(area[:120]):
        s -= 500
    return s


class GiGeoExtractor:
    """Resolves + fetches + extracts. Holds one Playwright page and a requests
    session for the run. Use as a context manager."""

    def __init__(self):
        self._pw = None
        self._browser = None
        self.page = None
        self.sess = requests.Session()
        self.sess.headers.update({"User-Agent": UA})

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        self.page = self._browser.new_page()
        self.page.set_default_timeout(30000)
        return self

    def __exit__(self, *exc):
        try:
            self._browser.close()
        finally:
            self._pw.stop()

    # --- fetching ----------------------------------------------------------
    def fetch_pdf(self, attachment_id: str) -> str | None:
        for _ in range(3):
            try:
                r = self.sess.get(f"{ATTACHMENT_HOST}/{attachment_id}",
                                  headers={"Accept": "*/*"}, timeout=60)
                if r.content[:4] == b"%PDF":
                    return _pdf_text(r.content)
                if r.status_code in (500, 502, 503):
                    time.sleep(1.3)
                    continue
                return None
            except Exception:
                time.sleep(1.3)
        return None

    def fetch_eurlex(self, url: str) -> str | None:
        try:
            self.page.goto(prefer_en(url), wait_until="domcontentloaded", timeout=30000)
            self.page.wait_for_timeout(1300)
            return self.page.inner_text("body")
        except Exception:
            return None

    # --- resolution --------------------------------------------------------
    def giview_detail(self, gid: str) -> dict:
        try:
            return self.sess.get(f"{GIVIEW_DETAIL}/{gid}?language=EN",
                                 headers={"Accept": "application/json",
                                          "Referer": "https://www.tmdn.org/giview/"},
                                 timeout=35).json().get("basicData", {})
        except Exception:
            return {}

    def resolve_documents(self, amb: dict, giview: dict) -> tuple[list[str], list[str]]:
        """Merge PDF attachment ids + OJ/EUR-Lex urls from eAmbrosia and GIView."""
        pdf_ids = [s["uri"] for s in (amb.get("summarySheets") or []) if s.get("uri")]
        urls = [p["uri"] for p in (amb.get("publications") or [])
                if p.get("uri") and ("eur-lex" in p["uri"] or "data.europa.eu/eli" in p["uri"])]
        for pub in (giview.get("publications") or []):
            u = pub.get("uri") or ""
            if ("eur-lex" in u or "data.europa.eu/eli" in u) and u not in urls:
                urls.append(u)
            m = re.search(r"/attachments/(\d+)", u)
            if m and m.group(1) not in pdf_ids:
                pdf_ids.append(m.group(1))
        sd = giview.get("singleDocument")
        if isinstance(sd, dict) and "eur-lex" in (sd.get("uri") or ""):
            urls.insert(0, sd["uri"])
        return pdf_ids, urls

    # --- top level ---------------------------------------------------------
    def extract(self, amb: dict) -> dict:
        """Full pipeline for one eAmbrosia GI record -> gi_details row fields."""
        name = (amb.get("protectedNames") or ["?"])[0]
        gid = amb.get("giIdentifier")
        giview = self.giview_detail(gid) if gid else {}
        pdf_ids, urls = self.resolve_documents(amb, giview)

        # Try EVERY candidate document (OJ entries AND summary/technical PDFs) and
        # keep the best-scoring demarcation. A GI's PDF may scramble under layout
        # while its OJ entry is clean (or vice versa), so we do not stop at first.
        best = None  # (score, heading, area, src_url, src_type)
        nuts: list[str] = []
        last_src = None
        def note_nuts(t):
            for cd in extract_nuts(t):
                if cd not in nuts:
                    nuts.append(cd)
        for u in urls:
            txt = self.fetch_eurlex(u)
            if not txt:
                continue
            note_nuts(txt); last_src = prefer_en(u)
            # A whole-gazette page is uri=OJ:...:FULL. NOT :TOC — every EUR-Lex URL
            # carries a ubiquitous &toc=OJ:...:TOC parameter that is not a gazette marker.
            multi_gi = bool(re.search(r":FULL\b", u, re.I))
            hit = extract_geo(txt, name, multi_gi=multi_gi)
            if hit:
                cand = (score_area(hit[1]), hit[0], hit[1], prefer_en(u),
                        "eli" if "data.europa.eu/eli" in u else "eurlex")
                if best is None or cand[0] > best[0]:
                    best = cand
        for aid in pdf_ids:
            txt = self.fetch_pdf(aid)
            if not txt:
                continue
            note_nuts(txt); last_src = f"{ATTACHMENT_HOST}/{aid}"
            hit = extract_geo(txt, name, is_pdf=True)
            if hit:
                cand = (score_area(hit[1]), hit[0], hit[1], f"{ATTACHMENT_HOST}/{aid}", "pdf")
                if best is None or cand[0] > best[0]:
                    best = cand
        # Priority: a CLEAN text demarcation > the document's own NUTS region code >
        # a weak/ambiguous text demarcation. So a region code beats a legal-reference
        # preamble, but a real municipality list still wins over the region code.
        area = heading = src_url = src_type = None
        if best and confidence_of(best[2]) == "clean":
            _, heading, area, src_url, src_type = best
        if area is None and nuts:
            area = "NUTS region(s): " + ", ".join(nuts[:12])
            heading = "NUTS area"; src_url = last_src; src_type = "nuts"
        if area is None and best:
            _, heading, area, src_url, src_type = best

        has_docs = bool(pdf_ids or urls)
        if area:
            conf = "clean" if (src_type == "nuts" or confidence_of(area) == "clean") else "approximate"
            status = "resolved" if conf == "clean" else "approximate"
        else:
            conf, status = "none", ("no_source" if not has_docs else "pending")

        return {
            "file_number": amb.get("fileNumber"),
            "gi_identifier": gid,
            "protected_name": name,
            "gi_type": amb.get("giType"),
            "product_type": amb.get("productType"),
            "countries": amb.get("countries") if isinstance(amb.get("countries"), list)
                         else ([amb["countries"]] if amb.get("countries") else None),
            "status": amb.get("status"),
            "eu_protection_date": amb.get("euProtectionDate"),
            "classification": amb.get("classification") or giview.get("classification"),
            "legal_instrument": amb.get("legalInstrument") or giview.get("legalInstrument"),
            "publications": amb.get("publications"),
            "competent_authority": amb.get("producerGroupName")
                                   or (giview.get("competentControlAuthorities")),
            "geographical_area": area[:8000] if area else None,
            "geo_nuts": nuts or None,
            "geo_heading": (heading or "")[:200] or None,
            "geo_source_url": src_url,
            "geo_source_type": src_type,
            "geo_confidence": conf,
            "geo_status": status,
        }


def roster(countries: list[str]) -> list[dict]:
    """All eAmbrosia GI records whose countries include any of `countries`
    (eAmbrosia is the authoritative superset, includes pending 'applied' files)."""
    er = requests.get(EAMBROSIA_REGISTER, headers={"User-Agent": UA, "Accept": "application/json"},
                      timeout=120).json()
    want = {c.upper() for c in countries}
    out = []
    for r in er:
        cs = r.get("countries")
        cs = [cs] if isinstance(cs, str) else (cs or [])
        if want & set(cs):
            out.append(r)
    out.sort(key=lambda r: (r.get("protectedNames") or ["?"])[0])
    return out
