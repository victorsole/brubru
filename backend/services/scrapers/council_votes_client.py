"""
Council of the EU voting-results client (MEUB Votes — Council results tab).

The Council publishes legislative voting results in its PUBLIC REGISTER
(/documents/public-register/votes/). The list page is Cloudflare-walled (needs the
WAF browser), but each result links to a clean PDF on the data.consilium subdomain
(plain httpx, no WAF). PDF page 1 = text (procedure ref, act, configuration, meeting);
PDF page 2 = a single IMAGE of the per-member-state result (green-up = in favour,
red-down = against, yellow circle = abstention) + QMV figures — pixels, not text.

So we vision-parse the page-2 image (Pixtral, EU-sovereign; GPT-4o fallback) into
structured per-country votes, with a self-consistency check against the QMV figures.
NO Anthropic (non-chat). Always keep the source PDF URL so the UI can link/verify.
"""

from __future__ import annotations

import base64
import json
import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

LIST_URL = "https://www.consilium.europa.eu/en/documents/public-register/votes/"
_TAG = re.compile(r"<[^>]+>")
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0 Safari/537.36")

# EU member states in Council protocol order (ISO-2; EL = Greece per EU usage).
EU27 = {
    "BE": "Belgium", "BG": "Bulgaria", "CZ": "Czechia", "DK": "Denmark", "DE": "Germany",
    "EE": "Estonia", "IE": "Ireland", "EL": "Greece", "GR": "Greece", "ES": "Spain",
    "FR": "France", "HR": "Croatia", "IT": "Italy", "CY": "Cyprus", "LV": "Latvia",
    "LT": "Lithuania", "LU": "Luxembourg", "HU": "Hungary", "MT": "Malta", "NL": "Netherlands",
    "AT": "Austria", "PL": "Poland", "PT": "Portugal", "RO": "Romania", "SI": "Slovenia",
    "SK": "Slovakia", "FI": "Finland", "SE": "Sweden",
}


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", _TAG.sub(" ", s or "")).strip()


# ---------------------------------------------------------------------------
# 1. List page (WAF browser) -> entries
# ---------------------------------------------------------------------------

def parse_list(html: str) -> List[Dict]:
    """Parse the public-register votes list into entries (text fields only)."""
    out: List[Dict] = []
    for block in re.split(r"gsc-public-register__result-item", html or "")[1:]:
        b = block[:4000]
        pdf = re.search(r"(https://data\.consilium\.europa\.eu/doc/document/([^/\"]+)/en/pdf)", b)
        if not pdf:
            continue
        pdf_url, st_id = pdf.group(1), pdf.group(2)
        det = re.search(r"gsc-public-register__result-details(.*?)$", b, re.S)
        text = _clean(det.group(1)) if det else _clean(b)
        # date dd/mm/yyyy after the doc ref
        dm = re.search(r"(\d{2}/\d{2}/\d{4})", text)
        # act type + title between "Voting result" and " - Adoption"
        act = re.search(r"Voting result\s*-?\s*(.*?)\s*-\s*Adoption of the legislative act", text, re.I)
        # configuration + meeting: "NNNNth meeting of the COUNCIL ... (CONFIG) <date>, <place>"
        meet = re.search(r"(\d{3,4})\w{0,2}\s+meeting of the COUNCIL OF THE EUROPEAN UNION\s*\(([^)]+)\)", text, re.I)
        out.append({
            "st_id": st_id,
            "pdf_url": pdf_url,
            "doc_ref": st_id.replace("-", " "),
            "pub_date": dm.group(1) if dm else None,
            "act_title": _clean(act.group(1)) if act else text[:300],
            "config_raw": _clean(meet.group(2)) if meet else None,
            "meeting_no": meet.group(1) if meet else None,
            "details": text[:600],
        })
    return out


# ---------------------------------------------------------------------------
# 2. PDF (httpx, no WAF) -> page-1 text fields + page-2 image
# ---------------------------------------------------------------------------

def fetch_pdf(pdf_url: str) -> Optional[bytes]:
    try:
        import httpx
        r = httpx.get(pdf_url, headers={"User-Agent": _UA}, follow_redirects=True, timeout=45)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/pdf"):
            return r.content
    except Exception as e:
        logger.warning("[COUNCIL-VOTES] pdf fetch failed %s: %s", pdf_url, e)
    return None


_PROC = re.compile(r"Interinstitutional File:\s*(\d{4}/\d{3,4}\s*\([A-Z]{2,4}\))")
# page-1 act title: "Subject: Voting result - <TITLE> - Adoption ... | NNNNth meeting ..."
_TITLE = re.compile(
    r"Subject:\s*Voting result\s*[-–]?\s*(.*?)\s*"
    r"(?:-\s*Adoption of the legislative act|\d{3,4}\w{0,2}\s+meeting of the COUNCIL)",
    re.I)
# meeting line: "NNNNth meeting of the COUNCIL OF THE EUROPEAN UNION (CONFIG) DATE, PLACE"
_MEET = re.compile(
    r"(\d{3,4})\w{0,2}\s+meeting of the COUNCIL OF THE EUROPEAN UNION\s*\(([^)]+)\)", re.I)


def parse_pdf(pdf_bytes: bytes) -> Dict:
    """page-1 text -> procedure_ref + act title + Council configuration + meeting;
    returns page count + page-2 image bytes."""
    import pypdf
    import io
    r = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    pages = len(r.pages)
    p1 = re.sub(r"\s+", " ", (r.pages[0].extract_text() or "")) if pages else ""
    proc = _PROC.search(p1)
    title_m = _TITLE.search(p1)
    meet_m = _MEET.search(p1)
    img = None
    if pages >= 2:
        try:
            imgs = list(r.pages[1].images)
            if imgs:
                # Re-encode to PNG via PIL — Council sheets are sometimes JPEG2000,
                # which the vision APIs reject; PIL normalises any format to PNG.
                from PIL import Image as _PILImage  # noqa
                import io as _io
                buf = _io.BytesIO()
                imgs[0].image.save(buf, format="PNG")
                img = buf.getvalue()
        except Exception as e:
            logger.warning("[COUNCIL-VOTES] page-2 image extract failed: %s", e)
    return {
        "pages": pages,
        "procedure_ref": re.sub(r"\s+", "", proc.group(1)) if proc else None,
        "act_title": _clean(title_m.group(1)) if title_m else None,
        "config_raw": _clean(meet_m.group(2)) if meet_m else None,
        "meeting_no": meet_m.group(1) if meet_m else None,
        "has_vote_image": img is not None,
        "vote_image": img,
    }


# ---------------------------------------------------------------------------
# 3. Vision parse the page-2 image -> per-country votes + validation
# ---------------------------------------------------------------------------

_VISION_PROMPT = (
    "This is the official Council of the EU voting-result sheet for a legislative act. "
    "Each EU member state row has a vote symbol: a GREEN UP arrow = in favour; a RED DOWN "
    "arrow = against; a YELLOW CIRCLE = abstention. Read every member state and return "
    "STRICT JSON ONLY (no prose), using ISO 3166-1 alpha-2 codes (Greece = EL): "
    '{"countries":[{"code":"BE","vote":"for|against|abstain"}, ...all 27...],'
    '"qmv":{"member_states_pct":<number|null>,"population_pct":<number|null>}}'
)


def _vision_call(png_b64: str, model: str, key: str, provider: str) -> Optional[dict]:
    import httpx
    if provider == "mistral":
        url = "https://api.mistral.ai/v1/chat/completions"
        payload = {"model": model, "temperature": 0, "max_tokens": 2000,
                   "messages": [{"role": "user", "content": [
                       {"type": "text", "text": _VISION_PROMPT},
                       {"type": "image_url", "image_url": f"data:image/png;base64,{png_b64}"}]}]}
    else:  # openai
        url = "https://api.openai.com/v1/chat/completions"
        payload = {"model": model, "temperature": 0, "max_tokens": 2000,
                   "messages": [{"role": "user", "content": [
                       {"type": "text", "text": _VISION_PROMPT},
                       {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{png_b64}"}}]}]}
    r = httpx.post(url, headers={"Authorization": f"Bearer {key}"}, json=payload, timeout=120)
    if r.status_code != 200:
        logger.warning("[COUNCIL-VOTES] vision %s HTTP %s: %s", model, r.status_code, r.text[:160])
        return None
    content = r.json()["choices"][0]["message"]["content"]
    m = re.search(r"\{.*\}", content, re.S)
    return json.loads(m.group(0)) if m else None


def vision_extract(png_bytes: bytes, mistral_key: Optional[str], openai_key: Optional[str]) -> Optional[Dict]:
    """Vision-parse the vote image into per-country votes + tally + a confidence flag.

    Tries Pixtral (EU-sovereign) then GPT-4o; cross-checks the per-country tally
    against the QMV member-states %. confidence='high' when they reconcile."""
    b64 = base64.b64encode(png_bytes).decode()
    engines = []
    if mistral_key:
        engines += [("mistral", "pixtral-large-latest", mistral_key),
                    ("mistral", "pixtral-12b-2409", mistral_key)]
    if openai_key:
        engines += [("openai", "gpt-4o", openai_key)]

    best = None
    for provider, model, key in engines:
        try:
            data = _vision_call(b64, model, key, provider)
        except Exception as e:
            logger.warning("[COUNCIL-VOTES] vision err %s: %s", model, str(e)[:120])
            continue
        if not data or not data.get("countries"):
            continue
        countries = {}
        for c in data["countries"]:
            code = (c.get("code") or "").upper().strip()
            code = "EL" if code == "GR" else code
            v = (c.get("vote") or "").lower()
            if code in EU27 and v in ("for", "against", "abstain"):
                countries[code] = v
        if not countries:
            continue
        f = sum(1 for v in countries.values() if v == "for")
        a = sum(1 for v in countries.values() if v == "against")
        ab = sum(1 for v in countries.values() if v == "abstain")
        qmv = data.get("qmv") or {}
        ms_pct = qmv.get("member_states_pct")
        # self-consistency: QMV member-state % should imply the same in-favour count
        confidence = "low"
        if len(countries) == 27:
            implied = round((ms_pct or 0) / 100 * 27) if ms_pct else None
            confidence = "high" if (implied is None or implied == f) else "medium"
        result = {
            "country_breakdown": countries, "votes_for": f, "votes_against": a,
            "votes_abstention": ab, "qmv": qmv, "model": model, "confidence": confidence,
            "n_countries": len(countries),
        }
        best = result
        if confidence == "high":
            break  # good enough; stop escalating engines
    return best
