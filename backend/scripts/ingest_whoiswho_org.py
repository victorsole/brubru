"""
Ingest the FULL EU Commission org hierarchy (Department -> Directorate -> Unit ->
Head of Unit + email) from the static Who-is-Who directory PDF (EUWhoiswho_COM_EN.pdf,
api_op.md). Writes knowledge_base/whoiswho_org.json, which MEUB Stakeholder Mapping's
Cards view uses to tell the user WHO to contact at unit level.

This is the granular companion to scripts/ingest_whoiswho_officials.py (top-5 per DG,
used by the Web/Map graph). Everything here is parsed verbatim from the PDF: names,
functions and emails are never invented. No Anthropic. Re-runnable.

Run:  python3.12 -m scripts.ingest_whoiswho_org --pdf /tmp/wiw_com.pdf
      python3.12 -m scripts.ingest_whoiswho_org            (downloads current PDF)
"""
from __future__ import annotations

import argparse
import io
import json
import re
import urllib.request
from pathlib import Path

PDF_URL = "https://op.europa.eu/webpub/wiw/pdf/EUWhoiswho_COM_EN.pdf"
OUT = Path(__file__).resolve().parents[1] / "knowledge_base" / "whoiswho_org.json"
_UA = {"User-Agent": "Mozilla/5.0 (compatible; Brubru/1.0; +https://brubru.beresol.eu)"}

_DG = re.compile(r"^DG ([A-Z]{2,8})\b\s*[—-]")
_DIR = re.compile(r"^DIR\s+([A-Za-z0-9/]+)\s*[—-]\s*(.+)$", re.I)
_UNIT = re.compile(r"^(\d{1,2})\.\s+(.+)$")
_NAME = re.compile(r"^(?:Mr|Ms|Mme|M)\.?\s+(.+)$")
_ADDR = re.compile(r"^(Avenue|Av\.|Rue|Boulevard|Bd|Chauss|Square|Place|Rond|BELGIUM|LUXEMBOURG|L-\d|\d{4}\b)", re.I)
_ADDR_INLINE = re.compile(r"\s+(?:Avenue|Rue|Boulevard|Chauss(?:é|e)e|Square|Place|Rond-Point)\b.*$", re.I)
# Phone lines end in a 5-digit extension; a glued unit number (1-2 digits) follows.
_GLUE = re.compile(r"^(Tel\..*?\d{5})(\d{1,2})\.\s+([A-Z].+)$")
_EMAIL = re.compile(r"[A-Za-z0-9.\-]+@ec\.europa\.eu")


def _titlecase_caps(raw: str) -> str:
    return " ".join(w.title() if w.isupper() else w for w in raw.split()).strip()


def _has_caps_surname(s: str) -> bool:
    return any(len(w) >= 2 and w.isupper() for w in s.split())


def _role_of(func: str | None):
    if not func:
        return None
    f = func.lower()
    if f.startswith("director-general"):
        return "dg"
    if "deputy director-general" in f or "deputy secretary-general" in f:
        return "deputy"
    if f.startswith("head of unit"):
        return "head"
    if f.startswith("director"):
        return "director"
    return None


def _presplit(lines: list[str]) -> list[str]:
    """Split phone lines that have a unit header glued on the end."""
    out = []
    for ln in lines:
        m = _GLUE.match(ln.strip())
        if m:
            out.append(m.group(1).strip())
            out.append(f"{m.group(2)}. {m.group(3).strip()}")
        else:
            out.append(ln)
    return out


def _email_at(lines: list[str], e: int) -> str | None:
    """Email on line e, joining a wrapped local-part from the previous line."""
    cur = lines[e].strip().replace(" ", "")
    prev = lines[e - 1].strip().replace(" ", "") if e > 0 else ""
    if prev.endswith("-"):            # wrapped local part, e.g. "Catherine.GESLAIN-"
        cur = prev + cur
    m = _EMAIL.search(cur)
    return m.group(0) if m else None


def _person_block(lines: list[str], i: int):
    """Parse a person starting at name-line i. Returns (person, next_index)."""
    name = _titlecase_caps(_NAME.match(lines[i].strip()).group(1))
    func, e = None, None
    for j in range(i + 1, min(i + 9, len(lines))):
        c = lines[j].strip()
        if not c:
            continue
        if "@ec.europa.eu" in c:
            e = j
            break
        if c.startswith("Tel"):
            break
        if func is None:
            func = c
    email = _email_at(lines, e) if e is not None else None
    nxt = (e + 1) if e is not None else (i + 1)
    return {"name": name, "function": func, "email": email}, nxt


def parse_pdf(data: bytes) -> dict:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    # Body pages only (they carry emails); this excludes the table of contents.
    body = [p.extract_text() or "" for p in reader.pages if "@ec.europa.eu" in (p.extract_text() or "")]
    lines = _presplit("\n".join(body).splitlines())

    dgs: dict[str, dict] = {}
    cur_dg = cur_dir = cur_unit = None
    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        if not ln:
            i += 1
            continue

        m = _DG.match(ln)
        if m:
            cur_dg = m.group(1)
            dgs.setdefault(cur_dg, {"director_general": None, "deputies": [], "directorates": []})
            cur_dir = cur_unit = None
            i += 1
            continue
        if not cur_dg:
            i += 1
            continue

        m = _DIR.match(ln)
        if m:
            cur_dir = {"code": m.group(1).upper(), "name": _titlecase_caps(m.group(2)),
                       "director": None, "units": []}
            dgs[cur_dg]["directorates"].append(cur_dir)
            cur_unit = None
            i += 1
            continue

        m = _UNIT.match(ln)
        if m and cur_dir is not None:
            cur_unit = {"code": f"{cur_dir['code']}.{m.group(1)}",
                        "name": _ADDR_INLINE.sub("", m.group(2).strip()).strip(), "head": None}
            cur_dir["units"].append(cur_unit)
            i += 1
            absorbed = 0
            while i < len(lines) and absorbed < 2:  # absorb wrapped unit-name continuation
                nxt = lines[i].strip()
                if (not nxt or _NAME.match(nxt) or _DIR.match(nxt) or _UNIT.match(nxt)
                        or "@" in nxt or nxt.startswith("Tel") or _ADDR.match(nxt)):
                    break
                cur_unit["name"] = (cur_unit["name"] + " " + _ADDR_INLINE.sub("", nxt)).strip()
                if _ADDR_INLINE.search(nxt):
                    break
                i += 1
                absorbed += 1
            continue

        if _NAME.match(ln) and _has_caps_surname(_NAME.match(ln).group(1)):
            person, nxt = _person_block(lines, i)
            role = _role_of(person["function"])
            if role == "dg" and dgs[cur_dg]["director_general"] is None:
                dgs[cur_dg]["director_general"] = person
            elif role == "deputy":
                dgs[cur_dg]["deputies"].append(person)
            elif role == "director" and cur_dir is not None and cur_dir["director"] is None:
                cur_dir["director"] = person
            elif role == "head" and cur_unit is not None and cur_unit["head"] is None:
                cur_unit["head"] = person
            i = max(i + 1, nxt)
            continue

        i += 1

    # clean unit names (strip any address fragment / trailing street number) and
    # prune empty directorates.
    for dg in dgs.values():
        for d in dg["directorates"]:
            for u in d["units"]:
                u["name"] = _clean_unit_name(u["name"])
        dg["directorates"] = [d for d in dg["directorates"] if d["director"] or d["units"]]
    return dgs


def _clean_unit_name(n: str) -> str:
    n = _ADDR_INLINE.sub("", n)
    n = re.sub(r"[\s,]+\d{1,4}\s*,?\s*$", "", n)   # trailing street number
    return n.strip(" ,")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf")
    args = ap.parse_args()
    if args.pdf:
        data = Path(args.pdf).read_bytes()
    else:
        print(f"[whoiswho-org] downloading {PDF_URL}")
        data = urllib.request.urlopen(urllib.request.Request(PDF_URL, headers=_UA), timeout=60).read()

    dgs = parse_pdf(data)
    units = sum(len(d["units"]) for dg in dgs.values() for d in dg["directorates"])
    heads = sum(1 for dg in dgs.values() for d in dg["directorates"] for u in d["units"] if u["head"] and u["head"]["email"])
    payload = {"source": "EUWhoiswho_COM_EN.pdf", "dg_count": len(dgs),
               "directorate_count": sum(len(dg["directorates"]) for dg in dgs.values()),
               "unit_count": units, "units_with_head_email": heads, "dgs": dgs}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[whoiswho-org] wrote {OUT}")
    print(f"  DGs {len(dgs)} | directorates {payload['directorate_count']} | units {units} | unit-heads w/ email {heads}")


if __name__ == "__main__":
    main()
